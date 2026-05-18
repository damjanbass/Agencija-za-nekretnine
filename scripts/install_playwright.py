"""
Helper za prvi setup Playwright-a.

Šta radi:
  1. Proverava da li je `playwright` Python paket instaliran (pip install).
  2. Pokreće `playwright install chromium` da preuzme Chromium binary (~170 MB).
  3. Testira launch + jedan fetch da potvrdi da sve radi.

Pokretanje:
    python -X utf8 -m scripts.install_playwright
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


def step(n: int, msg: str):
    print(f"\n[{n}] {msg}")


def main() -> int:
    step(1, "Provera Python paketa `playwright`")
    try:
        import playwright  # noqa: F401
        print("    [OK] paket instaliran")
    except ImportError:
        print("    [!] paket nije instaliran — instaliram preko pip-a")
        rc = subprocess.call([sys.executable, "-m", "pip", "install", "playwright>=1.49.0"])
        if rc != 0:
            print("    [FAIL] pip install neuspešan")
            return rc

    step(2, "Preuzimanje Chromium binary-ja (može trajati 1–3 min, ~170 MB)")
    rc = subprocess.call([sys.executable, "-m", "playwright", "install", "chromium"])
    if rc != 0:
        print("    [FAIL] chromium install neuspešan")
        return rc
    print("    [OK] chromium spreman")

    step(3, "Smoke test — launch headless Chrome i fetch example.com")
    from scrapers import browser
    html = browser.get_html("https://example.com/", extra_wait_ms=500)
    browser.close()
    if html and "Example Domain" in html:
        print("    [OK] browser radi, HTML uspešno učitan")
    else:
        print(f"    [FAIL] fetch nije uspeo (HTML length={len(html or '')})")
        return 1

    print("\n[✓] Playwright setup završen. Sad možeš da pokreneš:")
    print("    python -X utf8 -m scripts.scrape_market_daily --mock")
    return 0


if __name__ == "__main__":
    sys.exit(main())
