"""
Generiše click-to-WhatsApp deep linkove za agente.
Format: https://wa.me/<phone>?text=<encoded_message>
"""

import re
import urllib.parse


def _normalize_phone(phone: str) -> str:
    """Normalizuje srpski broj telefona na E.164 format bez +."""
    digits = re.sub(r"[^\d]", "", phone)
    # +381... ili 381...
    if digits.startswith("381"):
        return digits
    # 06x... ili 07x... → 381...
    if digits.startswith("0") and len(digits) >= 9:
        return "381" + digits[1:]
    return digits


def generate_agent_wa_link(
    buyer_phone:   str,
    buyer_name:    str,
    listing_title: str,
    agent_name:    str = "",
) -> str:
    """
    Vraća wa.me link koji agent klikne da bi kontaktirao kupca.
    Poruka je pred-popunjena na srpskom.
    """
    clean = _normalize_phone(buyer_phone)
    if not clean:
        return ""

    ime = buyer_name.split()[0] if buyer_name else "Vas"
    agent_part = f" — {agent_name}" if agent_name else ""
    listing_part = f" '{listing_title}'" if listing_title else ""

    text = (
        f"Pozdrav {ime}, javljam Vam se u vezi upita za oglas{listing_part}{agent_part}. "
        f"Kada Vam odgovara da razgovaramo?"
    )
    encoded = urllib.parse.quote(text)
    return f"https://wa.me/{clean}?text={encoded}"


def generate_buyer_wa_link(
    agent_phone: str,
    buyer_name:  str = "",
) -> str:
    """
    Link koji kupac može koristiti da kontaktira agenta direktno.
    Koristi se u automatskim email odgovorima.
    """
    clean = _normalize_phone(agent_phone)
    if not clean:
        return ""

    ime = buyer_name.split()[0] if buyer_name else "Vas"
    text = f"Pozdrav, kontaktiram Vas u vezi nekretnine — {ime}"
    encoded = urllib.parse.quote(text)
    return f"https://wa.me/{clean}?text={encoded}"
