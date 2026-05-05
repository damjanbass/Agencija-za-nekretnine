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
        .select("inquiries, contracts, agents(name)")
        .eq("agency_id", agency_id)
        .eq("week_start", ws)
        .order("inquiries", desc=True)
        .execute()
        .data
    )
    agents = [
        {
            "name":      row["agents"]["name"],
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


def save_report(agency_id: str, week_start: date, html: str):
    """Arhivira HTML izveštaj u bazu."""
    sb = get_client()
    sb.table("reports").upsert({
        "agency_id": agency_id,
        "week_start": week_start.isoformat(),
        "html":       html,
        "sent_at":    date.today().isoformat(),
    }, on_conflict="agency_id,week_start").execute()


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
