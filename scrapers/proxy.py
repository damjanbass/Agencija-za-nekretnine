"""
Proxy pool za scraping — rotacija po zahtevu.

Konfiguracija (u .env):
    SCRAPER_PROXIES=http://user:pass@host1:port,http://user:pass@host2:port

Ako SCRAPER_PROXIES nije podešen, sve ide bez proxy-ja (direktna konekcija).

Korišćenje:
    from scrapers.proxy import next_requests_proxy, next_playwright_proxy

    # Za requests.Session:
    session.proxies.update(next_requests_proxy())

    # Za Playwright browser.new_context():
    ctx = browser.new_context(proxy=next_playwright_proxy(), ...)
"""

import itertools
import threading
from typing import Optional
from urllib.parse import urlparse

import config

_lock   = threading.Lock()
_cycle  = None   # itertools.cycle nad listom proxy URL-ova


def _get_cycle():
    global _cycle
    if _cycle is None:
        with _lock:
            if _cycle is None:
                proxies = config.SCRAPER_PROXIES
                if proxies:
                    print(f"[proxy] Pool: {len(proxies)} proxy/proxies učitano.")
                else:
                    print("[proxy] Nema SCRAPER_PROXIES — koristim direktnu konekciju.")
                _cycle = itertools.cycle(proxies) if proxies else itertools.cycle([None])
    return _cycle


def next_url() -> Optional[str]:
    """Vraća sledeći proxy URL iz pool-a, ili None ako pool nije podešen."""
    with _lock:
        return next(_get_cycle())


def next_requests_proxy() -> dict:
    """
    Vraća dict spreman za requests.Session.proxies.update().
    Prazan dict ako nema proxy-ja.
    """
    url = next_url()
    if not url:
        return {}
    return {"http": url, "https": url}


def next_playwright_proxy() -> Optional[dict]:
    """
    Vraća dict spreman za Playwright browser.new_context(proxy=...).
    None ako nema proxy-ja.

    Playwright format:
        {"server": "http://host:port", "username": "user", "password": "pass"}
    """
    url = next_url()
    if not url:
        return None

    parsed = urlparse(url)
    proxy: dict = {"server": f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


def is_configured() -> bool:
    """True ako postoji bar jedan proxy u pool-u."""
    return bool(config.SCRAPER_PROXIES)
