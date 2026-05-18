"""
Dnevni cron — skrejpuje tržišne podatke i upisuje u Supabase.

Razlika od main.py:
  • main.py generiše izveštaj i koristi snapshot iz memorije (ad-hoc scrape).
  • Ovaj skript samostalno skuplja podatke svaki dan i čuva ih u
    market_snapshots + market_listings_sample. Iz tih podataka se kasnije
    računa pricing benchmark, DOM (Faza 2), trend (Faza 2), itd.

Pokretanje:
    python -X utf8 -m scripts.scrape_market_daily
    python -X utf8 -m scripts.scrape_market_daily --mock    # bez network-a
    python -X utf8 -m scripts.scrape_market_daily --sale-only

Cron primer (Linux):
    0 4 * * *  cd /app && python -X utf8 -m scripts.scrape_market_daily >> /var/log/scrape_market.log 2>&1
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import config
from plans import get_plan
from scrapers.market_data import fetch_market

# Svi sajtovi koje pratimo dnevno (nezavisno od planova — istorija je deljena resursa)
ALL_SITES = ["Halo oglasi", "4zida", "Nekretnine.rs", "CityExpert"]
DEFAULT_CITY = "beograd"


def determine_segments(agencies: list[dict]) -> set[tuple[str, str]]:
    """
    Vraća skup (city, transaction_type) koje treba skrejpovati.
    Bazirano na tracks_sale/tracks_rent preferencama agencija — ako nijedna
    agencija ne prati zakup, ne trošimo HTTP requeste na njega.
    """
    segments: set[tuple[str, str]] = set()
    for a in agencies:
        # Za sada držimo Beograd; multi-city dolazi u kasnijoj fazi.
        city = DEFAULT_CITY
        if a.get("tracks_sale", True):
            segments.add((city, "sale"))
        if a.get("tracks_rent", False):
            segments.add((city, "rent"))
    # Fallback: ako nema agencija, skuplji bar prodaju (osnovni dataset).
    if not segments:
        segments.add((DEFAULT_CITY, "sale"))
    return segments


def run(use_mock: bool = False, sale_only: bool = False, rent_only: bool = False) -> int:
    """Vraća broj uspešno persistiranih snapshot-a (sajt × segment)."""
    if use_mock or not config.SUPABASE_KEY:
        if not use_mock:
            print("[!] SUPABASE_KEY nije podešen — koristim mock segmente (sale).")
        segments = {(DEFAULT_CITY, "sale")}
    else:
        from data.supabase_client import get_all_active_clients
        agencies = get_all_active_clients()
        segments = determine_segments(agencies)
        print(f"[i] Aktivnih agencija: {len(agencies)}, segmenti za scrape: {sorted(segments)}")

    if sale_only:
        segments = {s for s in segments if s[1] == "sale"}
    if rent_only:
        segments = {s for s in segments if s[1] == "rent"}

    persisted = 0
    for city, ttype in sorted(segments):
        print(f"\n[→] Scrape: city={city}, transaction={ttype}, sites={ALL_SITES}")
        snapshots = fetch_market(
            sites=ALL_SITES,
            city=city,
            transaction_type=ttype,
            persist=not use_mock and bool(config.SUPABASE_KEY),
        )
        for s in snapshots:
            tag = "MOCK" if s.get("is_mock") else "LIVE"
            print(f"    [{tag}] {s['site']:15s} "
                  f"total={s.get('total_listings', 0):5d}  "
                  f"sample={s.get('raw_sample_count', 0):3d}  "
                  f"median={s.get('median_price_eur_m2') or '—'} €/m²")
        persisted += len(snapshots)

    print(f"\n[✓] Persistirano snapshot-a: {persisted}")
    return persisted


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock",      action="store_true", help="Koristi mock podatke (bez Supabase / network)")
    parser.add_argument("--sale-only", action="store_true", help="Skrejpuj samo prodaju")
    parser.add_argument("--rent-only", action="store_true", help="Skrejpuj samo zakup")
    args = parser.parse_args()
    run(use_mock=args.mock, sale_only=args.sale_only, rent_only=args.rent_only)
