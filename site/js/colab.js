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
  wrap.querySelectorAll("[data-restudy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      btn.disabled = true;
      btn.textContent = "🧠 Ré-étude lancée…";
      try {
        await apiPost(`/api/research/results/${btn.dataset.restudy}/study`, {});
        toast("Étude relancée ✅ — le bilan s'actualise dans un instant");
        setTimeout(renderResults, 2500);
      } catch (err) {
        toast(err.message, true);
        btn.disabled = false;
        btn.textContent = "🧠 Ré-étudier maintenant";
      }
    });
  });
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
  // Échec transitoire (moteur en repos…) : on permet de ré-étudier à la main.
  if (st.retryable || st.status === "error") {
    html += `<div style="margin:6px 0 0 8px"><button class="hint-btn" type="button" data-restudy="${esc(r.id)}">🧠 Ré-étudier maintenant</button></div>`;
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

/* ── Code viewer — lazy-load + copy (analyseur + agent) ──────────── */
function bindCodeViewer({ toggleId, copyId, viewerId, blockId, url, copyReadyLabel }) {
  const toggleBtn = document.getElementById(toggleId);
  const copyBtn = document.getElementById(copyId);
  const viewer = document.getElementById(viewerId);
  const codeBlock = document.getElementById(blockId);
  if (!toggleBtn && !copyBtn) return;
  let rawCode = null;

  async function loadCode() {
    if (rawCode !== null) return true;
    if (toggleBtn) {
      toggleBtn.dataset.prev = toggleBtn.textContent;
      toggleBtn.textContent = "Chargement…";
      toggleBtn.disabled = true;
    }
    if (copyBtn) copyBtn.disabled = true;
    try {
      const res = await fetch(url);
      if (!res.ok) throw new Error("HTTP " + res.status);
      rawCode = await res.text();
      if (codeBlock) codeBlock.textContent = rawCode;
      if (copyBtn) copyBtn.disabled = false;
      return true;
    } catch (err) {
      toast("Impossible de charger le code : " + err.message, true);
      return false;
    } finally {
      if (toggleBtn) {
        toggleBtn.disabled = false;
        if (viewer && viewer.style.display === "none") toggleBtn.textContent = toggleBtn.dataset.prev || "Afficher le code";
      }
    }
  }

  async function copyCode() {
    if (rawCode === null) {
      const ok = await loadCode();
      if (!ok) return;
    }
    const label = copyReadyLabel || "Copier le code";
    try {
      await navigator.clipboard.writeText(rawCode);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = rawCode;
      ta.style.cssText = "position:fixed;opacity:0";
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
    }
    if (copyBtn) {
      const prev = copyBtn.textContent;
      copyBtn.textContent = "✅ Copié !";
      setTimeout(() => { copyBtn.textContent = prev || label; }, 2000);
    }
    toast("Code copié — colle-le dans une cellule Colab");
  }

  if (toggleBtn && viewer) {
    toggleBtn.addEventListener("click", async () => {
      const visible = viewer.style.display !== "none";
      if (visible) {
        viewer.style.display = "none";
        toggleBtn.textContent = "Afficher le code";
        return;
      }
      if (rawCode === null) {
        const ok = await loadCode();
        if (!ok) { toggleBtn.textContent = "Afficher le code"; return; }
      }
      viewer.style.display = "block";
      toggleBtn.textContent = "Masquer le code";
    });
  }
  if (copyBtn) copyBtn.addEventListener("click", copyCode);
}

bindCodeViewer({
  toggleId: "btn-toggle-code",
  copyId: "btn-copy-code",
  viewerId: "code-viewer",
  blockId: "code-block",
  url: "/colab-notebook/analyze_discussions.py",
});
bindCodeViewer({
  toggleId: "btn-toggle-agent",
  copyId: "btn-copy-agent",
  viewerId: "code-viewer-agent",
  blockId: "code-block-agent",
  url: "/colab-notebook/agent_search.py",
  copyReadyLabel: "Copier le code (1 cellule)",
});
