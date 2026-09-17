/* Export des discussions (localStorage) vers l'analyseur Colab.
   Le bouton 📤 (barre du haut) ouvre une modale : sélection 1 à N des
   conversations du navigateur (localStorage `aiis.convos.v1`), puis copie
   une LIGNE base64 unique dans le presse-papier (ou téléchargement .json).
   Le script Colab `colab/analyze_discussions.py` la reçoit (input) et la
   décode — mêmes règles de sécurité : rien d'autre ne quitte le navigateur. */
"use strict";

const AIIS_EXPORT_KEY = "aiis.convos.v1"; // même clé que chat.js

function aiisExportPayload(convos) {
  return {
    app: "aiis",
    export_type: "discussions",
    exported_at: new Date().toISOString(),
    conversations: convos,
  };
}

function aiisToB64(obj) {
  // base64 sûr UTF-8 (accents, émojis) — une ligne, collable dans Colab.
  return btoa(unescape(encodeURIComponent(JSON.stringify(obj))));
}

(function initExportToColab() {
  const btn = document.getElementById("export-colab-btn");
  if (!btn) return;
  let modal = null;

  const titleOf = (c) => {
    if (c.title) return c.title;
    const first = (c.messages || [])
      .map((m) =>
        typeof m.content === "string"
          ? m.content
          : Array.isArray(m.content)
            ? ((m.content.find((b) => b && b.type === "text") || {}).text || "")
            : ""
      )
      .find(Boolean);
    return first ? first.trim().split("\n")[0].slice(0, 60) : "Sans titre";
  };

  function openModal() {
    if (modal) return;
    let convos = [];
    try { convos = JSON.parse(localStorage.getItem(AIIS_EXPORT_KEY) || "[]"); } catch { convos = []; }
    convos = Array.isArray(convos) ? convos : [];
    const sorted = convos.slice().sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

    const rows = sorted
      .map(
        (c, i) => `
        <label class="export-row">
          <input type="checkbox" value="${i}" checked />
          <span class="export-row-t" title="${esc(titleOf(c))}">${esc(titleOf(c))}</span>
          <span class="export-row-m muted small">${(c.messages || []).length} msg · ${new Date(c.updatedAt || c.createdAt || Date.now()).toLocaleDateString()}</span>
        </label>`
      )
      .join("") || `<div class="muted small" style="padding:8px">Aucune conversation dans ce navigateur (localStorage vide).</div>`;

    modal = document.createElement("div");
    modal.className = "export-backdrop";
    modal.innerHTML = `
      <div class="export-modal" role="dialog" aria-modal="true" aria-label="Exporter les discussions vers l'analyseur Colab">
        <div class="export-head">
          <h2>📤 Export vers l'analyseur Colab</h2>
          <button type="button" class="icon-btn export-close" aria-label="Fermer" title="Fermer"><svg class="ic"><use href="#i-x" /></svg></button>
        </div>
        <p class="small muted">
          Sélectionne 1 à N discussions stockées dans <b>ce navigateur</b> (localStorage).
          Une ligne base64 est copiée : colle-la dans la cellule
          <code>analyze_discussions</code> de Colab quand elle le demande (ou
          <a href="/colab.html" target="_blank" rel="noopener">page /colab</a>).
        </p>
        <div class="export-list">${rows}</div>
        <div class="export-actions">
          <label class="small"><input type="checkbox" class="export-all" checked /> toutes</label>
          <span class="muted small export-count"></span>
          <span class="spacer"></span>
          <button type="button" class="hint-btn export-dl" hidden>Télécharger .json</button>
          <button type="button" class="btn export-copy">Copier la ligne base64</button>
        </div>
        <pre class="export-blob" hidden></pre>
      </div>`;
    document.body.appendChild(modal);

    const list = modal.querySelector(".export-list");
    const allBox = modal.querySelector(".export-all");
    const count = modal.querySelector(".export-count");
    const copyBtn = modal.querySelector(".export-copy");
    const dlBtn = modal.querySelector(".export-dl");
    const blob = modal.querySelector(".export-blob");

    const updateCount = () => {
      const n = modal.querySelectorAll(".export-row input:checked").length;
      count.textContent = `${n}/${sorted.length} sélectionnée(s)`;
    };
    allBox.addEventListener("change", () => {
      modal.querySelectorAll(".export-row input").forEach((b) => { b.checked = allBox.checked; });
      updateCount();
    });
    list.addEventListener("change", (e) => {
      if (e.target.matches(".export-row input")) {
        const boxes = [...modal.querySelectorAll(".export-row input")];
        allBox.checked = boxes.length > 0 && boxes.every((b) => b.checked);
        updateCount();
      }
    });
    const selected = () =>
      [...modal.querySelectorAll(".export-row input:checked")].map((b) => sorted[parseInt(b.value, 10)]);
    const close = () => {
      modal.remove();
      modal = null;
      document.removeEventListener("keydown", onEsc);
    };
    const onEsc = (e) => { if (e.key === "Escape") close(); };
    modal.querySelector(".export-close").addEventListener("click", close);
    modal.addEventListener("click", (e) => { if (e.target === modal) close(); });
    document.addEventListener("keydown", onEsc);

    copyBtn.addEventListener("click", async () => {
      const sel = selected();
      if (!sel.length) { toast("Sélectionne au moins une discussion.", true); return; }
      const b64 = aiisToB64(aiisExportPayload(sel));
      blob.textContent = b64;
      blob.hidden = false;
      dlBtn.hidden = false;
      try {
        await navigator.clipboard.writeText(b64);
        toast(`✅ ${sel.length} discussion(s) copiée(s) en base64 — ouvre Colab et colle la ligne (Entrée).`);
      } catch {
        toast("Copie refusée par le navigateur : la ligne est affichée (sélectionne-la et copie-la).", true);
      }
    });
    dlBtn.addEventListener("click", () => {
      const sel = selected();
      if (!sel.length) { toast("Sélectionne au moins une discussion.", true); return; }
      const payload = JSON.stringify(aiisExportPayload(sel), null, 2);
      const blob2 = new Blob([payload], { type: "application/json" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob2);
      a.download = `discussions_export_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(a.href), 5000);
      toast("Fichier .json téléchargé (téléversable dans Colab : touche « f »).");
    });
    updateCount();
  }

  btn.addEventListener("click", openModal);
})();
