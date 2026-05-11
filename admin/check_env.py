"""
Preflight provera: validira da su sve neophodne env varijable podešene
i da spoljni servisi (Supabase, SMTP, Anthropic) prihvataju kredencijale.

Pokretanje:
  python -X utf8 admin/check_env.py

Izlazi sa exit code 0 ako je sve OK, 1 ako nešto nedostaje.
Korisno pre prvog produkcijskog run-a i nakon postavljanja GitHub Secrets.
"""

import os
import smtplib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

import config


REQUIRED = [
    "ANTHROPIC_API_KEY",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_PASS",
]

errors: list[str] = []
warnings: list[str] = []


def check(label: str, ok: bool, detail: str = ""):
    icon = "[✓]" if ok else "[✗]"
    line = f"{icon} {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    if not ok:
        errors.append(label)


def warn(label: str, detail: str):
    print(f"[!] {label} — {detail}")
    warnings.append(label)


def main():
    print("══ Env varijable ══")
    for name in REQUIRED:
        val = os.getenv(name, "")
        check(name, bool(val), "podešena" if val else "PRAZNA")

    print(f"\n══ Email config ══")
    check("EMAIL_FROM",      bool(config.EMAIL_FROM),      config.EMAIL_FROM or "PRAZAN")
    check("EMAIL_FROM_NAME", bool(config.EMAIL_FROM_NAME), config.EMAIL_FROM_NAME)
    if config.EMAIL_FROM and os.getenv("SMTP_USER") and config.EMAIL_FROM != os.getenv("SMTP_USER"):
        warn("EMAIL_FROM vs SMTP_USER", f"ne podudaraju se ({config.EMAIL_FROM} vs {os.getenv('SMTP_USER')}) — Gmail će odbiti")

    if errors:
        print(f"\n[STOP] {len(errors)} env varijabli nedostaje. Konekcione provere preskočene.")
        sys.exit(1)

    print(f"\n══ Konekcione provere ══")

    # Supabase
    try:
        from data.supabase_client import get_all_active_clients
        clients = get_all_active_clients()
        check("Supabase", True, f"{len(clients)} aktivnih agencija")
    except Exception as e:
        check("Supabase", False, str(e)[:120])

    # SMTP
    try:
        with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT"))) as server:
            server.ehlo()
            server.starttls()
            server.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS"))
        check("SMTP login", True, f"{os.getenv('SMTP_HOST')}:{os.getenv('SMTP_PORT')}")
    except Exception as e:
        check("SMTP login", False, str(e)[:120])

    # Anthropic
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=config.CLAUDE_MODEL,
            max_tokens=10,
            messages=[{"role": "user", "content": "ping"}],
        )
        check("Anthropic API", True, f"model={config.CLAUDE_MODEL}, response tokens={msg.usage.output_tokens}")
    except Exception as e:
        check("Anthropic API", False, str(e)[:120])

    if errors:
        print(f"\n[STOP] {len(errors)} problem(a). Pogledaj log iznad.")
        sys.exit(1)

    if warnings:
        print(f"\n[OK sa {len(warnings)} upozorenja] Sve veze rade.")
    else:
        print("\n[✓] Sve provere prošle. Sistem je spreman za produkciju.")


if __name__ == "__main__":
    main()
