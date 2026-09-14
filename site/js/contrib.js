/* Page /contributeur — contribution humaine + liste des skills (API). */
"use strict";

async function renderSkills() {
  const res = await apiGet("/api/skills");
  document.getElementById("skills-wrap").innerHTML = (res.skills || [])
    .map(
      (s) => `
      <div class="card" style="margin-bottom:12px">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
          <code style="color:var(--accent)">${esc(s.id)}</code>
          <span class="muted small">${esc(s.name)}</span>
          ${s.description_updated_by === "ai" ? '<span class="badge ai">description auto-améliorée par l'IA</span>' : ""}
        </div>
        <div class="small muted" style="margin-top:6px">${esc(s.description)}</div>
      </div>`
    )
    .join("");
}

renderSkills().catch((e) => toast(e.message, true));
renderStatusChip();
