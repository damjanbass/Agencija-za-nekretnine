"""
Nedeljni cron — šalje personalizovane izveštaje agentima (Basic/Pro/Premium).

Free plan nema agent izveštaje; Basic dobija osnovnu verziju; Pro dodaje trend
grafik i tabelu ličnih oglasa vs medijana tržišta; Premium dodatno dobija
AI komentar i pricing preporuke + PDF prilog.

Pokretanje:
    python -X utf8 -m scripts.send_agent_reports_weekly
    python -X utf8 -m scripts.send_agent_reports_weekly --mock --preview
    python -X utf8 -m scripts.send_agent_reports_weekly --mock --plan premium --preview

Cron primer (Linux, ponedeljak 8:00):
    0 8 * * 1  cd /app && python -X utf8 -m scripts.send_agent_reports_weekly >> /var/log/agent_reports.log 2>&1
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

from main import run_agent_reports


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true", help="Ne šalji mejl, samo generiši HTML")
    parser.add_argument("--mock",    action="store_true", help="Mock režim (bez Supabase)")
    parser.add_argument("--plan",    default=None,        help="Override plan_id u mock-u (basic/pro/premium)")
    args = parser.parse_args()
    run_agent_reports(preview=args.preview, use_mock=args.mock, plan_override=args.plan)
