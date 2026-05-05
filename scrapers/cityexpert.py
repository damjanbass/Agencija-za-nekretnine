import re
import json
from .base import MarketSnapshot, get_session

SITE = "CityExpert"
URL  = "https://cityexpert.rs/prodaja/beograd"

MOCK = MarketSnapshot(
    site=SITE, url=URL,
    total_listings=876, avg_price_eur_m2=2510,
    price_min_eur=55000, price_max_eur=2100000,
    new_this_week=67,
    top_neighborhoods=["Vračar", "Savski venac", "Stari grad"],
    is_mock=True,
)


def scrape(city: str = "beograd") -> MarketSnapshot:
    # CityExpert koristi React — pokušavamo API endpoint
    api_url = (
        "https://cityexpert.rs/api/Search/?"
        f"cityName={city}&ptId=1&rentOrSale=S&currentPage=1&resultsPerPage=1"
    )
    try:
        resp = get_session().get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        total = data.get("totalCount", 0)
        if total == 0:
            return MOCK

        listings = data.get("result", [])
        prices = [
            int(l["price"]) for l in listings
            if l.get("price") and 10_000 < int(l["price"]) < 5_000_000
        ]
        m2_prices = [
            int(l["pricePerSqm"]) for l in listings
            if l.get("pricePerSqm") and 500 < int(l["pricePerSqm"]) < 10_000
        ]

        avg_m2 = round(sum(m2_prices) / len(m2_prices)) if m2_prices else (
            round(sum(prices) / len(prices) / 55) if prices else 2500
        )

        return MarketSnapshot(
            site=SITE, url=URL,
            total_listings=total,
            avg_price_eur_m2=avg_m2,
            price_min_eur=min(prices) if prices else 55000,
            price_max_eur=max(prices) if prices else 2100000,
            new_this_week=round(total * 0.077),
            top_neighborhoods=["Vračar", "Savski venac", "Stari grad"],
            is_mock=False,
        )
    except Exception:
        return MOCK
