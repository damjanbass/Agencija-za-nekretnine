"""
Slanje email-ova vezanih za pretplate (aktivacija + račun).

Glavne funkcije:
    send_subscription_activated(agency, ...)
        — šalje se kada PayPal javi BILLING.SUBSCRIPTION.ACTIVATED
    send_invoice(agency, ...)
        — šalje se kada PayPal javi PAYMENT.SALE.COMPLETED

Sve email-ove renderujemo iz templates/ foldera (Jinja2).
"""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

import config
from mailer.sender import send_report_email
from plans import PLANS


# ── Setup Jinja env (templates/ folder u project rootu) ───────
_BASE_DIR = Path(__file__).resolve().parent.parent
_jinja = Environment(loader=FileSystemLoader(_BASE_DIR / "templates"))


# ── Helpers ───────────────────────────────────────────────────

def _fmt_date(value) -> str:
    """ISO date / datetime → 'DD.MM.YYYY'. Prima i string i datetime."""
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except Exception:
            return value
    return value.strftime("%d.%m.%Y")


def _plan_display_name(plan_id: str) -> str:
    return PLANS.get(plan_id, PLANS["free"]).name


def _plan_amount(plan_id: str) -> int:
    return PLANS.get(plan_id, PLANS["free"]).price_eur


def _billing_email(agency: dict) -> str:
    """Email za naplatu — ako postoji billing_email koristi njega, inače glavni."""
    return (agency.get("billing_email") or agency.get("email") or "").strip()


# ── send_subscription_activated ───────────────────────────────

def send_subscription_activated(agency: dict, plan_id: str | None = None,
                                 trial_ends_at: str | None = None) -> bool:
    """
    Šalje email da je pretplata aktivirana (početak probnog perioda).
    """
    to_email = _billing_email(agency)
    if not to_email:
        print("[billing_email] activation skipped — no email on agency")
        return False

    plan_id = plan_id or agency.get("plan_id") or "free"
    amount  = _plan_amount(plan_id)

    template = _jinja.get_template("email_subscription_activated.html")
    html = template.render(
        agency_name        = agency.get("name") or "vlasniče",
        plan_display_name  = _plan_display_name(plan_id),
        amount             = amount,
        trial_ends_at      = _fmt_date(trial_ends_at or agency.get("trial_ends_at")),
        support_email      = config.SUPPORT_EMAIL,
    )

    return send_report_email(
        to_email   = to_email,
        to_name    = agency.get("name") or to_email,
        subject    = "Pretplata aktivirana — probni period je započeo",
        html_body  = html,
    )


# ── send_invoice ──────────────────────────────────────────────

def send_invoice(agency: dict, plan_id: str | None, *,
                  charge_date: str | None = None,
                  period_start: str | None = None,
                  period_end: str | None = None,
                  next_charge_date: str | None = None,
                  amount: int | float | None = None,
                  invoice_number: str | None = None,
                  payment_method: str = "Kartica preko PayPal") -> bool:
    """
    Šalje račun za uspešnu naplatu (PAYMENT.SALE.COMPLETED).
    Polja koja nedostaju popunjavaju se iz agency / plan defaultova.
    """
    to_email = _billing_email(agency)
    if not to_email:
        print("[billing_email] invoice skipped — no email on agency")
        return False

    plan_id = plan_id or agency.get("plan_id") or "free"
    amount  = amount if amount is not None else _plan_amount(plan_id)

    if not invoice_number:
        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        invoice_number = f"INV-{ts}"

    template = _jinja.get_template("email_invoice.html")
    html = template.render(
        invoice_number     = invoice_number,
        charge_date        = _fmt_date(charge_date or datetime.utcnow().isoformat()),
        period_start       = _fmt_date(period_start),
        period_end         = _fmt_date(period_end),
        next_charge_date   = _fmt_date(next_charge_date),
        payment_method     = payment_method,
        agency_name        = agency.get("name") or "Agencija",
        pib                = agency.get("pib"),
        maticni_broj       = agency.get("maticni_broj"),
        legal_address      = agency.get("legal_address"),
        legal_city         = agency.get("legal_city"),
        billing_email      = to_email,
        provider_email     = config.SUPPORT_EMAIL or config.EMAIL_FROM,
        support_email      = config.SUPPORT_EMAIL or config.EMAIL_FROM,
        plan_display_name  = _plan_display_name(plan_id),
        amount             = amount,
    )

    return send_report_email(
        to_email   = to_email,
        to_name    = agency.get("name") or to_email,
        subject    = f"Račun {invoice_number} — {_plan_display_name(plan_id)} plan",
        html_body  = html,
    )
