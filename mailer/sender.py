import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config


def send_report_email(
    to_email: str,
    to_name: str,
    subject: str,
    html_body: str,
    pdf_bytes: bytes | None = None,
    pdf_filename: str = "izvestaj.pdf",
) -> bool:
    import os

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print("[EMAIL] SMTP kredencijali nisu podešeni — mejl nije poslat.")
        return False

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM}>"
    msg["To"]      = f"{to_name} <{to_email}>"

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if pdf_bytes:
        part = MIMEBase("application", "pdf")
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
        msg.attach(part)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(config.EMAIL_FROM, [to_email], msg.as_string())
        suffix = " + PDF" if pdf_bytes else ""
        print(f"[EMAIL] Poslat na {to_email}{suffix}")
        return True
    except Exception as e:
        print(f"[EMAIL] Greška: {e}")
        return False
