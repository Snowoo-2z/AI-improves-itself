/* Page Colab — tâches de recherche (notebook Colab) + résultats. */
"use strict";

async function renderTasks() {
  const res = await apiGet("/api/research/tasks");
  const wrap = document.getElementById("tasks-wrap");
  const items = res.tasks || [];
  if (!items.length) {
    wrap.innerHTML = `<div class="muted small">Aucune tâche. L'IA en ajoute quand elle a besoin d'infos web (skill add_research_task) ou via le formulaire.</div>`;
    return;
  }
  wrap.innerHTML =
    `<table>
      <thead><tr><th>Kind</th><th>Cible</th><th>Pourquoi</th><th>Par</th><th>Statut</th></tr></thead>
      <tbody>${items
        .map(
          (t) => {
            const target = String(t.target || "");
            // Seule une cible http(s) est cliquable (une requête de recherche ne l'est pas).
            const cell = /^https?:\/\//i.test(target)
              ? `<a href="${esc(target)}" target="_blank" rel="noopener">${esc(target.slice(0, 70))}${target.length > 70 ? "…" : ""}</a>`
              : esc(target.slice(0, 70)) + (target.length > 70 ? "…" : "");
            return `
          <tr>
            <td>${badge(t.kind)}</td>
            <td class="mono small">${cell}</td>
            <td class="small muted">${esc(t.reason || "—")}</td>
            <td>${t.by === "ai" ? '<span class="badge ai">🤖 IA</span>' : "<span class='badge'>humain</span>"}</td>
            <td>${badge(t.status)}</td>
          </tr>`;
          }
        )
        .join("")}</tbody>
    </table>`;
}

async function renderResults() {
  const res = await apiGet("/api/research/results");
  const wrap = document.getElementById("results-wrap");
  const items = res.results || [];
  if (!items.length) {
    wrap.innerHTML = `<div class="muted small">Aucun résultat exécuté pour l'instant (le notebook Colab alimente cette liste).</div>`;
    return;
  }
  wrap.innerHTML = items
    .map(
      (r) => `
      <details class="hist-item">
        <summary>${badge(r.kind)} · résultat de tâche <code>${esc(String(r.task_id || "—").slice(0, 12))}</code> · ${fmtDate(r.created_at)}</summary>
        ${renderStudy(r)}
        <pre class="block" style="margin-top:8px;max-height:300px;overflow:auto">${esc(JSON.stringify(r.data, null, 2))}</pre>
      </details>`
    )
    .join("");
}

/* Bilan de l'étude IA (structuration + vérification → écriture dans /data). */
function renderStudy(r) {
  const st = r.study;
  if (!st) {
    return `<div class="small muted">🧠 Étude IA : en cours ou non déclenchée… (2 appels LLM : structuration puis vérification)</div>`;
  }
  const statuses = {
    added: "✅ ajoutée à la base",
    duplicate: "♻️ déjà en base",
    rejected: "⛔ rejetée",
    skipped: "⏭️ ignorée",
    error: "❌ erreur",
  };
  const lbl = statuses[st.status] || st.status;
  const conf =
    typeof st.confidence === "number" ? `<span class="muted small">· confiance ${st.confidence}</span>` : "";
  let html = `<div class="study">🧠 Étude IA : <strong>${esc(lbl)}</strong> ${conf}${
    st.reason ? ` · <span class="muted small">${esc(st.reason)}</span>` : ""
  }</div>`;
  if (st.entry && st.entry.title) {
    html += `<div class="small" style="margin:4px 0 0 8px">« ${esc(st.entry.title)} » — ${esc(st.entry.summary)} ${
      st.entry.source ? ` · <span class="muted">${esc(st.entry.source)}</span>` : ""
    }</div>`;
  }
  return html;
}

const form = document.getElementById("task-form");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = form.querySelector("button");
  btn.disabled = true;
  try {
    const fd = new FormData(form);
    const res = await apiPost("/api/research/tasks", {
      kind: fd.get("kind"),
      target: fd.get("target"),
      reason: fd.get("reason"),
      by: "human",
    });
    form.reset();
    toast("Tâche ajoutée ✅ (id " + res.id + ")");
    renderTasks();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
  }
});

Promise.all([renderTasks(), renderResults()]).catch((e) => toast(e.message, true));
renderStatusChip();
