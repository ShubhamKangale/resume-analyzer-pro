"""
Brevo email test.  Usage:   python test_email.py someone@example.com
Prints Brevo's exact answer, so you can see WHY an email fails.
"""
import sys
import requests
from config import BREVO_API_KEY, BREVO_SENDER_EMAIL, BREVO_SENDER_NAME

if len(sys.argv) < 2:
    sys.exit("Usage: python test_email.py recipient@example.com")
if not BREVO_API_KEY:
    sys.exit("BREVO_API_KEY missing in .env")

print(f"Sender: {BREVO_SENDER_NAME} <{BREVO_SENDER_EMAIL}>")
r = requests.post(
    "https://api.brevo.com/v3/smtp/email",
    headers={"accept": "application/json", "api-key": BREVO_API_KEY, "content-type": "application/json"},
    json={
        "sender": {"name": BREVO_SENDER_NAME, "email": BREVO_SENDER_EMAIL},
        "to": [{"email": sys.argv[1]}],
        "subject": "Brevo test - AI Resume Analyzer",
        "htmlContent": "<p>Brevo email is working.</p>",
    },
    timeout=20,
)
print("HTTP", r.status_code, r.text)
print("OK - check inbox/spam" if r.status_code in (200, 201, 202) else "FAILED - see message above")
