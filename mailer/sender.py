import os
import re
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, formatdate, make_msgid
from html.parser import HTMLParser
import config


class _HTMLToText(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in ("br", "p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self._parts.append(" ")
                self._href = href
            else:
                self._href = None
        else:
            self._href = None

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip > 0:
            self._skip -= 1
        elif tag == "a" and getattr(self, "_href", None):
            self._parts.append(f" ({self._href})")
            self._href = None
        elif tag in ("p", "div", "tr", "li", "h1", "h2", "h3", "h4"):
            self._parts.append("\n")

    def handle_data(self, data):
        if self._skip == 0:
            self._parts.append(data)

    def text(self) -> str:
        joined = "".join(self._parts)
        joined = re.sub(r"[ \t]+", " ", joined)
        joined = re.sub(r"\n{3,}", "\n\n", joined)
        return joined.strip()


def _html_to_plaintext(html: str) -> str:
    parser = _HTMLToText()
    try:
        parser.feed(html)
        return parser.text()
    except Exception:
        return re.sub(r"<[^>]+>", "", html).strip()


def send_report_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "izvestaj.pdf",
    text_body: str | None = None,
) -> bool:
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print("[EMAIL] SMTP kredencijali nisu podešeni — mejl nije poslat.")
        return False

    from_addr = config.EMAIL_FROM or smtp_user
    reply_to = getattr(config, "SUPPORT_EMAIL", None) or from_addr

    # Gmail/Workspace SMTP odbacuje ili spam-flag-uje mejl ako se From ne poklapa
    # sa SMTP nalogom (osim ako je verifikovan kao alias). Logujemo upozorenje.
    if "gmail.com" in smtp_host.lower() and from_addr.lower() != smtp_user.lower():
        print(
            f"[EMAIL] UPOZORENJE: From ({from_addr}) se ne poklapa sa SMTP_USER "
            f"({smtp_user}). Gmail će ovo verovatno baciti u spam."
        )

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(text_body or _html_to_plaintext(html_body), "plain", "utf-8"))
    alt.attach(MIMEText(html_body, "html", "utf-8"))

    if pdf_bytes:
        msg = MIMEMultipart("mixed")
        msg.attach(alt)
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(part)
    else:
        msg = alt

    msg["Subject"]    = subject
    msg["From"]       = formataddr((config.EMAIL_FROM_NAME, from_addr))
    msg["To"]         = formataddr((to_name, to_email))
    msg["Reply-To"]   = reply_to
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=from_addr.split("@", 1)[-1] or None)
    msg["MIME-Version"] = "1.0"
    msg["X-Mailer"]   = "Nekretnine Reports"
    msg["Auto-Submitted"] = "auto-generated"

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(smtp_user, smtp_pass)
            server.sendmail(from_addr, [to_email], msg.as_string())
        suffix = " + PDF" if pdf_bytes else ""
        print(f"[EMAIL] Poslat na {to_email}{suffix}")
        return True
    except Exception as e:
        print(f"[EMAIL] Greška: {e}")
        return False
