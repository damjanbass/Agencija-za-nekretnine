"""
Admin CLI za onboarding agencija.

Pokretanje (iz root foldera projekta):
  python -X utf8 admin/onboard.py create-agency \\
      --name "Agencija Test d.o.o." \\
      --email "office@test.rs" \\
      --plan pro \\
      --revenue-goal 9000 \\
      --user-password "TempPass123"

Sve komande:
  create-agency  → kreira Supabase auth user + agencies red
  add-agent      → dodaje agenta postojećoj agenciji
  set-plan       → menja plan agencije
  set-goal       → menja nedeljni revenue goal
  list-agencies  → listanje svih agencija sa osnovnim metrikama

Koristi SUPABASE_KEY (service-role) iz .env.
"""

import argparse
import sys
from pathlib import Path

# Omogući import iz root foldera
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import config
from data.supabase_client import get_client


WEB_PANEL_URL   = "https://agencija-za-nekretnine-nine.vercel.app/app.html"
PUBLIC_BASE_URL = "https://agencija-za-nekretnine-nine.vercel.app/public.html"
VALID_PLANS     = ["basic", "pro", "premium"]


def cmd_create_agency(args):
    if len(args.user_password) < 6:
        sys.exit("[!] Password mora imati najmanje 6 karaktera (Supabase zahtev).")

    sb = get_client()

    print(f"[1/2] Kreiram Supabase auth user za {args.email}...")
    try:
        auth_result = sb.auth.admin.create_user({
            "email":         args.email,
            "password":      args.user_password,
            "email_confirm": True,
        })
        user_id = auth_result.user.id
    except Exception as e:
        sys.exit(f"[!] Auth user nije kreiran: {e}")
    print(f"      user_id = {user_id}")

    print(f"[2/2] Kreiram agencies red...")
    try:
        result = sb.table("agencies").insert({
            "name":         args.name,
            "email":        args.email,
            "user_id":      user_id,
            "plan_id":      args.plan,
            "revenue_goal": args.revenue_goal,
            "active":       True,
        }).execute()
        agency = result.data[0]
    except Exception as e:
        print(f"[!] Agencija nije kreirana: {e}")
        print(f"[!] Auth user {user_id} je već kreiran — obriši ga ručno iz Supabase Auth dashboarda ako ponavljaš.")
        sys.exit(1)

    print(f"      agency_id    = {agency['id']}")
    print(f"      public_token = {agency['public_token']}")

    print("\n[✓] Agencija uspešno kreirana.\n")
    print("───── POŠALJI KLIJENTU ─────")
    print(f"  Naziv:         {args.name}")
    print(f"  Plan:          {args.plan}")
    print(f"  Login URL:     {WEB_PANEL_URL}")
    print(f"  Email:         {args.email}")
    print(f"  Password:      {args.user_password}")
    print(f"  Public link:   {PUBLIC_BASE_URL}?token={agency['public_token']}")
    print("────────────────────────────\n")
    print(f"Sledeći korak: dodaj agente sa\n  python -X utf8 admin/onboard.py add-agent --agency-id {agency['id']} --name \"Ime\" --email \"email@...\"")


def cmd_add_agent(args):
    sb = get_client()
    try:
        result = sb.table("agents").insert({
            "agency_id": args.agency_id,
            "name":      args.name,
            "email":     args.email,
            "active":    True,
        }).execute()
    except Exception as e:
        sys.exit(f"[!] Agent nije dodat: {e}")
    print(f"[✓] Agent '{args.name}' ({args.email}) dodat.")
    print(f"    agent_id = {result.data[0]['id']}")


def cmd_set_plan(args):
    sb = get_client()
    result = sb.table("agencies").update({"plan_id": args.plan}).eq("id", args.agency_id).execute()
    if not result.data:
        sys.exit(f"[!] Agencija sa id={args.agency_id} ne postoji.")
    print(f"[✓] Plan agencije {args.agency_id} postavljen na '{args.plan}'.")


def cmd_set_goal(args):
    sb = get_client()
    result = sb.table("agencies").update({"revenue_goal": args.revenue_goal}).eq("id", args.agency_id).execute()
    if not result.data:
        sys.exit(f"[!] Agencija sa id={args.agency_id} ne postoji.")
    print(f"[✓] Nedeljni revenue goal agencije {args.agency_id} postavljen na {args.revenue_goal}€.")


def cmd_list_agencies(args):
    sb = get_client()
    agencies = sb.table("agencies").select(
        "id, name, email, plan_id, revenue_goal, active, public_token, created_at"
    ).order("created_at", desc=True).execute().data

    if not agencies:
        print("Nema agencija u bazi.")
        return

    # Brojač agenata po agenciji
    agents_count = {}
    agents_rows = sb.table("agents").select("agency_id").eq("active", True).execute().data
    for r in agents_rows:
        agents_count[r["agency_id"]] = agents_count.get(r["agency_id"], 0) + 1

    print(f"\n{'AGENCIJA':<35} {'PLAN':<8} {'GOAL':<8} {'AGENATA':<8} {'ID'}")
    print("─" * 110)
    for a in agencies:
        flag = "" if a["active"] else "  [NEAKTIVNA]"
        print(f"{a['name'][:34]:<35} {a['plan_id']:<8} {a['revenue_goal']:<8} {agents_count.get(a['id'], 0):<8} {a['id']}{flag}")
    print(f"\nUkupno: {len(agencies)} agencija.\n")


def main():
    parser = argparse.ArgumentParser(description="Admin CLI za onboarding agencija.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("create-agency", help="Kreira novu agenciju + auth user.")
    p.add_argument("--name",          required=True, help="Pun naziv agencije (npr. 'Agencija Test d.o.o.')")
    p.add_argument("--email",         required=True, help="Email agencije (i za web login)")
    p.add_argument("--plan",          default="basic", choices=VALID_PLANS)
    p.add_argument("--revenue-goal",  type=int, required=True, dest="revenue_goal",
                   help="NEDELJNI cilj prihoda u € (mesečni se računa kao 4× ova vrednost)")
    p.add_argument("--user-password", required=True, dest="user_password",
                   help="Početni password za web login (min 6 karaktera)")
    p.set_defaults(func=cmd_create_agency)

    p = sub.add_parser("add-agent", help="Dodaje agenta postojećoj agenciji.")
    p.add_argument("--agency-id", required=True, dest="agency_id", help="UUID agencije")
    p.add_argument("--name",      required=True)
    p.add_argument("--email",     required=True, help="Email agenta (za personalne izveštaje)")
    p.set_defaults(func=cmd_add_agent)

    p = sub.add_parser("set-plan", help="Menja plan agencije.")
    p.add_argument("--agency-id", required=True, dest="agency_id")
    p.add_argument("--plan",      required=True, choices=VALID_PLANS)
    p.set_defaults(func=cmd_set_plan)

    p = sub.add_parser("set-goal", help="Menja nedeljni revenue goal.")
    p.add_argument("--agency-id",    required=True, dest="agency_id")
    p.add_argument("--revenue-goal", required=True, type=int, dest="revenue_goal")
    p.set_defaults(func=cmd_set_goal)

    p = sub.add_parser("list-agencies", help="Listanje svih agencija.")
    p.set_defaults(func=cmd_list_agencies)

    args = parser.parse_args()
    if not config.SUPABASE_KEY:
        sys.exit("[!] SUPABASE_KEY nije podešen u .env — admin operacije nisu moguće.")
    args.func(args)


if __name__ == "__main__":
    main()
