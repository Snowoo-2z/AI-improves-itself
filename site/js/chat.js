/* Page / — chat plein écran style ChatGPT + conversations persistées (localStorage). */
"use strict";

/* ---------- DOM ---------- */
const chatScroll = document.getElementById("chat-scroll");
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const welcomeEl = document.getElementById("welcome");
const convoListEl = document.getElementById("convo-list");
const convoSearch = document.getElementById("convo-search");
const sidebar = document.getElementById("sidebar");
const overlay = document.getElementById("overlay");

/* ---------- État ---------- */
const LS_CONVOS = "aiis.convos.v1";
const LS_ACTIVE = "aiis.activeConvo.v1";
let convos = [];      // [{id, title, createdAt, updatedAt, messages:[{role, content, events?, warn?}]}]
let currentId = null; // null = nouveau chat (non persisté tant que vide)
let isSending = false;

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));
const current = () => convos.find((c) => c.id === currentId) || null;
const apiMessages = (c) => (c ? c.messages.map((m) => ({ role: m.role, content: m.content })) : []);
// Icônes SVG : renvoie vers le sprite <symbol> défini dans index.html.
const icon = (name) => `<svg class="ic" aria-hidden="true"><use href="#i-${name}" /></svg>`;

function load() {
  try { convos = JSON.parse(localStorage.getItem(LS_CONVOS) || "[]"); } catch { convos = []; }
  if (!Array.isArray(convos)) convos = [];
  currentId = localStorage.getItem(LS_ACTIVE) || null;
  if (currentId && !current()) currentId = null;
}
function save() {
  try {
    localStorage.setItem(LS_CONVOS, JSON.stringify(convos.slice(0, 100)));
    if (currentId) localStorage.setItem(LS_ACTIVE, currentId);
    else localStorage.removeItem(LS_ACTIVE);
  } catch {}
}
function touch(convo) {
  convo.updatedAt = Date.now();
  if (!convo.title) {
    const first = convo.messages.find((m) => m.role === "user");
    if (first) convo.title = first.content.trim().split("\n")[0].slice(0, 42) || "Sans titre";
  }
}

/* ---------- Rendu : messages ---------- */
function scrollBottom() {
  chatScroll.scrollTop = chatScroll.scrollHeight;
}

function traceCard({ cls, summaryHtml, bodyHtml, open }) {
  const d = document.createElement("details");
  d.className = "trace" + (cls ? " " + cls : "");
  if (open) d.open = true;
  const s = document.createElement("summary");
  s.innerHTML = summaryHtml;
  d.appendChild(s);
  if (bodyHtml) {
    const b = document.createElement("div");
    b.className = "trace-body";
    b.innerHTML = bodyHtml;
    d.appendChild(b);
  }
  return d;
}

function eventCard(ev) {
  if (ev.type === "tool") {
    const args = Object.entries(ev.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" · ");
    const ok = ev.result && ev.result.ok !== false;
    return traceCard({
      summaryHtml: `${icon("wrench")}<span>skill <b>${esc(ev.skill)}</b></span> <span class="muted">${esc(args).slice(0, 80)}</span>`,
      bodyHtml: ok ? "→ " + esc(JSON.stringify(ev.result)).slice(0, 400) : "→ Erreur : " + esc((ev.result || {}).error || "erreur"),
    });
  }
  if (ev.type === "prompt_update") {
    return traceCard({
      cls: "accent",
      open: true,
      summaryHtml: `${icon("terminal")}<span>L'IA a modifié son prompt « ${esc(ev.scope)} » → v${esc(ev.version)}</span>`,
      bodyHtml: `raison : ${esc(ev.reason || "")} — ${esc(ev.trigger || "")} · <a href="/prompt.html">voir l'historique →</a>`,
    });
  }
  return null;
}

const RETEST_HTML = `${icon("rotate")}<span>re-tester la chaîne maintenant</span>`;

function warnCard(w) {
  // w = {warnings:[], provider, fallback_to_demo, retry_human}
  const retry = w.retry_human ? ` · nouvel essai dans <b>${esc(w.retry_human)}</b>` : "";
  const served = w.fallback_to_demo ? "mode démo local" : `moteur <b>${esc(w.provider)}</b>`;
  const card = traceCard({
    cls: "warn-card",
    open: true,
    summaryHtml: `${icon("alert")}<span>Repli de moteur → ${served}${retry}</span>`,
    bodyHtml: (w.warnings || []).map(esc).join("<br>") +
      `<div style="margin-top:6px"><button class="hint-btn" type="button" data-retest>${RETEST_HTML}</button></div>`,
  });
  card.querySelector("[data-retest]").addEventListener("click", (e) => retestProviders(e.target.closest("[data-retest]")));
  return card;
}

function userMsgEl(content) {
  const wrap = document.createElement("div");
  wrap.className = "cmsg user";
  const b = document.createElement("div");
  b.className = "bubble umsg";
  b.textContent = content; // texte brut (white-space: pre-wrap en CSS)
  wrap.appendChild(b);
  return wrap;
}

function aiMsgEl(msg, { canRegen } = {}) {
  const wrap = document.createElement("div");
  wrap.className = "cmsg ai";
  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.innerHTML = icon("atom");
  const body = document.createElement("div");
  body.className = "abody";
  const content = document.createElement("div");
  content.className = "bubble md ghost";
  content.innerHTML = md(msg.content);
  const actions = document.createElement("div");
  actions.className = "actions";
  const copy = document.createElement("button");
  copy.type = "button";
  copy.className = "act-btn";
  copy.innerHTML = `${icon("copy")}<span>Copier</span>`;
  copy.addEventListener("click", async () => {
    const label = copy.querySelector("span");
    try {
      await navigator.clipboard.writeText(msg.content);
      label.textContent = "✓ Copié";
      setTimeout(() => { label.textContent = "Copier"; }, 1500);
    } catch { label.textContent = "Échec copie"; }
  });
  actions.appendChild(copy);
  if (canRegen) {
    const regen = document.createElement("button");
    regen.type = "button";
    regen.className = "act-btn";
    regen.innerHTML = `${icon("rotate")}<span>Régénérer</span>`;
    regen.addEventListener("click", () => regenerate());
    actions.appendChild(regen);
  }
  body.append(content, actions);
  wrap.append(avatar, body);
  return wrap;
}

function typingEl() {
  const wrap = document.createElement("div");
  wrap.className = "cmsg ai";
  wrap.innerHTML = `<div class="avatar">${icon("atom")}</div><div class="abody"><div class="dots"><span></span><span></span><span></span></div></div>`;
  return wrap;
}

function errorCard(message) {
  return traceCard({
    cls: "warn-card",
    open: true,
    summaryHtml: `${icon("alert")}<span>Erreur</span>`,
    bodyHtml: esc(message),
  });
}

/* ---------- Rendu : conversation courante ---------- */
function renderConvo() {
  chatLog.innerHTML = "";
  const c = current();
  const empty = !c || !c.messages.length;
  welcomeEl.style.display = empty ? "" : "none";
  if (!c) return;
  c.messages.forEach((m, idx) => {
    if (m.role === "user") {
      chatLog.appendChild(userMsgEl(m.content));
    } else {
      (m.events || []).forEach((ev) => {
        const card = eventCard(ev);
        if (card) chatLog.appendChild(card);
      });
      if (m.warn) chatLog.appendChild(warnCard(m.warn));
      chatLog.appendChild(aiMsgEl(m, { canRegen: idx === c.messages.length - 1 && !isSending }));
    }
  });
  scrollBottom();
}

/* ---------- Rendu : liste des conversations ---------- */
function groupOf(ts) {
  const d = new Date(ts);
  const now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = Math.round((day(now) - day(d)) / 86400000);
  if (diff <= 0) return "Aujourd'hui";
  if (diff === 1) return "Hier";
  if (diff <= 7) return "7 derniers jours";
  return "Plus anciens";
}

function renderConvoList() {
  const q = (convoSearch.value || "").trim().toLowerCase();
  const items = convos
    .filter((c) => !q || (c.title || "").toLowerCase().includes(q))
    .slice()
    .sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));
  convoListEl.innerHTML = "";
  if (!items.length) {
    convoListEl.innerHTML = `<div class="convo-empty small muted">${q ? "Aucun résultat." : "Aucune conversation pour l'instant."}</div>`;
    return;
  }
  let lastGroup = null;
  for (const c of items) {
    const g = groupOf(c.updatedAt || Date.now());
    if (g !== lastGroup) {
      lastGroup = g;
      const h = document.createElement("div");
      h.className = "cgroup";
      h.textContent = g;
      convoListEl.appendChild(h);
    }
    const el = document.createElement("div");
    el.className = "convo" + (c.id === currentId ? " active" : "");
    const title = document.createElement("span");
    title.className = "ctitle";
    title.textContent = c.title || "Sans titre";
    title.title = c.title || "";
    const rn = document.createElement("button");
    rn.type = "button"; rn.className = "crename"; rn.title = "Renommer";
    rn.innerHTML = icon("pencil");
    const del = document.createElement("button");
    del.type = "button"; del.className = "cdel"; del.title = "Supprimer";
    del.innerHTML = icon("x");
    el.append(title, rn, del);
    el.addEventListener("click", (e) => {
      // closest() car le clic peut viser le <svg>/<path> dans le bouton.
      if (e.target.closest(".crename,.cdel")) return;
      openConvo(c.id);
    });
    rn.addEventListener("click", () => startRename(c, el, title));
    del.addEventListener("click", () => deleteConvo(c.id));
    convoListEl.appendChild(el);
  }
}

function startRename(convo, el, titleEl) {
  const input = document.createElement("input");
  input.className = "crename-input";
  input.value = convo.title || "";
  titleEl.replaceWith(input);
  input.focus();
  input.select();
  const commit = (ok) => {
    if (ok && input.value.trim()) convo.title = input.value.trim().slice(0, 80);
    save();
    renderConvoList();
  };
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") commit(true);
    if (e.key === "Escape") commit(false);
    e.stopPropagation();
  });
  input.addEventListener("blur", () => commit(true));
  input.addEventListener("click", (e) => e.stopPropagation());
}

function openConvo(id) {
  if (isSending) return;
  currentId = id;
  save();
  renderConvoList();
  renderConvo();
  closeSidebarMobile();
  chatInput.focus();
}

function deleteConvo(id) {
  convos = convos.filter((c) => c.id !== id);
  if (currentId === id) currentId = null;
  save();
  renderConvoList();
  renderConvo();
  toast("Conversation supprimée");
}

function newChat() {
  if (isSending) return;
  currentId = null;
  save();
  renderConvoList();
  renderConvo();
  closeSidebarMobile();
  chatInput.focus();
}

/* ---------- Envoi ---------- */
async function send(text) {
  const msg = (text ?? chatInput.value).trim();
  if (!msg || isSending) return;
  let c = current();
  if (!c) {
    c = { id: uid(), title: "", createdAt: Date.now(), updatedAt: Date.now(), messages: [] };
    convos.unshift(c);
    currentId = c.id;
  }
  c.messages.push({ role: "user", content: msg });
  touch(c);
  save();
  chatInput.value = "";
  autoresize();
  welcomeEl.style.display = "none";
  chatLog.appendChild(userMsgEl(msg));
  scrollBottom();
  renderConvoList();
  await requestReply(c);
}

async function requestReply(convo) {
  isSending = true;
  sendBtn.disabled = true;
  const typing = typingEl();
  chatLog.appendChild(typing);
  scrollBottom();
  try {
    const res = await apiPost("/api/chat", { messages: apiMessages(convo) });
    typing.remove();
    (res.events || []).forEach((ev) => {
      const card = eventCard(ev);
      if (card) chatLog.appendChild(card);
    });
    let warn = null;
    if (res.warnings && res.warnings.length) {
      console.warn("warnings", res.warnings, "attempts", res.attempts || []);
      warn = {
        warnings: res.warnings,
        provider: res.provider,
        fallback_to_demo: !!res.fallback_to_demo,
        retry_human: res.provider_retry_in_human || "",
      };
      chatLog.appendChild(warnCard(warn));
    }
    const assistantMsg = { role: "assistant", content: res.reply, events: res.events || [], warn };
    convo.messages.push(assistantMsg);
    touch(convo);
    save();
    // Re-rend juste pour placer le bouton Régénérer sur le dernier message.
    renderConvo();
    renderConvoList();
    refreshStatus();
  } catch (e) {
    typing.remove();
    chatLog.appendChild(errorCard(e.message));
    scrollBottom();
  } finally {
    isSending = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

async function regenerate() {
  const c = current();
  if (!c || isSending) return;
  // Retire la dernière réponse IA (le dernier message user est rejoué).
  while (c.messages.length && c.messages[c.messages.length - 1].role === "assistant") c.messages.pop();
  if (!c.messages.length || c.messages[c.messages.length - 1].role !== "user") return;
  save();
  renderConvo();
  await requestReply(c);
}

/* ---------- Statut (topbar + sidebar) ---------- */
function refreshStatus() {
  apiGet("/api/status")
    .then((s) => {
      const modelEl = document.getElementById("model-name");
      if (modelEl) {
        modelEl.textContent = s.demo_mode
          ? "self-improving IA · démo"
          : `self-improving IA · ${s.primary_provider}${s.model ? " · " + s.model : ""}`;
      }
      const side = document.getElementById("side-status");
      if (side) {
        const main = (s.prompts || []).find((p) => p.id === "main");
        const pv = main ? ` · prompt v${main.version} (${esc(s.prompt_updated_by)})` : "";
        if (!s.demo_mode) {
          side.innerHTML = `<span class="chip ok">${esc(s.primary_provider)}${pv}</span>`;
        } else if (s.provider_errors && s.provider_errors.length) {
          side.innerHTML = `<span class="chip warn" title="${esc(s.provider_errors.join(" · "))}">démo · moteurs au repos${s.provider_retry_in_human ? ` (${esc(s.provider_retry_in_human)})` : ""}${pv}</span>`;
        } else {
          side.innerHTML = `<span class="chip warn">démo locale (sans clé API)${pv}</span>`;
        }
        const backend = s.store_backend || "local";
        const repo = s.store_repo ? ` · ${esc(s.store_repo)}` : "";
        side.innerHTML += ` <span class="chip" title="Base de données active">${icon("database")}<span>store: ${esc(backend)}${repo}</span></span>`;
      }
    })
    .catch(() => {});
}

async function retestProviders(btn) {
  if (btn) { btn.disabled = true; btn.textContent = "test des moteurs…"; }
  try {
    const res = await apiPost("/api/providers/retest", { force: true });
    const lines = Object.entries(res.ping || {}).map(([k, v]) => `${k} → ${v}`).join("\n");
    toast(res.errors && res.errors.length ? "Moteurs testés : " + res.errors.length + " en repos" : "Moteurs testés ✓");
    console.info("re-test de la chaîne\n" + lines);
  } catch (e) {
    toast(e.message, true);
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = RETEST_HTML; }
    refreshStatus();
    renderStatusChip();
  }
}

/* ---------- Composer : auto-resize + Entrée/↩ ---------- */
function autoresize() {
  chatInput.style.height = "auto";
  chatInput.style.height = Math.min(chatInput.scrollHeight, 200) + "px";
}
chatInput.addEventListener("input", autoresize);
chatInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

/* ---------- Sidebar : repli/dépliage (desktop) + tiroir (mobile) ---------- */
const LS_SIDE = "aiis.sidebar.v1";
const isMobile = () => window.matchMedia("(max-width: 900px)").matches;
function closeSidebarMobile() {
  sidebar.classList.remove("open");
  overlay.classList.remove("show");
}
document.getElementById("menu-btn").addEventListener("click", () => {
  if (isMobile()) {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("show", sidebar.classList.contains("open"));
  } else {
    document.body.classList.toggle("side-collapsed");
    try { localStorage.setItem(LS_SIDE, document.body.classList.contains("side-collapsed") ? "closed" : "open"); } catch {}
  }
});
overlay.addEventListener("click", closeSidebarMobile);
// En revenant sur desktop, le mode tiroir mobile ne doit pas rester coincé.
window.addEventListener("resize", () => { if (!isMobile()) closeSidebarMobile(); });
// Restaure le choix desktop (repliée ou non).
try { if (!isMobile() && localStorage.getItem(LS_SIDE) === "closed") document.body.classList.add("side-collapsed"); } catch {}

/* ---------- Init ---------- */
chatForm.addEventListener("submit", (e) => { e.preventDefault(); send(); });
document.getElementById("new-chat").addEventListener("click", newChat);
convoSearch.addEventListener("input", renderConvoList);
document.querySelectorAll(".sugg-card").forEach((b) => b.addEventListener("click", () => send(b.dataset.q)));

load();
renderConvoList();
renderConvo();
refreshStatus();
renderStatusChip();
autoresize();
chatInput.focus();
