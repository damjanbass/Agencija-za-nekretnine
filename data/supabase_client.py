from datetime import date, timedelta
from supabase import create_client, Client
import config


def get_client() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


def get_report_data(agency_id: str) -> dict:
    """
    Vuče sve podatke za nedeljni izveštaj iz Supabase.
    agency_id je UUID iz tabele agencies.
    Prikazuje prošlu nedelju (ponedeljak–nedelja).
    """
    sb = get_client()

    today = date.today()
    # Prošla nedelja: ponedeljak
    week_start = (today - timedelta(days=today.weekday() + 7))
    week_end   = week_start + timedelta(days=6)
    prev_week  = week_start - timedelta(days=7)

    ws  = week_start.isoformat()
    pws = prev_week.isoformat()

    # --- Agencija ---
    agency = (
        sb.table("agencies")
        .select("name, email, revenue_goal, plan_id")
        .eq("id", agency_id)
        .single()
        .execute()
        .data
    )

    # --- Ovonedeljni KPI ---
    kpi = (
        sb.table("weekly_kpis")
        .select("*")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .single()
        .execute()
        .data
    )

    # --- Prošlonedeljni KPI (za % upiti) ---
    prev_kpi = (
        sb.table("weekly_kpis")
        .select("inquiries")
        .eq("agency_id", agency_id)
        .eq("week_start", pws)
        .maybe_single()
        .execute()
        .data
    )

    # --- Upiti po izvoru ---
    sources_raw = (
        sb.table("inquiry_sources")
        .select("source, count")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .order("count", desc=True)
        .execute()
        .data
    )
    inquiries_by_source = {row["source"]: row["count"] for row in sources_raw}

    # --- Agenti + performanse ---
    perf_raw = (
        sb.table("agent_performance")
        .select("inquiries, contracts, agents(name, email)")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .order("inquiries", desc=True)
        .execute()
        .data
    )
    agents = [
        {
            "name":      row["agents"]["name"],
            "email":     row["agents"].get("email") or "",
            "inquiries": row["inquiries"],
            "contracts": row["contracts"],
        }
        for row in perf_raw
    ]

    return {
        "agency_name":            agency["name"],
        "agency_email":           agency["email"],
        "plan_id":                agency.get("plan_id", "free"),
        "week_start":             week_start.strftime("%d.%m.%Y"),
        "week_end":               week_end.strftime("%d.%m.%Y"),
        "generated_at":           today.strftime("%d.%m.%Y"),
        "active_listings":        kpi["active_listings"],
        "new_listings_this_week": kpi["new_listings"],
        "inquiries":              kpi["inquiries"],
        "prev_inquiries":         prev_kpi["inquiries"] if prev_kpi else kpi["inquiries"],
        "contracts_sale":         kpi["contracts_sale"],
        "contracts_rent":         kpi["contracts_rent"],
        "revenue":                int(kpi["revenue"]),
        "revenue_goal":           int(agency["revenue_goal"]),
        "inquiries_by_source":    inquiries_by_source,
        "agents":                 agents,
    }


def save_report(agency_id: str, week_start: date, html: str, report_type: str = "weekly"):
    """Arhivira HTML izveštaj u bazu."""
    sb = get_client()
    sb.table("reports").upsert({
        "agency_id":   agency_id,
        "week_start":  week_start.isoformat(),
        "html":        html,
        "sent_at":     date.today().isoformat(),
        "report_type": report_type,
    }, on_conflict="agency_id,week_start").execute()


def get_monthly_report_data(agency_id: str) -> dict:
    """Agregira sve nedeljne KPI-eve za prošli mesec."""
    sb = get_client()

    today = date.today()
    month_end   = today.replace(day=1) - timedelta(days=1)
    month_start = month_end.replace(day=1)

    agency = (
        sb.table("agencies")
        .select("name, email, revenue_goal, plan_id")
        .eq("id", agency_id)
        .single()
        .execute()
        .data
    )

    weeks_raw = (
        sb.table("weekly_kpis")
        .select("*")
        .eq("agency_id", agency_id)
        .gte("week_start", month_start.isoformat())
        .lte("week_start", month_end.isoformat())
        .order("week_start")
        .execute()
        .data
    )

    sources_raw = (
        sb.table("inquiry_sources")
        .select("source, count")
        .eq("agency_id", agency_id)
        .gte("week_start", month_start.isoformat())
        .lte("week_start", month_end.isoformat())
        .execute()
        .data
    )
    sources: dict = {}
    for row in sources_raw:
        sources[row["source"]] = sources.get(row["source"], 0) + row["count"]

    perf_raw = (
        sb.table("agent_performance")
        .select("inquiries, contracts, agents(name)")
        .eq("agency_id", agency_id)
        .gte("week_start", month_start.isoformat())
        .lte("week_start", month_end.isoformat())
        .execute()
        .data
    )
    agents: dict = {}
    for row in perf_raw:
        name = row["agents"]["name"]
        if name not in agents:
            agents[name] = {"name": name, "inquiries": 0, "contracts": 0}
        agents[name]["inquiries"] += row["inquiries"]
        agents[name]["contracts"] += row["contracts"]
    agents_list = sorted(agents.values(), key=lambda a: a["contracts"], reverse=True)

    # Prethodni mesec prihod (za poređenje)
    prev_end   = month_start - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    prev_weeks = (
        sb.table("weekly_kpis")
        .select("revenue")
        .eq("agency_id", agency_id)
        .gte("week_start", prev_start.isoformat())
        .lte("week_start", prev_end.isoformat())
        .execute()
        .data
    )
    prev_revenue = sum(w["revenue"] for w in prev_weeks)

    total_inquiries     = sum(w["inquiries"]      for w in weeks_raw)
    total_contracts_sale = sum(w["contracts_sale"] for w in weeks_raw)
    total_contracts_rent = sum(w["contracts_rent"] for w in weeks_raw)
    total_revenue       = sum(w["revenue"]         for w in weeks_raw)
    monthly_goal        = int(agency["revenue_goal"]) * len(weeks_raw) if weeks_raw else int(agency["revenue_goal"]) * 4

    best_week = max(weeks_raw, key=lambda w: w["contracts_sale"] + w["contracts_rent"]) if weeks_raw else None

    MONTHS_SR = ["", "januar", "februar", "mart", "april", "maj", "jun",
                 "jul", "avgust", "septembar", "oktobar", "novembar", "decembar"]

    return {
        "agency_name":          agency["name"],
        "agency_email":         agency["email"],
        "plan_id":              agency.get("plan_id", "free"),
        "month_name":           f"{MONTHS_SR[month_start.month]} {month_start.year}",
        "month_start":          month_start.strftime("%d.%m.%Y"),
        "month_end":            month_end.strftime("%d.%m.%Y"),
        "generated_at":         today.strftime("%d.%m.%Y"),
        "total_inquiries":      total_inquiries,
        "total_contracts_sale": total_contracts_sale,
        "total_contracts_rent": total_contracts_rent,
        "total_contracts":      total_contracts_sale + total_contracts_rent,
        "total_revenue":        int(total_revenue),
        "monthly_goal":         monthly_goal,
        "revenue_pct":          round((total_revenue / (monthly_goal or 1)) * 100),
        "prev_revenue":         int(prev_revenue),
        "revenue_change_pct":   round(((total_revenue - prev_revenue) / (prev_revenue or 1)) * 100),
        "weeks_count":          len(weeks_raw),
        "weekly_breakdown":     weeks_raw,
        "best_week":            best_week,
        "inquiries_by_source":  sources,
        "agents":               agents_list,
    }


def get_benchmark_data(week_start_iso: str) -> dict | None:
    """Vraća agregirane proseke svih agencija za datu nedelju."""
    sb = get_client()
    try:
        rows = (
            sb.table("weekly_kpis")
            .select("inquiries, contracts_sale, contracts_rent, revenue")
            .eq("week_start", week_start_iso)
            .execute()
            .data
        )
        if not rows or len(rows) < 2:
            return None
        convs = [
            (r["contracts_sale"] + r["contracts_rent"]) / max(r["inquiries"], 1) * 100
            for r in rows
        ]
        return {
            "avg_conversion": round(sum(convs) / len(convs), 1),
            "avg_revenue":    round(sum(r["revenue"] for r in rows) / len(rows)),
            "avg_inquiries":  round(sum(r["inquiries"] for r in rows) / len(rows)),
            "agency_count":   len(rows),
        }
    except Exception:
        return None


def get_all_active_clients() -> list[dict]:
    """Vraća sve aktivne agencije sa UUID-ovima i planovima."""
    sb = get_client()
    return (
        sb.table("agencies")
        .select("id, name, email, plan_id")
        .eq("active", True)
        .execute()
        .data
    )
