/* Rendu Markdown sûr — zéro dépendance, 100 % local (pas de CDN).
 * Usage : md("**salut**") → HTML assaini prêt pour innerHTML.
 * Gère : titres, gras/italique/barré, code inline + blocs ```lang``` (bouton
 * copier), listes (imbriquées, cases à cocher), citations, tableaux, liens,
 * images http(s), séparateurs. Tout le reste est échappé (anti-XSS).
 */
"use strict";

function md(src) {
  const escHtml = (s) =>
    String(s ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));

  // ---- URLs sûres (anti javascript: / data:) ----
  const safeUrl = (u) => {
    const t = String(u || "").trim();
    if (/^(https?:\/\/|mailto:)/i.test(t)) return escHtml(t);
    if (t.startsWith("/") && !t.startsWith("//")) return escHtml(t);
    if (t.startsWith("#")) return escHtml(t);
    return null;
  };

  let text = String(src ?? "").replace(/\r\n?/g, "\n");

  // ---- 1. Extraire les blocs de code clôturés (protégés du reste du parsing) ----
  const codeBlocks = [];
  text = text.replace(/```(\w[\w+-]*)?[ \t]*\n([\s\S]*?)(?:```|$)/g, (_, lang, code) => {
    codeBlocks.push({ lang: (lang || "").trim(), code: String(code).replace(/\n$/, "") });
    return `\n\x00CODE${codeBlocks.length - 1}\x00\n`;
  });

  // ---- 2. Échapper tout le HTML restant ----
  text = escHtml(text);

  // ---- 3. Inline (appliqué morceau par morceau, jamais dans le code) ----
  const inline = (s) => {
    // code inline protégé d'abord
    const spans = [];
    s = s.replace(/`([^`\n]+?)`/g, (_, c) => {
      spans.push(c);
      return `\x00SPAN${spans.length - 1}\x00`;
    });
    // balises générées (liens/images) mises de côté : l'emphase (*, _, ~)
    // ne doit jamais mordre dedans (ex. un _ dans une URL).
    const tags = [];
    const stash = (html) => {
      tags.push(html);
      return `\x00TAG${tags.length - 1}\x00`;
    };
    // URL avec parenthèses équilibrées d'un niveau : https://fr.wikipedia.org/wiki/X_(homonymie)
    const urlPat = String.raw`((?:[^\s()]|\([^\s()]*\))+)`;
    // images ![alt](url) — http(s) uniquement
    s = s.replace(new RegExp(String.raw`!\[([^\]\n]*?)\]\(${urlPat}(?:\s+&quot;.*?&quot;)?\)`, "g"), (_, alt, url) => {
      const u = safeUrl(url.replace(/&amp;/g, "&"));
      return u ? stash(`<img src="${u}" alt="${alt}" loading="lazy" />`) : inline(alt);
    });
    // liens [texte](url)
    s = s.replace(new RegExp(String.raw`\[([^\]\n]*?)\]\(${urlPat}\)`, "g"), (_, label, url) => {
      const u = safeUrl(url.replace(/&amp;/g, "&"));
      return u ? stash(`<a href="${u}" target="_blank" rel="noopener">${inline(label)}</a>`) : `${inline(label)}`;
    });
    // URLs nues → liens
    s = s.replace(/(^|[\s(])(https?:\/\/[^\s<)\]]+)/g, (_, pre, url) => {
      const u = safeUrl(url.replace(/&amp;/g, "&"));
      return u ? pre + stash(`<a href="${u}" target="_blank" rel="noopener">${url}</a>`) : `${pre}${url}`;
    });
    // gras+italique, gras, italique, barré
    s = s.replace(/\*\*\*([^*\n]+?)\*\*\*/g, "<strong><em>$1</em></strong>");
    s = s.replace(/___([^_\n]+?)___/g, "<strong><em>$1</em></strong>");
    s = s.replace(/\*\*([^*\n]+?)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/__([^_\n]+?)__/g, "<strong>$1</strong>");
    s = s.replace(/(^|[\s(])\*([^*\n]+?)\*/g, "$1<em>$2</em>");
    s = s.replace(/(^|[\s(])_([^_\n]+?)_/g, "$1<em>$2</em>");
    s = s.replace(/~~([^~\n]+?)~~/g, "<del>$1</del>");
    // restaurer liens/images puis code inline
    s = s.replace(/\x00TAG(\d+)\x00/g, (_, i) => tags[Number(i)]);
    s = s.replace(/\x00SPAN(\d+)\x00/g, (_, i) => `<code>${spans[Number(i)]}</code>`);
    return s;
  };

  // ---- 4. Blocs ----
  const lines = text.split("\n");
  const out = [];
  let para = [];
  const flushPara = () => {
    if (para.length) {
      // Confort chat : un \n simple = retour à la ligne (<br>).
      out.push(`<p>${para.map(inline).join("<br>")}</p>`);
      para = [];
    }
  };

  const isCodePh = (l) => /^\x00CODE\d+\x00$/.test(l.trim());
  const codeHtml = (l) => {
    const b = codeBlocks[Number(l.trim().replace(/\D/g, ""))];
    const label = b.lang ? escHtml(b.lang) : "code";
    return `<div class="codeblock"><div class="codeblock-head"><span>${label}</span>` +
      `<button type="button" class="copy-btn" data-copy>Copier</button></div>` +
      `<pre><code${b.lang ? ` class="lang-${escHtml(b.lang)}"` : ""}>${escHtml(b.code)}</code></pre></div>`;
  };

  const isTableDelim = (l) => /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(l) && l.includes("-");

  const tableHtml = (headLine, delimLine, bodyLines) => {
    const splitRow = (l) => {
      let t = l.trim();
      if (t.startsWith("|")) t = t.slice(1);
      if (t.endsWith("|")) t = t.slice(0, -1);
      return t.split("|").map((c) => c.trim());
    };
    // :--- gauche · :---: centré · ---: droite
    const aligns = splitRow(delimLine).map((c) => {
      if (!/^:?-+:?$/.test(c)) return "";
      const left = c.startsWith(":");
      const right = c.endsWith(":") && c.length > 1;
      if (left && right) return "center";
      if (left) return "left";
      if (right) return "right";
      return "";
    });
    const head = splitRow(headLine);
    const n = Math.max(head.length, aligns.length, 1);
    const th = (c, i) => `<th${aligns[i] ? ` style="text-align:${aligns[i]}"` : ""}>${inline(c)}</th>`;
    const td = (c, i) => `<td${aligns[i] ? ` style="text-align:${aligns[i]}"` : ""}>${inline(c)}</td>`;
    let h = `<div class="md-table"><table><thead><tr>`;
    for (let i = 0; i < n; i++) h += th(head[i] ?? "", i);
    h += `</tr></thead><tbody>`;
    for (const bl of bodyLines) {
      const cells = splitRow(bl);
      h += "<tr>";
      for (let i = 0; i < n; i++) h += td(cells[i] ?? "", i);
      h += "</tr>";
    }
    return h + `</tbody></table></div>`;
  };

  // Listes (puces / numérotées, imbrication par indentation, cases à cocher)
  const parseList = (start) => {
    const items = []; // {indent, ordered, body, task}
    let i = start;
    const re = /^(\s*)([-*+]|\d+[.)])\s+(.*)$/;
    const first = lines[start].match(re);
    const baseIndent = first[1].replace(/\t/g, "  ").length;
    const baseOrdered = /^\d/.test(first[2]);
    for (; i < lines.length; i++) {
      const m = lines[i].match(re);
      if (!m) break;
      const indent = m[1].replace(/\t/g, "  ").length;
      // Changement puces ↔ numérotée au niveau de base = nouvelle liste.
      if (i > start && indent === baseIndent && /^\d/.test(m[2]) !== baseOrdered) break;
      let body = m[3];
      let task = null;
      const tm = body.match(/^\[([ xX])\]\s+(.*)$/);
      if (tm) { task = tm[1].toLowerCase() === "x"; body = tm[2]; }
      items.push({ indent, ordered: /^\d/.test(m[2]), body, task });
    }
    // Construit l'arbre par niveaux d'indentation
    const root = { children: [] };
    const stack = [{ node: root, indent: -1 }];
    for (const it of items) {
      while (stack.length > 1 && it.indent <= stack[stack.length - 1].indent) stack.pop();
      const node = { ...it, children: [] };
      stack[stack.length - 1].node.children.push(node);
      stack.push({ node, indent: it.indent });
    }
    const render = (nodes) => {
      if (!nodes.length) return "";
      const ordered = nodes[0].ordered;
      const tag = ordered ? "ol" : "ul";
      return `<${tag}>` + nodes.map((n) => {
        const box = n.task === null ? "" :
          `<input type="checkbox" disabled${n.task ? " checked" : ""} /> `;
        return `<li>${box}${inline(n.body)}${render(n.children)}</li>`;
      }).join("") + `</${tag}>`;
    };
    return { html: render(root.children), next: i };
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const t = line.trim();

    if (!t) { flushPara(); continue; }
    if (isCodePh(line)) { flushPara(); out.push(codeHtml(line)); continue; }

    // Titres
    const h = t.match(/^(#{1,6})\s+(.*)$/);
    if (h) { flushPara(); out.push(`<h${h[1].length} class="md-h">${inline(h[2])}</h${h[1].length}>`); continue; }

    // Séparateur
    if (/^(-{3,}|\*{3,}|_{3,})$/.test(t)) { flushPara(); out.push("<hr />"); continue; }

    // Tableau : ligne avec | suivie d'une ligne délimiteur
    if (t.includes("|") && i + 1 < lines.length && isTableDelim(lines[i + 1])) {
      flushPara();
      const body = [];
      let j = i + 2;
      while (j < lines.length && lines[j].trim().includes("|") && lines[j].trim()) { body.push(lines[j]); j++; }
      out.push(tableHtml(line, lines[i + 1], body));
      i = j - 1;
      continue;
    }

    // Citation (récursif)
    if (/^&gt;/.test(t)) {
      flushPara();
      const quote = [];
      while (i < lines.length && (/^&gt;/.test(lines[i].trim()) || !lines[i].trim())) {
        quote.push(lines[i].trim().replace(/^&gt; ?/, ""));
        i++;
      }
      i--;
      // On décode les entités (&amp; EN DERNIER pour ne pas double-décoder)
      // puis md() ré-échappera proprement.
      const inner = quote.join("\n")
        .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'").replace(/&amp;/g, "&");
      out.push(`<blockquote>${md(inner)}</blockquote>`);
      continue;
    }

    // Liste
    if (/^(\s*)([-*+]|\d+[.)])\s+/.test(line)) {
      flushPara();
      const { html, next } = parseList(i);
      out.push(html);
      i = next - 1;
      continue;
    }

    para.push(line.trim());
  }
  flushPara();
  return out.join("\n");
}

// Bouton "Copier" des blocs de code (délégation globale, une seule fois)
if (typeof document !== "undefined" && !document.__mdCopyBound) {
  document.__mdCopyBound = true;
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-copy]");
    if (!btn) return;
    const code = btn.closest(".codeblock")?.querySelector("pre code");
    if (!code) return;
    try {
      await navigator.clipboard.writeText(code.innerText);
      const old = btn.textContent;
      btn.textContent = "Copié ✓";
      setTimeout(() => { btn.textContent = old; }, 1500);
    } catch {
      btn.textContent = "Échec copie";
    }
  });
}
