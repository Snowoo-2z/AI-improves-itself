/* Page / — chat avec l'IA + panneau système. */
"use strict";

const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const providerChip = document.getElementById("chat-provider");
let history = []; // [{role, content}] — l'assemblage du prompt se fait côté serveur

function addMsg(role, html) {
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  wrap.innerHTML = `<div class="bubble">${role === "ai" ? '<span class="who">IA · self-improving</span>' : '<span class="who">toi</span>'}${html}</div>`;
  chatLog.appendChild(wrap);
  chatLog.scrollTop = chatLog.scrollHeight;
  return wrap;
}

function addEvent(ev) {
  const el = document.createElement("div");
  el.className = "event" + (ev.type === "prompt_update" ? " accent" : "");
  if (ev.type === "tool") {
    const args = Object.entries(ev.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" · ");
    const ok = ev.result && ev.result.ok !== false;
    el.innerHTML =
      `<span class="e-title">🔧 skill ${esc(ev.skill)}</span> <span class="muted">(${esc(args)})</span>` +
      `<div class="e-detail">${ok ? "→ " + esc(JSON.stringify(ev.result).slice(0, 220)) : "→ ❌ " + esc((ev.result || {}).error || "erreur")}</div>`;
  } else if (ev.type === "prompt_update") {
    el.innerHTML =
      `<span class="e-title">🧬 L'IA a modifié son prompt système « ${esc(ev.scope)} » → v${esc(ev.version)}</span>` +
      `<div class="e-detail">raison : ${esc(ev.reason || "")} — ${esc(ev.trigger || "")}</div>`;
  }
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
}

async function send(text) {
  const msg = (text ?? chatInput.value).trim();
  if (!msg) return;
  chatInput.value = "";
  addMsg("user", esc(msg));
  history.push({ role: "user", content: msg });
  const btn = chatForm.querySelector("button");
  btn.disabled = true;
  try {
    const res = await apiPost("/api/chat", { messages: history });
    (res.events || []).forEach(addEvent);
    addMsg("ai", esc(res.reply));
    history.push({ role: "assistant", content: res.reply });
    if (res.warnings && res.warnings.length) {
      // Visible dans le chat (avant : console uniquement) : l'utilisateur doit
      // savoir quel moteur a échoué, LEQUEL répond à la place, et QUAND le
      // moteur au repos sera re-testé (fenêtre ~1 min, quota journalier → minuit…).
      console.warn("warnings", res.warnings, "attempts", res.attempts || []);
      const w = document.createElement("div");
      w.className = "event";
      const retry = res.provider_retry_in_human
        ? ` · nouvel essai automatique dans <b>${esc(res.provider_retry_in_human)}</b>`
        : "";
      const served = res.fallback_to_demo ? "mode démo local" : `moteur <b>${esc(res.provider)}</b>`;
      w.innerHTML =
        `<span class="e-title">⚠️ Repli de moteur → ${served}${retry}</span>` +
        `<div class="e-detail">${res.warnings.map(esc).join("<br>")}</div>` +
        `<div class="e-detail"><button class="hint-btn" type="button" id="retest-providers">🔁 re-tester la chaîne maintenant</button></div>`;
      chatLog.appendChild(w);
      chatLog.scrollTop = chatLog.scrollHeight;
      const retestBtn = document.getElementById("retest-providers");
      if (retestBtn) retestBtn.addEventListener("click", () => retestProviders(retestBtn));
    }
    refreshSide();
  } catch (e) {
    addMsg("ai", "⚠️ Erreur : " + esc(e.message));
  } finally {
    btn.disabled = false;
    chatInput.focus();
  }
}

function refreshSide() {
  apiGet("/api/status")
    .then((s) => {
      const ps = document.getElementById("prompt-status");
      if (ps) {
        ps.innerHTML =
          `<div class="chips" style="margin-bottom:10px">` +
          s.prompts.map((p) => `<span class="chip">${esc(p.id)} · v${p.version}</span>`).join("") +
          `</div>` +
          `<div class="small muted">Modifié par : <b>${esc(s.prompt_updated_by)}</b> — <a href="/prompt.html">voir l'historique complet →</a></div>`;
      }
      const act = document.getElementById("activity");
      if (act) {
        act.innerHTML = `
          <table>
            <tr><td>Requêtes au dev (/request)</td><td class="mono">${s.counts.dev_requests}</td></tr>
            <tr><td>Tâches recherche (/colab)</td><td class="mono">${s.counts.research_tasks}</td></tr>
            <tr><td>Résultats de recherche</td><td class="mono">${s.counts.research_results}</td></tr>
            <tr><td>Entrées base de données (/data)</td><td class="mono">${s.counts.knowledge}</td></tr>
          </table>`;
      }
      if (providerChip) {
        // Trois états réels : moteur cloud actif, démo faute de clé, démo parce
        // que les moteurs cloud sont au repos (429 / quota journalier / réseau).
        if (!s.demo_mode) {
          const model = s.model ? ` · ${esc(s.model)}` : "";
          providerChip.innerHTML = `<span class="chip ok">${esc(s.primary_provider)}${model}</span>`;
        } else if (s.provider_errors && s.provider_errors.length) {
          providerChip.innerHTML =
            `<span class="chip warn" title="${esc(s.provider_errors.join(" · "))}">demo-local · moteurs au repos` +
            (s.provider_retry_in_human ? ` (essai dans ${esc(s.provider_retry_in_human)})` : "") +
            `</span>`;
        } else {
          providerChip.innerHTML = '<span class="chip warn">demo-local (sans clé API)</span>';
        }
      }
    })
    .catch(() => {});
}

async function retestProviders(btn) {
  // Re-test forcé de la chaîne : utile juste après avoir ajouté une clé dans
  // .env, mais chaque test consomme 1 appel par provider (quota gratuit !).
  if (btn) { btn.disabled = true; btn.textContent = "⏳ test des moteurs…"; }
  try {
    const res = await apiPost("/api/providers/retest", { force: true });
    const lines = Object.entries(res.ping || {}).map(([k, v]) => `${k} → ${v}`).join("\n");
    toast(res.errors && res.errors.length ? "Moteurs testés : " + res.errors.length + " en repos" : "Moteurs testés ✅");
    console.info("re-test de la chaîne\n" + lines);
  } catch (e) {
    toast(e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = "🔁 re-tester la chaîne maintenant"; }
    refreshSide();
    renderStatusChip();
  }
}

chatForm.addEventListener("submit", (e) => { e.preventDefault(); send(); });
document.querySelectorAll(".hint-btn").forEach((b) => b.addEventListener("click", () => send(b.dataset.q)));
refreshSide();
renderStatusChip();
