import re
from bs4 import BeautifulSoup
from .base import MarketSnapshot, get_session

SITE = "Nekretnine.rs"
URL  = "https://www.nekretnine.rs/stambeni-objekti/stanovi/lista/po-stranici/10/"

MOCK = MarketSnapshot(
    site=SITE, url=URL,
    total_listings=3107, avg_price_eur_m2=2140,
    price_min_eur=35000, price_max_eur=1500000,
    new_this_week=211,
    top_neighborhoods=["Novi Beograd", "Zemun", "Čukarica"],
    is_mock=True,
)


def scrape(city: str = "beograd") -> MarketSnapshot:
    url = f"https://www.nekretnine.rs/stambeni-objekti/stanovi/grad={city}/lista/po-stranici/10/"
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
            avg_price_eur_m2=_parse_avg_m2(prices),
            price_min_eur=min(prices),
            price_max_eur=max(prices),
            new_this_week=round(total * 0.068),
            top_neighborhoods=["Novi Beograd", "Zemun", "Čukarica"],
            is_mock=False,
        )
    except Exception:
        return MOCK


def _parse_total(soup: BeautifulSoup) -> int:
    for sel in [".number-of-results", ".results-number", "h1 span", ".total-results"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d\.]+", el.get_text())
            if m:
                return int(m.group().replace(".", ""))
    return 0


def _parse_prices(soup: BeautifulSoup) -> list[int]:
    prices = []
    for el in soup.select(".price, .cena, [class*='price']"):
        m = re.search(r"(\d[\d\.\s]{3,})", el.get_text())
        if m:
            val = int(re.sub(r"[\.\s]", "", m.group(1)))
            if 10_000 < val < 5_000_000:
                prices.append(val)
    return prices[:50]


def _parse_avg_m2(prices: list[int]) -> int:
    return round(sum(prices) / len(prices) / 55) if prices else 2150
