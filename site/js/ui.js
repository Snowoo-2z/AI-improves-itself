/* Petits utilitaires partagés par toutes les pages. */
"use strict";

const API = window.AIIS_CONFIG.apiBase || "";

async function apiGet(path) {
  const r = await fetch(API + path, { headers: { Accept: "application/json" } });
  if (!r.ok) throw new Error(`GET ${path} → ${r.status} ${await r.text()}`);
  return r.json();
}

async function apiPost(path, body) {
  const r = await fetch(API + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  if (!r.ok) throw new Error(`POST ${path} → ${r.status} ${await r.text()}`);
  return r.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function fmtDate(t) {
  if (!t) return "—";
  if (typeof t === "number") t = t * 1000;
  const d = new Date(t);
  if (isNaN(d.getTime())) return String(t);
  return d.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}

function badge(value) {
  const v = String(value ?? "").toLowerCase();
  const cls = ["open", "done", "pending", "failed", "ai", "info", "processing"].includes(v) ? v : "";
  return `<span class="badge ${cls}">${esc(v || "—")}</span>`;
}

function toast(msg, isError) {
  const el = document.createElement("div");
  el.className = "toast";
  if (isError) el.style.borderColor = "var(--danger)";
  el.textContent = msg;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function renderStatusChip() {
  const el = document.getElementById("status-chip");
  if (!el) return;
  apiGet("/api/status")
    .then((s) => {
      // MODE DÉMO peut vouloir dire deux choses très différentes : aucune clé
      // configurée, OU moteurs cloud au repos (429 / quota journalier / réseau).
      let mode = "MODE DÉMO";
      if (!s.demo_mode) {
        mode = esc(s.primary_provider).toUpperCase();
      } else if (s.provider_errors && s.provider_errors.length) {
        mode = "DÉMO · MOTEURS AU REPOS" + (s.provider_retry_in_human ? ` (${esc(s.provider_retry_in_human)})` : "");
      }
      const title = (s.provider_errors || []).join("\n");
      el.innerHTML =
        `<span class="chip ${s.demo_mode ? "warn" : "ok"}"${title ? ` title="${esc(title)}"` : ""}>${mode}</span> ` +
        `<span class="chip">prompt main v${s.prompt_main_version} (${esc(s.prompt_updated_by)})</span>`;
    })
    .catch(() => { el.textContent = "API indisponible"; });
}
