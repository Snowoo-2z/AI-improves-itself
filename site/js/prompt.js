/* Page /prompt — le prompt système versionné, ses garde-fous, son historique. */
"use strict";

async function render() {
  const res = await apiGet("/api/prompt-system");
  const wrap = document.getElementById("prompts-wrap");
  wrap.innerHTML = res.prompts
    .map((p) => {
      const byAi = p.updated_by === "ai";
      const guards = (p.keywords || []).length
        ? `<div class="small muted">Garde-fou (mots-clés déclencheurs) : ${p.keywords.map((k) => `<code>${esc(k)}</code>`).join(" · ")}</div>`
        : `<div class="small muted">Toujours chargé (scope global).</div>`;
      const hist = (p.history || [])
        .slice()
        .reverse()
        .map(
          (h) => `
          <details class="hist-item">
            <summary>v${h.version} → v${h.version + 1} · par <b>${esc(h.author)}</b> · ${fmtDate(h.at)} · ${esc(h.trigger || "")}</summary>
            <div class="small" style="margin-top:8px"><b>Raison :</b> ${esc(h.reason || "—")}</div>
            <details style="margin-top:8px"><summary class="small muted">contenu avant modification</summary>
              <div class="old">${esc(h.content)}</div>
            </details>
          </details>`
        )
        .join("");
      return `
      <div class="card">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-bottom:10px">
          <h2 style="margin:0">Prompt « ${esc(p.id)} »</h2>
          <span class="chip">scope : ${esc(p.scope)}</span>
          <span class="chip ${byAi ? "ai" : "ok"}">v${p.version}</span>
          <span class="chip">par ${esc(p.updated_by)}</span>
        </div>
        ${guards}
        <div class="prompt-box" style="margin-top:10px">${esc(p.content)}</div>
        ${hist ? `<h3 style="margin-top:16px">Historique des auto-modifications</h3>${hist}` : ""}
      </div>`;
    })
    .join("");
}

render().catch((e) => toast(e.message, true));
renderStatusChip();
