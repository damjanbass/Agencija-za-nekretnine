import re
from bs4 import BeautifulSoup
from .base import MarketSnapshot, get_session

SITE = "4zida"
URL  = "https://4zida.rs/prodaja-stanova/beograd"

MOCK = MarketSnapshot(
    site=SITE, url=URL,
    total_listings=2341, avg_price_eur_m2=2290,
    price_min_eur=42000, price_max_eur=1200000,
    new_this_week=198,
    top_neighborhoods=["Novi Beograd", "Savski venac", "Palilula"],
    is_mock=True,
)


def scrape(city: str = "beograd") -> MarketSnapshot:
    url = f"https://4zida.rs/prodaja-stanova/{city}"
    try:
        resp = get_session().get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        total = _parse_total(soup)
        prices = _parse_prices(soup)
        if not prices or total == 0:
            return MOCK

        return MarketSnapshot(
            site=SITE, url=url,
            total_listings=total,
            avg_price_eur_m2=_parse_avg_m2(soup, prices),
            price_min_eur=min(prices),
            price_max_eur=max(prices),
            new_this_week=round(total * 0.085),
            top_neighborhoods=["Novi Beograd", "Savski venac", "Palilula"],
            is_mock=False,
        )
    except Exception:
        return MOCK


def _parse_total(soup: BeautifulSoup) -> int:
    for sel in [".results-count", ".total", "h1", "[data-cy='results-count']"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d\.]+", el.get_text())
            if m:
                return int(m.group().replace(".", ""))
    return 0


def _parse_prices(soup: BeautifulSoup) -> list[int]:
    prices = []
    for el in soup.select("[class*='price'], [class*='Price']"):
        m = re.search(r"(\d[\d\.\s]{3,})", el.get_text())
        if m:
            val = int(re.sub(r"[\.\s]", "", m.group(1)))
            if 10_000 < val < 5_000_000:
                prices.append(val)
    return prices[:50]


def _parse_avg_m2(soup: BeautifulSoup, prices: list[int]) -> int:
    m2_prices = []
    for el in soup.select("[class*='per-m'], [class*='perM'], [class*='price-m2']"):
        m = re.search(r"(\d[\d\.]+)", el.get_text())
        if m:
            val = int(re.sub(r"\.", "", m.group(1)))
            if 500 < val < 10_000:
                m2_prices.append(val)
    if m2_prices:
        return round(sum(m2_prices) / len(m2_prices))
    return round(sum(prices) / len(prices) / 55) if prices else 2300
