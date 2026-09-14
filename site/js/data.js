/* Page /data — base de connaissances + redirections vers les datas. */
"use strict";

async function render() {
  const res = await apiGet("/api/data/entries");
  const items = res.entries || [];
  const byCat = {};
  items.forEach((e) => { (byCat[e.category || "autres"] = byCat[e.category || "autres"] || 0)++; });
  document.getElementById("cats").innerHTML = Object.entries(byCat)
    .map(([c, n]) => `<span class="chip">${esc(c)} · ${n}</span>`)
    .join(" ");

  const sorted = items.slice().sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")));
  document.getElementById("data-table").innerHTML =
    `<table>
      <thead><tr><th>Titre</th><th>Catégorie</th><th>Date</th><th>Résumé</th><th>Source</th></tr></thead>
      <tbody>${sorted
        .map(
          (e) => `
          <tr>
            <td><b>${esc(e.title)}</b></td>
            <td>${badge(e.category || "—")}</td>
            <td class="mono small">${esc(e.date || "—")}</td>
            <td class="small muted">${esc(e.summary || "—")}</td>
            <td class="mono small">${esc(e.source || "—")}</td>
          </tr>`
        )
        .join("")}</tbody>
    </table>`;
}

render().catch((e) => toast(e.message, true));
renderStatusChip();
