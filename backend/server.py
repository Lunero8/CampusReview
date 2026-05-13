"""
server.py
---------
Where: /backend/server.py
What:  The actual HTTP server. Built on Python's http.server (standard library).
Why:   Serves both:
         1. Static frontend files (HTML, CSS, JS) from /frontend
         2. JSON API endpoints defined in routes.py

Run:
    python server.py
Then open:
    http://localhost:8000
"""

import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import database
import routes

# Folder that contains all frontend files
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

PORT = 8000

# Map of URL path -> safe relative file path inside /frontend
PAGE_ROUTES = {
    "/": "pages/login.html",
    "/login": "pages/login.html",
    "/admin": "pages/admin.html",
    "/head": "pages/head.html",
    # /review/<token> handled separately (regex)
}

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript; charset=utf-8",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".svg":  "image/svg+xml",
    ".ico":  "image/x-icon",
}


class Handler(BaseHTTPRequestHandler):
    # Quieter logs
    def log_message(self, fmt, *args):
        print("[server]", self.address_string(), fmt % args)

    # ---------- routing ----------

    def do_GET(self):
        path = self.path.split("?", 1)[0]

        # API
        if path.startswith("/api/"):
            return self._dispatch_api("GET", path)

        # Public review form: /review/<token>  -> serve review.html
        if re.match(r"^/review/[A-Za-z0-9_\-]+$", path):
            return self._serve_file("pages/review.html")

        # Page routes
        if path in PAGE_ROUTES:
            return self._serve_file(PAGE_ROUTES[path])

        # Static asset under /css /js etc.
        return self._serve_static(path.lstrip("/"))

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            return self._dispatch_api("POST", path)
        self.send_error(404)

    def do_PUT(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            return self._dispatch_api("PUT", path)
        self.send_error(404)

    def do_DELETE(self):
        path = self.path.split("?", 1)[0]
        if path.startswith("/api/"):
            return self._dispatch_api("DELETE", path)
        self.send_error(404)

    # ---------- API dispatch ----------

    def _dispatch_api(self, method, path):
        try:
            # auth
            if method == "POST" and path == "/api/login":   return routes.login(self)
            if method == "POST" and path == "/api/logout":  return routes.logout(self)
            if method == "GET"  and path == "/api/me":      return routes.me(self)

            # admin
            if method == "POST" and path == "/api/admin/users":     return routes.admin_create_user(self)
            if method == "GET"  and path == "/api/admin/users":     return routes.admin_list_users(self)

            m = re.match(r"^/api/admin/users/(admin|head)/(\d+)$", path)
            if m and method == "PUT":    return routes.admin_update_user(self, m.group(1), int(m.group(2)))
            if m and method == "DELETE": return routes.admin_delete_user(self, m.group(1), int(m.group(2)))

            if method == "GET" and path == "/api/admin/forms":     return routes.admin_all_forms(self)
            if method == "GET" and path == "/api/admin/analytics": return routes.admin_analytics(self)
            if method == "GET" and path == "/api/admin/logs":      return routes.admin_logs(self)

            # head
            if method == "PUT"  and path == "/api/head/profile":  return routes.head_update_profile(self)
            if method == "PUT"  and path == "/api/head/password": return routes.head_change_password(self)
            if method == "POST" and path == "/api/head/forms":    return routes.head_create_form(self)
            if method == "GET"  and path == "/api/head/forms":    return routes.head_list_forms(self)

            m = re.match(r"^/api/head/forms/(\d+)$", path)
            if m and method == "PUT":    return routes.head_update_form(self, int(m.group(1)))
            if m and method == "DELETE": return routes.head_delete_form(self, int(m.group(1)))

            m = re.match(r"^/api/head/forms/(\d+)/responses$", path)
            if m and method == "GET":    return routes.head_form_responses(self, int(m.group(1)))

            if method == "GET" and path == "/api/head/analytics": return routes.head_analytics(self)

            # public
            m = re.match(r"^/api/public/form/([A-Za-z0-9_\-]+)$", path)
            if m and method == "GET":  return routes.public_get_form(self, m.group(1))
            if m and method == "POST": return routes.public_submit_form(self, m.group(1))

            self.send_error(404, "API endpoint not found")
        except Exception as e:
            print("API error:", e)
            self.send_error(500, "Internal server error")

    # ---------- static ----------

    def _serve_file(self, rel_path):
        full = os.path.join(FRONTEND_DIR, rel_path)
        if not os.path.isfile(full):
            return self.send_error(404)
        ext = os.path.splitext(full)[1].lower()
        ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_static(self, rel_path):
        # Prevent directory traversal
        safe = os.path.normpath(rel_path)
        if safe.startswith("..") or os.path.isabs(safe):
            return self.send_error(403)
        full = os.path.join(FRONTEND_DIR, safe)
        if os.path.isfile(full):
            return self._serve_file(safe)
        self.send_error(404)


def main():
    # Make sure DB exists
    database.init_db()
    print(f"Serving CampusReview on http://localhost:{PORT}")
    print(f"Frontend dir: {FRONTEND_DIR}")
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()


if __name__ == "__main__":
    main()
