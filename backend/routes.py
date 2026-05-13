"""
routes.py
---------
Where: /backend/routes.py
What:  All API endpoints. Each function takes the HTTP handler and does its job.
Why:   Keeps server.py tiny. Server.py just dispatches paths to functions here.

API map:
  POST /api/login                       -> {role, username, password}
  POST /api/logout                      -> logout
  GET  /api/me                          -> current session

  Admin only:
  POST /api/admin/users                 -> create admin or head
  GET  /api/admin/users                 -> list all users
  PUT  /api/admin/users/<role>/<id>     -> edit / block / unblock / reset password
  DELETE /api/admin/users/<role>/<id>   -> delete
  GET  /api/admin/forms                 -> all forms (monitoring)
  GET  /api/admin/analytics             -> system analytics
  GET  /api/admin/logs                  -> activity logs

  Head only:
  PUT  /api/head/profile                -> update profile
  PUT  /api/head/password               -> change password
  POST /api/head/forms                  -> create form (with questions)
  GET  /api/head/forms                  -> list own forms
  PUT  /api/head/forms/<id>             -> edit form
  DELETE /api/head/forms/<id>           -> delete form
  GET  /api/head/forms/<id>/responses   -> submissions + answers
  GET  /api/head/analytics              -> own analytics

  Public:
  GET  /api/public/form/<token>         -> get form for student
  POST /api/public/form/<token>         -> submit anonymous answers
"""

from datetime import datetime
from database import get_connection, hash_password
from auth import (
    create_session, destroy_session, get_session_from_headers,
    build_set_cookie, build_clear_cookie,
)
from utils import json_response, read_json_body, make_token, clean_str


# ---------- helpers ----------

def log_action(actor_role, actor_id, action):
    conn = get_connection()
    conn.execute(
        "INSERT INTO activity_logs (actor_role, actor_id, action, created_at) VALUES (?,?,?,?)",
        (actor_role, actor_id, action, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def require_session(handler, role=None):
    """Return session dict or send 401 and return None."""
    res = get_session_from_headers(handler.headers)
    if not res or not res[0]:
        json_response(handler, 401, {"error": "Not logged in"})
        return None
    sess, _sid = res
    if role and sess["role"] != role:
        json_response(handler, 403, {"error": "Forbidden"})
        return None
    return sess


# ---------- auth ----------

def login(handler):
    data = read_json_body(handler)
    role = data.get("role")
    username = clean_str(data.get("username"), 100)
    password = data.get("password") or ""

    if role not in ("admin", "head") or not username or not password:
        return json_response(handler, 400, {"error": "Missing fields"})

    table = "admins" if role == "admin" else "department_heads"
    conn = get_connection()
    row = conn.execute(
        f"SELECT * FROM {table} WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if not row or row["password_hash"] != hash_password(password):
        return json_response(handler, 401, {"error": "Invalid credentials"})
    if row["blocked"]:
        return json_response(handler, 403, {"error": "Account is blocked"})

    sid = create_session(role, row["id"])
    log_action(role, row["id"], "login")
    json_response(handler, 200, {"ok": True, "role": role, "username": username},
                  extra_headers=[("Set-Cookie", build_set_cookie(sid))])


def logout(handler):
    res = get_session_from_headers(handler.headers)
    if res and res[1]:
        destroy_session(res[1])
    json_response(handler, 200, {"ok": True},
                  extra_headers=[("Set-Cookie", build_clear_cookie())])


def me(handler):
    res = get_session_from_headers(handler.headers)
    if not res or not res[0]:
        return json_response(handler, 200, {"loggedIn": False})
    sess = res[0]
    table = "admins" if sess["role"] == "admin" else "department_heads"
    conn = get_connection()
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (sess["user_id"],)).fetchone()
    conn.close()
    if not row:
        return json_response(handler, 200, {"loggedIn": False})
    info = {"loggedIn": True, "role": sess["role"], "id": row["id"], "username": row["username"]}
    if sess["role"] == "head":
        info["full_name"] = row["full_name"]
        info["department"] = row["department"]
    json_response(handler, 200, info)


# ---------- admin: users ----------

def admin_create_user(handler):
    sess = require_session(handler, "admin")
    if not sess: return
    data = read_json_body(handler)
    role = data.get("role")
    username = clean_str(data.get("username"), 100)
    password = data.get("password") or ""
    if role not in ("admin", "head") or not username or len(password) < 4:
        return json_response(handler, 400, {"error": "Invalid input (password >=4 chars)"})

    conn = get_connection()
    try:
        if role == "admin":
            conn.execute(
                "INSERT INTO admins (username, password_hash, created_at) VALUES (?,?,?)",
                (username, hash_password(password), datetime.utcnow().isoformat()),
            )
        else:
            full_name = clean_str(data.get("full_name"), 100)
            department = clean_str(data.get("department"), 100)
            if not full_name or not department:
                conn.close()
                return json_response(handler, 400, {"error": "full_name and department required"})
            conn.execute(
                """INSERT INTO department_heads
                   (username, full_name, department, password_hash, created_at)
                   VALUES (?,?,?,?,?)""",
                (username, full_name, department, hash_password(password), datetime.utcnow().isoformat()),
            )
        conn.commit()
    except Exception as e:
        conn.close()
        return json_response(handler, 400, {"error": f"Could not create user: {e}"})
    conn.close()
    log_action("admin", sess["user_id"], f"create {role} {username}")
    json_response(handler, 200, {"ok": True})


def admin_list_users(handler):
    if not require_session(handler, "admin"): return
    conn = get_connection()
    admins = [dict(r) for r in conn.execute(
        "SELECT id, username, blocked, created_at FROM admins").fetchall()]
    heads = [dict(r) for r in conn.execute(
        "SELECT id, username, full_name, department, blocked, created_at FROM department_heads").fetchall()]
    conn.close()
    json_response(handler, 200, {"admins": admins, "heads": heads})


def admin_update_user(handler, role, user_id):
    sess = require_session(handler, "admin")
    if not sess: return
    if role not in ("admin", "head"):
        return json_response(handler, 400, {"error": "Bad role"})
    data = read_json_body(handler)
    table = "admins" if role == "admin" else "department_heads"

    conn = get_connection()
    row = conn.execute(f"SELECT * FROM {table} WHERE id = ?", (user_id,)).fetchone()
    if not row:
        conn.close()
        return json_response(handler, 404, {"error": "Not found"})

    fields, values = [], []
    if "username" in data:
        fields.append("username = ?"); values.append(clean_str(data["username"], 100))
    if "blocked" in data:
        fields.append("blocked = ?"); values.append(1 if data["blocked"] else 0)
    if "password" in data and data["password"]:
        fields.append("password_hash = ?"); values.append(hash_password(data["password"]))
    if role == "head":
        if "full_name" in data:
            fields.append("full_name = ?"); values.append(clean_str(data["full_name"], 100))
        if "department" in data:
            fields.append("department = ?"); values.append(clean_str(data["department"], 100))

    if not fields:
        conn.close()
        return json_response(handler, 400, {"error": "Nothing to update"})

    values.append(user_id)
    try:
        conn.execute(f"UPDATE {table} SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    except Exception as e:
        conn.close()
        return json_response(handler, 400, {"error": str(e)})
    conn.close()
    log_action("admin", sess["user_id"], f"update {role} {user_id}")
    json_response(handler, 200, {"ok": True})


def admin_delete_user(handler, role, user_id):
    sess = require_session(handler, "admin")
    if not sess: return
    if role not in ("admin", "head"):
        return json_response(handler, 400, {"error": "Bad role"})
    table = "admins" if role == "admin" else "department_heads"
    conn = get_connection()
    conn.execute(f"DELETE FROM {table} WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    log_action("admin", sess["user_id"], f"delete {role} {user_id}")
    json_response(handler, 200, {"ok": True})


def admin_all_forms(handler):
    if not require_session(handler, "admin"): return
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.id, f.title, f.token, f.expires_at, f.created_at,
               h.username AS owner, h.department,
               (SELECT COUNT(*) FROM submissions s WHERE s.form_id = f.id) AS submission_count
        FROM forms f
        LEFT JOIN department_heads h ON h.id = f.owner_id
        ORDER BY f.created_at DESC
    """).fetchall()
    conn.close()
    json_response(handler, 200, {"forms": [dict(r) for r in rows]})


def admin_analytics(handler):
    if not require_session(handler, "admin"): return
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    total_forms = conn.execute("SELECT COUNT(*) AS c FROM forms").fetchone()["c"]
    active_forms = conn.execute(
        "SELECT COUNT(*) AS c FROM forms WHERE expires_at IS NULL OR expires_at > ?",
        (now,)
    ).fetchone()["c"]
    expired_forms = total_forms - active_forms
    total_subs = conn.execute("SELECT COUNT(*) AS c FROM submissions").fetchone()["c"]
    total_admins = conn.execute("SELECT COUNT(*) AS c FROM admins").fetchone()["c"]
    total_heads = conn.execute("SELECT COUNT(*) AS c FROM department_heads").fetchone()["c"]
    avg_rating = conn.execute("""
        SELECT AVG(CAST(a.answer_text AS REAL)) AS avg_r
        FROM answers a JOIN questions q ON q.id = a.question_id
        WHERE q.qtype = 'rating' AND a.answer_text IS NOT NULL AND a.answer_text != ''
    """).fetchone()["avg_r"]
    conn.close()
    json_response(handler, 200, {
        "total_forms": total_forms,
        "active_forms": active_forms,
        "expired_forms": expired_forms,
        "total_submissions": total_subs,
        "total_admins": total_admins,
        "total_heads": total_heads,
        "average_rating": round(avg_rating, 2) if avg_rating else None,
    })


def admin_logs(handler):
    if not require_session(handler, "admin"): return
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM activity_logs ORDER BY id DESC LIMIT 200"
    ).fetchall()
    conn.close()
    json_response(handler, 200, {"logs": [dict(r) for r in rows]})


# ---------- head: profile/password ----------

def head_update_profile(handler):
    sess = require_session(handler, "head")
    if not sess: return
    data = read_json_body(handler)
    full_name = clean_str(data.get("full_name"), 100)
    department = clean_str(data.get("department"), 100)
    if not full_name or not department:
        return json_response(handler, 400, {"error": "Missing fields"})
    conn = get_connection()
    conn.execute(
        "UPDATE department_heads SET full_name=?, department=? WHERE id=?",
        (full_name, department, sess["user_id"]),
    )
    conn.commit()
    conn.close()
    json_response(handler, 200, {"ok": True})


def head_change_password(handler):
    sess = require_session(handler, "head")
    if not sess: return
    data = read_json_body(handler)
    old = data.get("old_password") or ""
    new = data.get("new_password") or ""
    if len(new) < 4:
        return json_response(handler, 400, {"error": "Password too short"})
    conn = get_connection()
    row = conn.execute(
        "SELECT password_hash FROM department_heads WHERE id=?", (sess["user_id"],)
    ).fetchone()
    if not row or row["password_hash"] != hash_password(old):
        conn.close()
        return json_response(handler, 400, {"error": "Old password incorrect"})
    conn.execute(
        "UPDATE department_heads SET password_hash=? WHERE id=?",
        (hash_password(new), sess["user_id"]),
    )
    conn.commit()
    conn.close()
    json_response(handler, 200, {"ok": True})


# ---------- head: forms ----------

def _save_questions(conn, form_id, questions):
    """Insert questions for a form. Wipes old ones first (used on edit)."""
    conn.execute("DELETE FROM questions WHERE form_id = ?", (form_id,))
    for i, q in enumerate(questions or []):
        qtype = q.get("qtype")
        if qtype not in ("short", "long", "yesno", "checkbox", "radio", "rating"):
            continue
        label = clean_str(q.get("label"), 300)
        if not label:
            continue
        opts = q.get("options") or []
        if isinstance(opts, list):
            opts_str = "|".join(clean_str(o, 100) for o in opts)
        else:
            opts_str = clean_str(opts, 500)
        required = 1 if q.get("required") else 0
        conn.execute(
            """INSERT INTO questions (form_id, qtype, label, options, required, position)
               VALUES (?,?,?,?,?,?)""",
            (form_id, qtype, label, opts_str, required, i),
        )


def head_create_form(handler):
    sess = require_session(handler, "head")
    if not sess: return
    data = read_json_body(handler)
    title = clean_str(data.get("title"), 200)
    if not title:
        return json_response(handler, 400, {"error": "Title required"})
    description = clean_str(data.get("description"), 1000)
    expires_at = clean_str(data.get("expires_at"), 50) or None
    token = make_token()

    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO forms (owner_id, title, description, token, expires_at, created_at)
           VALUES (?,?,?,?,?,?)""",
        (sess["user_id"], title, description, token, expires_at, datetime.utcnow().isoformat()),
    )
    form_id = cur.lastrowid
    _save_questions(conn, form_id, data.get("questions"))
    conn.commit()
    conn.close()
    log_action("head", sess["user_id"], f"create form {form_id}")
    json_response(handler, 200, {"ok": True, "id": form_id, "token": token})


def head_list_forms(handler):
    sess = require_session(handler, "head")
    if not sess: return
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, (SELECT COUNT(*) FROM submissions s WHERE s.form_id=f.id) AS submission_count
        FROM forms f WHERE owner_id=? ORDER BY created_at DESC
    """, (sess["user_id"],)).fetchall()
    conn.close()
    json_response(handler, 200, {"forms": [dict(r) for r in rows]})


def head_update_form(handler, form_id):
    sess = require_session(handler, "head")
    if not sess: return
    data = read_json_body(handler)
    conn = get_connection()
    row = conn.execute("SELECT * FROM forms WHERE id=? AND owner_id=?",
                       (form_id, sess["user_id"])).fetchone()
    if not row:
        conn.close()
        return json_response(handler, 404, {"error": "Not found"})
    title = clean_str(data.get("title", row["title"]), 200)
    description = clean_str(data.get("description", row["description"] or ""), 1000)
    expires_at = data.get("expires_at", row["expires_at"])
    conn.execute(
        "UPDATE forms SET title=?, description=?, expires_at=? WHERE id=?",
        (title, description, expires_at, form_id),
    )
    if "questions" in data:
        _save_questions(conn, form_id, data["questions"])
    conn.commit()
    conn.close()
    log_action("head", sess["user_id"], f"update form {form_id}")
    json_response(handler, 200, {"ok": True})


def head_delete_form(handler, form_id):
    sess = require_session(handler, "head")
    if not sess: return
    conn = get_connection()
    conn.execute("DELETE FROM forms WHERE id=? AND owner_id=?", (form_id, sess["user_id"]))
    conn.commit()
    conn.close()
    log_action("head", sess["user_id"], f"delete form {form_id}")
    json_response(handler, 200, {"ok": True})


def head_form_responses(handler, form_id):
    sess = require_session(handler, "head")
    if not sess: return
    conn = get_connection()
    form = conn.execute("SELECT * FROM forms WHERE id=? AND owner_id=?",
                        (form_id, sess["user_id"])).fetchone()
    if not form:
        conn.close()
        return json_response(handler, 404, {"error": "Not found"})
    questions = [dict(r) for r in conn.execute(
        "SELECT * FROM questions WHERE form_id=? ORDER BY position", (form_id,)).fetchall()]
    subs = conn.execute(
        "SELECT * FROM submissions WHERE form_id=? ORDER BY id DESC", (form_id,)).fetchall()
    submissions = []
    for s in subs:
        ans = conn.execute(
            "SELECT question_id, answer_text FROM answers WHERE submission_id=?", (s["id"],)
        ).fetchall()
        submissions.append({
            "id": s["id"],
            "submitted_at": s["submitted_at"],
            "answers": {a["question_id"]: a["answer_text"] for a in ans},
        })
    conn.close()
    json_response(handler, 200, {
        "form": dict(form), "questions": questions, "submissions": submissions
    })


def head_analytics(handler):
    sess = require_session(handler, "head")
    if not sess: return
    now = datetime.utcnow().isoformat()
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) AS c FROM forms WHERE owner_id=?",
                         (sess["user_id"],)).fetchone()["c"]
    active = conn.execute("""SELECT COUNT(*) AS c FROM forms
                             WHERE owner_id=? AND (expires_at IS NULL OR expires_at > ?)""",
                          (sess["user_id"], now)).fetchone()["c"]
    subs = conn.execute("""SELECT COUNT(*) AS c FROM submissions s
                           JOIN forms f ON f.id=s.form_id WHERE f.owner_id=?""",
                        (sess["user_id"],)).fetchone()["c"]
    avg = conn.execute("""SELECT AVG(CAST(a.answer_text AS REAL)) AS avg_r
                          FROM answers a
                          JOIN questions q ON q.id=a.question_id
                          JOIN forms f ON f.id=q.form_id
                          WHERE f.owner_id=? AND q.qtype='rating'
                            AND a.answer_text IS NOT NULL AND a.answer_text!=''""",
                       (sess["user_id"],)).fetchone()["avg_r"]
    conn.close()
    json_response(handler, 200, {
        "total_forms": total, "active_forms": active, "expired_forms": total - active,
        "total_submissions": subs,
        "average_rating": round(avg, 2) if avg else None,
    })


# ---------- public ----------

def public_get_form(handler, token):
    conn = get_connection()
    form = conn.execute("SELECT * FROM forms WHERE token=?", (token,)).fetchone()
    if not form:
        conn.close()
        return json_response(handler, 404, {"error": "Form not found"})
    if form["expires_at"] and form["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        return json_response(handler, 410, {"error": "This form has expired"})
    questions = [dict(r) for r in conn.execute(
        "SELECT id, qtype, label, options, required, position FROM questions WHERE form_id=? ORDER BY position",
        (form["id"],)).fetchall()]
    conn.close()
    json_response(handler, 200, {
        "title": form["title"],
        "description": form["description"],
        "questions": questions,
    })


def public_submit_form(handler, token):
    data = read_json_body(handler)
    answers = data.get("answers") or {}
    conn = get_connection()
    form = conn.execute("SELECT * FROM forms WHERE token=?", (token,)).fetchone()
    if not form:
        conn.close()
        return json_response(handler, 404, {"error": "Form not found"})
    if form["expires_at"] and form["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        return json_response(handler, 410, {"error": "This form has expired"})

    questions = conn.execute(
        "SELECT * FROM questions WHERE form_id=?", (form["id"],)).fetchall()

    # Validate required questions
    for q in questions:
        val = answers.get(str(q["id"]))
        if q["required"] and (val is None or str(val).strip() == ""):
            conn.close()
            return json_response(handler, 400,
                                 {"error": f"Question '{q['label']}' is required"})

    cur = conn.execute(
        "INSERT INTO submissions (form_id, submitted_at) VALUES (?,?)",
        (form["id"], datetime.utcnow().isoformat()),
    )
    sub_id = cur.lastrowid
    for q in questions:
        val = answers.get(str(q["id"]))
        if isinstance(val, list):
            val = "|".join(clean_str(x, 200) for x in val)
        else:
            val = clean_str(val, 2000)
        conn.execute(
            "INSERT INTO answers (submission_id, question_id, answer_text) VALUES (?,?,?)",
            (sub_id, q["id"], val),
        )
    conn.commit()
    conn.close()
    json_response(handler, 200, {"ok": True})
