"""
Detektuje stale oglase (60+ dana aktivni) i računa koliko su precenjeni
u odnosu na tržišnu medijanu kvarta.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


_TYPE_LABELS = {
    "stan":      "stan",
    "kuca":      "kuću",
    "poslovni":  "poslovni prostor",
    "plac":      "plac",
}
_TXN_LABELS = {
    "prodaja": "prodaju",
    "zakup":   "izdavanje",
}


def get_stale_listings(agency_id: str, stale_days: int = 60) -> list[dict]:
    """
    Vraća aktivne oglase koji su objavljeni pre više od stale_days dana.
    Sortira po starosti (najstariji prvi).
    """
    from data.supabase_client import get_client
    cutoff = (datetime.now(timezone.utc) - timedelta(days=stale_days)).isoformat()
    sb = get_client()
    res = (
        sb.table("listings")
        .select(
            "id, title, type, transaction, price, area_m2, city, municipality, "
            "rooms, floor, agent_id, seller_name, seller_phone, seller_email, "
            "portal_url, first_published_at, view_count, inquiry_count, agents(name, email, phone)"
        )
        .eq("agency_id", agency_id)
        .eq("active", True)
        .lt("first_published_at", cutoff)
        .order("first_published_at", desc=False)
        .execute()
    )
    return res.data or []


def enrich_with_benchmark(
    listings: list[dict],
    agency_id: str,
) -> list[dict]:
    """
    Za svaki stale oglas dodaje tržišni benchmark (medijana €/m² kvarta).
    Reuse: data.supabase_client.compute_pricing_benchmark — ali filtriramo
    samo oglase koji su već u stale listi.
    """
    from data.supabase_client import compute_pricing_benchmark

    # compute_pricing_benchmark vraća benchmark za SVE aktivne oglase
    # mapiramo po ID-u
    try:
        all_benchmarks = compute_pricing_benchmark(agency_id)
        bench_by_id = {b["listing_id"]: b for b in all_benchmarks if b.get("listing_id")}
    except Exception as e:
        print(f"    [StaleNudge] Benchmark nije dostupan: {e}")
        bench_by_id = {}

    enriched = []
    now = datetime.now(timezone.utc)

    for listing in listings:
        lid = listing.get("id")
        bench = bench_by_id.get(lid, {})

        # Dani na tržištu
        pub_str = listing.get("first_published_at") or listing.get("created_at") or ""
        days_on_market = 0
        if pub_str:
            try:
                pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                days_on_market = (now - pub_dt).days
            except Exception:
                pass

        price = float(listing.get("price") or 0)
        area  = float(listing.get("area_m2") or 1)
        price_m2 = round(price / area) if area > 0 else 0

        median_m2     = bench.get("median_eur_m2")
        delta_pct     = bench.get("delta_pct")
        overpriced    = bench.get("overpriced_flag", False)
        suggested_price: Optional[int] = None

        if median_m2 and area > 0:
            # Predlog: tržišna medijana + 5% margine, zaokruženo na 1000€
            suggested_raw = median_m2 * area * 1.05
            suggested_price = int(round(suggested_raw / 1000) * 1000)

        enriched.append({
            **listing,
            "days_on_market":  days_on_market,
            "price_m2":        price_m2,
            "median_m2":       median_m2,
            "delta_pct":       delta_pct,
            "overpriced":      overpriced,
            "suggested_price": suggested_price,
            "type_label":      _TYPE_LABELS.get(listing.get("type", ""), listing.get("type", "")),
            "txn_label":       _TXN_LABELS.get(listing.get("transaction", ""), listing.get("transaction", "")),
        })

    # Prioritizuj: precenjeni + najstariji
    enriched.sort(key=lambda x: (not x["overpriced"], -x["days_on_market"]))
    return enriched
