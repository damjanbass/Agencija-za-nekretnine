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
                           snapshots: list[dict], city: str,
                           benchmark: dict | None = None) -> dict:
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
        "benchmark":            benchmark,
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

        # Benchmark
        benchmark = None
        if plan.allows_benchmark():
            if not use_mock and config.SUPABASE_KEY:
                from datetime import datetime as _dt
                from data.supabase_client import get_benchmark_data
                _ws_iso = _dt.strptime(data["week_start"], "%d.%m.%Y").strftime("%Y-%m-%d")
                benchmark = get_benchmark_data(_ws_iso)
            else:
                from data.mock_data import get_mock_benchmark
                benchmark = get_mock_benchmark()
            if benchmark:
                print(f"    [Benchmark] {benchmark['agency_count']} agencija — prosek konverzija {benchmark['avg_conversion']}%, prihod {benchmark['avg_revenue']:,}€")
            else:
                print("    [Benchmark] Nema dovoljno podataka za poređenje.")

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
            print(f"    [+] Dobro:    {analysis['dobro']}")
            print(f"    [!] Pažnja:   {analysis['paznja']}")
            print(f"    [→] Predlog:  {analysis['predlog']}")
            print(f"    [~] Prognoza: {analysis.get('prognoza', '—')}")

        # Render
        html = render_report(prepare_template_vars(data, analysis, snapshots, city, benchmark))

        slug = data["agency_name"].lower().replace(" ", "_")
        out  = Path(__file__).parent / f"izvestaj_{slug}.html"
        out.write_text(html, encoding="utf-8")
        print(f"    [HTML] {out.name}")

        # Arhiviranje u Supabase
        if not use_mock and config.SUPABASE_KEY:
            today      = date.today()
            week_start = today - timedelta(days=today.weekday() + 7)
            save_report(agency_id, week_start, html, report_type="weekly")
            print("    [DB] Arhivirano u Supabase.")

        # PDF export
        pdf_bytes = None
        if plan.allows_pdf():
            from pdf.generator import generate_pdf
            print("    [PDF] Generišem PDF...")
            pdf_bytes = generate_pdf(html)
            pdf_out = Path(__file__).parent / f"izvestaj_{slug}.pdf"
            pdf_out.write_bytes(pdf_bytes)
            print(f"    [PDF] {pdf_out.name}")
        else:
            print(f"    [PDF] Nije dostupno na {plan.name} planu.")

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
                    pdf_bytes=pdf_bytes,
                    pdf_filename=f"izvestaj_{slug}_{data['week_start'].replace('.', '-')}.pdf",
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

        # Tržišna analiza (za mesečni kontekst)
        snapshots = []
        if plan.allows_market():
            print(f"    [Scraping] Preuzimam podatke sa: {', '.join(plan.market_sites)}")
            snapshots = fetch_market(plan.market_sites, city="beograd")
            mock_count = sum(1 for s in snapshots if s["is_mock"])
            print(f"    [Scraping] {len(snapshots) - mock_count} live, {mock_count} mock snapshot-a")

        analysis = None
        if plan.allows_ai() and config.ANTHROPIC_API_KEY:
            from ai.analyze import generate_monthly_analysis
            print("    [AI] Pozivam Claude za mesečnu analizu...")
            analysis = generate_monthly_analysis(data, market=snapshots or None)
        elif plan.allows_ai():
            from ai.analyze import generate_monthly_analysis_fallback
            print("    [AI] Nema ANTHROPIC_API_KEY — fallback mesečna analiza.")
            analysis = generate_monthly_analysis_fallback(data)
        else:
            print(f"    [AI] Nije dostupno na {plan.name} planu.")

        if analysis:
            print(f"    [+] Dobro:    {analysis['dobro']}")
            print(f"    [!] Pažnja:   {analysis['paznja']}")
            print(f"    [→] Predlog:  {analysis['predlog']}")
            print(f"    [~] Prognoza: {analysis.get('prognoza', '—')}")

        vars = {**data, "analysis": analysis, "plan": plan}
        html = render_report(vars, template="monthly_report.html")

        slug = data["agency_name"].lower().replace(" ", "_")
        out  = Path(__file__).parent / f"mesecni_{slug}.html"
        out.write_text(html, encoding="utf-8")
        print(f"    [HTML] {out.name}")

        # Arhiviranje u Supabase
        if not use_mock and config.SUPABASE_KEY:
            today       = date.today()
            month_end   = today.replace(day=1) - timedelta(days=1)
            month_start = month_end.replace(day=1)
            from data.supabase_client import save_report
            save_report(agency_id, month_start, html, report_type="monthly")
            print("    [DB] Arhivirano u Supabase.")

        # PDF export
        pdf_bytes = None
        if plan.allows_pdf():
            from pdf.generator import generate_pdf
            print("    [PDF] Generišem PDF...")
            pdf_bytes = generate_pdf(html)
            pdf_out = Path(__file__).parent / f"mesecni_{slug}.pdf"
            pdf_out.write_bytes(pdf_bytes)
            print(f"    [PDF] {pdf_out.name}")
        else:
            print(f"    [PDF] Nije dostupno na {plan.name} planu.")

        if not preview:
            if plan.allows_email():
                from mailer.sender import send_report_email
                subject = f"Mesečni izveštaj — {data['month_name']}"
                send_report_email(
                    to_email=data.get("agency_email", ""),
                    to_name=data["agency_name"],
                    subject=subject,
                    html_body=html,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=f"mesecni_{slug}_{data['month_name'].replace(' ', '_')}.pdf",
                )
            else:
                print(f"    [EMAIL] Slanje nije dostupno na {plan.name} planu.")
        else:
            print("    [EMAIL] Preview mod — mejl nije poslat.")

    print("\n[✓] Mesečni izveštaji gotovi.")


def run_agent_reports(preview: bool = False, use_mock: bool = False):
    if use_mock or not config.SUPABASE_KEY:
        from data.mock_data import get_mock_report_data
        clients_data = [("mock", get_mock_report_data())]
    else:
        from data.supabase_client import get_all_active_clients, get_report_data
        clients_raw  = get_all_active_clients()
        clients_data = [(c["id"], get_report_data(c["id"])) for c in clients_raw]

    for agency_id, data in clients_data:
        plan = get_plan(data.get("plan_id", "free"))
        if not plan.allows_agent_reports():
            print(f"\n[skip] {data['agency_name']} — agent izveštaji nisu dostupni na {plan.name} planu.")
            continue

        agents = data["agents"]
        agents_sorted = sorted(agents, key=lambda a: a["contracts"] / max(a["inquiries"], 1), reverse=True)
        team_inquiries = sum(a["inquiries"] for a in agents)
        team_contracts = sum(a["contracts"] for a in agents)
        team_conv      = round(team_contracts / max(team_inquiries, 1) * 100, 1)

        print(f"\n[→] Agent izveštaji: {data['agency_name']}  ({data['week_start']} – {data['week_end']})")

        for rank, agent in enumerate(agents_sorted, start=1):
            if not agent.get("email"):
                print(f"    [skip] {agent['name']} — nema email adrese")
                continue

            agent_conv = round(agent["contracts"] / max(agent["inquiries"], 1) * 100, 1)
            vars = {
                **data,
                "agent_name":       agent["name"],
                "agent_conversion": agent_conv,
                "agent_inquiries":  agent["inquiries"],
                "agent_contracts":  agent["contracts"],
                "agent_rank":       rank,
                "team_size":        len(agents_sorted),
                "team_conversion":  team_conv,
            }

            html = render_report(vars, template="agent_report.html")

            if preview:
                slug = agent["name"].lower().replace(" ", "_")
                out  = Path(__file__).parent / f"agent_{slug}.html"
                out.write_text(html, encoding="utf-8")
                print(f"    [preview] {agent['name']} → {out.name}")
            else:
                subject = f"Vaš nedeljni izveštaj — {data['week_start']}"
                send_report_email(
                    to_email=agent["email"],
                    to_name=agent["name"],
                    subject=subject,
                    html_body=html,
                )
                print(f"    [✓] {agent['name']} ({agent['email']})")

    print("\n[✓] Agent izveštaji gotovi.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview",       action="store_true", help="Ne šalji mejl")
    parser.add_argument("--mock",          action="store_true", help="Koristi mock podatke")
    parser.add_argument("--monthly",       action="store_true", help="Mesečni izveštaj umesto nedeljnog")
    parser.add_argument("--agent-reports", action="store_true", help="Pošalji personalne izveštaje agentima")
    parser.add_argument("--city",          default="beograd",   help="Grad za tržišnu analizu")
    args = parser.parse_args()
    if args.monthly:
        run_monthly(preview=args.preview, use_mock=args.mock)
    elif args.agent_reports:
        run_agent_reports(preview=args.preview, use_mock=args.mock)
    else:
        run(preview=args.preview, use_mock=args.mock, city=args.city)
