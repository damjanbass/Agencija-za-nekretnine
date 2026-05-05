import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config


def send_report_email(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """
    Šalje HTML izveštaj mejlom.
    Podržava SendGrid SMTP i Gmail SMTP.
    Podesi SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS u environment promenljivama.
    """
    import os

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")

    if not smtp_user or not smtp_pass:
        print(f"[EMAIL] SMTP kredencijali nisu podešeni — mejl nije poslat.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"{config.EMAIL_FROM_NAME} <{config.EMAIL_FROM}>"
    msg["To"]      = f"{to_name} <{to_email}>"

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(config.EMAIL_FROM, [to_email], msg.as_string())
        print(f"[EMAIL] Poslat na {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] Greška: {e}")
        return False
