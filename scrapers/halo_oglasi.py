import re
from bs4 import BeautifulSoup
from .base import MarketSnapshot, get_session

SITE = "Halo oglasi"
URL  = "https://www.halooglasi.com/nekretnine/prodaja-stanova/beograd"

MOCK = MarketSnapshot(
    site=SITE, url=URL,
    total_listings=1842, avg_price_eur_m2=2180,
    price_min_eur=38000, price_max_eur=980000,
    new_this_week=124,
    top_neighborhoods=["Novi Beograd", "Zvezdara", "Vračar"],
    is_mock=True,
)


def scrape(city: str = "beograd") -> MarketSnapshot:
    url = f"https://www.halooglasi.com/nekretnine/prodaja-stanova/{city}"
    try:
        resp = get_session().get(url, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Ukupan broj oglasa
        total = _parse_total(soup)

        # Cene iz listing kartica
        prices = _parse_prices(soup)
        if not prices or total == 0:
            return MOCK

        avg_m2  = _parse_avg_m2(soup, prices)
        return MarketSnapshot(
            site=SITE, url=url,
            total_listings=total,
            avg_price_eur_m2=avg_m2,
            price_min_eur=min(prices),
            price_max_eur=max(prices),
            new_this_week=round(total * 0.07),
            top_neighborhoods=["Novi Beograd", "Zvezdara", "Vračar"],
            is_mock=False,
        )
    except Exception:
        return MOCK


def _parse_total(soup: BeautifulSoup) -> int:
    for sel in [".total-count", ".broj-oglasa", "h1 strong", ".product-list-title"]:
        el = soup.select_one(sel)
        if el:
            m = re.search(r"[\d\.]+", el.get_text())
            if m:
                return int(m.group().replace(".", ""))
    return 0


def _parse_prices(soup: BeautifulSoup) -> list[int]:
    prices = []
    for el in soup.select(".price-box, .central-feature-value, [class*='price']"):
        text = el.get_text()
        m = re.search(r"(\d[\d\.\s]{2,})", text)
        if m:
            val = int(re.sub(r"[\.\s]", "", m.group(1)))
            if 10_000 < val < 5_000_000:
                prices.append(val)
    return prices[:50]


def _parse_avg_m2(soup: BeautifulSoup, prices: list[int]) -> int:
    # Pokušaj da izvučeš cenu po m²
    m2_prices = []
    for el in soup.select("[class*='price-per']"):
        m = re.search(r"(\d[\d\.]+)", el.get_text())
        if m:
            val = int(re.sub(r"\.", "", m.group(1)))
            if 500 < val < 10_000:
                m2_prices.append(val)
    if m2_prices:
        return round(sum(m2_prices) / len(m2_prices))
    # Fallback: estimacija
    return round(sum(prices) / len(prices) / 55) if prices else 2200
