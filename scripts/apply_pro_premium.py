"""
Primenjuje izmene plana Pro/Premium direktno preko Supabase-py.
Pokretanje:
  python -X utf8 scripts/apply_pro_premium.py

Šta radi:
  1. UPDATE plans (Pro: 1 agencija / 10 agenata / 6 meseci, cena 49€)
  2. UPSERT Premium plan (79€, neograničeno agenata, 12 meseci, custom_branding)
  3. Kreira Storage bucket "agency-logos" (public read)

ALTER TABLE agencies ADD COLUMN logo_url i Storage policy ne mogu preko klijenta —
ti koraci ostaju za Supabase Dashboard (skripta će ih prijaviti na kraju).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from supabase import create_client


def main():
    if not config.SUPABASE_KEY:
        print("[X] SUPABASE_KEY nije postavljen u .env")
        sys.exit(1)

    sb = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    # ── 1. Pro: novi limiti ─────────────────────────────────────────────
    print("[1/3] Update Pro plan...")
    try:
        res = (
            sb.table("plans")
            .update({
                "max_agencies":   1,
                "max_agents":     10,
                "history_months": 6,
                "price_eur":      49,
            })
            .eq("id", "pro")
            .execute()
        )
        if res.data:
            row = res.data[0]
            print(f"    [OK] Pro: agencies={row['max_agencies']}, agents={row['max_agents']}, history={row['history_months']} mes, {row['price_eur']}€")
        else:
            print("    [!] Pro plan nije pronađen u tabeli — preskačem.")
    except Exception as e:
        print(f"    [X] Greška: {e}")
        sys.exit(2)

    # ── 2. Premium: insert ili update ───────────────────────────────────
    print("[2/3] Upsert Premium plan...")
    try:
        res = (
            sb.table("plans")
            .upsert({
                "id":              "premium",
                "name":            "Premium",
                "price_eur":       79,
                "max_agencies":    1,
                "max_agents":      -1,
                "history_months":  12,
                "ai_analysis":     True,
                "email_send":      True,
                "weekly_report":   True,
                "monthly_report":  True,
                "daily_report":    False,
                "pdf_export":      True,
                "custom_branding": True,
            }, on_conflict="id")
            .execute()
        )
        if res.data:
            row = res.data[0]
            print(f"    [OK] Premium: agents={row['max_agents']} (-1=neograničeno), history={row['history_months']} mes, branding={row['custom_branding']}, {row['price_eur']}€")
    except Exception as e:
        print(f"    [X] Greška: {e}")
        sys.exit(3)

    # ── 3. Storage bucket "agency-logos" ────────────────────────────────
    print("[3/3] Kreiram Storage bucket 'agency-logos'...")
    try:
        existing = sb.storage.list_buckets()
        names    = [b.name for b in existing]
        if "agency-logos" in names:
            print("    [OK] Bucket već postoji — preskačem.")
        else:
            sb.storage.create_bucket(
                "agency-logos",
                options={"public": True, "file_size_limit": 2 * 1024 * 1024},
            )
            print("    [OK] Bucket 'agency-logos' kreiran (public read, 2MB limit).")
    except Exception as e:
        print(f"    [X] Greška pri kreiranju bucket-a: {e}")
        print("        (Možda već postoji ili API ključ nema dovoljne privilegije.)")

    # ── Šta NIJE moguće preko klijenta ──────────────────────────────────
    print()
    print("=" * 60)
    print("OSTAJE RUČNO U Supabase Dashboard SQL Editor-u:")
    print()
    print("  ALTER TABLE agencies ADD COLUMN IF NOT EXISTS logo_url TEXT;")
    print()
    print("Ovaj DDL ne može preko REST API-ja. Otvori Dashboard → SQL")
    print("Editor → New query → nalepi liniju iznad → Run.")
    print()
    print("Takođe (opciono) u Storage → agency-logos → Policies dodati:")
    print("  • INSERT/UPDATE/DELETE: ulogovani korisnici, path = '<agency_id>.*'")
    print("=" * 60)


if __name__ == "__main__":
    main()
