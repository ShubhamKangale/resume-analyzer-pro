"""
Manually mark a user as email-verified (for users stuck at the login screen).
Usage:  python verify_user.py user@example.com
"""
import sys
from utils.db import run_query

if len(sys.argv) < 2:
    sys.exit("Usage: python verify_user.py user@example.com")
email = sys.argv[1].strip().lower()
user = run_query("SELECT user_id FROM users WHERE email = %s", (email,), fetch_one=True)
if not user:
    sys.exit("No user with that email.")
run_query("UPDATE users SET email_verified = 1 WHERE user_id = %s", (user["user_id"],), commit=True)
print(f"{email} is now verified - they can log in.")
