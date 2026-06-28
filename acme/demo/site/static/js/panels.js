/** Entity list, inspector panel, source chips. */

export function renderSourceChips(sources, active) {
  const el = document.getElementById("source-chips");
  if (!el) return;
  el.innerHTML = sources
    .map(
      (s) =>
        `<span class="source-chip${s.id === active ? " active" : ""}" data-source="${s.id}">${s.label}</span>`
    )
    .join("");
}

export function renderEntityList(nodes, selectedId, onSelect) {
  const el = document.getElementById("entity-list");
  if (!el) return;
  if (!nodes.length) {
    el.innerHTML = `<div class="empty-state">Run a search to populate the graph.</div>`;
    return;
  }
  el.innerHTML = nodes
    .map(
      (n) => `
    <div class="entity-row${n.id === selectedId ? " selected" : ""}" data-id="${n.id}">
      <span class="entity-dot ${n.kind}"></span>
      <div>
        <div class="entity-title">${escapeHtml(n.label)}</div>
        <div class="entity-meta">${escapeHtml(n.source || n.kind)}</div>
      </div>
      <span class="entity-score">${n.score ?? "—"}</span>
    </div>`
    )
    .join("");

  el.querySelectorAll(".entity-row").forEach((row) => {
    row.addEventListener("click", () => {
      const id = row.dataset.id;
      const node = nodes.find((x) => x.id === id);
      if (node) onSelect(node);
    });
  });
}

export function renderInspector(node, detail) {
  const el = document.getElementById("inspector");
  if (!el || !node) return;

  const stats = detail?.stats || node.stats || {};
  const relations = detail?.relations || node.relations || [];

  el.innerHTML = `
    <div class="inspector-header">
      <div class="inspector-type">${escapeHtml(node.kind)} · ${escapeHtml(node.source || "oss")}</div>
      <h2 class="inspector-title">${escapeHtml(node.label)}</h2>
      <p class="inspector-desc">${escapeHtml(detail?.description || node.description || "")}</p>
    </div>
    <div class="stat-grid">
      ${Object.entries(stats)
        .slice(0, 4)
        .map(
          ([k, v]) => `
        <div class="stat-cell">
          <div class="stat-cell-label">${escapeHtml(k)}</div>
          <div class="stat-cell-value">${escapeHtml(String(v))}</div>
        </div>`
        )
        .join("")}
    </div>
    ${
      relations.length
        ? `<div class="mono dim" style="margin-bottom:8px">Relations</div>
           <div class="relation-list">${relations
             .map(
               (r) => `
             <div class="relation-item" data-rel-id="${escapeHtml(r.id)}">
               <span>${escapeHtml(r.label)}</span>
               <span class="relation-arrow">→ ${escapeHtml(r.type)}</span>
             </div>`
             )
             .join("")}</div>`
        : ""
    }
    ${
      node.url
        ? `<a class="source-link" href="${escapeHtml(node.url)}" target="_blank" rel="noopener">Open in ${escapeHtml(node.source || "source")} ↗</a>`
        : ""
    }
  `;
}

export function renderSearchResults(groups, onPick) {
  const el = document.getElementById("search-results");
  if (!el) return;
  if (!groups.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = groups
    .map(
      (g) => `
    <div class="search-group">
      <div class="search-group-title">${escapeHtml(g.source)}</div>
      ${g.items
        .map(
          (item) => `
        <div class="search-hit" data-pick="${encodeURIComponent(JSON.stringify(item))}">
          <div class="search-hit-title">${escapeHtml(item.label)}</div>
          <div class="search-hit-sub">${escapeHtml(item.sub || "")}</div>
        </div>`
        )
        .join("")}
    </div>`
    )
    .join("");

  el.querySelectorAll(".search-hit").forEach((hit) => {
    hit.addEventListener("click", () => {
      try {
        onPick(JSON.parse(decodeURIComponent(hit.dataset.pick)));
      } catch (_) {}
    });
  });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
