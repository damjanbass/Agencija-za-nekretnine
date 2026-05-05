from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import MarketSnapshot
from . import halo_oglasi, cetirizida, nekretnine_rs, cityexpert

SCRAPERS = {
    "Halo oglasi":  halo_oglasi.scrape,
    "4zida":        cetirizida.scrape,
    "Nekretnine.rs": nekretnine_rs.scrape,
    "CityExpert":   cityexpert.scrape,
}


def fetch_market(sites: list[str], city: str = "beograd") -> list[dict]:
    """
    Paralelno skrejpuje tražene sajtove.
    sites: lista naziva kao u SCRAPERS ključevima.
    Vraća listu rečnika sortiranu po broju oglasa (opadajuće).
    """
    results: list[MarketSnapshot] = []

    active = {name: fn for name, fn in SCRAPERS.items() if name in sites}
    if not active:
        return []

    with ThreadPoolExecutor(max_workers=len(active)) as pool:
        futures = {pool.submit(fn, city): name for name, fn in active.items()}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception:
                pass

    results.sort(key=lambda s: s.total_listings, reverse=True)
    return [s.to_dict() for s in results]


def market_summary(snapshots: list[dict]) -> dict:
    """Agregirani pregled tržišta za AI analizu."""
    if not snapshots:
        return {}

    total  = sum(s["total_listings"] for s in snapshots)
    avg_m2 = round(sum(s["avg_price_eur_m2"] for s in snapshots) / len(snapshots))
    new_wk = sum(s["new_this_week"] for s in snapshots)

    return {
        "total_market_listings": total,
        "avg_market_price_m2":   avg_m2,
        "new_market_this_week":  new_wk,
        "sites_count":           len(snapshots),
    }
