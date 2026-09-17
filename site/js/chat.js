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
const modelNameEl = document.getElementById("model-name");
const thinkingBtn = document.getElementById("thinking-btn");

/* ---------- État ---------- */
const LS_CONVOS = "aiis.convos.v1";
const LS_ACTIVE = "aiis.activeConvo.v1";
const LS_THINKING = "aiis.thinking.v1";

let convos = [];      // [{id, title, createdAt, updatedAt, messages:[{role, content, thinking?, thinkingEffort?, thinkingMs?, events?, warn?}]}]
let currentId = null; // null = nouveau chat (non persisté tant que vide)
let isSending = false;

/* Mode Pensée : effort de réflexion choisi en bas de la barre de chat (façon Claude).
   "off" = réponse directe sans bloc de réflexion ; sinon l'IA raisonne dans un
   bloc <think> proportionnel à l'effort. Persisté (mêmes niveaux que le back). */
const THINKING_EFFORTS = ["off", "low", "medium", "high"];
const THINKING_LABELS = { off: "Thinking", low: "Faible", medium: "Moyen", high: "Élevé" };
let thinkingEffort = "off";

// Vision : images en attente pour ce message (remis à zéro à chaque envoi,
// changement de conversation ou nouveau chat). Chaque entrée = data-URL
// { type:"image_url", image_url:{url} } → envoyé tel quel à l'API. Pas de
// stockage fichier : tout part en base64 vers le moteur de vision.
const MAX_IMAGES = 4;
const MAX_IMAGE_BYTES = 2 * 1024 * 1024;
let pendingImages = [];

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : String(Date.now() + Math.random()));
const current = () => convos.find((c) => c.id === currentId) || null;
/* Vision : extrait le texte d'un contenu (string ou blocs) et les blocs image.
   `apiMessages` conserve les blocs (le back les envoie au moteur de vision). */
const textOf = (c) => {
  if (typeof c === "string") return c;
  if (Array.isArray(c)) {
    return c
      .filter((b) => b && b.type === "text")
      .map((b) => String(b.text || ""))
      .join("\n");
  }
  return String(c ?? "");
};
const imagesOf = (c) =>
  Array.isArray(c)
    ? c.filter((b) => b && b.type === "image_url" && b.image_url)
    : [];
const apiMessages = (c) =>
  c ? c.messages.map((m) => ({ role: m.role, content: m.content })) : [];
const showTitle = (c) => {
  if (!c) return "Nouveau chat";
  if (c.renamedByUser) return c.title || "Conversation";
  if (!c.messages || !c.messages.length) return "Nouveau chat";
  if (c.title) return c.title;
  const q = c.messages.find((m) => m.role === "user");
  return q ? q.content.trim().split("\n")[0].slice(0, 42) : "Nouveau chat";
};
const activeHint = (c) => {
  if (!c || !c.messages || !c.messages.length) return "";
  if (c.renamedByUser) return "";
  if (c.title) return "Titre généré par l'IA";
  return c.messages.find((m) => m.role === "user") ? "Titre provisoire — l'IA le nommera" : "";
};

function load() {
  try { convos = JSON.parse(localStorage.getItem(LS_CONVOS) || "[]"); } catch { convos = []; }
  if (!Array.isArray(convos)) convos = [];
  currentId = localStorage.getItem(LS_ACTIVE) || null;
  if (currentId && !current()) currentId = null;
  try {
    const raw = localStorage.getItem(LS_THINKING);
    if (raw === "true") thinkingEffort = "medium"; // migration de l'ancien réglage booléen
    else if (raw && THINKING_EFFORTS.includes(raw)) thinkingEffort = raw;
    else thinkingEffort = "off";
  } catch {
    thinkingEffort = "off";
  }
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
}

// Icônes SVG : renvoie vers le sprite <symbol> défini dans index.html.
const icon = (name) => `<svg class="ic" aria-hidden="true"><use href="#i-${name}" /></svg>`;

const thinkingMenu = document.getElementById("thinking-menu");

function updateThinkingUI() {
  if (!thinkingBtn) return;
  const active = thinkingEffort !== "off";
  thinkingBtn.classList.toggle("active", active);
  thinkingBtn.setAttribute("aria-pressed", active ? "true" : "false");
  thinkingBtn.title = active
    ? `Mode Pensée : EFFORT ${THINKING_LABELS[thinkingEffort].toUpperCase()} (cliquer pour changer)`
    : "Mode Pensée : DÉSACTIVÉ (cliquer pour choisir l'effort)";
  const label = thinkingBtn.querySelector(".thinking-label");
  if (label) label.textContent = THINKING_LABELS[thinkingEffort];
  document.querySelectorAll(".thinking-opt").forEach((o) => {
    const on = o.dataset.effort === thinkingEffort;
    o.classList.toggle("selected", on);
    o.setAttribute("aria-checked", on ? "true" : "false");
  });
}

let thinkingMenuOpen = false;
function openThinkingMenu() {
  if (!thinkingMenu) return;
  thinkingMenu.hidden = false;
  thinkingMenuOpen = true;
  thinkingBtn.setAttribute("aria-expanded", "true");
}
function closeThinkingMenu() {
  if (!thinkingMenu) return;
  thinkingMenu.hidden = true;
  thinkingMenuOpen = false;
  thinkingBtn.setAttribute("aria-expanded", "false");
}
function setThinkingEffort(effort) {
  if (!THINKING_EFFORTS.includes(effort)) return;
  thinkingEffort = effort;
  try {
    localStorage.setItem(LS_THINKING, effort);
  } catch {}
  closeThinkingMenu();
  updateThinkingUI();
}

if (thinkingBtn) {
  thinkingBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    if (thinkingMenuOpen) closeThinkingMenu();
    else openThinkingMenu();
  });
  if (thinkingMenu) {
    thinkingMenu.addEventListener("click", (e) => {
      const opt = e.target.closest(".thinking-opt");
      if (opt) setThinkingEffort(opt.dataset.effort);
    });
    // Clic ailleurs ou Échap : referme le menu.
    document.addEventListener("click", (e) => {
      if (thinkingMenuOpen && !e.target.closest(".thinking-picker")) closeThinkingMenu();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && thinkingMenuOpen) {
        closeThinkingMenu();
        thinkingBtn.focus();
      }
    });
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

function thinkingTimeLabel(thinkingText, ms) {
  if (!thinkingText) return "";
  const fmt = (sec) => String(sec < 10 ? Math.round(sec * 10) / 10 : Math.round(sec)).replace(".", ",") + " s";
  // Durée mesurée (stream progressif) si disponible, sinon estimation à ~4 mots/s
  // (cas du mode démo : le bloc arrive en un seul jeton → pas de mesure possible).
  if (ms && ms >= 400) return fmt(ms / 1000);
  const words = thinkingText.trim().split(/\s+/).length;
  return fmt(Math.max(0.2, words / 4));
}

function thinkingCard(thinkingText, { open = false, effort = null, ms = 0 } = {}) {
  const d = document.createElement("details");
  d.className = "thinking-box";
  if (open) d.open = true;
  const effortBadge = effort && effort !== "off"
    ? `<span class="thinking-effort">effort ${THINKING_LABELS[effort] || effort}</span>`
    : "";
  const s = document.createElement("summary");
  s.innerHTML = `${icon("brain")}<span>Think</span>${effortBadge}<span class="thinking-time">(${thinkingTimeLabel(thinkingText, ms)})</span>`;
  const content = document.createElement("div");
  content.className = "thinking-content";
  content.textContent = thinkingText;
  d.append(s, content);
  return d;
}

function parseRawThinking(raw) {
  if (!raw) return { reply: "", thinking: "", isThinkingLive: false };
  const openIdx = raw.indexOf("<think>");
  if (openIdx === -1) {
    return { reply: raw, thinking: "", isThinkingLive: false };
  }
  const closeIdx = raw.indexOf("</think>", openIdx);
  if (closeIdx === -1) {
    // Balise <think> ouverte mais non fermée : flux de pensée en cours
    const thinking = raw.slice(openIdx + 7).trimStart();
    const replyBefore = raw.slice(0, openIdx).trim();
    return { reply: replyBefore, thinking, isThinkingLive: true };
  }
  const thinking = raw.slice(openIdx + 7, closeIdx).trim();
  const reply = (raw.slice(0, openIdx) + raw.slice(closeIdx + 8)).trimStart();
  return { reply, thinking, isThinkingLive: false };
}

function eventCard(ev) {
  if (ev.type === "tool") {
    if (ev.skill === "web_agent") {
      const r = ev.result || {};
      const say = r.say || (ev.args || {}).say || "";
      const hits = Array.isArray(r.hits) ? r.hits : [];
      const lines = hits.slice(0, 5).map((h, i) => {
        const title = esc(h.title || "(sans titre)");
        const url = esc(h.url || "");
        const snip = esc((h.snippet || h.excerpt || "").slice(0, 160));
        return `<div class="agent-hit"><b>${i + 1}.</b> ${title}${url ? ` <span class="muted">${url}</span>` : ""}<br>${snip}</div>`;
      }).join("");
      return traceCard({
        cls: "agent",
        open: true,
        summaryHtml: `${icon("wrench")}<span>agent · <b>${esc(r.kind || "search")}</b></span> <span class="muted">${esc(say || r.target || "").slice(0, 90)}</span>`,
        bodyHtml:
          (say ? `<p><i>${esc(say)}</i></p>` : "") +
          `<p class="muted small">${esc(r.engine || "")} · ${esc(r.browser || "http")} · ${hits.length} hit(s)</p>` +
          (lines || "→ aucun hit") +
          (r.next_hint ? `<p class="muted small">${esc(r.next_hint)}</p>` : ""),
      });
    }
    const args = Object.entries(ev.args || {}).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(" · ");
    const ok = ev.result && ev.result.ok !== false;
    return traceCard({
      summaryHtml: `${icon("wrench")}<span>skill <b>${esc(ev.skill)}</b></span> <span class="muted">${esc(args).slice(0, 80)}</span>`,
      bodyHtml: ok
        ? "→ " + esc(JSON.stringify(ev.result)).slice(0, 400)
        : "→ Erreur : " + esc((ev.result || {}).error || "erreur"),
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
  if (Array.isArray(content)) {
    const imgs = imagesOf(content);
    const text = textOf(content).trim();
    if (imgs.length) {
      const figs = document.createElement("div");
      figs.className = "umsg-imgs";
      for (const blk of imgs) {
        const img = document.createElement("img");
        img.src = (blk.image_url && blk.image_url.url) || "";
        img.alt = "Image jointe au message";
        img.loading = "lazy";
        figs.appendChild(img);
      }
      wrap.appendChild(figs);
    }
    if (text) {
      const b = document.createElement("div");
      b.className = "bubble umsg";
      b.textContent = text;
      wrap.appendChild(b);
    }
    if (!imgs.length && !text) {
      const b = document.createElement("div");
      b.className = "bubble umsg";
      b.textContent = "[image]";
      wrap.appendChild(b);
    }
    return wrap;
  }
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

  if (msg.thinking) {
    body.appendChild(thinkingCard(msg.thinking, { open: false, effort: msg.thinkingEffort, ms: msg.thinkingMs || 0 }));
  }

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

/* ---------- Titre affiché dans la barre du haut ---------- */
function renderTitle() {
  const c = current();
  if (!c) {
    modelNameEl.textContent = "Nouveau chat";
    modelNameEl.classList.remove("ai-title", "provisional");
    return;
  }
  const hint = activeHint(c);
  modelNameEl.textContent = showTitle(c);
  modelNameEl.classList.toggle("ai-title", !!hint && c.title);
  modelNameEl.classList.toggle("provisional", !!hint && !c.title);
  modelNameEl.title = hint || showTitle(c);
}

/* ---------- Rendu : conversation courante ---------- */
function renderConvo() {
  chatLog.innerHTML = "";
  const c = current();
  const empty = !c || !c.messages.length;
  welcomeEl.style.display = empty ? "" : "none";
  renderTitle();
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
    .filter((c) => !q || (showTitle(c) || "").toLowerCase().includes(q))
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
    title.textContent = showTitle(c);
    title.title = showTitle(c);
    const rn = document.createElement("button");
    rn.type = "button"; rn.className = "crename"; rn.title = "Renommer";
    rn.innerHTML = icon("pencil");
    const del = document.createElement("button");
    del.type = "button"; del.className = "cdel"; del.title = "Supprimer";
    del.innerHTML = icon("x");
    el.append(title, rn, del);
    el.addEventListener("click", (e) => {
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
  input.value = showTitle(convo);
  titleEl.replaceWith(input);
  input.focus();
  input.select();
  const commit = (ok) => {
    if (ok && input.value.trim()) {
      convo.title = input.value.trim().slice(0, 80);
      convo.renamedByUser = true;
    }
    save();
    renderConvoList();
    renderTitle();
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
  pendingImages = [];
  renderStaged();
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
  pendingImages = [];
  renderStaged();
  save();
  renderConvoList();
  renderConvo();
  closeSidebarMobile();
  chatInput.focus();
}

/* ---------- Envoi ---------- */
async function send(text) {
  const raw = text ?? chatInput.value;
  const msg = String(raw ?? "").trim();
  const images = pendingImages.slice(0, MAX_IMAGES);
  if (!msg && !images.length) return;
  if (isSending) return;

  let c = current();
  if (!c) {
    c = { id: uid(), title: "", createdAt: Date.now(), updatedAt: Date.now(), messages: [] };
    convos.unshift(c);
    currentId = c.id;
  }

  const content = images.length
    ? [
        ...(msg ? [{ type: "text", text: msg }] : []),
        ...images.map((u) => ({ type: "image_url", image_url: { url: u } })),
      ]
    : msg;

  c.messages.push({ role: "user", content });
  touch(c);
  save();
  chatInput.value = "";
  pendingImages = [];
  renderStaged();
  autoresize();
  welcomeEl.style.display = "none";
  chatLog.appendChild(userMsgEl(content));
  scrollBottom();
  renderConvoList();
  renderTitle();
  await requestReply(c);
}

/* Assistant en cours (élément reconstruit à chaque delta). */
function createAssistant() {
  const wrap = document.createElement("div");
  wrap.className = "cmsg ai";
  wrap.innerHTML = `<div class="avatar">${icon("atom")}</div><div class="abody"><div class="live-thinking-slot"></div><div class="bubble md ghost live-bubble"></div><div class="actions"><button type="button" class="act-btn live-copy">${icon("copy")}<span>Copier</span></button></div></div>`;
  let rawText = "";
  let thinkingStart = 0; // horodatage du 1er jeton du bloc de réflexion
  let thinkingMs = 0;    // durée mesurée du raisonnement (0 = pas mesurable, ex. démo)
  const liveThinkingSlot = wrap.querySelector(".live-thinking-slot");
  const bubble = wrap.querySelector(".bubble");
  const copyBtn = wrap.querySelector(".live-copy");

  copyBtn.addEventListener("click", async () => {
    const label = copyBtn.querySelector("span");
    try {
      const parsed = parseRawThinking(rawText);
      await navigator.clipboard.writeText(parsed.reply || rawText);
      label.textContent = "✓ Copié";
      setTimeout(() => { label.textContent = "Copier"; }, 1500);
    } catch { label.textContent = "Échec copie"; }
  });

  return {
    el: wrap,
    append() { if (!wrap.parentNode) chatLog.appendChild(wrap); },
    appendToken(delta) {
      rawText += delta;
      const parsed = parseRawThinking(rawText);
      if (parsed.thinking) {
        if (!thinkingStart) thinkingStart = performance.now();
        let box = liveThinkingSlot.querySelector(".thinking-box");
        if (!box) {
          box = document.createElement("details");
          box.className = "thinking-box";
          box.open = true;
          const effortBadge = thinkingEffort !== "off"
            ? `<span class="thinking-effort">effort ${THINKING_LABELS[thinkingEffort]}</span>`
            : "";
          box.innerHTML = `
            <summary>${icon("brain")}<span class="think-title">Think…</span>${effortBadge}<span class="thinking-live-badge"></span></summary>
            <div class="thinking-content"></div>
          `;
          liveThinkingSlot.appendChild(box);
        }
        const contentEl = box.querySelector(".thinking-content");
        if (contentEl) contentEl.textContent = parsed.thinking;
        const titleEl = box.querySelector(".think-title");
        const badgeEl = box.querySelector(".thinking-live-badge");
        if (!parsed.isThinkingLive) {
          if (titleEl) titleEl.textContent = "Think";
          if (badgeEl) badgeEl.remove();
          if (!thinkingMs) thinkingMs = Math.round(performance.now() - thinkingStart);
        }
      }
      bubble.innerHTML = md(parsed.reply);
      scrollBottom();
    },
    get text() { return parseRawThinking(rawText).reply; },
    get thinkingMs() { return thinkingMs; },
    remove() { wrap.remove(); },
  };
}

/* Lit un flux SSE retourné par /api/chat/stream et alimente `events`.
   Récupère : les deltas `token` (pour les afficher en direct), puis l'événement
   `done` (reply complet + events + warnings + attempts). Lance `onToken` pour
   chaque delta et `onDone` une seule fois à la fin.
 */
async function consumeStream(url, body, { onToken, onDone }) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => "");
    throw new Error(`POST ${url} → ${res.status} ${detail}`);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  let finished = false;
  let donePayload = null;
  while (!finished) {
    const { value, done } = await reader.read();
    buf += decoder.decode(value || new Uint8Array(), { stream: !done });
    const parts = buf.split("\n\n");
    buf = parts.pop();
    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload || payload === "[DONE]") continue;
        let ev;
        try { ev = JSON.parse(payload); } catch { continue; }
        if (ev.type === "token") onToken(ev);
        else if (ev.type === "done") donePayload = ev;
      }
    }
    if (done) finished = true;
  }
  onDone(donePayload);
}

/* Génère un titre via le modèle (best-effort, le premier provider cloud qui
   répond). L'IA ne voit QUE le message utilisateur décodé, jamais les event
   tools/prompt internes. Si le titre ne convient pas, l'utilisateur peut le
   renommer ; son choix gagne alors définitivement (renamedByUser).
 */
async function generateAITitle(msgs) {
  if (!msgs || !msgs.length) return null;
  const q = msgs.filter((m) => m.role === "user").map((m) => textOf(m.content)).join("\n");
  try {
    const r = await apiPost("/api/title", {
      messages: [
        {
          role: "user",
          content:
            "Génère UN titre court (2 à 5 mots, en français si la question est en français) " +
            "qui résume cette conversation, sans guillemets ni ponctuation finale :\n" +
            q.slice(0, 400),
        },
      ],
    });
    const t = String(r.title || "").trim();
    return t && t.length < 80 ? t : null;
  } catch {
    return null;
  }
}

async function requestReply(convo) {
  isSending = true;
  sendBtn.disabled = true;
  const typing = typingEl();
  chatLog.appendChild(typing);
  scrollBottom();

  let ai = createAssistant();
  try {
    await consumeStream(
      API + "/api/chat/stream",
      { messages: apiMessages(convo), thinking: thinkingEffort },
      {
        onToken: (ev) => {
          if (typing.parentNode) typing.remove();
          ai.append();
          ai.appendToken(ev.content || "");
        },
        onDone: (done) => {
          finishReply(convo, done);
        },
      }
    );
  } catch (e) {
    typing.remove();
    ai.remove();
    chatLog.appendChild(errorCard(e.message));
    scrollBottom();
  } finally {
    isSending = false;
    sendBtn.disabled = false;
    chatInput.focus();
  }
}

function finishReply(convo, done, ai) {
  const typing = chatLog.querySelector(".cmsg .dots");
  if (typing) typing.closest(".cmsg").remove();
  if (!done) {
    chatLog.appendChild(errorCard("Réponse interrompue (aucun événement `done` reçu)."));
    scrollBottom();
    return;
  }
  (done.events || []).forEach((ev) => {
    const card = eventCard(ev);
    if (card) chatLog.appendChild(card);
  });
  let warn = null;
  if (done.warnings && done.warnings.length) {
    console.warn("warnings", done.warnings, "attempts", done.attempts || []);
    warn = {
      warnings: done.warnings,
      provider: done.provider,
      fallback_to_demo: !!done.fallback_to_demo,
      retry_human: done.provider_retry_in_human || "",
    };
    chatLog.appendChild(warnCard(warn));
  }
  const assistantMsg = {
    role: "assistant",
    content: done.reply,
    thinking: done.thinking || (parseRawThinking(done.reply || "").thinking || null),
    thinkingEffort: done.thinking_effort || (thinkingEffort !== "off" ? thinkingEffort : null),
    // Durée réelle du raisonnement (ms) si le flux était progressif ; sinon null
    // → la carte estime à partir du nombre de mots (~4 mots/s).
    thinkingMs: ai && ai.thinkingMs >= 400 ? ai.thinkingMs : null,
    events: done.events || [],
    warn,
  };
  convo.messages.push(assistantMsg);
  touch(convo);
  save();

  // Re-rend pour placer le bouton Régénérer sur le dernier message.
  renderConvo();
  renderConvoList();
  renderTitle();

  if (!convo.renamedByUser && !convo.title) {
    generateAITitle(convo.messages).then((t) => {
      if (t && !convo.renamedByUser && !convo.title) {
        convo.title = t;
        save();
        renderConvoList();
        renderTitle();
      }
    });
  }
}

async function regenerate() {
  const c = current();
  if (!c || isSending) return;
  while (c.messages.length && c.messages[c.messages.length - 1].role === "assistant") c.messages.pop();
  if (!c.messages.length || c.messages[c.messages.length - 1].role !== "user") return;
  save();
  renderConvo();
  await requestReply(c);
}

/* ---------- Statut ---------- */
function refreshStatus() {
  apiGet("/api/status")
    .then((s) => {
      const side = document.getElementById("side-status");
      if (!side) return;
      const main = (s.prompts || []).find((p) => p.id === "main");
      const pv = main ? ` · prompt v${main.version}` : "";
      if (!s.demo_mode) {
        side.innerHTML = `<span class="chip ok">${esc(s.primary_provider)}${pv}</span>`;
      } else if (s.provider_errors && s.provider_errors.length) {
        side.innerHTML = `<span class="chip warn" title="${esc(s.provider_errors.join(" · "))}">démo · moteurs au repos${s.provider_retry_in_human ? ` (${esc(s.provider_retry_in_human)})` : ""}${pv}</span>`;
      } else {
        side.innerHTML = `<span class="chip warn">démo locale (aucune clé API)${pv}</span>`;
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
  }
}

/* ---------- Composer : images (vision) ---------- */
function imageThumb(dataUrl) {
  const el = document.createElement("div");
  el.className = "att";
  const img = document.createElement("img");
  img.src = dataUrl;
  img.alt = "";
  const x = document.createElement("button");
  x.type = "button";
  x.className = "att-x";
  x.title = "Retirer l'image";
  x.setAttribute("aria-label", "Retirer l'image");
  x.innerHTML = icon("x");
  x.addEventListener("click", () => {
    pendingImages = pendingImages.filter((u) => u !== dataUrl);
    renderStaged();
  });
  el.append(img, x);
  return el;
}

function renderStaged() {
  const strip = document.getElementById("image-strip");
  if (!strip) return;
  strip.innerHTML = "";
  strip.hidden = pendingImages.length === 0;
  for (const u of pendingImages) strip.appendChild(imageThumb(u));
  const btn = document.getElementById("attach-btn");
  if (btn) btn.disabled = pendingImages.length >= MAX_IMAGES;
}

function addImages(files) {
  if (isSending) { toast("Réponse en cours…", true); return; }
  const list = Array.from(files || []).slice(0, MAX_IMAGES - pendingImages.length);
  const rejected = [];
  let over = 0;
  let done = 0;
  const finish = () => {
    if (rejected.length) toast((over ? "Certaines images dépassent 2 Mo. " : "") + rejected.join(" · "), true);
    renderStaged();
  };
  if (!list.length) { if (files && files.length) toast("Maximum " + MAX_IMAGES + " images par message.", true); return; }
  for (const f of list) {
    if (f.size > MAX_IMAGE_BYTES) { over += 1; continue; }
    const r = new FileReader();
    r.onload = () => {
      const dataUrl = String(r.result);
      if (pendingImages.length < MAX_IMAGES) {
        pendingImages.push(dataUrl);
      }
      done += 1;
      if (done === list.length - over) finish();
    };
    r.onerror = () => { rejected.push(f.name + " illisible"); done += 1; if (done === list.length - over) finish(); };
    r.readAsDataURL(f);
  }
}

const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("file-input");
if (attachBtn && fileInput) {
  attachBtn.addEventListener("click", () => fileInput.click());
  fileInput.addEventListener("change", () => {
    addImages(fileInput.files);
    fileInput.value = "";
  });
}

/* Coller une image (capture d'écran ou fichier copié) : elle part en vision. */
document.addEventListener("paste", (e) => {
  if (isSending) return;
  const files = [];
  for (const item of Array.from(e.clipboardData?.items || [])) {
    if (item.kind === "file" && item.type && item.type.startsWith("image/")) {
      const f = item.getAsFile();
      if (f) files.push(f);
    }
  }
  if (files.length) {
    e.preventDefault();
    addImages(files);
  }
});

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
window.addEventListener("resize", () => { if (!isMobile()) closeSidebarMobile(); });
try { if (!isMobile() && localStorage.getItem(LS_SIDE) === "closed") document.body.classList.add("side-collapsed"); } catch {}

/* ---------- Init ---------- */
chatForm.addEventListener("submit", (e) => { e.preventDefault(); send(); });
const topNewChat = document.getElementById("top-new-chat");
if (topNewChat) topNewChat.addEventListener("click", newChat);
document.querySelectorAll("a[href='/index.html']").forEach((a) => {
  a.addEventListener("click", (e) => { e.preventDefault(); newChat(); });
});
convoSearch.addEventListener("input", renderConvoList);
document.querySelectorAll(".sugg-card").forEach((b) => b.addEventListener("click", () => send(b.dataset.q)));

load();
updateThinkingUI();
renderConvoList();
renderConvo();
refreshStatus();
autoresize();
chatInput.focus();
