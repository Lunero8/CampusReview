"""
auth.py
-------
Where: /backend/auth.py
What:  Simple cookie-based session management for admins and department heads.
Why:   We need to know "who is logged in" across requests without using any
       framework. We store sessions in memory (a Python dict).

NOTE: In-memory sessions reset when the server restarts. That's fine for a
beginner / IDP project. For production you'd persist sessions in the DB.
"""

import secrets
from http import cookies

# In-memory session store: { session_id: {"role": "admin"/"head", "user_id": int} }
SESSIONS = {}

COOKIE_NAME = "campusreview_session"


def create_session(role, user_id):
    """Generate a random session id and remember which user it belongs to."""
    sid = secrets.token_hex(32)
    SESSIONS[sid] = {"role": role, "user_id": user_id}
    return sid


def destroy_session(sid):
    """Remove a session (used on logout)."""
    SESSIONS.pop(sid, None)


def get_session_from_headers(headers):
    """
    Read the Cookie header from an incoming request and return
    the matching session dict, or None if not logged in.
    """
    raw_cookie = headers.get("Cookie")
    if not raw_cookie:
        return None
    c = cookies.SimpleCookie()
    c.load(raw_cookie)
    if COOKIE_NAME not in c:
        return None
    sid = c[COOKIE_NAME].value
    return SESSIONS.get(sid), sid


def build_set_cookie(sid):
    """Build a Set-Cookie header value to log a user in."""
    # HttpOnly = JS can't read it (basic XSS protection)
    # Path=/   = cookie is sent on every page
    # Max-Age  = 8 hours
    return f"{COOKIE_NAME}={sid}; HttpOnly; Path=/; Max-Age=28800; SameSite=Lax"


def build_clear_cookie():
    """Build a Set-Cookie header that deletes the session cookie."""
    return f"{COOKIE_NAME}=; HttpOnly; Path=/; Max-Age=0; SameSite=Lax"
