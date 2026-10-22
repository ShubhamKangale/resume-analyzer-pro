import hashlib
import hmac
import html
import os
import re
import requests

from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

from config import (
    SECRET_KEY, APP_BASE_URL, VERIFY_TOKEN_MAX_AGE, RESET_TOKEN_MAX_AGE,
    BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME,
)

_verify_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="email-verify")
_reset_serializer = URLSafeTimedSerializer(SECRET_KEY, salt="password-reset")

# Pragmatic format check (the real proof is the email itself)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")


def is_valid_email_format(email):
    return bool(email) and len(email) <= 150 and bool(EMAIL_RE.match(email))


def smtp_configured():
    # We use the Brevo HTTP API (not SMTP) -- configured when key + sender are present
    return bool(BREVO_API_KEY and BREVO_SENDER_EMAIL)


# ----------------------------------------------------------------
# Email-verification tokens
# ----------------------------------------------------------------
def make_token(email):
    return _verify_serializer.dumps(email)


def read_token(token):
    """Return (email, error) where error is None, 'expired' or 'invalid'."""
    try:
        return _verify_serializer.loads(token, max_age=VERIFY_TOKEN_MAX_AGE), None
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"


# ----------------------------------------------------------------
# Password-reset tokens
# ----------------------------------------------------------------
def _fingerprint(password_hash):
    return hashlib.sha256((password_hash or "").encode()).hexdigest()[:16]


def make_reset_token(email, password_hash):
    return _reset_serializer.dumps({"e": email, "f": _fingerprint(password_hash)})


def read_reset_token(token):
    """Return (payload, error). payload = {'e': email, 'f': fingerprint}."""
    try:
        payload = _reset_serializer.loads(token, max_age=RESET_TOKEN_MAX_AGE)
    except SignatureExpired:
        return None, "expired"
    except BadSignature:
        return None, "invalid"
    if not isinstance(payload, dict) or "e" not in payload or "f" not in payload:
        return None, "invalid"
    return payload, None


def reset_token_matches(payload, current_password_hash):
    """True only if the password has NOT changed since the token was issued."""
    return hmac.compare_digest(payload["f"], _fingerprint(current_password_hash))


# ----------------------------------------------------------------
# Sending (Brevo HTTP API)
# ----------------------------------------------------------------
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
_BREVO_HINTS = {
    400: "Most common cause: the sender email is not verified in Brevo. Add it under "
         "Senders, Domains & Dedicated IPs -> Senders and click the verification mail.",
    401: "API key is wrong/revoked, or Brevo 'Authorized IPs' is on and blocks this IP "
         "(Brevo -> Security -> Authorized IPs -> deactivate or add your IP).",
    403: "Your Brevo account is not activated for sending yet - contact Brevo support, "
         "or check the account for a pending validation.",
    429: "Brevo rate/daily limit reached (free plan = 300 emails/day).",
}
def _send(to_email, subject, text_body, html_body, dev_label, link):
    """Send via Brevo HTTP API, or print the link in dev mode. Returns True on success."""
    if not smtp_configured():
        print(f"\n[DEV] Brevo not configured (BREVO_API_KEY / BREVO_SENDER_EMAIL). "
              f"{dev_label} for {to_email}:\n{link}\n")
        return True

    headers = {
        "accept": "application/json",
        "api-key": BREVO_API_KEY,
        "content-type": "application/json",
    }
    payload = {
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_body,
        "textContent": text_body,
    }

    try:
        response = requests.post(BREVO_URL, headers=headers, json=payload, timeout=20)
    except requests.RequestException as exc:
        print(f"[EMAIL ERROR] network problem sending to {to_email}: {exc}")
        return False

    if response.status_code in (200, 201, 202):
        return True

    print(f"[EMAIL ERROR] Brevo rejected the email to {to_email} "
          f"(HTTP {response.status_code}): {response.text}")
    hint = _BREVO_HINTS.get(response.status_code)
    if hint:
        print(f"[EMAIL HINT] {hint}")
    # Always print the link too so a developer can finish the flow while email is being fixed
    print(f"[DEV] {dev_label} for {to_email}:\n{link}\n")
    return False


def _button(link, label):
    return (f'<p><a href="{link}" style="background:#1F7A5C;color:#fff;padding:10px 18px;'
            f'border-radius:6px;text-decoration:none">{label}</a></p>')


def send_verification_email(name, email):
    link = f"{APP_BASE_URL.rstrip('/')}/verify/{make_token(email)}"
    hours = VERIFY_TOKEN_MAX_AGE // 3600
    text = (
        f"Hi {name},\n\nThanks for registering at AI Resume Analyzer. Please confirm your email "
        f"address by opening this link (valid for {hours} hours):\n\n{link}\n\n"
        f"If you didn't create this account, you can ignore this email."
    )
    body = (
        f"<p>Hi {html.escape(name)},</p>"
        f"<p>Thanks for registering at <b>AI Resume Analyzer</b>. Please confirm your email address:</p>"
        f"{_button(link, 'Verify my email')}"
        f"<p>Or paste this link into your browser:<br>{link}</p>"
        f"<p>This link is valid for {hours} hours. If you didn't create this account, ignore this email.</p>"
    )
    return _send(email, "Verify your email - AI Resume Analyzer", text, body, "Verification link", link)


def send_password_reset_email(name, email, password_hash):
    link = f"{APP_BASE_URL.rstrip('/')}/reset-password/{make_reset_token(email, password_hash)}"
    minutes = RESET_TOKEN_MAX_AGE // 60
    text = (
        f"Hi {name},\n\nWe received a request to reset your AI Resume Analyzer password. "
        f"Open this link to choose a new one (valid for {minutes} minutes, works once):\n\n{link}\n\n"
        f"If you didn't ask for this, you can safely ignore this email - your password won't change."
    )
    body = (
        f"<p>Hi {html.escape(name)},</p>"
        f"<p>We received a request to reset your <b>AI Resume Analyzer</b> password.</p>"
        f"{_button(link, 'Reset my password')}"
        f"<p>Or paste this link into your browser:<br>{link}</p>"
        f"<p>This link is valid for {minutes} minutes and works only once. "
        f"If you didn't ask for this, ignore this email - your password won't change.</p>"
    )
    return _send(email, "Reset your password - AI Resume Analyzer", text, body, "Password reset link", link)