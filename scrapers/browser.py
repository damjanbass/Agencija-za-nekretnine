"""
Playwright wrapper za sajtove koji blokiraju `requests` (Cloudflare WAF, SPA hydration).

Singleton browser instance — pokreće Chromium jednom po procesu, deli kontekst
između scraperskih poziva. Manual stealth patches da WebDriver-detection prođe.

Instalacija (jednom):
    pip install playwright>=1.49.0
    python -m playwright install chromium
"""
from __future__ import annotations

import random
import threading
from typing import Optional


# Lazy state
_lock = threading.Lock()
_pw = None
_browser = None
_available: Optional[bool] = None  # None = nije proveravano, True/False = poznato


# Iste UA stringove kao u base.py — usklađen otisak
_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


# JS injection — uklanja navigator.webdriver i druge WebDriver tragove
_STEALTH_INIT_SCRIPT = """
// 1. Sakrij navigator.webdriver
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// 2. Realan plugins niz (Chrome ima minimum 3 plugin-a)
Object.defineProperty(navigator, 'plugins', {
  get: () => [
    { name: 'PDF Viewer', filename: 'internal-pdf-viewer' },
    { name: 'Chrome PDF Viewer', filename: 'internal-pdf-viewer' },
    { name: 'Native Client', filename: 'internal-nacl-plugin' },
  ],
});

// 3. Languages konzistentno sa Accept-Language header-om
Object.defineProperty(navigator, 'languages', {
  get: () => ['sr-RS', 'sr', 'en-US', 'en'],
});

// 4. window.chrome objekat (postoji u pravom Chrome-u, ne u headless-u po defaultu)
if (!window.chrome) {
  window.chrome = { runtime: {}, loadTimes: () => ({}), csi: () => ({}) };
}

// 5. Permissions API
const origQuery = navigator.permissions && navigator.permissions.query;
if (origQuery) {
  navigator.permissions.query = (params) =>
    params.name === 'notifications'
      ? Promise.resolve({ state: Notification.permission })
      : origQuery(params);
}

// 6. WebGL vendor / renderer (headless ima 'Brian Paul / Mesa OffScreen')
const getParameter = WebGLRenderingContext.prototype.getParameter;
WebGLRenderingContext.prototype.getParameter = function (param) {
  if (param === 37445) return 'Intel Inc.';       // UNMASKED_VENDOR_WEBGL
  if (param === 37446) return 'Intel Iris OpenGL Engine';  // UNMASKED_RENDERER_WEBGL
  return getParameter.call(this, param);
};
"""


def is_available() -> bool:
    """Vraća True ako je playwright instaliran I chromium browser dostupan."""
    global _available
    if _available is not None:
        return _available
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        _available = True
    except ImportError:
        print("[browser] playwright nije instaliran — `pip install playwright && python -m playwright install chromium`")
        _available = False
    return _available


def _ensure_browser():
    """Lazy init globalnog Chromium instance-a."""
    global _pw, _browser
    if _browser is not None:
        return _browser
    with _lock:
        if _browser is not None:
            return _browser
        from playwright.sync_api import sync_playwright
        _pw = sync_playwright().start()
        try:
            _browser = _pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--no-sandbox",
                ],
            )
        except Exception as e:
            print(f"[browser] chromium launch failed: {e}")
            print("[browser] Pokušaj: python -m playwright install chromium")
            _pw.stop()
            _pw = None
            raise
        return _browser


def close():
    """Eksplicitno zatvori browser (npr. na kraju cron skripta)."""
    global _pw, _browser
    with _lock:
        if _browser is not None:
            try: _browser.close()
            except Exception: pass
            _browser = None
        if _pw is not None:
            try: _pw.stop()
            except Exception: pass
            _pw = None


def get_html(
    url: str,
    referer: Optional[str] = None,
    wait_for_selector: Optional[str] = None,
    timeout_ms: int = 25000,
    extra_wait_ms: int = 1500,
    wait_until: str = "domcontentloaded",
    scroll_to_load: bool = False,
) -> Optional[str]:
    """
    Učita stranicu kroz pravi headless Chrome (sa stealth patches), vrati pun HTML.

    `wait_for_selector` — ako je dato, čeka da se selektor pojavi (za SPA hydration).
    Ako je None, čeka samo domcontentloaded + extra_wait_ms (za dodatnu JS aktivnost).

    Vraća None ako Playwright nije instaliran ili dođe do greške.
    """
    if not is_available():
        return None

    try:
        browser = _ensure_browser()
    except Exception:
        return None

    from .proxy import next_playwright_proxy
    ua = random.choice(_UAS)
    extra_headers = {
        "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    if referer:
        extra_headers["Referer"] = referer

    ctx_kwargs: dict = {
        "user_agent": ua,
        "locale": "sr-RS",
        "timezone_id": "Europe/Belgrade",
        "viewport": {"width": 1366, "height": 768},
        "extra_http_headers": extra_headers,
    }
    pw_proxy = next_playwright_proxy()
    if pw_proxy:
        ctx_kwargs["proxy"] = pw_proxy

    ctx = None
    page = None
    try:
        ctx = browser.new_context(**ctx_kwargs)
        # Injektuj stealth patches u svaku stranicu pre nego što sajt JS pokrene
        ctx.add_init_script(_STEALTH_INIT_SCRIPT)

        page = ctx.new_page()
        page.goto(url, wait_until=wait_until, timeout=timeout_ms)

        if wait_for_selector:
            try:
                page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
            except Exception:
                # Selektor se nije pojavio — vraćamo šta imamo, scraper će dalje gledati
                pass

        # Scroll-down — okida lazy-load listing kartica u SPA aplikacijama
        if scroll_to_load:
            try:
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(800)
                page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

        # Sačekaj malo dodatnih JS aktivnosti (lazy-loaded kartice, hydration finish)
        if extra_wait_ms > 0:
            page.wait_for_timeout(extra_wait_ms)

        html = page.content()
        return html
    except Exception as e:
        print(f"[browser] get_html failed on {url[:60]}…: {type(e).__name__}: {e}")
        return None
    finally:
        try:
            if page: page.close()
        except Exception: pass
        try:
            if ctx: ctx.close()
        except Exception: pass
