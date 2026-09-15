/* Page Request — file de requêtes IA → dev (et humain → dev). */
"use strict";

async function render() {
  const res = await apiGet("/api/requests");
  const wrap = document.getElementById("requests-wrap");
  const items = res.requests || [];
  if (!items.length) {
    wrap.innerHTML = `<div class="card muted">Aucune requête pour l'instant. L'IA en ouvre quand elle manque d'un outil — ou utilise le formulaire ci-dessous.</div>`;
  } else {
    wrap.innerHTML =
      `<table>
        <thead><tr><th>Titre</th><th>Type</th><th>De</th><th>Statut</th><th>Créée le</th></tr></thead>
        <tbody>${items
          .map(
            (r) => `
            <tr>
              <td><b>${esc(r.title)}</b>${r.description ? `<div class="small muted">${esc(r.description).slice(0, 200)}${r.description.length > 200 ? "…" : ""}</div>` : ""}</td>
              <td>${badge(r.type)}</td>
              <td>${r.from_role === "ai" ? '<span class="badge ai">🤖 IA</span>' : '<span class="badge">humain</span>'}</td>
              <td>${badge(r.status)}</td>
              <td class="mono small">${fmtDate(r.created_at)}</td>
            </tr>`
          )
          .join("")}</tbody>
      </table>`;
  }
}

const form = document.getElementById("request-form");
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = form.querySelector("button");
  btn.disabled = true;
  try {
    const fd = new FormData(form);
    const res = await apiPost("/api/requests", {
      title: fd.get("title"),
      description: fd.get("description"),
      type: fd.get("type"),
      from_role: fd.get("from_role"),
    });
    form.reset();
    toast("Requête envoyée ✅ (id " + res.id + ")");
    render();
    renderStatusChip();
  } catch (err) {
    toast(err.message, true);
  } finally {
    btn.disabled = false;
  }
});

render().catch((e) => toast(e.message, true));
renderStatusChip();
