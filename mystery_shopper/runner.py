"""
Mystery Shopper — šalje fejk upit na oglas agencije i meri vreme odgovora.

Tok:
  1. Nađi oglas agencije na Halo Oglasi (iz market_listings_sample ili konfig URL-a)
  2. Pošalji fejk upit via Playwright (realni browser)
  3. Kreiraj lead u bazi sa is_mystery_shopper=True
  4. SLA engine prati odgovor kao normalan lead
  5. Posle 24h scorer generiše ocenu i šalje izveštaj
"""

import random
import time
from datetime import datetime, timezone
from typing import Optional

# Fejk srpski podaci za mystery shopper (različiti svaki put)
_FAKE_NAMES = [
    ("Petar", "Marković"), ("Milica", "Jovanović"), ("Stefan", "Nikolić"),
    ("Ana", "Popović"),    ("Nikola", "Đorđević"),  ("Jelena", "Stanković"),
    ("Marko", "Ilić"),     ("Dragana", "Pavlović"),  ("Ivan", "Kostić"),
]
_FAKE_MESSAGES = [
    "Zainteresovan/a sam za ovaj oglas. Da li je još uvek dostupno? Kada bi mogao/la da obiđem?",
    "Molim Vas da me kontaktirate u vezi ovog oglasa. Imam par pitanja.",
    "Vidio/la sam oglas i bio/la bih zainteresovan/a za više detalja. Hvala.",
    "Da li je cena fiksna ili postoji mogućnost dogovora? Zainteresovan/a sam.",
    "Kada je moguć obilazak? Zainteresovan/a sam za nekretninu.",
]


def _random_shopper() -> dict:
    name = random.choice(_FAKE_NAMES)
    msg = random.choice(_FAKE_MESSAGES)
    # Realistično formatiran srpski mobilni broj — izgleda kao pravi
    prefix = random.choice(["060", "061", "062", "063", "064", "065"])
    phone = f"{prefix} {random.randint(100,999)} {random.randint(1000,9999)}"
    return {
        "first_name": name[0],
        "last_name":  name[1],
        "full_name":  f"{name[0]} {name[1]}",
        "phone":      phone,
        "message":    msg,
    }


def _find_agency_listing(agency_name: str, listing_url: Optional[str] = None) -> Optional[str]:
    """
    Vraća URL oglasa koji ćemo testirati.
    Prioritet: 1) konfigurisani URL, 2) listing iz market_listings_sample, 3) None
    """
    if listing_url:
        return listing_url

    try:
        from data.supabase_client import get_client
        sb = get_client()
        res = (
            sb.table("market_listings_sample")
            .select("url, publisher")
            .ilike("publisher", f"%{agency_name[:20]}%")
            .eq("site", "Halo oglasi")
            .limit(10)
            .execute()
        )
        listings = res.data or []
        if listings:
            chosen = random.choice(listings)
            return chosen["url"]
    except Exception as e:
        print(f"    [MystShopper] Nije pronašao listing u bazi: {e}")
    return None


def _submit_halo_inquiry(
    listing_url: str,
    shopper:     dict,
    email:       str,
) -> bool:
    """
    Otvara oglas na Halo Oglasi via Playwright i šalje poruku agentu.
    Vraća True ako je forma uspešno poslata.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PwTimeout
    except ImportError:
        print("    [MystShopper] Playwright nije instaliran. Pokreni: pip install playwright && playwright install chromium")
        return False

    print(f"    [MystShopper] Otvaramo: {listing_url}")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                locale="sr-RS",
            )
            page = ctx.new_page()
            page.goto(listing_url, wait_until="domcontentloaded", timeout=30_000)
            time.sleep(random.uniform(1.5, 3.0))

            # Pokušaj da nađemo i kliknemo "Pošalji poruku" dugme / tab
            for trigger_sel in [
                "button:has-text('Pošalji poruku')",
                "button:has-text('Kontaktiraj')",
                "a:has-text('Pošalji poruku')",
                "[data-action='send-message']",
                ".contact-form-trigger",
            ]:
                try:
                    btn = page.locator(trigger_sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        time.sleep(1.0)
                        break
                except PwTimeout:
                    continue

            # Popuni formu — probamo više selektora jer portali menjaju markup
            _fill(page, ["input[name='name']", "#ContactName", ".contact-name input"], shopper["full_name"])
            _fill(page, ["input[name='email']", "#ContactEmail", ".contact-email input"], email)
            _fill(page, ["input[name='phone']", "#ContactPhone", ".contact-phone input"], shopper["phone"])
            _fill_text(page, ["textarea[name='message']", "#ContactMessage", ".contact-message textarea"], shopper["message"])

            # Pošalji
            submitted = False
            for submit_sel in [
                "button[type='submit']:has-text('Pošalji')",
                "input[type='submit']",
                "button:has-text('Pošalji')",
                ".send-message-btn",
                "button[type='submit']",
            ]:
                try:
                    btn = page.locator(submit_sel).first
                    if btn.is_visible(timeout=2000):
                        btn.click()
                        time.sleep(2.0)
                        submitted = True
                        break
                except PwTimeout:
                    continue

            browser.close()
            if submitted:
                print("    [MystShopper] Forma poslata.")
            else:
                print("    [MystShopper] Forma nije pronađena — portal je možda promenio markup.")
            return submitted

    except Exception as e:
        print(f"    [MystShopper] Playwright greška: {e}")
        return False


def _fill(page, selectors: list, value: str) -> None:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.fill(value)
                return
        except Exception:
            continue


def _fill_text(page, selectors: list, value: str) -> None:
    for sel in selectors:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=1500):
                el.fill(value)
                return
        except Exception:
            continue


def run_mystery_shop(
    agency_id:    str,
    agency_name:  str,
    shopper_email: str,
    listing_url:  Optional[str] = None,
    dry_run:      bool = False,
) -> Optional[dict]:
    """
    Puni ciklus mystery shoppinga za jednu agenciju.
    Vraća dict sa info o kreiranom lead-u, ili None ako nije uspelo.
    """
    from data.leads_client import create_lead

    target_url = _find_agency_listing(agency_name, listing_url)
    if not target_url:
        print(f"    [MystShopper] {agency_name} — nije pronađen oglas za testiranje.")
        return None

    shopper = _random_shopper()
    print(f"    [MystShopper] {agency_name} — šalje upit kao '{shopper['full_name']}' na {target_url}")

    submitted = False
    if not dry_run:
        submitted = _submit_halo_inquiry(target_url, shopper, shopper_email)
    else:
        print(f"    [MystShopper] [dry] Preskačem Playwright submission.")
        submitted = True  # U dry run smatramo da je poslato

    if not submitted and not dry_run:
        print("    [MystShopper] Submission nije uspeo — lead neće biti kreiran.")
        return None

    # Kreiraj lead u bazi označen kao mystery shopper
    now = datetime.now(timezone.utc)
    lead_data = {
        "source":              "mystery_shopper",
        "external_message_id": f"ms_{agency_id}_{int(now.timestamp())}",
        "buyer_name":          shopper["full_name"],
        "buyer_phone":         shopper["phone"],
        "buyer_email":         shopper_email,
        "message":             shopper["message"],
        "listing_title":       target_url.split("/")[-1][:100],
        "listing_url":         target_url,
        "received_at":         now,
        "is_mystery_shopper":  True,
    }

    if dry_run:
        print(f"    [MystShopper] [dry] Lead bi bio kreiran: {shopper['full_name']} / {shopper['phone']}")
        return lead_data

    created = create_lead(agency_id, lead_data)
    if created:
        from data.leads_client import log_event
        log_event(created["id"], "mystery_shop_sent", actor="system", note=target_url)
        print(f"    [MystShopper] Lead kreiran (ID: {created['id'][:8]}...)")
        return created

    return None
