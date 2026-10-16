"""Tool: send an email (used only after the traveller approves).

If SMTP is not configured, nothing is sent and the app shows the link to copy instead.
"""
import smtplib
from email.message import EmailMessage

from .. import config


def email_configured() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD)


def send_email(to: str, subject: str, text: str) -> tuple[bool, str]:
    if not email_configured():
        return False, "Email is not configured; share the link manually."
    msg = EmailMessage()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.send_message(msg)
        return True, f"Email sent to {to}."
    except (smtplib.SMTPException, OSError) as e:
        return False, f"Email failed ({e.__class__.__name__}); share the link manually."
