"""
Šalje email alertove pri SLA kršenju.
Koristi postojeću mailer/sender.py infrastrukturu.
"""

from mailer.sender import send_report_email


def _source_label(source: str) -> str:
    return {
        "halo_oglasi":  "Halo Oglasi",
        "4zida":        "4Zida",
        "nekretnine_rs": "Nekretnine.rs",
    }.get(source, source.replace("_", " ").title())


def _minutes_label(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes} min"
    h = minutes // 60
    m = minutes % 60
    return f"{h}h {m}min" if m else f"{h}h"


def send_agent_lead_alert(
    agent_email:   str,
    agent_name:    str,
    agency_name:   str,
    lead:          dict,
    wa_link:       str,
    respond_url:   str,
    sla_minutes:   int = 15,
) -> bool:
    """
    Šalje agentu email sa detaljem lead-a, WA linkom i dugmetom za potvrdu.
    """
    buyer = lead.get("buyer_name") or "Nepoznat kupac"
    listing = lead.get("listing_title") or "—"
    phone = lead.get("buyer_phone") or "—"
    message = lead.get("message") or "—"
    source = _source_label(lead.get("source", ""))

    html = f"""<!DOCTYPE html>
<html lang="sr">
<head><meta charset="UTF-8">
<style>
  body {{ font-family: system-ui, sans-serif; background:#f4f6f9; margin:0; padding:24px; }}
  .card {{ background:white; border-radius:12px; max-width:540px; margin:0 auto;
           padding:28px 32px; box-shadow:0 2px 16px rgba(0,0,0,0.08); }}
  .badge {{ display:inline-block; background:#fef2f2; color:#dc2626; font-size:0.78rem;
            font-weight:700; padding:4px 10px; border-radius:99px; margin-bottom:16px; }}
  h2 {{ font-size:1.2rem; margin:0 0 6px; color:#1a1a2e; }}
  .meta {{ font-size:0.88rem; color:#6b7280; margin-bottom:20px; }}
  .field {{ margin-bottom:12px; }}
  .field label {{ font-size:0.75rem; font-weight:700; color:#8892a4;
                  text-transform:uppercase; letter-spacing:0.05em; display:block; margin-bottom:3px; }}
  .field span {{ font-size:0.96rem; color:#1a1a2e; font-weight:500; }}
  .msg-box {{ background:#f8f9fc; border-left:3px solid #2563eb;
              border-radius:6px; padding:12px 14px; font-size:0.93rem;
              color:#374151; margin-bottom:20px; font-style:italic; }}
  .btn {{ display:inline-block; padding:13px 24px; border-radius:9px;
          font-size:0.96rem; font-weight:700; text-decoration:none;
          margin-right:10px; margin-bottom:8px; }}
  .btn-wa {{ background:#25D366; color:white; }}
  .btn-done {{ background:#2563eb; color:white; }}
  .timer {{ background:#fef3c7; border:1px solid #fde68a; border-radius:8px;
            padding:10px 14px; font-size:0.88rem; color:#92400e;
            font-weight:600; margin-bottom:20px; }}
  .footer {{ font-size:0.78rem; color:#9ca3af; margin-top:24px; text-align:center; }}
</style>
</head>
<body>
<div class="card">
  <span class="badge">⏱ Novi lead — {_minutes_label(sla_minutes)} SLA</span>
  <h2>Novi upit za oglas</h2>
  <p class="meta">Izvor: <strong>{source}</strong></p>

  <div class="timer">
    ⚠️ Imaš <strong>{_minutes_label(sla_minutes)}</strong> da odgovoriš kupcu —
    ako ne reagujete, vlasnik agencije dobija alert.
  </div>

  <div class="field">
    <label>Kupac</label>
    <span>{buyer}</span>
  </div>
  <div class="field">
    <label>Telefon</label>
    <span>{phone}</span>
  </div>
  <div class="field">
    <label>Oglas</label>
    <span>{listing}</span>
  </div>

  <div class="msg-box">
    &ldquo;{message}&rdquo;
  </div>

  <a href="{wa_link}" class="btn btn-wa">💬 Odgovori na WhatsApp</a>
  <a href="{respond_url}" class="btn btn-done">✓ Odgovorio sam</a>

  <p class="footer">{agency_name} · Lead Rescue by Izveštaj.com</p>
</div>
</body>
</html>"""

    return send_report_email(
        to_email=agent_email,
        to_name=agent_name,
        subject=f"⏱ Novi lead: {buyer} — {listing}",
        html_body=html,
    )


def send_owner_escalation(
    owner_email:  str,
    owner_name:   str,
    agency_name:  str,
    lead:         dict,
    agent_name:   str,
    elapsed_min:  int,
    reassigned_to: str | None = None,
) -> bool:
    """
    Šalje vlasniku alert kada agent premaši SLA.
    """
    buyer = lead.get("buyer_name") or "Nepoznat kupac"
    listing = lead.get("listing_title") or "—"
    phone = lead.get("buyer_phone") or "—"
    source = _source_label(lead.get("source", ""))

    reassign_note = ""
    if reassigned_to:
        reassign_note = f"""
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;
                    padding:10px 14px;font-size:0.88rem;color:#166534;margin-top:12px;">
          ↩ Lead je automatski preraspoređen na <strong>{reassigned_to}</strong>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="sr">
<head><meta charset="UTF-8">
<style>
  body {{ font-family: system-ui, sans-serif; background:#f4f6f9; margin:0; padding:24px; }}
  .card {{ background:white; border-radius:12px; max-width:540px; margin:0 auto;
           padding:28px 32px; box-shadow:0 2px 16px rgba(0,0,0,0.08); }}
  .badge {{ display:inline-block; background:#fef2f2; color:#dc2626; font-size:0.78rem;
            font-weight:700; padding:4px 10px; border-radius:99px; margin-bottom:16px; }}
  h2 {{ font-size:1.2rem; margin:0 0 6px; color:#1a1a2e; }}
  .meta {{ font-size:0.88rem; color:#6b7280; margin-bottom:20px; }}
  .field {{ margin-bottom:12px; }}
  .field label {{ font-size:0.75rem; font-weight:700; color:#8892a4;
                  text-transform:uppercase; letter-spacing:0.05em; display:block; margin-bottom:3px; }}
  .field span {{ font-size:0.96rem; color:#1a1a2e; font-weight:500; }}
  .alert-box {{ background:#fef2f2; border:1px solid #fecaca; border-radius:8px;
                padding:10px 14px; font-size:0.88rem; color:#991b1b;
                font-weight:600; margin-bottom:20px; }}
  .footer {{ font-size:0.78rem; color:#9ca3af; margin-top:24px; text-align:center; }}
</style>
</head>
<body>
<div class="card">
  <span class="badge">🚨 SLA prekoračen</span>
  <h2>Lead nije obrađen na vreme</h2>
  <p class="meta">Agencija: <strong>{agency_name}</strong> · Izvor: <strong>{source}</strong></p>

  <div class="alert-box">
    ⚠️ <strong>{agent_name}</strong> nije odgovorio na lead od <strong>{buyer}</strong>
    već <strong>{_minutes_label(elapsed_min)}</strong>.
  </div>

  <div class="field">
    <label>Kupac</label>
    <span>{buyer}</span>
  </div>
  <div class="field">
    <label>Telefon</label>
    <span>{phone}</span>
  </div>
  <div class="field">
    <label>Oglas</label>
    <span>{listing}</span>
  </div>
  <div class="field">
    <label>Dodeljen agentu</label>
    <span>{agent_name}</span>
  </div>

  {reassign_note}

  <p class="footer">{agency_name} · Lead Rescue by Izveštaj.com</p>
</div>
</body>
</html>"""

    return send_report_email(
        to_email=owner_email,
        to_name=owner_name,
        subject=f"🚨 {agent_name} nije obradio lead: {buyer} — {listing}",
        html_body=html,
    )
