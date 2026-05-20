"""
Supabase operacije za Lead Rescue Engine.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from data.supabase_client import get_client


def get_agencies_with_imap() -> list[dict]:
    """Vraća sve aktivne agencije koje imaju konfigurisan IMAP inbox."""
    sb = get_client()
    res = (
        sb.table("agencies")
        .select("id, name, email, escalation_email, sla_minutes, imap_host, imap_port, imap_user, imap_pass, imap_folder, plan_id")
        .eq("active", True)
        .not_.is_("imap_host", "null")
        .not_.is_("imap_user", "null")
        .execute()
    )
    return res.data or []


def lead_exists(agency_id: str, external_message_id: str) -> bool:
    """Proverava duplikat po external_message_id."""
    sb = get_client()
    res = (
        sb.table("leads")
        .select("id")
        .eq("agency_id", agency_id)
        .eq("external_message_id", external_message_id)
        .limit(1)
        .execute()
    )
    return len(res.data) > 0


def create_lead(agency_id: str, lead_data: dict) -> Optional[dict]:
    """Kreira novi lead zapis. Vraća kreiran red ili None."""
    sb = get_client()
    payload = {
        "agency_id":           agency_id,
        "source":              lead_data["source"],
        "external_message_id": lead_data.get("external_message_id"),
        "buyer_name":          lead_data.get("buyer_name"),
        "buyer_phone":         lead_data.get("buyer_phone"),
        "buyer_email":         lead_data.get("buyer_email"),
        "message":             lead_data.get("message"),
        "listing_title":       lead_data.get("listing_title"),
        "listing_url":         lead_data.get("listing_url"),
        "status":              "new",
        "is_mystery_shopper":  lead_data.get("is_mystery_shopper", False),
        "received_at":         (
            lead_data["received_at"].isoformat()
            if lead_data.get("received_at")
            else datetime.now(timezone.utc).isoformat()
        ),
    }
    res = sb.table("leads").insert(payload).execute()
    return res.data[0] if res.data else None


def get_unassigned_leads(agency_id: str) -> list[dict]:
    """Lead-ovi koji još nisu dodeljeni agentu."""
    sb = get_client()
    res = (
        sb.table("leads")
        .select("*")
        .eq("agency_id", agency_id)
        .eq("status", "new")
        .order("received_at", desc=False)
        .execute()
    )
    return res.data or []


def get_assigned_leads_past_sla(agency_id: str) -> list[dict]:
    """Lead-ovi kojima je prošao SLA rok a još nisu odgovoreni."""
    now_iso = datetime.now(timezone.utc).isoformat()
    sb = get_client()
    res = (
        sb.table("leads")
        .select("*, agents(id, name, email, phone)")
        .eq("agency_id", agency_id)
        .eq("status", "assigned")
        .lt("sla_deadline", now_iso)
        .execute()
    )
    return res.data or []


def get_active_agents(agency_id: str) -> list[dict]:
    """Aktivni agenti agencije, sortirani po broju dodeljenih lead-ova (round-robin)."""
    sb = get_client()
    res = (
        sb.table("agents")
        .select("id, name, email, phone, lead_assignments")
        .eq("agency_id", agency_id)
        .eq("active", True)
        .order("lead_assignments", desc=False)
        .execute()
    )
    return res.data or []


def assign_lead(lead_id: str, agent_id: str, sla_minutes: int) -> bool:
    """Dodeljuje lead agentu i pokreće SLA tajmer."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=sla_minutes)
    sb = get_client()

    res = (
        sb.table("leads")
        .update({
            "assigned_agent_id": agent_id,
            "status":            "assigned",
            "assigned_at":       now.isoformat(),
            "sla_deadline":      deadline.isoformat(),
        })
        .eq("id", lead_id)
        .execute()
    )

    # Povećaj lead_assignments agentu
    sb.rpc("increment_lead_assignments", {"agent_id": agent_id}).execute()

    return bool(res.data)


def mark_lead_responded(lead_id: str) -> bool:
    """Označava lead kao odgovoren i računa response_time_minutes."""
    sb = get_client()

    lead_res = sb.table("leads").select("assigned_at").eq("id", lead_id).single().execute()
    if not lead_res.data:
        return False

    now = datetime.now(timezone.utc)
    response_time: Optional[int] = None
    assigned_at_str = lead_res.data.get("assigned_at")
    if assigned_at_str:
        try:
            assigned_at = datetime.fromisoformat(assigned_at_str.replace("Z", "+00:00"))
            response_time = int((now - assigned_at).total_seconds() / 60)
        except Exception:
            pass

    res = (
        sb.table("leads")
        .update({
            "status":                "responded",
            "responded_at":          now.isoformat(),
            "response_time_minutes": response_time,
        })
        .eq("id", lead_id)
        .execute()
    )
    return bool(res.data)


def escalate_lead(lead_id: str) -> bool:
    """Označava lead kao eskaliran vlasniku."""
    sb = get_client()
    res = (
        sb.table("leads")
        .update({
            "status":       "escalated",
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", lead_id)
        .execute()
    )
    return bool(res.data)


def reassign_lead(lead_id: str, new_agent_id: str, sla_minutes: int) -> bool:
    """Preraspoređuje eskaliran lead na drugog agenta."""
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=sla_minutes)
    sb = get_client()
    res = (
        sb.table("leads")
        .update({
            "assigned_agent_id": new_agent_id,
            "status":            "assigned",
            "assigned_at":       now.isoformat(),
            "sla_deadline":      deadline.isoformat(),
            "escalated_at":      None,
        })
        .eq("id", lead_id)
        .execute()
    )
    sb.rpc("increment_lead_assignments", {"agent_id": new_agent_id}).execute()
    return bool(res.data)


def log_event(lead_id: str, event_type: str, actor: str = "system", note: str = "") -> None:
    """Beleži događaj u audit log."""
    try:
        sb = get_client()
        sb.table("lead_events").insert({
            "lead_id":    lead_id,
            "event_type": event_type,
            "actor":      actor,
            "note":       note,
        }).execute()
    except Exception as e:
        print(f"    [warn] log_event failed: {e}")


def get_brief_data(agency_id: str, sla_minutes: int = 15) -> dict:
    """
    Skuplja sve podatke potrebne za jutarnji brief:
    - pending/escalated lead-ovi sa agent info
    - response time statistika po agentu (7 dana)
    - ukupni stats (7 dana)
    """
    from lead_rescue.whatsapp_links import generate_agent_wa_link

    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    sb = get_client()

    # Otvoreni lead-ovi (new + assigned + escalated)
    open_res = (
        sb.table("leads")
        .select("*, agents(id, name, email, phone)")
        .eq("agency_id", agency_id)
        .in_("status", ["new", "assigned", "escalated"])
        .order("received_at", desc=False)
        .execute()
    )
    open_leads = open_res.data or []

    source_labels = {
        "halo_oglasi": "Halo Oglasi",
        "4zida": "4Zida",
        "nekretnine_rs": "Nekretnine.rs",
        "web": "Web",
    }

    pending_leads = []
    for lead in open_leads:
        agent_data = lead.get("agents") or {}
        agent_name = agent_data.get("name") or "—"
        agent_phone = agent_data.get("phone") or ""

        # Koliko dugo čeka
        received_str = lead.get("received_at") or lead.get("created_at")
        waiting_label = "—"
        if received_str:
            try:
                received_at = datetime.fromisoformat(received_str.replace("Z", "+00:00"))
                mins = int((now - received_at).total_seconds() / 60)
                if mins < 60:
                    waiting_label = f"{mins}min"
                else:
                    waiting_label = f"{mins // 60}h {mins % 60}min"
            except Exception:
                pass

        # WA link za agenta da kontaktira kupca
        wa_link = ""
        if lead.get("buyer_phone") and agent_name != "—":
            wa_link = generate_agent_wa_link(
                buyer_phone=lead["buyer_phone"],
                buyer_name=lead.get("buyer_name") or "",
                listing_title=lead.get("listing_title") or "",
                agent_name=agent_name,
            )

        pending_leads.append({
            "id":           lead["id"],
            "buyer_name":   lead.get("buyer_name") or "Nepoznat kupac",
            "buyer_phone":  lead.get("buyer_phone"),
            "listing_title": lead.get("listing_title"),
            "source_label": source_labels.get(lead.get("source", ""), lead.get("source", "")),
            "agent_name":   agent_name,
            "waiting_label": waiting_label,
            "is_escalated": lead.get("status") == "escalated",
            "wa_link":      wa_link,
        })

    # Response time po agentu (poslednih 7 dana, samo responded)
    responded_res = (
        sb.table("leads")
        .select("assigned_agent_id, response_time_minutes, agents(name)")
        .eq("agency_id", agency_id)
        .eq("status", "responded")
        .gte("responded_at", week_ago)
        .not_.is_("response_time_minutes", "null")
        .execute()
    )
    responded_rows = responded_res.data or []

    agent_times: dict[str, list[int]] = {}
    for row in responded_rows:
        agent_data = row.get("agents") or {}
        name = agent_data.get("name") or row.get("assigned_agent_id") or "?"
        t = row.get("response_time_minutes")
        if t is not None:
            agent_times.setdefault(name, []).append(t)

    # Maksimum za normalizaciju bara
    all_avgs = [round(sum(v) / len(v)) for v in agent_times.values() if v]
    max_avg = max(all_avgs) if all_avgs else 1

    agent_stats = sorted([
        {
            "name":    name,
            "avg_min": round(sum(times) / len(times)),
            "bar_pct": round(sum(times) / len(times) / max(max_avg, 1) * 100),
        }
        for name, times in agent_times.items()
    ], key=lambda x: x["avg_min"])

    # Ukupni stats (7 dana)
    stats = get_lead_stats(agency_id, days=7)

    return {
        "pending_leads":    pending_leads,
        "pending_count":    len(pending_leads),
        "agent_stats":      agent_stats,
        "avg_response_min": stats.get("avg_time_min"),
        "responded_7d":     stats.get("responded", 0),
    }


def get_lead_stats(agency_id: str, days: int = 30) -> dict:
    """Agregat za jutarnji brief — ukupno, odgovoreno, prosečno vreme."""
    from_dt = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sb = get_client()
    res = (
        sb.table("leads")
        .select("status, response_time_minutes, source")
        .eq("agency_id", agency_id)
        .gte("created_at", from_dt)
        .execute()
    )
    rows = res.data or []

    total = len(rows)
    responded = [r for r in rows if r["status"] == "responded"]
    times = [r["response_time_minutes"] for r in responded if r.get("response_time_minutes")]
    avg_time = round(sum(times) / len(times)) if times else None

    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    return {
        "total":          total,
        "responded":      len(responded),
        "avg_time_min":   avg_time,
        "by_status":      by_status,
    }
