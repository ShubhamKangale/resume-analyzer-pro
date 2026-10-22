# AI Resume Analyzer

A full-stack web app that scores a resume against a job description using
keyword/NLP matching, built to match the architecture in the project synopsis:

- **Front end:** HTML5, CSS3, vanilla JavaScript
- **Back end:** Python (Flask)
- **Database:** MySQL

## Project structure

```
ai_resume_analyzer/
├── app.py                 # Flask app & all routes
├── config.py               # Settings (DB creds, upload limits)
├── create_admin.py         # CLI script to create the first admin account
├── schema.sql               # MySQL schema + seed skills list
├── requirements.txt
├── utils/
│   ├── db.py                # MySQL connection pool + query helper
│   ├── parser.py             # PDF/DOCX text extraction
│   ├── matcher.py             # Keyword matching & scoring engine
│   ├── ai_features.py         # LLM tools: STAR, roadmap, interview, red flags, pitch
│   ├── github_verifier.py     # GitHub languages vs resume cross-check (no LLM)
│   └── report.py               # PDF report generation
├── templates/                    # Jinja2 HTML templates
│   ├── base.html, index.html, login.html, register.html,
│   │   upload.html, dashboard.html, admin.html
└── static/
    ├── css/style.css
    └── js/main.js, analyze.js, ai_tools.js
```

## Setup

1. **Install MySQL** and create the schema:
   ```bash
   mysql -u root -p < schema.sql
   ```

2. **Create a virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Set your API keys** (needed for the AI tools):
   ```bash
   export GEMINI_API_KEY=...        # free: https://aistudio.google.com/app/apikey
   export GITHUB_TOKEN=ghp_...      # optional, raises GitHub rate limit 60 -> 5000/hr
   ```
   Optional: `LLM_MODEL` (default `gemini-3.1-flash-lite`), `LLM_TEMPERATURE` (default 0.2).

   **Email verification (SMTP)** - new users must verify their email before logging in:
   ```bash
   export SMTP_HOST=smtp.gmail.com
   export SMTP_PORT=587
   export SMTP_USER=youraddress@gmail.com
   export SMTP_PASSWORD=your-16-char-google-app-password
   export APP_BASE_URL=http://localhost:5000
   ```
   If SMTP is not set, the verification link is printed in the server console (dev mode).

   **Set your database credentials** (or edit `config.py` directly):
   ```bash
   export DB_HOST=localhost
   export DB_USER=root
   export DB_PASSWORD=yourpassword
   export DB_NAME=resume_analyzer
   export RESUME_ANALYZER_SECRET_KEY=some-random-string
   ```

   *Existing database from an earlier version?* Run `mysql -u root -p < migration_email_verification.sql`
   once (adds the `email_verified` column and marks current users as verified).

4. **Create an admin account** (admins are auto-verified):
   ```bash
   python create_admin.py
   ```

5. **Run the app:**
   ```bash
   python app.py
   ```
   Visit `http://localhost:5000`.

## How it maps to the synopsis

| Synopsis module | File(s) |
|---|---|
| User Authentication Module | `app.py` (register/login/logout routes) |
| Resume Upload & Parsing Module | `utils/parser.py`, `/api/analyze` route |
| NLP Analysis / Matching & Scoring Module | `utils/matcher.py` |
| Report Generation Module | `utils/report.py`, `/report/<id>` route |
| Admin Module | `/admin` routes, `templates/admin.html` |
| Database Design (Chapter 4.5) | `schema.sql` |

## Notes

- Passwords are hashed with Werkzeug's `generate_password_hash` — never stored in plain text.
- Uploaded files are saved with a UUID-prefixed name to avoid collisions.
- The matching algorithm is a transparent keyword/skill-overlap scorer (see Chapter 5.3
  of the synopsis); swapping in a semantic model (e.g. Sentence-BERT) later only
  requires changing `utils/matcher.py`.

## AI career tools (shown on the results panel after an analysis)

| Feature | Endpoint | Output JSON |
|---|---|---|
| STAR Method Auto-Rewriter | `POST /api/ai/star_rewrite` | `[{original_point, rewritten_point}]` |
| Missing Skill Learning Roadmap | `POST /api/ai/roadmap` | `target_skill, week_1..week_4` |
| Mock Interviewer | `POST /api/ai/interview` | `interview_questions[]` |
| Red Flag & Buzzword Catcher | `POST /api/ai/red_flags` | `overused_buzzwords[], improvement_suggestions[]` |
| Elevator Pitch | `POST /api/ai/pitch` | `elevator_pitch` |
| GitHub Cross-Verifier (no LLM) | `POST /api/github-verify` | verified / unverified languages |

- All LLM calls use `temperature=0.2` and strict-JSON prompts; replies are parsed
  (fences stripped, one automatic retry) and normalised in `utils/ai_features.py`.
- LLM provider is Google Gemini (`google-genai` SDK) with `response_mime_type=application/json`.
- LLM outputs are cached in the `ai_feature_results` table (re-run `schema.sql`
  to create it; it is safe on an existing DB). "Regenerate" bypasses the cache.
- GitHub check uses `requests.get("https://api.github.com/users/{username}/repos")`,
  skips forks, and compares each repo's `language` field with languages found in the resume.

## Email verification

`/register` -> account created with `email_verified=0` -> signed link emailed (`/verify/<token>`,
valid 24h) -> login is blocked until verified. `/resend-verification` sends a fresh link
(and never reveals whether an email is registered). Tokens are signed with `SECRET_KEY`
(itsdangerous), so set a strong `RESUME_ANALYZER_SECRET_KEY` in production.

## Forgot password

`/forgot-password` -> user enters email -> signed reset link emailed (`/reset-password/<token>`,
valid 1 hour) -> user sets a new password (min 6 chars, must be confirmed).

- Same response whether or not the email exists (no account enumeration).
- Links are **single-use**: the token embeds a fingerprint of the current password hash,
  so once the password changes the old link stops working. No extra DB column is needed.
- Verification and reset tokens use different salts, so one can't be used as the other.
- Completing a reset also marks the email as verified.
- Without SMTP configured, the reset link is printed in the server console (dev mode).
- Admins can use it too; `reset_password.py`-style CLI reset is no longer required.

## Email troubleshooting

- No SMTP settings = **no email is sent**; the link is printed in the server terminal and the page says so.
- Put settings in a `.env` file next to `app.py` (copy `.env.example`). It is loaded automatically,
  so you don't have to re-export variables every time you open a terminal.
- Run `python test_email.py` to send a real test email and get a plain-language diagnosis
  (wrong app password, 2-step verification off, blocked port, etc.).
- Gmail needs a 16-character **App Password** (myaccount.google.com/apppasswords), not your normal password.
- Check the Spam folder, and keep `.env` private (it is in `.gitignore`).

- Connection errors like `WinError 10053`: the app connects to Gmail over **IPv4 only** by default
  (`SMTP_FORCE_IPV4=1`), which fixes broken-IPv6 networks. `python test_email.py` tries both modes
  and tells you which one works. If port 587 is blocked, try `SMTP_PORT=465`, or a mobile hotspot.

## Theme

The UI uses a 4-colour palette: black `#0B0B0B`, cream `#F1EFEA`, gray `#A8A5A5`, orange `#FF6A00`
(thick borders, offset shadows, pill buttons). All colours are CSS variables at the top of
`static/css/style.css`, so the whole look can be changed in one place.


## Email (Brevo API) - quick fix guide

`.env` needs:
```
BREVO_API_KEY=xkeysib-...
BREVO_SENDER_EMAIL=<an address verified in Brevo>
```
Brevo -> Senders, Domains & Dedicated IPs -> Senders -> add the address and click the
confirmation mail. Test with `python test_email.py you@example.com` (prints Brevo's exact error).
If Brevo -> Security -> "Authorized IPs" is enabled, add your IP or disable it.
Stuck users: `python verify_user.py user@example.com`. Dev shortcut: `SKIP_EMAIL_VERIFICATION=1`.
