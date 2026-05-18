"""
Dnevni cron — generiše alert digest i šalje mejl Premium agencijama.

Razlika od nedeljnog izveštaja:
  • main.py šalje SVE Premium podatke u sklopu nedeljnog izveštaja.
  • Ovaj skript šalje KRATAK digest (3-5 alerta) svako jutro — samo
    actionable stvari koje su se desile od juče.

Pokretanje:
    python -X utf8 -m scripts.send_alerts_daily
    python -X utf8 -m scripts.send_alerts_daily --mock     # bez Supabase
    python -X utf8 -m scripts.send_alerts_daily --dry-run  # generiši HTML, ne šalji mejl

Cron primer (Linux, 7:00 svako jutro):
    0 7 * * *  cd /app && python -X utf8 -m scripts.send_alerts_daily >> /var/log/alerts.log 2>&1
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from jinja2 import Environment, FileSystemLoader

import config
from plans import get_plan
from mailer.sender import send_report_email


def render_alert_email(vars: dict) -> str:
    template_dir = Path(__file__).parent.parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    env.globals["support_email"] = config.SUPPORT_EMAIL
    return env.get_template("email_alert.html").render(**vars)


def run(use_mock: bool = False, dry_run: bool = False) -> int:
    """Vraća broj poslatih mejlova."""
    if use_mock or not config.SUPABASE_KEY:
        from data.mock_data import get_mock_alerts
        agencies = [{
            "id":           "mock",
            "name":         "Nekretnine Centar d.o.o.",
            "email":        "office@nekretninecentar.rs",
            "plan_id":      "premium",
            "alerts":       get_mock_alerts(),
        }]
    else:
        from data.supabase_client import get_all_active_clients, generate_market_alerts
        clients = get_all_active_clients()
        agencies = []
        for c in clients:
            plan = get_plan(c["plan_id"])
            if not plan.allows_alerts():
                continue
            try:
                alerts = generate_market_alerts(c["id"])
            except Exception as e:
                print(f"[{c['name']}] generate_market_alerts failed: {e}")
                continue
            if not alerts:
                continue
            agencies.append({
                "id":     c["id"],
                "name":   c["name"],
                "email":  c["email"],
                "plan_id": c["plan_id"],
                "alerts": alerts,
            })

    if not agencies:
        print("[i] Nema agencija sa aktivnim alertima — preskačem slanje.")
        return 0

    sent = 0
    today_str = date.today().strftime("%d.%m.%Y")
    dashboard_url = f"{config.APP_BASE_URL}/app.html" if getattr(config, "APP_BASE_URL", None) else None

    for a in agencies:
        html = render_alert_email({
            "agency_name":   a["name"],
            "alerts":        a["alerts"],
            "generated_at":  today_str,
            "dashboard_url": dashboard_url,
        })

        if dry_run:
            slug = a["id"].lower().replace(" ", "_")
            out = Path(__file__).parent.parent / f"alert_{slug}.html"
            out.write_text(html, encoding="utf-8")
            print(f"[DRY-RUN] {a['name']}: {len(a['alerts'])} alerta — HTML sačuvan u {out.name}")
            sent += 1
            continue

        subject = f"Tržišni alert — {len(a['alerts'])} {'stavka' if len(a['alerts']) == 1 else 'stavke'}"
        ok = send_report_email(
            to_email=a["email"],
            to_name=a["name"],
            subject=subject,
            html_body=html,
            pdf_bytes=None,
        )
        if ok:
            sent += 1
            print(f"[OK]   {a['name']}: {len(a['alerts'])} alerta poslato.")
        else:
            print(f"[FAIL] {a['name']}: slanje neuspešno.")

    print(f"\n[✓] Poslato mejlova: {sent}/{len(agencies)}")
    return sent


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mock",    action="store_true", help="Mock režim (bez Supabase)")
    parser.add_argument("--dry-run", action="store_true", help="Generiši HTML ali ne šalji mejl")
    args = parser.parse_args()
    run(use_mock=args.mock, dry_run=args.dry_run)
