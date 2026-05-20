"""
Čita email inbox agencije via IMAP i parsira upite sa portala nekretnina.
Podržani portali: Halo Oglasi, 4Zida, Nekretnine.rs
"""

import email
import imaplib
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.header import decode_header
from typing import Optional


# Prepoznajemo portal po From adresi
PORTAL_SENDERS = {
    "halooglasi.com":  "halo_oglasi",
    "halo-oglasi.com": "halo_oglasi",
    "4zida.rs":        "4zida",
    "cetirizida.rs":   "4zida",
    "nekretnine.rs":   "nekretnine_rs",
}

# Regex za srpski/međunarodni broj telefona
_PHONE_RE = re.compile(
    r"(?:Tel(?:efon)?|Phone|Mob(?:ile)?|Kontakt)?[:\s]*"
    r"(\+?381[\s\-]?\d[\s\-]?\d{3}[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
    r"|0\d{1,2}[\s\-/]?\d{3,4}[\s\-/]?\d{3,4})",
    re.IGNORECASE,
)

# Regex za ime kupca
_NAME_PATTERNS = [
    re.compile(r"(?:Ime|Korisnik|Kontakt|Od|From|Name)[:\s]+([A-ZŠĐČĆŽ][a-zšđčćžA-ZŠĐČĆŽ\-']{1,30}(?:\s[A-ZŠĐČĆŽ][a-zšđčćžA-ZŠĐČĆŽ\-']{1,30})+)", re.UNICODE),
    re.compile(r"(?:upit od|poruku od|kontaktira vas|poslao poruku)\s+([A-ZŠĐČĆŽ][a-zšđčćžA-ZŠĐČĆŽ\-']{1,30}(?:\s[A-ZŠĐČĆŽ][a-zšđčćžA-ZŠĐČĆŽ\-']{1,30})+)", re.IGNORECASE | re.UNICODE),
]

# Regex za email kupca
_EMAIL_RE = re.compile(
    r"(?:E-?mail|Email)[:\s]+([a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,})",
    re.IGNORECASE,
)

# Regex za poruku kupca
_MSG_PATTERNS = [
    re.compile(r"(?:Poruka|Message|Sadržaj|Tekst)[:\s]*[\r\n]+[\"\']?(.*?)[\"\']?(?:\r\n\r\n|Oglas|Link|$)", re.DOTALL | re.IGNORECASE),
    re.compile(r"\"(.*?)\"", re.DOTALL),
]

# Regex za URL oglasa
_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:halooglasi\.com|4zida\.rs|nekretnine\.rs)/\S+",
    re.IGNORECASE,
)


@dataclass
class ParsedLead:
    source:              str
    external_message_id: str
    buyer_name:          Optional[str] = None
    buyer_phone:         Optional[str] = None
    buyer_email:         Optional[str] = None
    message:             Optional[str] = None
    listing_title:       Optional[str] = None
    listing_url:         Optional[str] = None
    received_at:         Optional[datetime] = None
    raw_subject:         str = ""
    raw_body:            str = ""


def _decode_header_str(raw: str) -> str:
    parts = decode_header(raw)
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def _get_text_body(msg: email.message.Message) -> str:
    body_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    body_parts.append(payload.decode(charset, errors="replace"))
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            body_parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(body_parts)


def _detect_source(from_addr: str) -> Optional[str]:
    from_lower = from_addr.lower()
    for domain, source in PORTAL_SENDERS.items():
        if domain in from_lower:
            return source
    return None


def _clean_phone(raw: str) -> str:
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("0") and not digits.startswith("+"):
        digits = "+381" + digits[1:]
    return digits


def _extract_listing_title_from_subject(subject: str) -> str:
    # Ukloni standardne prefikse portala
    for prefix in [
        r"Nova poruka.*?oglas[:\s]+[\"']?",
        r"Novi upit.*?oglas[:\s]+[\"']?",
        r"Poruka za oglas[:\s]+[\"']?",
        r"Upit za oglas[:\s]+[\"']?",
        r"Kontakt.*?oglas[:\s]+[\"']?",
    ]:
        cleaned = re.sub(prefix, "", subject, flags=re.IGNORECASE).strip().strip("\"'")
        if cleaned and cleaned != subject.strip():
            return cleaned[:200]
    return subject.strip()[:200]


def _parse_body(body: str, subject: str, source: str) -> dict:
    result: dict = {}

    # Ime
    for pattern in _NAME_PATTERNS:
        m = pattern.search(body)
        if m:
            result["buyer_name"] = m.group(1).strip()
            break

    # Telefon
    m = _PHONE_RE.search(body)
    if m:
        result["buyer_phone"] = _clean_phone(m.group(1))

    # Email kupca
    m = _EMAIL_RE.search(body)
    if m:
        result["buyer_email"] = m.group(1).strip()

    # Poruka
    for pattern in _MSG_PATTERNS:
        m = pattern.search(body)
        if m:
            msg_text = m.group(1).strip()
            if len(msg_text) > 10:
                result["message"] = msg_text[:1000]
                break

    # URL oglasa
    m = _URL_RE.search(body)
    if m:
        result["listing_url"] = m.group(0)

    # Naslov oglasa
    result["listing_title"] = _extract_listing_title_from_subject(subject)

    return result


def parse_portal_emails(
    imap_host:   str,
    imap_port:   int,
    imap_user:   str,
    imap_pass:   str,
    imap_folder: str = "INBOX",
    mark_seen:   bool = True,
) -> list[ParsedLead]:
    """
    Konektuje se na IMAP, čita nepročitane mejlove od portala,
    parsira ih i vraća listu ParsedLead objekata.
    """
    leads: list[ParsedLead] = []

    try:
        conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        conn.login(imap_user, imap_pass)
        conn.select(imap_folder)
    except Exception as e:
        print(f"    [IMAP] Konekcija neuspešna ({imap_host}): {e}")
        return leads

    try:
        # Traži nepročitane od poznatih portala
        _, msg_nums = conn.search(None, "UNSEEN")
        num_list = msg_nums[0].split() if msg_nums[0] else []

        for num in num_list:
            try:
                _, data = conn.fetch(num, "(RFC822)")
                raw = data[0][1]
                msg = email.message_from_bytes(raw)

                from_addr = msg.get("From", "")
                source = _detect_source(from_addr)
                if not source:
                    continue  # Nije portal upit

                subject = _decode_header_str(msg.get("Subject", ""))
                msg_id  = msg.get("Message-ID", "") or str(uuid.uuid4())

                # Datum primanja
                date_str = msg.get("Date", "")
                received_at: Optional[datetime] = None
                try:
                    from email.utils import parsedate_to_datetime
                    received_at = parsedate_to_datetime(date_str).astimezone(timezone.utc)
                except Exception:
                    received_at = datetime.now(timezone.utc)

                body = _get_text_body(msg)
                parsed = _parse_body(body, subject, source)

                lead = ParsedLead(
                    source=source,
                    external_message_id=msg_id.strip("<>"),
                    buyer_name=parsed.get("buyer_name"),
                    buyer_phone=parsed.get("buyer_phone"),
                    buyer_email=parsed.get("buyer_email"),
                    message=parsed.get("message"),
                    listing_title=parsed.get("listing_title"),
                    listing_url=parsed.get("listing_url"),
                    received_at=received_at,
                    raw_subject=subject,
                    raw_body=body[:2000],
                )
                leads.append(lead)

                if mark_seen:
                    conn.store(num, "+FLAGS", "\\Seen")

            except Exception as e:
                print(f"    [IMAP] Greška pri parsiranju mejla {num}: {e}")
                continue

    finally:
        try:
            conn.logout()
        except Exception:
            pass

    return leads
