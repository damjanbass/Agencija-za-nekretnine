import random
import time
from dataclasses import dataclass, field
from datetime import date
from statistics import median
import requests


# Rotiramo nekoliko realnih Chrome/Firefox UA stringova — anti-bot detekcija često
# blokira specifične "scraper-like" UA (curl/python-requests/...)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:130.0) Gecko/20100101 Firefox/130.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]


def _build_headers(ua: str | None = None, referer: str | None = None) -> dict:
    """Vraća realistične browser headers koji prolaze većinu bot-detection filtera."""
    ua = ua or random.choice(USER_AGENTS)
    h = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "sr-RS,sr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none" if not referer else "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    # Chrome-only sec-ch-ua hints — Firefox UA ih ne šalje
    if "Chrome" in ua and "Firefox" not in ua:
        h.update({
            "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"' if "Windows" in ua else ('"macOS"' if "Mac" in ua else '"Linux"'),
        })
    if referer:
        h["Referer"] = referer
    return h


# Legacy alias (drugi moduli mogu da ga importuju)
HEADERS = _build_headers()


@dataclass
class Listing:
    """Pojedinačni oglas izvučen iz scrape-a. Upisuje se u market_listings_sample."""
    site:             str
    external_id:      str
    url:              str
    transaction_type: str            # 'sale' | 'rent'
    property_type:    str = "apartment"
    city:             str = "beograd"
    neighborhood:     str | None = None
    area_m2:          float | None = None
    rooms:            float | None = None
    floor:            str | None = None
    year_built:       int | None = None
    price_eur:        int | None = None
    listed_at:        str | None = None        # ISO date 'YYYY-MM-DD' ili None
    publisher:        str | None = None
    publisher_type:   str | None = None        # 'agency' | 'private' | 'unknown'
    title:            str | None = None

    @property
    def price_eur_m2(self) -> float | None:
        if self.price_eur and self.area_m2 and self.area_m2 > 0:
            return round(self.price_eur / self.area_m2, 2)
        return None

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["price_eur_m2"] = self.price_eur_m2
        return d


@dataclass
class MarketSnapshot:
    """Agregirani snimak tržišta. Računa se iz `listings` ako su dostupni."""
    site:                 str
    url:                  str
    transaction_type:     str = "sale"
    city:                 str = "beograd"
    property_type:        str = "apartment"

    total_listings:       int = 0
    avg_price_eur_m2:     int | None = None
    median_price_eur_m2:  int | None = None
    price_p25:            int | None = None
    price_p75:            int | None = None
    avg_total_price_eur:  int | None = None
    price_min_eur:        int = 0
    price_max_eur:        int = 0
    new_this_week:        int = 0
    raw_sample_count:     int = 0
    top_neighborhoods:    list = field(default_factory=list)  # [{"name":..., "count":...}]
    scraped_at:           str = field(default_factory=lambda: date.today().isoformat())
    is_mock:              bool = False

    # Pojedinačni oglasi — ne ulaze u to_dict() jer se upisuju zasebno u market_listings_sample
    listings:             list = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d.pop("listings", None)
        return d


def get_session(referer: str | None = None) -> requests.Session:
    from .proxy import next_requests_proxy
    s = requests.Session()
    s.headers.update(_build_headers(referer=referer))
    s.timeout = 15
    proxy = next_requests_proxy()
    if proxy:
        s.proxies.update(proxy)
    return s


def fetch_with_retry(
    session: requests.Session,
    url: str,
    referer: str | None = None,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    timeout: int = 15,
) -> requests.Response | None:
    """
    GET sa retry + exponential backoff + UA rotacijom.
    Rotira UA na 403/429 (verovatno bot-detect). Vraća None ako svi pokušaji neuspeli.
    """
    from .proxy import next_requests_proxy
    last_status = None
    for attempt in range(max_retries):
        try:
            headers_override = {}
            if referer:
                headers_override["Referer"] = referer
            # Rotacija UA i proxy-ja na ponovljenom pokušaju
            if attempt > 0:
                headers_override.update(_build_headers(referer=referer))
                new_proxy = next_requests_proxy()
                if new_proxy:
                    session.proxies.update(new_proxy)
            resp = session.get(url, headers=headers_override, timeout=timeout)
            last_status = resp.status_code
            if resp.status_code == 200:
                return resp
            if resp.status_code in (403, 429, 503):
                wait = backoff_base ** attempt + random.uniform(0.3, 1.2)
                print(f"    [retry] {resp.status_code} on {url[:60]}… → sleep {wait:.1f}s, rotate UA")
                time.sleep(wait)
                continue
            # 4xx (osim 403/429) ili 5xx — ne retry
            print(f"    [http] {resp.status_code} on {url[:80]}")
            return None
        except requests.RequestException as e:
            wait = backoff_base ** attempt + random.uniform(0.3, 1.2)
            print(f"    [exc] {type(e).__name__} on {url[:60]}… → sleep {wait:.1f}s")
            time.sleep(wait)
    print(f"    [http] giving up on {url[:80]} after {max_retries} attempts (last status={last_status})")
    return None


def fetch_html(
    url: str,
    referer: str | None = None,
    session: requests.Session | None = None,
    prefer_browser: bool = False,
    wait_for_selector: str | None = None,
    wait_until: str = "domcontentloaded",
    scroll_to_load: bool = False,
    extra_wait_ms: int = 1500,
) -> str | None:
    """
    Unified HTML fetcher za scrapere.
      • prefer_browser=True (Cloudflare/SPA): direktno Playwright, requests kao fallback
      • prefer_browser=False (statički sajtovi): requests prvi, Playwright na 403/timeout

    Vraća HTML string ili None.
    """
    def _try_browser() -> str | None:
        from . import browser
        return browser.get_html(
            url, referer=referer, wait_for_selector=wait_for_selector,
            wait_until=wait_until, scroll_to_load=scroll_to_load,
            extra_wait_ms=extra_wait_ms,
        )

    def _try_requests() -> str | None:
        s = session or get_session(referer=referer)
        resp = fetch_with_retry(s, url, referer=referer)
        return resp.text if resp is not None else None

    if prefer_browser:
        html = _try_browser()
        if html:
            return html
        print(f"    [fallback] browser failed, probam requests na {url[:60]}…")
        return _try_requests()
    else:
        html = _try_requests()
        if html:
            return html
        print(f"    [fallback] requests failed, probam browser na {url[:60]}…")
        return _try_browser()


def aggregate_from_listings(listings: list[Listing]) -> dict:
    """
    Iz liste pojedinačnih oglasa izračunaj agregate: prosek, medijana, P25, P75,
    top kvartovi (dinamički, ne hardkodovani).

    Vraća dict koji se može direktno spread-ovati u MarketSnapshot:
        MarketSnapshot(..., **aggregate_from_listings(listings))
    """
    if not listings:
        return {}

    m2_prices    = [l.price_eur_m2 for l in listings if l.price_eur_m2 is not None]
    total_prices = [l.price_eur for l in listings if l.price_eur is not None]

    result: dict = {
        "raw_sample_count": len(listings),
    }

    if m2_prices:
        m2_sorted = sorted(m2_prices)
        n = len(m2_sorted)
        result["avg_price_eur_m2"]    = round(sum(m2_sorted) / n)
        result["median_price_eur_m2"] = round(median(m2_sorted))
        result["price_p25"]           = round(m2_sorted[n // 4])
        result["price_p75"]           = round(m2_sorted[(3 * n) // 4])

    if total_prices:
        result["avg_total_price_eur"] = round(sum(total_prices) / len(total_prices))
        result["price_min_eur"]       = min(total_prices)
        result["price_max_eur"]       = max(total_prices)

    # Top kvartovi iz stvarnih podataka — ne više hardkodovani
    counts: dict[str, int] = {}
    for l in listings:
        if l.neighborhood:
            counts[l.neighborhood] = counts.get(l.neighborhood, 0) + 1
    top = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:5]
    result["top_neighborhoods"] = [{"name": n, "count": c} for n, c in top]

    return result
