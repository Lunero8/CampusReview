"""
utils.py
--------
Where: /backend/utils.py
What:  Small helper functions shared by the server.
"""

import json
import secrets


def json_response(handler, status, payload, extra_headers=None):
    """Send a JSON HTTP response from a BaseHTTPRequestHandler."""
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    if extra_headers:
        for k, v in extra_headers:
            handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)


def read_json_body(handler):
    """Parse JSON from the request body. Returns {} if empty/invalid."""
    length = int(handler.headers.get("Content-Length") or 0)
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def make_token():
    """Random URL-safe token for unique form links."""
    return secrets.token_urlsafe(16)


def clean_str(value, max_len=500):
    """Trim a string and cap length. Basic input validation."""
    if value is None:
        return ""
    s = str(value).strip()
    return s[:max_len]
