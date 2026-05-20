"""
Pokretanje:
  python -X utf8 main.py              # šalje svim klijentima iz Supabase
  python -X utf8 main.py --preview    # generiše HTML, ne šalje mejl
  python -X utf8 main.py --mock       # koristi mock podatke (bez Supabase)
"""

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config
from ai.analyze import (
    generate_agent_analysis,
    generate_agent_analysis_fallback,
    generate_analysis,
    generate_analysis_fallback,
)
from mailer.sender import send_report_email
from plans import get_plan
from scrapers.market_data import fetch_market, market_summary

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def _build_trend_chart_points(series: list[dict], width: int = 200, height: int = 60,
                              y_field: str = "median_eur_m2") -> list[dict]:
    """Normalizuje series u SVG (x, y) tačke za polyline. y_field bira polje iz svake tačke."""
    if not series or len(series) < 2:
        return []
    vals = [s[y_field] for s in series if s.get(y_field) is not None]
    if len(vals) < 2:
        return []
    vmin, vmax = min(vals), max(vals)
    span = max(vmax - vmin, 1)
    n = len(series)
    pad_top, pad_bot = 5, 5
    inner_h = height - pad_top - pad_bot
    points = []
    for i, s in enumerate(series):
        x = round(i * (width / (n - 1)), 2)
        v = s.get(y_field) if s.get(y_field) is not None else vmin
        y = round(pad_top + (1 - (v - vmin) / span) * inner_h, 2)
        points.append({"x": x, "y": y})
    return points


def prepare_template_vars(data: dict, analysis: dict | None,
                           snapshots: list[dict], city: str,
                           benchmark: dict | None = None,
                           pricing_benchmark: list[dict] | None = None,
                           market_trend: dict | None = None,
                           dom_stats: dict | None = None,
                           hot_zones: list[dict] | None = None,
                           pricing_recommendations: list[dict] | None = None,
                           listing_opportunities: list[dict] | None = None,
                           competitor_inventory: dict | None = None) -> dict:
    inquiries_change = data["inquiries"] - data["prev_inquiries"]
    safe_prev        = data["prev_inquiries"] or 1
    inquiries_pct    = round((inquiries_change / safe_prev) * 100)
    revenue_pct      = round((data["revenue"] / (data["revenue_goal"] or 1)) * 100)
    max_source       = max(data["inquiries_by_source"].values(), default=1)

    sign = "+" if inquiries_change >= 0 else ""
    inquiries_change_str = f"{sign}{inquiries_change} ({sign}{inquiries_pct}%)"

    plan = get_plan(data.get("plan_id", "basic"))

    return {
        **data,
        "analysis":             analysis,
        "plan":                 plan,
        "agency_logo":          data.get("logo_url") if plan.allows_branding() else None,
        "market_snapshots":     snapshots,
        "market_summary":       market_summary(snapshots) if snapshots else None,
        "market_city":          city,
        "inquiries_change":     inquiries_change,
        "inquiries_change_str": inquiries_change_str,
        "contracts_total":      data["contracts_sale"] + data["contracts_rent"],
        "revenue_pct":          revenue_pct,
        "max_source_count":     max_source,
        "benchmark":            benchmark,
        "pricing_benchmark":              pricing_benchmark or [],
        "pricing_benchmark_available":    plan.allows_pricing_benchmark(),
        "market_trend":                   market_trend,
        "trend_chart_points":             _build_trend_chart_points(market_trend["series"]) if market_trend else [],
        "dom_stats":                      dom_stats,
        "hot_zones":                      hot_zones or [],
        "pricing_recommendations":        pricing_recommendations or [],
        "listing_opportunities":          listing_opportunities or [],
        "competitor_inventory":           competitor_inventory or {},
        "alerts_available":               plan.allows_alerts(),
    }


def render_report(vars: dict, template: str = "report.html") -> str:
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    env.globals["support_email"] = config.SUPPORT_EMAIL
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
        clients_data = []
        for c in clients_raw:
            try:
                clients_data.append((c["id"], get_report_data(c["id"])))
            except LookupError as e:
                print(f"[!] Preskačem klijenta {c.get('id')}: {e}")

    for agency_id, data in clients_data:
        plan = get_plan(data.get("plan_id", "basic"))
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

        # Pricing benchmark (Pro+) — vaše cene vs medijana tržišta po segmentu
        pricing_benchmark: list[dict] = []
        market_trend: dict | None = None
        dom_stats: dict | None = None
        hot_zones: list[dict] = []
        if plan.allows_pricing_benchmark():
            if use_mock or not config.SUPABASE_KEY:
                from data.mock_data import (
                    get_mock_pricing_benchmark, get_mock_market_trend,
                    get_mock_dom_stats, get_mock_hot_zones,
                )
                pricing_benchmark = get_mock_pricing_benchmark()
                market_trend = get_mock_market_trend()
                dom_stats    = get_mock_dom_stats()
                hot_zones    = get_mock_hot_zones()
                print(f"    [PricingBench] Mock režim — "
                      f"{len(pricing_benchmark)} oglasa, trend MoM {market_trend['mom_pct']}%, "
                      f"DOM {dom_stats['median_dom_days']}d, {len(hot_zones)} hot zone.")
            else:
                from data.supabase_client import (
                    compute_pricing_benchmark, get_market_trend,
                    compute_dom_stats, compute_hot_zones,
                )
                pricing_benchmark = compute_pricing_benchmark(agency_id)
                # Faza 2 trend/DOM/hot zones — gradski nivo (sale; rent dodajemo kad agencija aktivira)
                market_trend = get_market_trend(transaction_type="sale", city=city)
                dom_stats    = compute_dom_stats(transaction_type="sale", city=city)
                hot_zones    = compute_hot_zones(transaction_type="sale", city=city)
                over = sum(1 for r in pricing_benchmark if r.get("overpriced_flag"))
                under = sum(1 for r in pricing_benchmark if r.get("underpriced_flag"))
                trend_str = f"MoM {market_trend['mom_pct']}%" if market_trend else "trend —"
                dom_str   = f"DOM {dom_stats['median_dom_days']}d" if dom_stats else "DOM —"
                print(f"    [PricingBench] {len(pricing_benchmark)} oglasa "
                      f"({over} iznad, {under} ispod), {trend_str}, {dom_str}, "
                      f"{len(hot_zones)} hot zone.")
        else:
            print(f"    [PricingBench] Nije dostupno na {plan.name} planu.")

        # Faza 3 Intelligence Pack (Premium only)
        pricing_recommendations: list[dict] = []
        listing_opportunities:   list[dict] = []
        competitor_inventory:    dict       = {}
        if plan.allows_alerts():
            if use_mock or not config.SUPABASE_KEY:
                from data.mock_data import (
                    get_mock_pricing_recommendations,
                    get_mock_listing_opportunities,
                    get_mock_competitor_inventory,
                )
                pricing_recommendations = get_mock_pricing_recommendations()
                listing_opportunities   = get_mock_listing_opportunities()
                competitor_inventory    = get_mock_competitor_inventory()
                print(f"    [Intel] Mock režim — "
                      f"{len(pricing_recommendations)} recs, "
                      f"{len(listing_opportunities)} opps, "
                      f"{competitor_inventory.get('total_agencies', 0)} agencija.")
            else:
                from data.supabase_client import (
                    compute_pricing_recommendations,
                    compute_listing_opportunities,
                    compute_competitor_inventory,
                )
                pricing_recommendations = compute_pricing_recommendations(agency_id)
                listing_opportunities   = compute_listing_opportunities(city=city)
                competitor_inventory    = compute_competitor_inventory(city=city)
                print(f"    [Intel] {len(pricing_recommendations)} recs, "
                      f"{len(listing_opportunities)} opps, "
                      f"{competitor_inventory.get('total_agencies', 0)} agencija.")
        elif plan.allows_pricing_benchmark():
            print(f"    [Intel] Nije dostupno na {plan.name} planu (Premium only).")

        # AI analiza
        market_for_ai = snapshots if snapshots else None
        ai_kwargs = dict(
            market=market_for_ai,
            pricing_benchmark=pricing_benchmark or None,
            dom_stats=dom_stats,
            trend=market_trend,
            hot_zones=hot_zones or None,
        )
        if plan.allows_ai() and config.ANTHROPIC_API_KEY:
            print("    [AI] Pozivam Claude...")
            try:
                analysis = generate_analysis(data, **ai_kwargs)
            except Exception as e:
                print(f"    [AI] Claude poziv neuspešan ({type(e).__name__}) — fallback.")
                analysis = generate_analysis_fallback(data, market=market_for_ai)
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
        html = render_report(prepare_template_vars(
            data, analysis, snapshots, city, benchmark,
            pricing_benchmark=pricing_benchmark,
            market_trend=market_trend,
            dom_stats=dom_stats,
            hot_zones=hot_zones,
            pricing_recommendations=pricing_recommendations,
            listing_opportunities=listing_opportunities,
            competitor_inventory=competitor_inventory,
        ))

        slug = re.sub(r"[^\w]", "_", data["agency_name"].lower()).strip("_")
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
        if preview:
            print(f"    [PDF] Preview mod — preskočeno.")
        elif plan.allows_pdf():
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
        plan = get_plan(data.get("plan_id", "basic"))
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
            from ai.analyze import generate_monthly_analysis, generate_monthly_analysis_fallback
            print("    [AI] Pozivam Claude za mesečnu analizu...")
            try:
                analysis = generate_monthly_analysis(data, market=snapshots or None)
            except Exception as e:
                print(f"    [AI] Claude poziv neuspešan ({type(e).__name__}) — fallback.")
                analysis = generate_monthly_analysis_fallback(data)
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

        vars = {
            **data,
            "analysis":    analysis,
            "plan":        plan,
            "agency_logo": data.get("logo_url") if plan.allows_branding() else None,
        }
        html = render_report(vars, template="monthly_report.html")

        slug = re.sub(r"[^\w]", "_", data["agency_name"].lower()).strip("_")
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
        if preview:
            print(f"    [PDF] Preview mod — preskočeno.")
        elif plan.allows_pdf():
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


def _gather_agent_extras(agency_id: str, agent: dict, plan, use_mock: bool) -> dict:
    """Vraća per-agent dodatne podatke (history, listings, hot_zones, pricing_recs) zavisno od plana."""
    extras = {
        "history":             [],
        "listings_benchmark":  [],
        "hot_zones_for_agent": [],
        "pricing_recommendations": [],
    }

    if plan.id not in ("pro", "premium"):
        return extras

    weeks = 26 if plan.id == "pro" else 52
    agent_id = agent.get("id")

    if use_mock or not config.SUPABASE_KEY or not agent_id:
        from data.mock_data import (
            get_mock_agent_history,
            get_mock_agent_listings_benchmark,
            get_mock_agent_hot_zones,
            get_mock_agent_pricing_recommendations,
        )
        extras["history"]             = get_mock_agent_history(agent_id or "", weeks=weeks)
        extras["listings_benchmark"]  = get_mock_agent_listings_benchmark(agent_id or "")
        extras["hot_zones_for_agent"] = get_mock_agent_hot_zones(agent_id or "")
        if plan.id == "premium":
            extras["pricing_recommendations"] = get_mock_agent_pricing_recommendations(agent_id or "")
        return extras

    from data.supabase_client import (
        get_agent_history,
        get_agent_listings_with_benchmark,
        get_agent_hot_zones,
        compute_agent_pricing_recommendations,
    )
    extras["history"]             = get_agent_history(agent_id, weeks=weeks)
    extras["listings_benchmark"]  = get_agent_listings_with_benchmark(agency_id, agent_id)
    extras["hot_zones_for_agent"] = get_agent_hot_zones(agency_id, agent_id)
    if plan.id == "premium":
        extras["pricing_recommendations"] = compute_agent_pricing_recommendations(agency_id, agent_id)
    return extras


def run_agent_reports(preview: bool = False, use_mock: bool = False, plan_override: str | None = None):
    if use_mock or not config.SUPABASE_KEY:
        from data.mock_data import get_mock_report_data
        mock_plan = plan_override or "pro"
        clients_data = [("mock", get_mock_report_data(plan_id=mock_plan))]
    else:
        from data.supabase_client import get_all_active_clients, get_report_data
        clients_raw  = get_all_active_clients()
        clients_data = [(c["id"], get_report_data(c["id"])) for c in clients_raw]

    for agency_id, data in clients_data:
        plan = get_plan(data.get("plan_id", "basic"))
        if not plan.allows_agent_reports():
            print(f"\n[skip] {data['agency_name']} — agent izveštaji nisu dostupni na {plan.name} planu.")
            continue

        agents = data["agents"]
        agents_sorted = sorted(agents, key=lambda a: a["contracts"] / max(a["inquiries"], 1), reverse=True)
        team_inquiries = sum(a["inquiries"] for a in agents)
        team_contracts = sum(a["contracts"] for a in agents)
        team_conv      = round(team_contracts / max(team_inquiries, 1) * 100, 1)

        print(f"\n[→] Agent izveštaji: {data['agency_name']}  ({data['week_start']} – {data['week_end']})  [{plan.name}]")

        # ISO week_start za Supabase (DD.MM.YYYY → YYYY-MM-DD)
        try:
            from datetime import datetime
            week_start_iso = datetime.strptime(data["week_start"], "%d.%m.%Y").strftime("%Y-%m-%d")
        except Exception:
            week_start_iso = data["week_start"]

        for rank, agent in enumerate(agents_sorted, start=1):
            agent_id   = agent.get("id")
            agent_conv = round(agent["contracts"] / max(agent["inquiries"], 1) * 100, 1)

            extras = _gather_agent_extras(agency_id, agent, plan, use_mock=use_mock)

            ai_analysis = None
            if plan.id == "premium":
                try:
                    if config.ANTHROPIC_API_KEY:
                        ai_analysis = generate_agent_analysis(
                            agent=agent,
                            team_conversion=team_conv,
                            team_size=len(agents_sorted),
                            agent_rank=rank,
                            agent_listings_benchmark=extras["listings_benchmark"],
                            agent_pricing_recs=extras["pricing_recommendations"],
                            history=extras["history"],
                        )
                    else:
                        raise RuntimeError("nema ANTHROPIC_API_KEY")
                except Exception as e:
                    print(f"    [warn] AI analiza pala za {agent['name']}: {e} — koristim fallback")
                    ai_analysis = generate_agent_analysis_fallback(
                        agent=agent,
                        team_conversion=team_conv,
                        team_size=len(agents_sorted),
                        agent_rank=rank,
                        agent_listings_benchmark=extras["listings_benchmark"],
                        agent_pricing_recs=extras["pricing_recommendations"],
                        history=extras["history"],
                    )

            history      = extras["history"]
            trend_points = _build_trend_chart_points(history, y_field="conversion") if len(history) >= 4 else []

            report_vars = {
                **data,
                "plan":             plan,
                "agent_name":       agent["name"],
                "agent_conversion": agent_conv,
                "agent_inquiries":  agent["inquiries"],
                "agent_contracts":  agent["contracts"],
                "agent_rank":       rank,
                "team_size":        len(agents_sorted),
                "team_conversion":  team_conv,
                "agency_logo":      data.get("logo_url") if plan.allows_branding() else None,
                "agent_history":          history,
                "trend_chart_points":     trend_points,
                "listings_benchmark":     extras["listings_benchmark"],
                "hot_zones":              extras["hot_zones_for_agent"],
                "ai_analysis":            ai_analysis,
                "pricing_recommendations": extras["pricing_recommendations"],
            }

            html = render_report(report_vars, template="agent_report.html")

            # Čuvamo HTML u Supabase (pristup kroz web app → Agenti tab)
            if not use_mock and config.SUPABASE_KEY and agent_id:
                try:
                    from data.supabase_client import save_agent_report_html
                    saved = save_agent_report_html(agency_id, agent_id, week_start_iso, html)
                    if not saved:
                        print(f"    [warn] Supabase save nije uspeo za {agent['name']}")
                except Exception as e:
                    print(f"    [warn] Supabase save pao za {agent['name']}: {e}")

            # PDF za Premium (opt-in email ili preview)
            pdf_bytes    = None
            pdf_filename = None
            if plan.id == "premium":
                try:
                    from pdf.generator import generate_pdf
                    pdf_bytes    = generate_pdf(html)
                    slug         = re.sub(r"[^a-z0-9]+", "_", agent["name"].lower()).strip("_")
                    pdf_filename = f"izvestaj_{slug}_{week_start_iso}.pdf"
                except Exception as e:
                    print(f"    [warn] PDF generisanje palo za {agent['name']}: {e}")

            if preview:
                slug = re.sub(r"[^a-z0-9]+", "_", agent["name"].lower()).strip("_")
                out  = Path(__file__).parent / f"agent_{slug}.html"
                out.write_text(html, encoding="utf-8")
                print(f"    [preview] {agent['name']} → {out.name}"
                      + (f"  (+ PDF {len(pdf_bytes)} B)" if pdf_bytes else ""))
                if pdf_bytes and pdf_filename:
                    (Path(__file__).parent / pdf_filename).write_bytes(pdf_bytes)
            else:
                # Bulk email — samo ako agent ima email (opt-in, vlasnik može pozvati i ručno)
                if agent.get("email"):
                    subject = f"Nedeljni izveštaj agencije — {data['week_start']}"
                    send_report_email(
                        to_email=agent["email"],
                        to_name=agent["name"],
                        subject=subject,
                        html_body=html,
                        pdf_bytes=pdf_bytes,
                        pdf_filename=pdf_filename or "izvestaj.pdf",
                    )
                    print(f"    [email] {agent['name']} ({agent['email']})"
                          + (" + PDF" if pdf_bytes else ""))
                else:
                    print(f"    [saved] {agent['name']} — sačuvan u Supabase (nema email)")

    print("\n[✓] Agent izveštaji gotovi.")


def run_daily_brief(preview: bool = False) -> None:
    """
    Šalje jutarnji brief vlasniku agencije (7:30 svako jutro).
    Sadrži: pending lead-ovi, response time po agentu, ukupni stats.
    """
    if not config.SUPABASE_KEY:
        print("[!] SUPABASE_KEY nije podešen — daily brief nije dostupan bez baze.")
        return

    from datetime import date as _date
    from data.leads_client import get_brief_data
    from data.supabase_client import get_all_active_clients

    clients = get_all_active_clients()
    if not clients:
        print("[Daily Brief] Nema aktivnih klijenata.")
        return

    template_dir = Path(__file__).parent / "templates"
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    env.globals["support_email"] = config.SUPPORT_EMAIL
    tpl = env.get_template("daily_brief.html")

    d = _date.today()
    today_label = f"{d.day}. {d.month}. {d.year}."

    for client in clients:
        plan = get_plan(client.get("plan_id", "basic"))
        if not plan.allows_lead_rescue():
            continue

        agency_id = client["id"]
        agency_name = client.get("name", "Agencija")
        agency_email = client.get("email", "")
        sla_min = client.get("sla_minutes") or 15

        print(f"\n[Daily Brief] {agency_name}")

        try:
            brief = get_brief_data(agency_id, sla_minutes=sla_min)
        except Exception as e:
            print(f"    [!] Greška pri učitavanju podataka: {e}")
            continue

        dashboard_url = getattr(config, "APP_BASE_URL", "https://app.izvestaj.com") + "/leads"

        html = tpl.render(
            agency_name=agency_name,
            today_label=today_label,
            dashboard_url=dashboard_url,
            **brief,
        )

        slug = re.sub(r"[^\w]", "_", agency_name.lower()).strip("_")
        out = Path(__file__).parent / f"brief_{slug}.html"
        out.write_text(html, encoding="utf-8")
        print(f"    [HTML] {out.name}")

        if not preview and agency_email:
            pending = brief.get("pending_count", 0)
            avg = brief.get("avg_response_min")
            avg_str = f"{avg}min" if avg else "—"
            subject = f"☀️ Jutarnji brief — {pending} lead-ova čeka · prosek {avg_str}"
            send_report_email(
                to_email=agency_email,
                to_name=agency_name,
                subject=subject,
                html_body=html,
            )
            print(f"    [EMAIL] Poslat na {agency_email}")
        else:
            print("    [EMAIL] Preview mod — mejl nije poslat.")

    print("\n[✓] Daily brief gotov.")




def run_stale_nudge(preview: bool = False) -> None:
    """
    Detektuje stale oglase (60+ dana) i šalje agentu email sa
    predlogom poruke za prodavca + WA linkom.
    """
    if not config.SUPABASE_KEY:
        print("[!] SUPABASE_KEY nije podešen.")
        return

    from data.supabase_client import get_all_active_clients, get_client
    from stale_listings.detector import enrich_with_benchmark, get_stale_listings
    from stale_listings.nudge import send_nudge_email

    clients = get_all_active_clients()
    for client in clients:
        plan = get_plan(client.get("plan_id", "basic"))
        if not plan.allows_stale_nudge():
            continue

        agency_id   = client["id"]
        agency_name = client.get("name", "Agencija")
        stale_days  = 60

        print(f"\n[StaleNudge] {agency_name}")
        stale = get_stale_listings(agency_id, stale_days=stale_days)
        if not stale:
            print(f"    Nema oglasa starijih od {stale_days} dana.")
            continue

        enriched = enrich_with_benchmark(stale, agency_id)
        print(f"    {len(enriched)} stale oglasa ({sum(1 for x in enriched if x['overpriced'])} precenjeno)")

        # Grupiši po agentu
        by_agent: dict[str, list[dict]] = {}
        unassigned: list[dict] = []
        for lst in enriched:
            agent_data = lst.get("agents") or {}
            agent_email = agent_data.get("email")
            if agent_email:
                by_agent.setdefault(agent_email, {"name": agent_data.get("name", ""), "items": []})
                by_agent[agent_email]["items"].append(lst)
            else:
                unassigned.append(lst)

        # Pošalji svakom agentu njegova stale
        for agent_email, info in by_agent.items():
            if preview:
                print(f"    [preview] {info['name']} ({agent_email}) — {len(info['items'])} oglasa")
                continue
            ok = send_nudge_email(
                agent_email=agent_email,
                agent_name=info["name"],
                agency_name=agency_name,
                listings=info["items"],
            )
            status = "poslat" if ok else "greška"
            print(f"    [{status}] {info['name']} ({agent_email}) — {len(info['items'])} oglasa")

        # Nezasignrani oglasi → šalji vlasniku
        if unassigned:
            owner_email = client.get("escalation_email") or client.get("email")
            if owner_email and not preview:
                send_nudge_email(
                    agent_email=owner_email,
                    agent_name=agency_name,
                    agency_name=agency_name,
                    listings=unassigned,
                )
                print(f"    [vlasnik] {len(unassigned)} oglasa bez agenta → {owner_email}")

    print("\n[✓] Stale nudge gotov.")


def run_lead_rescue(dry_run: bool = False) -> None:
    """Fetch inbox + dodela + SLA provera — kompletan ciklus."""
    if not config.SUPABASE_KEY:
        print("[!] SUPABASE_KEY nije podešen — lead rescue nije dostupan bez baze.")
        return
    from lead_rescue.sla_engine import run_full_cycle
    run_full_cycle(dry_run=dry_run)


def run_check_sla() -> None:
    """Samo SLA provera (eskalacija) — pokreće se svaki minut via cron."""
    if not config.SUPABASE_KEY:
        print("[!] SUPABASE_KEY nije podešen.")
        return
    from lead_rescue.sla_engine import check_sla_breaches
    print("\n[SLA Check]")
    s = check_sla_breaches()
    print(f"  Eskalirano: {s['escalated']}, Preraspoređeno: {s['reassigned']}, Greške: {s['errors']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview",       action="store_true", help="Ne šalji mejl")
    parser.add_argument("--mock",          action="store_true", help="Koristi mock podatke")
    parser.add_argument("--monthly",       action="store_true", help="Mesečni izveštaj umesto nedeljnog")
    parser.add_argument("--agent-reports", action="store_true", help="Pošalji personalne izveštaje agentima")
    parser.add_argument("--daily-brief",    action="store_true", help="Pošalji jutarnji brief svim vlasnicima (07:30)")
    parser.add_argument("--stale-nudge",    action="store_true", help="Detektuj stale oglase i pošalji agentu WA predlog za prodavca")
    parser.add_argument("--lead-rescue",   action="store_true", help="Fetch inbox + dodeli agentima + SLA provera")
    parser.add_argument("--check-sla",     action="store_true", help="Samo SLA provera (pokreće se svakih 60s)")
    parser.add_argument("--dry-run",       action="store_true", help="Simulacija bez pisanja u bazu")
    parser.add_argument("--plan",          default=None,        help="Override plan_id za mock testiranje (basic/pro/premium)")
    parser.add_argument("--city",          default="beograd",   help="Grad za tržišnu analizu")
    args = parser.parse_args()

    if args.monthly:
        run_monthly(preview=args.preview, use_mock=args.mock)
    elif args.agent_reports:
        run_agent_reports(preview=args.preview, use_mock=args.mock, plan_override=args.plan)
    elif args.daily_brief:
        run_daily_brief(preview=args.preview)
    elif args.stale_nudge:
        run_stale_nudge(preview=args.preview)
    elif args.lead_rescue:
        run_lead_rescue(dry_run=args.dry_run)
    elif args.check_sla:
        run_check_sla()
    else:
        run(preview=args.preview, use_mock=args.mock, city=args.city)
