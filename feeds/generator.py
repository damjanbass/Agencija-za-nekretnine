"""
Generiše XML feed za svaki portal i uploaduje na Supabase Storage.

Pokretanje:
  python -X utf8 feeds/generator.py          # sve agencije, svi portali
  python -X utf8 feeds/generator.py --mock   # koristi mock podatke
  python -X utf8 feeds/generator.py --local  # čuva XML lokalno (ne uploaduje)

Javni URL fajlova:
  https://cesxmcbodcpfnpyusxhj.supabase.co/storage/v1/object/public/feeds/{slug}_{portal}.xml
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import config
from feeds.portals.halo_oglasi  import build_xml as halo_xml
from feeds.portals.cetirizida   import build_xml as zida_xml
from feeds.portals.nekretnine_rs import build_xml as nekrs_xml

PORTALS = {
    "halo_oglasi":   halo_xml,
    "4zida":         zida_xml,
    "nekretnine_rs": nekrs_xml,
}


def get_listings(agency_id: str) -> list[dict]:
    from supabase import create_client
    sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    res = sb.table("listings").select("*").eq("agency_id", agency_id).eq("active", True).execute()
    return res.data or []


def get_agency_info(agency_id: str) -> dict:
    from supabase import create_client
    sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    res = sb.table("agencies").select("id, name, email").eq("id", agency_id).single().execute()
    return res.data


def upload_feed(slug: str, portal: str, xml_bytes: bytes) -> str:
    from supabase import create_client
    sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    filename = f"{slug}_{portal}.xml"
    try:
        sb.storage.from_("feeds").upload(
            filename, xml_bytes,
            {"content-type": "application/xml; charset=utf-8", "upsert": "true"}
        )
    except Exception:
        sb.storage.from_("feeds").update(
            filename, xml_bytes,
            {"content-type": "application/xml; charset=utf-8"}
        )
    return sb.storage.from_("feeds").get_public_url(filename)


def run(use_mock: bool = False, local_only: bool = False):
    if use_mock or not config.SUPABASE_KEY:
        from feeds.mock_listings import MOCK_AGENCY, MOCK_LISTINGS
        clients = [(MOCK_AGENCY, MOCK_LISTINGS)]
    else:
        from supabase import create_client
        sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        agencies = sb.table("agencies").select("id, name, email").eq("active", True).execute().data
        clients = [(a, get_listings(a["id"])) for a in agencies]

    for agency, listings in clients:
        slug = agency["name"].lower().replace(" ", "_")
        print(f"\n[→] {agency['name']} — {len(listings)} aktivnih oglasa")

        if not listings:
            print("    [!] Nema oglasa, preskačem.")
            continue

        for portal_name, build_fn in PORTALS.items():
            xml_bytes = build_fn(agency, listings)

            if local_only:
                out = Path(__file__).parent / f"{slug}_{portal_name}.xml"
                out.write_bytes(xml_bytes)
                print(f"    [{portal_name}] Sačuvan lokalno: {out.name}")
            else:
                try:
                    url = upload_feed(slug, portal_name, xml_bytes)
                    print(f"    [{portal_name}] {url}")
                except Exception as e:
                    print(f"    [{portal_name}] Greška pri uploadu: {e}")

    print("\n[✓] Feedovi generisani.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock",  action="store_true", help="Koristi mock podatke")
    parser.add_argument("--local", action="store_true", help="Čuvaj XML lokalno")
    args = parser.parse_args()
    run(use_mock=args.mock, local_only=args.local)
