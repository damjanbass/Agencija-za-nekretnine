"""
Generiše WhatsApp poruku za prodavca i šalje email agentu.
"""

import urllib.parse
from typing import Optional

from mailer.sender import send_report_email


def _wa_link(phone: str, text: str) -> str:
    digits = phone.replace(" ", "").replace("-", "")
    if digits.startswith("0"):
        digits = "381" + digits[1:]
    elif digits.startswith("+"):
        digits = digits[1:]
    return f"https://wa.me/{digits}?text={urllib.parse.quote(text)}"


def generate_seller_message(listing: dict) -> str:
    """
    Generiše prirodan srpski tekst koji agent šalje prodavcu.
    Sadrži: dane na tržištu, broj pregleda/upita, cenu vs medijanu, predlog.
    """
    days     = listing.get("days_on_market", 0)
    location = listing.get("municipality") or listing.get("city") or "Beogradu"
    t_label  = listing.get("type_label", "nekretninu")
    price    = int(listing.get("price") or 0)
    delta    = listing.get("delta_pct")
    suggest  = listing.get("suggested_price")
    views    = listing.get("view_count") or 0
    inquiries = listing.get("inquiry_count") or 0
    seller   = (listing.get("seller_name") or "").split()[0] or "Poštovani"

    lines = [f"Pozdrav {seller},"]
    lines.append(
        f"Javljam Vam se u vezi Vaše {t_label} u {location}u, "
        f"koju smo objavili pre {days} {'dan' if days == 1 else 'dana'}."
    )

    stats_parts = []
    if views:
        stats_parts.append(f"{views} {'pregled' if views == 1 else 'pregleda'}")
    if inquiries:
        stats_parts.append(f"{inquiries} {'upit' if inquiries == 1 else 'upita'}")
    if stats_parts:
        lines.append(f"Do sada smo imali {' i '.join(stats_parts)}.")

    if delta is not None and delta > 5:
        diff_eur = price - (suggest or price)
        lines.append(
            f"Analiza tržišta pokazuje da je Vaša nekretnina trenutno "
            f"{round(delta)}% iznad medijane za sličan {t_label} u {location}u."
        )
        if suggest and diff_eur > 0:
            lines.append(
                f"Na osnovu aktuelnih transakcija, predlažem snižavanje cene na "
                f"{suggest:,}€ (razlika: {diff_eur:,}€). "
                f"Očekujem da ćemo u roku od 2 nedelje privući 3–5 ozbiljnih upita."
            )
    elif days >= 90:
        lines.append(
            f"Oglas je aktivan već {days} dana — razmislite o osvežavanju "
            f"fotografija ili male korekcije cene kako bismo postigli novi talas interesovanja."
        )

    lines.append("Javljajte se ako imate pitanja. Pozdrav!")
    return "\n\n".join(lines)


def send_nudge_email(
    agent_email:   str,
    agent_name:    str,
    agency_name:   str,
    listings:      list[dict],
) -> bool:
    """
    Šalje agentu email sa listom stale oglasa i WA linkovima za prodavce.
    """
    if not listings:
        return False

    cards_html = ""
    for lst in listings:
        message   = generate_seller_message(lst)
        wa_link   = ""
        seller_ph = lst.get("seller_phone") or ""
        if seller_ph:
            wa_link = _wa_link(seller_ph, message)

        price     = int(lst.get("price") or 0)
        suggest   = lst.get("suggested_price")
        delta     = lst.get("delta_pct")
        days      = lst.get("days_on_market", 0)
        location  = lst.get("municipality") or lst.get("city") or "—"
        title     = lst.get("title") or "—"
        seller    = lst.get("seller_name") or "—"
        seller_ph_label = seller_ph or "nije unet"
        agent_data = lst.get("agents") or {}
        assigned = agent_data.get("name") or "—"

        overpriced_badge = ""
        if delta and delta > 5:
            overpriced_badge = f'<span style="background:#fee2e2;color:#991b1b;font-size:0.72rem;font-weight:700;padding:2px 8px;border-radius:99px;margin-left:8px;">+{round(delta)}% iznad medijane</span>'

        delta_row = ""
        if delta is not None:
            color = "#dc2626" if delta > 5 else "#16a34a"
            delta_row = f'<div class="row"><span class="lbl">Delta vs medijana</span><span class="val" style="color:{color}">{("+" if delta>0 else "")}{round(delta)}%</span></div>'

        suggest_row = ""
        if suggest and suggest < price:
            diff = price - suggest
            suggest_row = f'<div class="row"><span class="lbl">Predlog cene</span><span class="val" style="color:#2563eb"><strong>{suggest:,}€</strong> (−{diff:,}€)</span></div>'

        wa_btn = ""
        if wa_link:
            wa_btn = f'<a href="{wa_link}" style="display:inline-block;margin-top:10px;background:#25D366;color:white;text-decoration:none;font-size:0.82rem;font-weight:700;padding:8px 16px;border-radius:7px;">💬 Pošalji prodavcu na WhatsApp</a>'
        else:
            wa_btn = '<div style="font-size:0.78rem;color:#9ca3af;margin-top:8px;">⚠️ Telefon prodavca nije unet — dodaj ga u listu oglasa.</div>'

        msg_escaped = message.replace("\n", "<br>").replace("'", "&#39;")

        cards_html += f"""
<div style="background:white;border-radius:10px;padding:18px 20px;margin-bottom:14px;
            box-shadow:0 2px 8px rgba(0,0,0,0.06);border-left:3px solid {'#dc2626' if (delta or 0)>5 else '#f59e0b'};">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:12px;">
    <div>
      <span style="font-size:0.95rem;font-weight:700;color:#1a1a2e;">{title}</span>
      {overpriced_badge}
    </div>
    <span style="font-size:0.8rem;color:#6b7280;white-space:nowrap;margin-left:12px;">{days} dana</span>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;margin-bottom:12px;">
    <div class="row"><span class="lbl">Lokacija</span><span class="val">{location}</span></div>
    <div class="row"><span class="lbl">Cena</span><span class="val">{price:,}€</span></div>
    <div class="row"><span class="lbl">Prodavac</span><span class="val">{seller}</span></div>
    <div class="row"><span class="lbl">Tel. prodavca</span><span class="val">{seller_ph_label}</span></div>
    {delta_row}
    {suggest_row}
  </div>
  <details style="margin-bottom:10px;">
    <summary style="font-size:0.82rem;font-weight:600;color:#2563eb;cursor:pointer;">
      Predlog poruke za prodavca ↓
    </summary>
    <div style="background:#f8f9fc;border-radius:6px;padding:12px;margin-top:8px;
                font-size:0.85rem;color:#374151;line-height:1.6;font-style:italic;">
      {msg_escaped}
    </div>
  </details>
  {wa_btn}
</div>"""

    html = f"""<!DOCTYPE html>
<html lang="sr">
<head><meta charset="UTF-8">
<style>
  * {{ margin:0;padding:0;box-sizing:border-box; }}
  body {{ font-family:'Segoe UI',Arial,sans-serif;background:#f4f6f9;color:#1a1a2e;padding:24px; }}
  .wrapper {{ max-width:580px;margin:0 auto;background:white;border-radius:14px;overflow:hidden;
             box-shadow:0 4px 24px rgba(0,0,0,0.10); }}
  .header {{ background:linear-gradient(135deg,#1a1a2e 0%,#0f3460 60%,#1d4ed8 100%);
             padding:26px 30px;color:white; }}
  .header h1 {{ font-size:19px;font-weight:700;margin-bottom:4px; }}
  .header .sub {{ font-size:13px;opacity:0.7; }}
  .body {{ padding:22px 28px; }}
  .intro {{ font-size:0.92rem;color:#4a5168;margin-bottom:18px;line-height:1.6; }}
  .row {{ display:flex;justify-content:space-between;padding:5px 0;font-size:0.85rem; }}
  .lbl {{ color:#8892a4; }}
  .val {{ font-weight:600;color:#1a1a2e; }}
  .footer {{ background:#f8f9fc;border-top:1px solid #eaedf3;padding:14px 28px;
             font-size:11px;color:#9ca3af;text-align:center; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Stale Listing Nudge</h1>
    <div class="sub">{agency_name} · {len(listings)} {'oglas' if len(listings)==1 else 'oglasa'} za pažnju</div>
  </div>
  <div class="body">
    <p class="intro">
      Ovi oglasi su aktivni duže od 60 dana bez ugovora. Ispod je predlog poruke
      za svakog prodavca — klikni WhatsApp dugme i poruka je već popunjena.
    </p>
    {cards_html}
  </div>
  <div class="footer">Stale Listing Nudge · Lead Rescue by Izveštaj.com</div>
</div>
</body>
</html>"""

    return send_report_email(
        to_email=agent_email,
        to_name=agent_name,
        subject=f"📋 {len(listings)} {'oglas čeka' if len(listings)==1 else 'oglasa čekaju'} — predlog za prodavce",
        html_body=html,
    )
