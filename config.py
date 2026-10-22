"""
Central configuration for AI Resume Analyzer.
In production, load these values from environment variables instead of
hard-coding them here (e.g. using python-dotenv).
"""
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_dotenv(path):
    """Tiny .env reader (KEY=VALUE per line). Real environment variables win over the file."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


_load_dotenv(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = os.environ.get("RESUME_ANALYZER_SECRET_KEY", "change-this-secret-key-in-production")

DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "localhost"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", ""),
    "database": os.environ.get("DB_NAME", "resume_analyzer"),
}

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
REPORT_FOLDER = os.path.join(BASE_DIR, "reports")
ALLOWED_EXTENSIONS = {"pdf", "docx"}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB max upload size


# ---- AI features (LLM: Google Gemini) ----
# Free key: https://aistudio.google.com/app/apikey  ->  export GEMINI_API_KEY=...
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# gemini-2.5-flash-lite has the most generous free-tier limits.
# Try gemini-2.5-flash for better quality (lower free-tier limit).
# NOTE: gemini-2.5-* models are now restricted/retired for new projects (404 "no longer available").
# Use a Gemini 3.x model. If one is unavailable, the next one in LLM_FALLBACK_MODELS is tried.
LLM_MODEL = os.environ.get("LLM_MODEL", "gemini-3.1-flash-lite")
LLM_FALLBACK_MODELS = [
    m.strip() for m in os.environ.get(
        "LLM_FALLBACK_MODELS", "gemini-3.5-flash-lite,gemini-3.5-flash,gemini-2.5-flash-lite"
    ).split(",") if m.strip()
]
# Low temperature keeps the JSON output format stable (0.2-0.3 recommended).
LLM_TEMPERATURE = float(os.environ.get("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "4096"))
# Resume / JD text longer than this is truncated before being sent to the LLM.
LLM_MAX_INPUT_CHARS = 12000

# ---- GitHub cross-verifier ----
# Optional. Without a token GitHub allows only 60 requests/hour per IP.
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

# ---- Email verification (SMTP) ----
# Gmail example: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587,
# SMTP_USER=you@gmail.com, SMTP_PASSWORD=<16-char Google App Password>
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
if "gmail" in SMTP_HOST.lower():
    SMTP_PASSWORD = SMTP_PASSWORD.replace(" ", "")  # Google shows App Passwords with spaces
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER
# Connect over IPv4 only. Some Windows/ISP networks have broken IPv6 routes to Gmail,
# which shows up as "WinError 10053 connection aborted". Set SMTP_FORCE_IPV4=0 to disable.
SMTP_FORCE_IPV4 = os.environ.get("SMTP_FORCE_IPV4", "1").strip().lower() not in ("0", "false", "no")
# ---- Email via Brevo HTTP API (works even when SMTP ports are blocked) ----
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
# IMPORTANT: this sender address MUST be added & verified in Brevo
# (Brevo dashboard -> Senders, Domains & Dedicated IPs -> Senders), otherwise Brevo rejects every email.
BREVO_SENDER_EMAIL = os.environ.get("BREVO_SENDER_EMAIL", "").strip() or SMTP_USER
BREVO_SENDER_NAME = os.environ.get("BREVO_SENDER_NAME", "AI Resume Analyzer").strip()
# Dev-only escape hatch: 1 = new users are auto-verified (no email needed). Keep 0 in production.
SKIP_EMAIL_VERIFICATION = os.environ.get("SKIP_EMAIL_VERIFICATION", "0").strip().lower() in ("1", "true", "yes")
# Public base URL used inside the verification link
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000")
# Verification link validity (seconds)
VERIFY_TOKEN_MAX_AGE = 24 * 60 * 60

# Password-reset link validity (seconds) - kept short on purpose
RESET_TOKEN_MAX_AGE = 60 * 60
