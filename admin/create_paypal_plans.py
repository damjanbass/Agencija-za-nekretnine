"""
Kreira PayPal Products + Billing Plans (Basic, Pro, Premium) preko REST API-ja.

Pokretanje:
    python -X utf8 admin/create_paypal_plans.py

Zahteva env varijable (iz .env):
    PAYPAL_CLIENT_ID
    PAYPAL_SECRET
    PAYPAL_API_BASE  (live ili sandbox)

Štampa plan ID-ove koje treba upisati u web/checkout.html → PAYPAL_PLAN_IDS.
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

load_dotenv()

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
SECRET    = os.getenv("PAYPAL_SECRET", "")
API_BASE  = os.getenv("PAYPAL_API_BASE", "https://api-m.paypal.com")

PLANS = [
    {"key": "basic",   "name": "Basic",   "description": "Izveštaj Basic — do 3 agenta, nedeljni AI izveštaj",      "price": "29.00"},
    {"key": "pro",     "name": "Pro",     "description": "Izveštaj Pro — do 10 agenata, nedeljni + mesečni izveštaj", "price": "79.00"},
    {"key": "premium", "name": "Premium", "description": "Izveštaj Premium — neograničeni agenti, custom branding",   "price": "149.00"},
]


def get_token() -> str:
    r = requests.post(
        f"{API_BASE}/v1/oauth2/token",
        auth=(CLIENT_ID, SECRET),
        data={"grant_type": "client_credentials"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def create_product(token: str, name: str, description: str) -> str:
    r = requests.post(
        f"{API_BASE}/v1/catalogs/products",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "name":        name,
            "description": description,
            "type":        "SERVICE",
            "category":    "SOFTWARE",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()["id"]


def create_billing_plan(token: str, product_id: str, name: str, price: str) -> str:
    """Trial 30 dana @ 0€ → mesečno @ price EUR, neograničeno."""
    r = requests.post(
        f"{API_BASE}/v1/billing/plans",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        json={
            "product_id": product_id,
            "name":        name,
            "description": f"{name} — 30 dana besplatno, zatim {price} EUR/mesečno",
            "billing_cycles": [
                {
                    "frequency":      {"interval_unit": "DAY",   "interval_count": 30},
                    "tenure_type":    "TRIAL",
                    "sequence":       1,
                    "total_cycles":   1,
                    "pricing_scheme": {"fixed_price": {"value": "0", "currency_code": "EUR"}},
                },
                {
                    "frequency":      {"interval_unit": "MONTH", "interval_count": 1},
                    "tenure_type":    "REGULAR",
                    "sequence":       2,
                    "total_cycles":   0,
                    "pricing_scheme": {"fixed_price": {"value": price, "currency_code": "EUR"}},
                },
            ],
            "payment_preferences": {
                "auto_bill_outstanding":     True,
                "setup_fee":                 {"value": "0", "currency_code": "EUR"},
                "setup_fee_failure_action":  "CONTINUE",
                "payment_failure_threshold": 2,
            },
        },
        timeout=15,
    )
    if r.status_code >= 400:
        print(f"[!] Greška pri kreiranju plana {name}: {r.status_code}")
        print(r.text)
        r.raise_for_status()
    return r.json()["id"]


def main():
    if not CLIENT_ID or not SECRET:
        print("[!] PAYPAL_CLIENT_ID / PAYPAL_SECRET nisu podešeni u .env")
        sys.exit(1)

    print(f"PayPal API: {API_BASE}")
    print("Uzimam access token...")
    token = get_token()
    print("OK\n")

    results = {}
    for plan in PLANS:
        print(f"── {plan['name']} ──")
        print(f"  Kreiram product...")
        product_id = create_product(token, plan["name"], plan["description"])
        print(f"  Product ID: {product_id}")

        print(f"  Kreiram billing plan (30d trial → {plan['price']}€/mes)...")
        plan_id = create_billing_plan(token, product_id, plan["name"], plan["price"])
        print(f"  Plan ID: {plan_id}\n")

        results[plan["key"]] = plan_id

    print("=" * 60)
    print("GOTOVO! Upisi ove plan ID-ove u web/checkout.html:")
    print("=" * 60)
    print()
    print("  const PAYPAL_PLAN_IDS = {")
    for key, plan_id in results.items():
        print(f'    {key:8s} "{plan_id}",')
    print("  };")
    print()


if __name__ == "__main__":
    main()
