"""
database.py
-----------
Where: /backend/database.py
What:  Creates the SQLite database file and all tables for CampusReview.
Why:   We need persistent storage for admins, department heads, forms,
       questions, submissions, answers, and activity logs.

Run this file ONCE before starting the server:
    python database.py
"""

import sqlite3
import os
import hashlib
from datetime import datetime

# Path to the SQLite database file (lives in /database/campusreview.db)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "campusreview.db")
DB_PATH = os.path.abspath(DB_PATH)


def get_connection():
    """Open a new SQLite connection. Each request gets its own connection."""
    # check_same_thread=False because http.server may use threads
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    # Return rows as dict-like objects so we can do row["name"]
    conn.row_factory = sqlite3.Row
    # Enforce foreign keys (SQLite has them off by default)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def hash_password(password):
    """
    Beginner-friendly password hashing using SHA-256.
    NOTE: For a real production system you'd use bcrypt/argon2,
    but the spec says: only Python standard library.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_db():
    """Create all tables if they don't exist, and insert a default admin."""
    # Make sure the /database folder exists
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = get_connection()
    cur = conn.cursor()

    # ---- admins table ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # ---- department_heads table ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS department_heads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            blocked INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    # ---- forms table ----
    # owner_id = id of the department head who created this form
    # token    = unique random string used in the public review link
    cur.execute("""
        CREATE TABLE IF NOT EXISTS forms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            token TEXT UNIQUE NOT NULL,
            expires_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (owner_id) REFERENCES department_heads(id) ON DELETE CASCADE
        )
    """)

    # ---- questions table ----
    # qtype: 'short', 'long', 'yesno', 'checkbox', 'radio', 'rating'
    # options: JSON-ish string for checkbox/radio options (we use simple "|" separator)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id INTEGER NOT NULL,
            qtype TEXT NOT NULL,
            label TEXT NOT NULL,
            options TEXT,
            required INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (form_id) REFERENCES forms(id) ON DELETE CASCADE
        )
    """)

    # ---- submissions table ----
    # Anonymous: we only store the form_id and a timestamp.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id INTEGER NOT NULL,
            submitted_at TEXT NOT NULL,
            FOREIGN KEY (form_id) REFERENCES forms(id) ON DELETE CASCADE
        )
    """)

    # ---- answers table ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL,
            answer_text TEXT,
            FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE,
            FOREIGN KEY (question_id) REFERENCES questions(id) ON DELETE CASCADE
        )
    """)

    # ---- activity_logs table ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_role TEXT NOT NULL,
            actor_id INTEGER,
            action TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # ---- Insert a default admin if none exists ----
    cur.execute("SELECT COUNT(*) AS c FROM admins")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), datetime.utcnow().isoformat()),
        )
        print("Default admin created -> username: admin  password: admin123")

    conn.commit()
    conn.close()
    print(f"Database ready at: {DB_PATH}")


if __name__ == "__main__":
    init_db()
