/* common.js — small helpers used by every page */

// Wrap fetch with JSON conventions and credentials (so cookies are sent)
async function api(path, options = {}) {
  const opts = {
    method: options.method || "GET",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
  };
  if (options.body) opts.body = JSON.stringify(options.body);
  const res = await fetch(path, opts);
  let data = {};
  try { data = await res.json(); } catch (_) {}
  if (!res.ok) {
    const msg = (data && data.error) || `Request failed (${res.status})`;
    throw new Error(msg);
  }
  return data;
}

// Toast notification
function toast(msg, type = "") {
  let el = document.getElementById("toast");
  if (!el) {
    el = document.createElement("div");
    el.id = "toast";
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.className = "show " + type;
  setTimeout(() => { el.className = ""; }, 2500);
}

// Escape user-supplied text before injecting into HTML
function esc(s) {
  if (s === null || s === undefined) return "";
  return String(s)
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function showSection(id) {
  document.querySelectorAll(".section").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".sidebar a[data-section]").forEach(a => a.classList.remove("active"));
  const sec = document.getElementById(id);
  if (sec) sec.classList.add("active");
  const link = document.querySelector(`.sidebar a[data-section="${id}"]`);
  if (link) link.classList.add("active");
}

async function logout() {
  try { await api("/api/logout", { method: "POST" }); } catch (_) {}
  window.location.href = "/login";
}
