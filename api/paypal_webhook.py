"""
PayPal Subscriptions webhook → Supabase agencies.subscription_status sync.

Pokretanje (lokalno):
    python -X utf8 -m api.paypal_webhook

Endpointi:
    POST /webhook/paypal   — prima eventove (verifikuje potpis preko PayPal API-ja)
    POST /admin/expire     — pokreće reconciliation (sa X-Admin-Token header-om)

Environment varijable:
    PAYPAL_WEBHOOK_ID       — ID webhook-a iz PayPal Dashboarda
    PAYPAL_CLIENT_ID        — REST API client id
    PAYPAL_SECRET           — REST API secret
    PAYPAL_API_BASE         — https://api-m.paypal.com (live) ili https://api-m.sandbox.paypal.com
    ADMIN_TOKEN             — bilo koji random string; štiti /admin/expire
    SUPABASE_URL, SUPABASE_KEY — već postoje u config.py
"""

import os
import sys
from datetime import datetime, timezone

import requests
from fastapi import FastAPI, HTTPException, Header, Request

import config
from data.supabase_client import get_client, expire_stale_trials
from mailer.billing_email import send_invoice, send_subscription_activated

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID", "")
PAYPAL_CLIENT_ID  = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_SECRET     = os.getenv("PAYPAL_SECRET", "")
PAYPAL_API_BASE   = os.getenv("PAYPAL_API_BASE", "https://api-m.paypal.com")
ADMIN_TOKEN       = os.getenv("ADMIN_TOKEN", "")

app = FastAPI(title="PayPal subscription webhook")


# ── PayPal helpers ────────────────────────────────────────────

def _paypal_access_token() -> str:
    r = requests.post(
        f"{PAYPAL_API_BASE}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _verify_signature(headers: dict, raw_body: bytes) -> bool:
    """Pita PayPal da potvrdi potpis webhook event-a."""
    if not PAYPAL_WEBHOOK_ID:
        # Razvoj — preskoči verifikaciju ali jasno upozori u logu.
        print("[paypal] WARNING: PAYPAL_WEBHOOK_ID nije podešen, preskačem verifikaciju potpisa.")
        return True

    token = _paypal_access_token()
    payload = {
        "auth_algo":         headers.get("paypal-auth-algo", ""),
        "cert_url":          headers.get("paypal-cert-url", ""),
        "transmission_id":   headers.get("paypal-transmission-id", ""),
        "transmission_sig":  headers.get("paypal-transmission-sig", ""),
        "transmission_time": headers.get("paypal-transmission-time", ""),
        "webhook_id":        PAYPAL_WEBHOOK_ID,
        "webhook_event":     __import__("json").loads(raw_body.decode("utf-8")),
    }
    r = requests.post(
        f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=10,
    )
    r.raise_for_status()
    return r.json().get("verification_status") == "SUCCESS"


# ── DB update ─────────────────────────────────────────────────

def _update_by_subscription(sub_id: str, fields: dict) -> int:
    sb = get_client()
    res = (
        sb.table("agencies")
        .update(fields)
        .eq("paypal_subscription_id", sub_id)
        .execute()
    )
    return len(res.data or [])


def _get_agency_by_subscription(sub_id: str) -> dict | None:
    """Učitava agenciju + sva billing polja za slanje email-a."""
    sb = get_client()
    res = (
        sb.table("agencies")
        .select("id, name, email, billing_email, plan_id, trial_ends_at, "
                "current_period_end, paypal_subscription_id, pib, maticni_broj, "
                "legal_address, legal_city")
        .eq("paypal_subscription_id", sub_id)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def _set_subscription_on_agency(agency_id: str, sub_id: str, plan_id: str | None = None) -> None:
    sb = get_client()
    fields = {"paypal_subscription_id": sub_id, "subscription_status": "active"}
    if plan_id:
        fields["plan_id"] = plan_id
    sb.table("agencies").update(fields).eq("id", agency_id).execute()


# ── Event handling ────────────────────────────────────────────

def _handle_event(event: dict) -> None:
    et = event.get("event_type", "")
    resource = event.get("resource", {}) or {}
    sub_id = resource.get("id") or resource.get("billing_agreement_id") or ""

    if not sub_id:
        print(f"[paypal] {et} — nedostaje subscription id, preskačem")
        return

    if et in ("BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.RE-ACTIVATED"):
        period_end = (resource.get("billing_info") or {}).get("next_billing_time")
        n = _update_by_subscription(sub_id, {
            "subscription_status": "active",
            "current_period_end":  period_end,
        })
        print(f"[paypal] {et} sub={sub_id} updated={n}")

        # Email: aktivacija pretplate (početak probnog perioda)
        try:
            agency = _get_agency_by_subscription(sub_id)
            if agency:
                send_subscription_activated(
                    agency        = agency,
                    plan_id       = agency.get("plan_id"),
                    trial_ends_at = agency.get("trial_ends_at") or period_end,
                )
        except Exception as e:
            print(f"[paypal] activation email greška: {e}")

    elif et == "PAYMENT.SALE.COMPLETED":
        # Obnova perioda — guramo current_period_end kad PayPal već zna sledeći datum.
        period_end = resource.get("next_billing_time")
        fields = {"subscription_status": "active"}
        if period_end:
            fields["current_period_end"] = period_end
        n = _update_by_subscription(sub_id, fields)
        print(f"[paypal] {et} sub={sub_id} updated={n}")

        # Email: račun za uspešnu naplatu
        try:
            agency = _get_agency_by_subscription(sub_id)
            if agency:
                amount_raw   = (resource.get("amount") or {}).get("total")
                sale_id      = resource.get("id") or ""
                create_time  = resource.get("create_time")
                amount_value = float(amount_raw) if amount_raw else None
                send_invoice(
                    agency           = agency,
                    plan_id          = agency.get("plan_id"),
                    invoice_number   = f"INV-{sale_id[-12:]}" if sale_id else None,
                    charge_date      = create_time,
                    period_start     = create_time,
                    period_end       = period_end,
                    next_charge_date = period_end,
                    amount           = amount_value,
                )
        except Exception as e:
            print(f"[paypal] invoice email greška: {e}")

    elif et in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED"):
        n = _update_by_subscription(sub_id, {"subscription_status": "canceled"})
        print(f"[paypal] {et} sub={sub_id} updated={n}")

    elif et in ("BILLING.SUBSCRIPTION.SUSPENDED", "PAYMENT.SALE.DENIED",
                "BILLING.SUBSCRIPTION.PAYMENT.FAILED"):
        n = _update_by_subscription(sub_id, {"subscription_status": "past_due"})
        print(f"[paypal] {et} sub={sub_id} updated={n}")

    else:
        print(f"[paypal] {et} sub={sub_id} — bez akcije")


# ── HTTP endpoints ────────────────────────────────────────────

@app.post("/webhook/paypal")
async def paypal_webhook(req: Request):
    raw = await req.body()
    headers = {k.lower(): v for k, v in req.headers.items()}
    if not _verify_signature(headers, raw):
        raise HTTPException(status_code=400, detail="Invalid signature")
    event = await req.json()
    _handle_event(event)
    return {"ok": True}


@app.post("/admin/expire")
async def admin_expire(x_admin_token: str = Header(default="")):
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    n = expire_stale_trials()
    return {"expired": n, "at": datetime.now(timezone.utc).isoformat()}


@app.post("/admin/activate")
async def admin_activate(payload: dict, x_admin_token: str = Header(default="")):
    """
    Ručna aktivacija pretplate posle PayPal checkout-a (callback iz web/checkout.html).
    Body: { "agency_id": "...", "subscription_id": "...", "plan_id": "pro" }
    """
    if not ADMIN_TOKEN or x_admin_token != ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    agency_id = payload.get("agency_id")
    sub_id    = payload.get("subscription_id")
    plan_id   = payload.get("plan_id")
    if not agency_id or not sub_id:
        raise HTTPException(status_code=400, detail="agency_id and subscription_id required")
    _set_subscription_on_agency(agency_id, sub_id, plan_id)
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8787"))
    uvicorn.run(app, host="0.0.0.0", port=port)
