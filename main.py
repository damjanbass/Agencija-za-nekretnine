"""
Pokretanje:
  python -X utf8 main.py              # šalje svim klijentima iz Supabase
  python -X utf8 main.py --preview    # generiše HTML, ne šalje mejl
  python -X utf8 main.py --mock       # koristi mock podatke (bez Supabase)
"""

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config
from ai.analyze import generate_analysis, generate_analysis_fallback
from mailer.sender import send_report_email
from plans import get_plan
from scrapers.market_data import fetch_market, market_summary

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def prepare_template_vars(data: dict, analysis: dict | None,
                           snapshots: list[dict], city: str) -> dict:
    inquiries_change = data["inquiries"] - data["prev_inquiries"]
    safe_prev        = data["prev_inquiries"] or 1
    inquiries_pct    = round((inquiries_change / safe_prev) * 100)
    revenue_pct      = round((data["revenue"] / (data["revenue_goal"] or 1)) * 100)
    max_source       = max(data["inquiries_by_source"].values(), default=1)

    sign = "+" if inquiries_change >= 0 else ""
    inquiries_change_str = f"{sign}{inquiries_change} ({sign}{inquiries_pct}%)"

    plan = get_plan(data.get("plan_id", "free"))

    return {
        **data,
        "analysis":             analysis,
        "plan":                 plan,
        "market_snapshots":     snapshots,
        "market_summary":       market_summary(snapshots) if snapshots else None,
        "market_city":          city,
        "inquiries_change":     inquiries_change,
        "inquiries_change_str": inquiries_change_str,
        "contracts_total":      data["contracts_sale"] + data["contracts_rent"],
        "revenue_pct":          revenue_pct,
        "max_source_count":     max_source,
    }


def render_report(vars: dict, template: str = "report.html") -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    return env.get_template(template).render(**vars)


def run(preview: bool = False, use_mock: bool = False, city: str = "beograd"):
    if use_mock or not config.SUPABASE_KEY:
        if not use_mock:
            print("[!] SUPABASE_KEY nije podešen — koristim mock podatke.")
        from data.mock_data import get_mock_report_data
        clients_data = [("mock", get_mock_report_data())]
    else:
        from data.supabase_client import get_all_active_clients, get_report_data, save_report
        clients_raw  = get_all_active_clients()
        clients_data = [(c["id"], get_report_data(c["id"])) for c in clients_raw]

    for agency_id, data in clients_data:
        plan = get_plan(data.get("plan_id", "free"))
        print(f"\n[→] {data['agency_name']}  [{plan.name} · {plan.price_eur}€/mes]"
              f"  ({data['week_start']} – {data['week_end']})")

        # Plan: broj agenata
        agents = data["agents"]
        if not plan.agent_limit_ok(len(agents)):
            agents = agents[:plan.max_agents]
            print(f"    [Plan] Agenti ograničeni na {plan.max_agents} ({plan.name})")
        data["agents"] = agents

        # Tržišna analiza
        snapshots = []
        if plan.allows_market():
            print(f"    [Scraping] Preuzimam podatke sa: {', '.join(plan.market_sites)}")
            snapshots = fetch_market(plan.market_sites, city=city)
            mock_count = sum(1 for s in snapshots if s["is_mock"])
            live_count = len(snapshots) - mock_count
            print(f"    [Scraping] {live_count} live, {mock_count} mock snapshot-a")
        else:
            print(f"    [Tržište] Nije dostupno na {plan.name} planu.")

        # AI analiza
        market_for_ai = snapshots if snapshots else None
        if plan.allows_ai() and config.ANTHROPIC_API_KEY:
            print("    [AI] Pozivam Claude...")
            analysis = generate_analysis(data, market=market_for_ai)
        elif plan.allows_ai():
            print("    [AI] Nema ANTHROPIC_API_KEY — fallback analiza.")
            analysis = generate_analysis_fallback(data, market=market_for_ai)
        else:
            print(f"    [AI] Nije dostupno na {plan.name} planu.")
            analysis = None

        if analysis:
            print(f"    [+] Dobro:   {analysis['dobro']}")
            print(f"    [!] Pažnja:  {analysis['paznja']}")
            print(f"    [→] Predlog: {analysis['predlog']}")

        # Render
        html = render_report(prepare_template_vars(data, analysis, snapshots, city))

        slug = data["agency_name"].lower().replace(" ", "_")
        out  = Path(__file__).parent / f"izvestaj_{slug}.html"
        out.write_text(html, encoding="utf-8")
        print(f"    [HTML] {out.name}")

        # Arhiviranje u Supabase
        if not use_mock and config.SUPABASE_KEY:
            today      = date.today()
            week_start = today - timedelta(days=today.weekday() + 7)
            save_report(agency_id, week_start, html)
            print("    [DB] Arhivirano u Supabase.")

        # Slanje mejla
        if not preview:
            if not plan.allows_email():
                print(f"    [EMAIL] Slanje nije dostupno na {plan.name} planu.")
            else:
                subject = f"Nedeljni izveštaj — {data['week_start']} – {data['week_end']}"
                send_report_email(
                    to_email=data.get("agency_email", ""),
                    to_name=data["agency_name"],
                    subject=subject,
                    html_body=html,
                )
        else:
            print("    [EMAIL] Preview mod — mejl nije poslat.")

    print("\n[✓] Gotovo.")


def run_monthly(preview: bool = False, use_mock: bool = False):
    if use_mock or not config.SUPABASE_KEY:
        from data.mock_data import get_mock_monthly_data
        clients_data = [("mock", get_mock_monthly_data())]
    else:
        from data.supabase_client import get_all_active_clients, get_monthly_report_data
        clients_raw  = get_all_active_clients()
        clients_data = [(c["id"], get_monthly_report_data(c["id"])) for c in clients_raw]

    for agency_id, data in clients_data:
        plan = get_plan(data.get("plan_id", "free"))
        print(f"\n[→] {data['agency_name']}  [{plan.name}]  ({data['month_name']})")

        analysis = None
        if plan.allows_ai() and config.ANTHROPIC_API_KEY:
            from ai.analyze import generate_monthly_analysis
            print("    [AI] Pozivam Claude za mesečnu analizu...")
            analysis = generate_monthly_analysis(data)
            print(f"    [+] Dobro:   {analysis['dobro']}")
            print(f"    [!] Pažnja:  {analysis['paznja']}")
            print(f"    [→] Predlog: {analysis['predlog']}")

        vars = {**data, "analysis": analysis, "plan": plan}
        html = render_report(vars, template="monthly_report.html")

        slug = data["agency_name"].lower().replace(" ", "_")
        out  = Path(__file__).parent / f"mesecni_{slug}.html"
        out.write_text(html, encoding="utf-8")
        print(f"    [HTML] {out.name}")

        if not preview:
            if plan.allows_email():
                from mailer.sender import send_report_email
                subject = f"Mesečni izveštaj — {data['month_name']}"
                send_report_email(
                    to_email=data.get("agency_email", ""),
                    to_name=data["agency_name"],
                    subject=subject,
                    html_body=html,
                )
            else:
                print(f"    [EMAIL] Slanje nije dostupno na {plan.name} planu.")
        else:
            print("    [EMAIL] Preview mod — mejl nije poslat.")

    print("\n[✓] Mesečni izveštaji gotovi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Ne šalji mejl")
    parser.add_argument("--mock",    action="store_true", help="Koristi mock podatke")
    parser.add_argument("--monthly", action="store_true", help="Mesečni izveštaj umesto nedeljnog")
    parser.add_argument("--city",    default="beograd",  help="Grad za tržišnu analizu")
    args = parser.parse_args()
    if args.monthly:
        run_monthly(preview=args.preview, use_mock=args.mock)
    else:
        run(preview=args.preview, use_mock=args.mock, city=args.city)
