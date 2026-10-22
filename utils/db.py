"""
Database connection helper for AI Resume Analyzer.
Uses mysql-connector-python with simple context-managed helper functions.
"""
import mysql.connector
from mysql.connector import pooling
from config import DB_CONFIG

_pool = pooling.MySQLConnectionPool(
    pool_name="resume_analyzer_pool",
    pool_size=5,
    **DB_CONFIG
)


def get_connection():
    """Return a pooled MySQL connection. Caller is responsible for closing it."""
    return _pool.get_connection()


def run_query(query, params=None, fetch=False, fetch_one=False, commit=False):
    """
    Convenience helper to run a query with automatic connection handling.
    - fetch=True returns all rows as list of dicts
    - fetch_one=True returns a single row as dict
    - commit=True commits the transaction (for INSERT/UPDATE/DELETE)
    Returns lastrowid for INSERT statements when commit=True and not fetching.
    """
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(query, params or ())
        result = None
        if fetch_one:
            result = cursor.fetchone()
        elif fetch:
            result = cursor.fetchall()
        if commit:
            conn.commit()
            if not fetch and not fetch_one:
                result = cursor.lastrowid
        return result
    finally:
        cursor.close()
        conn.close()
