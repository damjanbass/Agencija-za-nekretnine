"""
Mystery Shopper Scorer — izračunava ocenu i šalje izveštaj vlasniku.
Pokreće se 24h nakon svakog mystery shop testa.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional


def _grade(response_time_min: Optional[int]) -> dict:
    """Pretvara vreme odgovora u ocenu A–F."""
    if response_time_min is None:
        return {"letter": "F", "label": "Bez odgovora", "color": "#dc2626", "bar_pct": 0}
    if response_time_min <= 5:
        return {"letter": "A", "label": "Odlično",          "color": "#16a34a", "bar_pct": 100}
    if response_time_min <= 15:
        return {"letter": "B", "label": "Dobro",            "color": "#65a30d", "bar_pct": 80}
    if response_time_min <= 30:
        return {"letter": "C", "label": "Može bolje",       "color": "#d97706", "bar_pct": 55}
    if response_time_min <= 60:
        return {"letter": "D", "label": "Loše",             "color": "#ea580c", "bar_pct": 30}
    return         {"letter": "F", "label": "Kritično",         "color": "#dc2626", "bar_pct": 10}


def _minutes_label(minutes: Optional[int]) -> str:
    if minutes is None:
        return "nema odgovora"
    if minutes < 60:
        return f"{minutes} min"
    h, m = divmod(minutes, 60)
    return f"{h}h {m}min" if m else f"{h}h"


def get_mystery_shop_results(agency_id: str, days: int = 30) -> list[dict]:
    """Vraća listu završenih mystery shop testova za agenciju."""
    from data.supabase_client import get_client
    from_dt = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    sb = get_client()
    res = (
        sb.table("leads")
        .select("id, received_at, responded_at, response_time_minutes, status, listing_url, assigned_agent_id, agents(name)")
        .eq("agency_id", agency_id)
        .eq("source", "mystery_shopper")
        .gte("created_at", from_dt)
        .order("created_at", desc=True)
        .execute()
    )
    rows = res.data or []
    results = []
    for row in rows:
        rt = row.get("response_time_minutes")
        grade = _grade(rt)
        agent_data = row.get("agents") or {}
        results.append({
            "date":          (row.get("received_at") or "")[:10],
            "agent_name":    agent_data.get("name") or "—",
            "response_time": rt,
            "time_label":    _minutes_label(rt),
            "status":        row.get("status"),
            "grade":         grade,
            "listing_url":   row.get("listing_url"),
        })
    return results


def get_latest_pending_shop(agency_id: str) -> Optional[dict]:
    """
    Vraća najnoviji mystery shop koji je još uvek otvoren (24h window).
    Koristi se da proveri da li treba da se pošalje score report.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    from data.supabase_client import get_client
    sb = get_client()
    res = (
        sb.table("leads")
        .select("id, received_at, response_time_minutes, status, listing_url, agents(name)")
        .eq("agency_id", agency_id)
        .eq("source", "mystery_shopper")
        .in_("status", ["new", "assigned", "escalated", "responded"])
        .gte("received_at", cutoff)
        .order("received_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None


def build_score_report(agency_name: str, results: list[dict]) -> dict:
    """Agregira listu testova u summary za email/brief."""
    if not results:
        return {
            "total_tests":  0,
            "avg_grade":    "—",
            "avg_time_min": None,
            "latest":       None,
        }

    times = [r["response_time"] for r in results if r["response_time"] is not None]
    avg_time = round(sum(times) / len(times)) if times else None
    avg_grade = _grade(avg_time)

    return {
        "total_tests":  len(results),
        "avg_grade":    avg_grade,
        "avg_time_min": avg_time,
        "avg_time_label": _minutes_label(avg_time),
        "latest":       results[0] if results else None,
        "results":      results,
    }


def send_score_report(
    agency_id:    str,
    agency_name:  str,
    owner_email:  str,
    owner_name:   str,
    lead:         dict,
) -> bool:
    """Šalje mystery shopper score report vlasniku agencije."""
    from mailer.sender import send_report_email

    rt = lead.get("response_time_minutes")
    grade = _grade(rt)
    agent_data = lead.get("agents") or {}
    agent_name = agent_data.get("name") or "—"
    listing_url = lead.get("listing_url") or "—"
    time_label = _minutes_label(rt)

    # Benchmark (simuliran — prosek beogradskih agencija)
    benchmark_min = 24
    benchmark_label = _minutes_label(benchmark_min)

    comparison = ""
    if rt is not None:
        diff = benchmark_min - rt
        if diff > 0:
            comparison = f"<strong style='color:#16a34a'>+{diff} min brže</strong> od proseka tržišta"
        elif diff < 0:
            comparison = f"<strong style='color:#dc2626'>{abs(diff)} min sporije</strong> od proseka tržišta"
        else:
            comparison = "tačno na nivou proseka tržišta"

    html = f"""<!DOCTYPE html>
<html lang="sr">
<head><meta charset="UTF-8">
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background:#f4f6f9; margin:0; padding:24px; }}
  .wrapper {{ background:white; border-radius:14px; max-width:560px; margin:0 auto;
             overflow:hidden; box-shadow:0 4px 24px rgba(0,0,0,0.10); }}
  .header {{ background:linear-gradient(135deg,#1a1a2e 0%,#0f3460 60%,#1d4ed8 100%);
             padding:28px 32px 24px; color:#fff; }}
  .header h1 {{ font-size:20px; font-weight:700; margin-bottom:4px; }}
  .header .sub {{ font-size:13px; opacity:0.7; }}
  .body {{ padding:28px 32px; }}
  .grade-big {{
    text-align:center; padding:28px 0 22px;
  }}
  .grade-letter {{
    font-size:5rem; font-weight:900; line-height:1; color:{grade['color']};
  }}
  .grade-label {{
    font-size:1.1rem; font-weight:700; color:{grade['color']}; margin-top:4px;
  }}
  .grade-time {{
    font-size:0.95rem; color:#6b7280; margin-top:6px;
  }}
  .details {{
    background:#f8f9fc; border-radius:10px; padding:16px 18px; margin-bottom:20px;
  }}
  .row {{ display:flex; justify-content:space-between; padding:8px 0;
          border-bottom:1px solid #eaedf3; font-size:0.92rem; }}
  .row:last-child {{ border-bottom:none; }}
  .row-label {{ color:#6b7280; }}
  .row-val {{ font-weight:600; color:#1a1a2e; }}
  .benchmark {{
    background:#eff6ff; border:1px solid #bfdbfe; border-radius:8px;
    padding:12px 16px; font-size:0.88rem; color:#1e3a8a; margin-bottom:20px;
  }}
  .tip {{
    background:#fffbeb; border-left:3px solid #f59e0b;
    border-radius:6px; padding:12px 14px;
    font-size:0.88rem; color:#92400e; margin-bottom:20px;
  }}
  .footer {{ background:#f8f9fc; border-top:1px solid #eaedf3;
             padding:16px 32px; font-size:11px; color:#9ca3af; text-align:center; }}
</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>Mystery Shopper Rezultat</h1>
    <div class="sub">{agency_name} · {lead.get('received_at', '')[:10]}</div>
  </div>
  <div class="body">
    <div class="grade-big">
      <div class="grade-letter">{grade['letter']}</div>
      <div class="grade-label">{grade['label']}</div>
      <div class="grade-time">Vreme odgovora: <strong>{time_label}</strong></div>
    </div>

    <div class="details">
      <div class="row"><span class="row-label">Agent koji je odgovorio</span><span class="row-val">{agent_name}</span></div>
      <div class="row"><span class="row-label">Oglas testiran</span><span class="row-val"><a href="{listing_url}" style="color:#2563eb">Halo Oglasi</a></span></div>
      <div class="row"><span class="row-label">Poslan upit u</span><span class="row-val">{(lead.get('received_at') or '')[:16].replace('T', ' ')}</span></div>
      <div class="row"><span class="row-label">Odgovoreno u</span><span class="row-val">{(lead.get('responded_at') or 'bez odgovora')[:16].replace('T', ' ')}</span></div>
    </div>

    {'<div class="benchmark">📊 Tvoja agencija: <strong>' + time_label + '</strong> · Prosek tržišta: <strong>' + benchmark_label + '</strong> · ' + comparison + '</div>' if rt is not None else '<div class="benchmark" style="background:#fef2f2;border-color:#fecaca;color:#991b1b;">🚨 Agent nije odgovorio na mystery shop upit u roku od 24h.</div>'}

    {'<div class="tip">💡 <strong>Preporuka:</strong> Cilj je vreme ispod 10 min. Podesite SLA na 10 min i uvajte dnevni brief da agenti ostanu fokusirani.</div>' if (rt is None or rt > 15) else ''}

  </div>
  <div class="footer">Mystery Shopper · Lead Rescue by Izveštaj.com</div>
</div>
</body>
</html>"""

    return send_report_email(
        to_email=owner_email,
        to_name=owner_name,
        subject=f"🔍 Mystery Shopper: ocena {grade['letter']} — {time_label}",
        html_body=html,
    )
