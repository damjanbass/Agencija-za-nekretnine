"""
SLA Engine — orkestrira celokupan lead rescue tok:
  1. fetch_and_store_leads()  — čita inbox, pravi lead zapise
  2. assign_new_leads()       — dodeljuje agentima (round-robin)
  3. check_sla_breaches()     — eskalira i/ili preraspoređuje
"""

import config
from data.leads_client import (
    assign_lead,
    create_lead,
    escalate_lead,
    get_active_agents,
    get_agencies_with_imap,
    get_assigned_leads_past_sla,
    get_unassigned_leads,
    lead_exists,
    log_event,
    reassign_lead,
)
from lead_rescue.escalation import send_agent_lead_alert, send_owner_escalation
from lead_rescue.inbox_parser import parse_portal_emails
from lead_rescue.whatsapp_links import generate_agent_wa_link


def _respond_url(lead_id: str) -> str:
    base = getattr(config, "APP_BASE_URL", "https://app.izvestaj.com")
    return f"{base}/lead-respond?id={lead_id}"


def fetch_and_store_leads(dry_run: bool = False) -> dict:
    """
    Prolazi kroz sve agencije sa IMAP-om, parsira nove email-ove
    i upisuje lead-ove u bazu. Vraća statistiku.
    """
    agencies = get_agencies_with_imap()
    stats = {"agencies": len(agencies), "new": 0, "skipped_dup": 0, "errors": 0}

    for agency in agencies:
        agency_id = agency["id"]
        sla_min = agency.get("sla_minutes") or 15

        print(f"    [IMAP] {agency['name']} — čitam inbox ({agency['imap_host']})...")
        try:
            parsed_leads = parse_portal_emails(
                imap_host=agency["imap_host"],
                imap_port=agency.get("imap_port") or 993,
                imap_user=agency["imap_user"],
                imap_pass=agency["imap_pass"],
                imap_folder=agency.get("imap_folder") or "INBOX",
                mark_seen=not dry_run,
            )
        except Exception as e:
            print(f"    [IMAP] Greška kod {agency['name']}: {e}")
            stats["errors"] += 1
            continue

        for pl in parsed_leads:
            ext_id = pl.external_message_id
            if ext_id and lead_exists(agency_id, ext_id):
                stats["skipped_dup"] += 1
                continue

            lead_data = {
                "source":              pl.source,
                "external_message_id": pl.external_message_id,
                "buyer_name":          pl.buyer_name,
                "buyer_phone":         pl.buyer_phone,
                "buyer_email":         pl.buyer_email,
                "message":             pl.message,
                "listing_title":       pl.listing_title,
                "listing_url":         pl.listing_url,
                "received_at":         pl.received_at,
            }

            if dry_run:
                print(f"        [dry] Lead: {pl.buyer_name} / {pl.buyer_phone} — {pl.listing_title}")
                stats["new"] += 1
                continue

            created = create_lead(agency_id, lead_data)
            if created:
                log_event(created["id"], "received", actor="system", note=pl.source)
                stats["new"] += 1
                print(f"        [+] {pl.buyer_name or '?'} / {pl.buyer_phone or '?'} — {pl.listing_title or pl.raw_subject}")
            else:
                stats["errors"] += 1

    return stats


def assign_new_leads(dry_run: bool = False) -> dict:
    """
    Dodeljuje agentima sve lead-ove sa statusom 'new' (round-robin).
    Šalje email alert agentu.
    """
    agencies = get_agencies_with_imap()
    stats = {"assigned": 0, "no_agents": 0, "errors": 0}

    for agency in agencies:
        agency_id = agency["id"]
        sla_min = agency.get("sla_minutes") or 15
        unassigned = get_unassigned_leads(agency_id)
        if not unassigned:
            continue

        agents = get_active_agents(agency_id)
        if not agents:
            print(f"    [SLA] {agency['name']} — nema aktivnih agenata!")
            stats["no_agents"] += len(unassigned)
            continue

        agent_idx = 0
        for lead in unassigned:
            agent = agents[agent_idx % len(agents)]
            agent_idx += 1

            lead_id = lead["id"]
            agent_id = agent["id"]
            agent_email = agent.get("email")
            agent_phone = agent.get("phone", "")

            # WhatsApp link za agenta
            wa_link = ""
            buyer_phone = lead.get("buyer_phone") or ""
            if buyer_phone:
                wa_link = generate_agent_wa_link(
                    buyer_phone=buyer_phone,
                    buyer_name=lead.get("buyer_name") or "",
                    listing_title=lead.get("listing_title") or "",
                    agent_name=agent["name"],
                )

            respond_url = _respond_url(lead_id)

            if dry_run:
                print(f"        [dry] Assign: {lead.get('buyer_name')} → {agent['name']} (SLA {sla_min}min)")
                stats["assigned"] += 1
                continue

            ok = assign_lead(lead_id, agent_id, sla_min)
            if ok:
                log_event(lead_id, "assigned", actor="system", note=agent["name"])
                stats["assigned"] += 1

                # Email alert agentu (samo ako ima email)
                if agent_email:
                    try:
                        send_agent_lead_alert(
                            agent_email=agent_email,
                            agent_name=agent["name"],
                            agency_name=agency["name"],
                            lead=lead,
                            wa_link=wa_link,
                            respond_url=respond_url,
                            sla_minutes=sla_min,
                        )
                        log_event(lead_id, "agent_notified", actor="system", note=agent_email)
                        print(f"        [→] {lead.get('buyer_name') or '?'} dodeljen {agent['name']} (alert poslat)")
                    except Exception as e:
                        print(f"        [warn] Email agentu {agent['name']} pao: {e}")
                else:
                    print(f"        [→] {lead.get('buyer_name') or '?'} dodeljen {agent['name']} (nema email)")
            else:
                stats["errors"] += 1

    return stats


def check_sla_breaches(dry_run: bool = False) -> dict:
    """
    Proverava sve 'assigned' lead-ove kojima je prošao SLA rok.
    Eskalira vlasniku i preraspoređuje na sledećeg agenta.
    """
    from datetime import datetime, timezone

    agencies = get_agencies_with_imap()
    stats = {"escalated": 0, "reassigned": 0, "errors": 0}

    for agency in agencies:
        agency_id = agency["id"]
        sla_min = agency.get("sla_minutes") or 15
        owner_email = agency.get("escalation_email") or agency.get("email")
        owner_name = agency["name"]

        breached = get_assigned_leads_past_sla(agency_id)
        if not breached:
            continue

        agents = get_active_agents(agency_id)

        for lead in breached:
            lead_id = lead["id"]
            agent_data = lead.get("agents") or {}
            agent_name = agent_data.get("name") or "nepoznat agent"

            # Koliko minuta je prošlo od dodele
            elapsed_min = sla_min
            assigned_at_str = lead.get("assigned_at")
            if assigned_at_str:
                try:
                    assigned_at = datetime.fromisoformat(assigned_at_str.replace("Z", "+00:00"))
                    elapsed_min = int((datetime.now(timezone.utc) - assigned_at).total_seconds() / 60)
                except Exception:
                    pass

            # Nađi sledećeg agenta (ne istog koji je kasnio)
            current_agent_id = lead.get("assigned_agent_id")
            next_agent = next(
                (a for a in agents if a["id"] != current_agent_id),
                None,
            )
            reassigned_name = next_agent["name"] if next_agent else None

            if dry_run:
                print(f"        [dry] SLA breach: {lead.get('buyer_name')} @ {agent_name} (+{elapsed_min}min)"
                      + (f" → preraspoređujem na {reassigned_name}" if reassigned_name else ""))
                stats["escalated"] += 1
                continue

            # Eskalacija u DB
            escalate_lead(lead_id)
            log_event(lead_id, "escalated", actor="system",
                      note=f"SLA prekoračen za {elapsed_min}min by {agent_name}")
            stats["escalated"] += 1

            # Preraspoređivanje
            if next_agent:
                reassign_lead(lead_id, next_agent["id"], sla_min)
                log_event(lead_id, "reassigned", actor="system", note=next_agent["name"])
                stats["reassigned"] += 1

                # Pošalji alert novom agentu
                if next_agent.get("email"):
                    wa_link = ""
                    if lead.get("buyer_phone"):
                        wa_link = generate_agent_wa_link(
                            buyer_phone=lead["buyer_phone"],
                            buyer_name=lead.get("buyer_name") or "",
                            listing_title=lead.get("listing_title") or "",
                            agent_name=next_agent["name"],
                        )
                    try:
                        send_agent_lead_alert(
                            agent_email=next_agent["email"],
                            agent_name=next_agent["name"],
                            agency_name=agency["name"],
                            lead=lead,
                            wa_link=wa_link,
                            respond_url=_respond_url(lead_id),
                            sla_minutes=sla_min,
                        )
                    except Exception as e:
                        print(f"        [warn] Reassign email pao za {next_agent['name']}: {e}")

            # Alert vlasniku
            if owner_email:
                try:
                    send_owner_escalation(
                        owner_email=owner_email,
                        owner_name=owner_name,
                        agency_name=agency["name"],
                        lead=lead,
                        agent_name=agent_name,
                        elapsed_min=elapsed_min,
                        reassigned_to=reassigned_name,
                    )
                    log_event(lead_id, "owner_alerted", actor="system", note=owner_email)
                    print(f"        [!] Eskalacija: {lead.get('buyer_name')} / {agent_name} → owner alert poslat")
                except Exception as e:
                    print(f"        [warn] Owner alert pao: {e}")
            else:
                print(f"        [!] Eskalacija: {lead.get('buyer_name')} / {agent_name} — nema owner email!")

    return stats


def run_full_cycle(dry_run: bool = False) -> None:
    """Pokreće sve tri faze redom: fetch → assign → SLA check."""
    print("\n[Lead Rescue] === Fetch inbox ===")
    s1 = fetch_and_store_leads(dry_run=dry_run)
    print(f"    Novi: {s1['new']}, Duplikati: {s1['skipped_dup']}, Greške: {s1['errors']}")

    print("\n[Lead Rescue] === Dodela agentima ===")
    s2 = assign_new_leads(dry_run=dry_run)
    print(f"    Dodeljeno: {s2['assigned']}, Bez agenata: {s2['no_agents']}, Greške: {s2['errors']}")

    print("\n[Lead Rescue] === SLA provera ===")
    s3 = check_sla_breaches(dry_run=dry_run)
    print(f"    Eskalirano: {s3['escalated']}, Preraspoređeno: {s3['reassigned']}, Greške: {s3['errors']}")

    print("\n[Lead Rescue] === Gotovo ===")
