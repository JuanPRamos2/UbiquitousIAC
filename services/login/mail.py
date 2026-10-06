import json
import smtplib
from email.message import EmailMessage

import config


def send_verification(to_email, verify_url, as_json=False):
    if not config.MAIL_HOST:
        return False
    payload = {
        "code": "EMAIL_VERIFICATION_REQUIRED",
        "to": to_email,
        "subject": "Verifica tu correo · Librería",
        "userExists": True,
        "emailVerified": False,
        "expiresInHours": config.VERIFICATION_HOURS,
        "verify": {"href": verify_url, "method": "GET"},
        "message": "Confirma tu correo con verify.href. El usuario ya existe en PostgreSQL.",
    }
    message = EmailMessage()
    message["Subject"] = payload["subject"]
    message["From"] = config.MAIL_FROM
    message["To"] = to_email
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    if as_json:
        message.set_content(body, subtype="json")
    else:
        message.set_content(body + "\n")
    with smtplib.SMTP(config.MAIL_HOST, config.MAIL_PORT, timeout=12) as smtp:
        if config.MAIL_STARTTLS:
            smtp.starttls()
        if config.MAIL_USER:
            smtp.login(config.MAIL_USER, config.MAIL_PASSWORD)
        smtp.send_message(message)
    return True
