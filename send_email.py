import os
import smtplib
from email.message import EmailMessage


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_name: str,
    from_email: str,
    reply_to: str,
) -> bool:
    host = os.environ["BREVO_SMTP_HOST"]
    port = int(os.environ["BREVO_SMTP_PORT"])
    login = os.environ["BREVO_SMTP_LOGIN"]
    key = os.environ["BREVO_SMTP_KEY"]

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = f"{from_name} <{from_email}>"
    msg["To"] = to_email
    msg["Reply-To"] = reply_to
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(login, key)
            smtp.send_message(msg)
        return True
    except Exception as exc:
        print(f"[send_email] ERROR sending to {to_email}: {exc}")
        return False
