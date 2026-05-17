"""
Dnevni cron — prebaci istekle trial/active naloge na 'expired'.

Pokretanje:
    python -X utf8 -m scripts.expire_trials
"""
import sys

from data.supabase_client import expire_stale_trials

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

if __name__ == "__main__":
    n = expire_stale_trials()
    print(f"[expire_trials] expired_rows={n}")
