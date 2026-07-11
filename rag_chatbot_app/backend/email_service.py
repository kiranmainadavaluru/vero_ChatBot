"""
Sends verification emails via SMTP.

If SMTP_HOST isn't configured (the default on a fresh clone), this
falls back to printing the verification link to the console instead
of failing - so registration still works end-to-end on a laptop with
zero email setup. Set SMTP_HOST/SMTP_USER/SMTP_PASSWORD in .env to
actually deliver mail (see config.py for the Gmail example).
"""
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config


def send_verification_email(to_email, token):
    link = f"{config.FRONTEND_URL}/?verify_token={token}"

    if not config.SMTP_HOST:
        print("\n" + "=" * 60)
        print(f"📧 [dev mode - no SMTP configured] Verification link for {to_email}:")
        print(f"   {link}")
        print("=" * 60 + "\n")
        return

    subject = "Verify your Vero account"
    body = (
        "Hi,\n\n"
        "Click the link below to verify your email and activate your Vero account:\n\n"
        f"{link}\n\n"
        f"This link expires in {config.EMAIL_VERIFICATION_EXPIRY_HOURS} hours.\n\n"
        "If you didn't create this account, you can ignore this email."
    )

    msg = MIMEMultipart()
    msg["From"] = config.SMTP_FROM
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
            server.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [to_email], msg.as_string())
    except Exception as e:
        # Don't let a flaky SMTP server break registration - log it
        # and let the user hit "resend" once mail is working again.
        print(f"⚠️  Could not send verification email to {to_email}: {e}")
