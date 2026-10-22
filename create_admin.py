"""
One-time CLI helper to create the first administrator account.

Usage:
    python create_admin.py
"""
import getpass
from werkzeug.security import generate_password_hash
from utils.db import run_query


def main():
    print("=== Create AI Resume Analyzer Admin Account ===")
    name = input("Admin name: ").strip()
    email = input("Admin email: ").strip().lower()
    password = getpass.getpass("Admin password: ")

    existing = run_query("SELECT user_id FROM users WHERE email = %s", (email,), fetch_one=True)
    if existing:
        print("A user with this email already exists.")
        return

    password_hash = generate_password_hash(password)
    run_query(
        "INSERT INTO users (name, email, password_hash, role, email_verified) VALUES (%s, %s, %s, 'admin', 1)",
        (name, email, password_hash),
        commit=True,
    )
    print(f"Admin account created for {email}. You can now log in from /login.")


if __name__ == "__main__":
    main()
