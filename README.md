# CampusReview — Anonymous University Teacher Review System

A complete IDP-style web app for collecting **anonymous** student reviews of
teachers via unique form links. Built with **only**:

- Raw HTML, CSS, Vanilla JavaScript (frontend)
- Pure Python standard library (`http.server`, `sqlite3`, `datetime`, `hashlib`, `secrets`)
- SQLite (database)

No frameworks. No npm. No external libraries. No CDNs.

---

## Features

- **Admin**: secure login, create/edit/delete/block users (admins & department heads), view all forms, monitor activity logs, system analytics.
- **Department Head**: secure login, profile + password management, build review forms with multiple question types, set expiration dates, generate unique anonymous links, view per-form responses with simple analytics charts.
- **Public Student**: opens a unique form link, submits an anonymous review — no login, no account, no name collected.
- **Form builder** supports 6 question types: short text, long text, yes/no, checkbox, radio, rating (1–5).
- **Analytics**: total/active/expired forms, total submissions, average ratings, response distribution bars (pure CSS, no chart library).

---

## Technologies

| Layer    | Tech |
|----------|------|
| Frontend | HTML5, CSS3, Vanilla ES6 JavaScript |
| Backend  | Python 3 (`http.server`, `sqlite3`, `hashlib`, `secrets`, `datetime`) |
| Database | SQLite (single file: `database/campusreview.db`) |

---

## Folder Structure

```
campusreview/
├── backend/
│   ├── server.py        # HTTP server + static file serving + API dispatch
│   ├── database.py      # SQLite schema + default admin
│   ├── auth.py          # Cookie-based session management
│   ├── routes.py        # All API endpoints
│   └── utils.py         # Helpers (JSON, tokens, validation)
├── frontend/
│   ├── css/style.css
│   ├── js/common.js
│   └── pages/
│       ├── login.html
│       ├── admin.html
│       ├── head.html
│       └── review.html  # public anonymous form
├── database/
│   └── campusreview.db  # auto-created on first run
└── README.md
```

---

## Database Tables

- **admins** — admin users (username, password_hash, blocked)
- **department_heads** — head users (+ full_name, department)
- **forms** — review forms (owner_id, title, description, unique token, expires_at)
- **questions** — questions belonging to a form (qtype, label, options, required, position)
- **submissions** — anonymous submission record (form_id, submitted_at)
- **answers** — individual answers (submission_id, question_id, answer_text)
- **activity_logs** — actions taken by admins/heads

All foreign keys cascade on delete.

---

## Authentication Flow

1. User opens `/login` and chooses role (Admin or Department Head).
2. Browser sends `POST /api/login` with `{role, username, password}`.
3. Server verifies SHA-256 password hash. If OK, generates a random session id and stores it in memory.
4. Server returns a `Set-Cookie: campusreview_session=...; HttpOnly`.
5. On every subsequent request the cookie is sent back; the server looks up the session id and identifies the user.
6. `POST /api/logout` clears the cookie and deletes the session.

Public students never authenticate — they just open `/review/<token>`.

---

## Form Submission Flow

1. Department head creates a form. Server generates a unique URL-safe token and stores questions.
2. Head copies the link `http(s)://<host>/review/<token>` and shares it with students.
3. Student opens the link → frontend calls `GET /api/public/form/<token>` to load questions.
4. Student fills the form → frontend calls `POST /api/public/form/<token>` with `{answers: { questionId: value, ... }}`.
5. Server validates required fields, checks expiration, inserts a `submissions` row + one `answers` row per question. **No identifying info is stored.**

---

## How to Run

### 1. Requirements
- Python 3.8+
- No `pip install` needed — only standard library is used.

### 2. Initialize the database
```bash
cd backend
python database.py
```
This creates `database/campusreview.db` and a default admin.

### 3. Start the server
```bash
python server.py
```
Then open: <http://localhost:8000>

> The server also auto-initializes the database on first start, so step 2 is optional.

### Default Admin Credentials
- Username: `admin`
- Password: `admin123`

**Change this after first login** (create a new admin from the Users page, then delete the default).

---

## How to Deploy

The app is self-contained — anywhere Python 3 runs, it runs.

- **Local**: `python server.py`
- **VPS** (Ubuntu/Debian): copy the folder, run `python3 backend/server.py`. Use `nohup`, `tmux`, or a `systemd` unit to keep it running. Optionally put nginx in front for HTTPS.
- **Python hosting** (PythonAnywhere, Railway, etc.): point the service to `backend/server.py`, expose port 8000.

To change the port, edit `PORT = 8000` near the top of `backend/server.py`.

---

## Common Errors & Fixes

| Error | Fix |
|-------|-----|
| `Address already in use` | Port 8000 busy. Change `PORT` in `server.py` or kill the other process. |
| `sqlite3.OperationalError: unable to open database` | Make sure the `database/` folder exists or run `python database.py` first. |
| Logged out after server restart | Sessions are in-memory by design (simplicity). Log in again. |
| Form link 404 | The token is invalid or the form was deleted. |
| `This form has expired` | Department head set an expiration date in the past. |

---

## Future Improvements

- Persist sessions in the database (survive server restarts)
- Use bcrypt/argon2 for password hashing
- Rate-limiting on submissions to prevent spam
- CSV export of responses
- Email notifications when a new submission arrives
- HTTPS via reverse proxy (nginx + Let's Encrypt)
- Per-department admin scoping
