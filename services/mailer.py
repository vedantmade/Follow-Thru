"""Email via Gmail SMTP. Every message is also logged in the outbox table,
so the app can show it even when sending is off or the person has no email.

.env:  GMAIL_USER=agent@gmail.com   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
Demo:  pass override_to="judge@x.com" to route every email to one address.
"""
import os
import smtplib
from email.message import EmailMessage

from . import db


def send(recipient_name, subject, body, override_to=None):
    """Returns a status string: 'sent to …', 'outbox only (…)'."""
    to = override_to or db.get_email(recipient_name)
    user, pwd = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD")

    if not to:
        status = "outbox only (no email on file)"
    elif not (user and pwd):
        status = "outbox only (email sending not configured)"
    else:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = f"Meeting Agent <{user}>", to, subject
        msg.set_content(body)
        try:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as s:
                s.login(user, pwd.replace(" ", ""))
                s.send_message(msg)
            status = f"sent to {to}"
        except Exception as e:  # noqa: BLE001
            status = f"outbox only (send failed: {e})"

    db.log_outbox(recipient_name, to, subject, body, status)
    return status
