from .base import MarketSnapshot
from . import halo_oglasi, cetirizida, nekretnine_rs, cityexpert

SCRAPERS = {
    "Halo oglasi":   halo_oglasi.scrape,
    "4zida":         cetirizida.scrape,
    "Nekretnine.rs": nekretnine_rs.scrape,
    "CityExpert":    cityexpert.scrape,
}


def fetch_market(
    sites: list[str],
    city: str = "beograd",
    transaction_type: str = "sale",
    persist: bool = False,
) -> list[dict]:
    """
    Paralelno skrejpuje tražene sajtove za zadati transaction_type ('sale' | 'rent').

    Vraća listu rečnika (snapshot bez `listings` polja) sortiranu po broju oglasa.

    Ako `persist=True`, snapshot + pojedinačni listinzi se upisuju u Supabase
    (market_snapshots + market_listings_sample). Koristi se iz daily cron-a.
    Pri generisanju izveštaja persist=False (već imamo persistirane podatke iz crona).
    """
    snapshots: list[MarketSnapshot] = []

    active = {name: fn for name, fn in SCRAPERS.items() if name in sites}
    if not active:
        return []

    # Sekvencijalno — Playwright sync API nije thread-safe.
    # ThreadPoolExecutor bi izazvao "greenlet.error: Cannot switch to a different thread".
    # Daily cron ima dovoljno vremena; ~4 sajta × ~30s = ~2 minuta ukupno.
    for name, fn in active.items():
        try:
            snapshots.append(fn(city, transaction_type))
        except Exception as e:
            print(f"[fetch_market] {name} failed: {e}")

    if persist:
        try:
            from data.supabase_client import save_market_snapshot
            for snap in snapshots:
                listings_dicts = [l.to_dict() for l in snap.listings]
                save_market_snapshot(snap.to_dict(), listings_dicts)
        except Exception as e:
            print(f"[fetch_market] persist failed: {e}")

    snapshots.sort(key=lambda s: s.total_listings, reverse=True)
    return [s.to_dict() for s in snapshots]


def fetch_market_all_segments(
    sites: list[str],
    city: str = "beograd",
    transaction_types: list[str] | None = None,
    persist: bool = False,
) -> dict[str, list[dict]]:
    """
    Skrejpuje za više transaction_type-ova odjednom.
    Vraća dict: {'sale': [...snapshots...], 'rent': [...snapshots...]}.
    """
    transaction_types = transaction_types or ["sale"]
    return {
        ttype: fetch_market(sites, city=city, transaction_type=ttype, persist=persist)
        for ttype in transaction_types
    }


def market_summary(snapshots: list[dict]) -> dict:
    """Agregirani pregled tržišta za AI analizu i header strip u izveštaju."""
    if not snapshots:
        return {}

    total  = sum(s.get("total_listings", 0) for s in snapshots)
    m2_vals = [s["avg_price_eur_m2"] for s in snapshots if s.get("avg_price_eur_m2")]
    avg_m2 = round(sum(m2_vals) / len(m2_vals)) if m2_vals else None
    new_wk = sum(s.get("new_this_week", 0) for s in snapshots)

    return {
        "total_market_listings": total,
        "avg_market_price_m2":   avg_m2,
        "new_market_this_week":  new_wk,
        "sites_count":           len(snapshots),
    }
