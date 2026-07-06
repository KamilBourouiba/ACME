(function () {
  "use strict";

  const API = "/api/v1/quant";
  let state = null;
  let traceStep = 0;
  let traceFollowLive = true;
  let lastTraceLen = 0;

  const $ = (sel) => document.querySelector(sel);

  function fmt(n, dec = 2) {
    if (n == null || isNaN(n)) return "—";
    return n.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }

  function fmtPct(n) {
    if (n == null || isNaN(n)) return "—";
    const sign = n >= 0 ? "+" : "";
    return sign + n.toFixed(2) + "%";
  }

  function fmtMoney(n) {
    if (n == null || isNaN(n)) return "—";
    const sign = n >= 0 ? "" : "-";
    return sign + "$" + fmt(Math.abs(n), 0);
  }

  function pnlClass(n) {
    if (n == null) return "";
    return n >= 0 ? "positive" : "negative";
  }

  function toast(msg) {
    const el = $("#toast");
    el.textContent = msg;
    el.hidden = false;
    setTimeout(() => { el.hidden = true; }, 3500);
  }

  function timeShort(iso) {
    if (!iso) return "—";
    const d = new Date(iso);
    return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  async function fetchState() {
    const r = await fetch(API + "/state");
    if (!r.ok) throw new Error("Failed to load state");
    return r.json();
  }

  function isCrypto(sym) {
    return String(sym).toUpperCase().endsWith("-USD");
  }

  function fmtQty(symbol, qty) {
    if (qty == null || isNaN(qty)) return "—";
    const dec = isCrypto(symbol) ? 4 : 1;
    return qty.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
  }

  function assetTag(sym) {
    return isCrypto(sym)
      ? '<span class="asset-tag crypto">CRYPTO</span>'
      : '<span class="asset-tag equity">EQUITY</span>';
  }

  function sumUnrealized(positions) {
    return positions.reduce((n, p) => n + (p.unrealized_pnl || 0), 0);
  }

  function renderPositionsStrip(positions) {
    const cards = $("#positions-cards");
    const strip = $("#positions-strip");
    const countEl = $("#positions-count");
    const upnlEl = $("#positions-upnl");
    const pill = $("#positions-pill");
    const summary = $("#positions-summary");
    const totalUpnl = sumUnrealized(positions);

    countEl.textContent = positions.length
      ? positions.length + " open"
      : "0 open";
    upnlEl.textContent = positions.length
      ? "uPnL " + fmtMoney(totalUpnl) + " (" + fmtPct(
          positions.reduce((s, p) => s + (p.unrealized_pnl_pct || 0), 0) / positions.length
        ) + " avg)"
      : "uPnL —";
    upnlEl.className = "positions-upnl " + pnlClass(totalUpnl);

    summary.textContent = positions.length
      ? positions.length + " · " + fmtMoney(totalUpnl)
      : "0";
    pill.className = "stat-pill " + (positions.length ? "positions-live " + pnlClass(totalUpnl) : "positions-idle-pill");
    strip.classList.toggle("has-positions", positions.length > 0);

    if (!positions.length) {
      cards.innerHTML = '<div class="positions-idle"><span class="idle-icon">○</span> All cash — no open positions yet<br><span class="idle-hint">Scalp entries appear here instantly (crypto 24/7)</span></div>';
      return;
    }

    const sorted = [...positions].sort((a, b) => Math.abs(b.unrealized_pnl) - Math.abs(a.unrealized_pnl));
    cards.innerHTML = sorted.map((pos) => `
      <article class="position-card ${pnlClass(pos.unrealized_pnl)}">
        <div class="pc-head">
          <span class="pc-symbol">${pos.symbol}</span>
          ${assetTag(pos.symbol)}
          <span class="pc-side">LONG</span>
        </div>
        <div class="pc-upnl ${pnlClass(pos.unrealized_pnl)}">${fmtMoney(pos.unrealized_pnl)}</div>
        <div class="pc-upnl-pct ${pnlClass(pos.unrealized_pnl)}">${fmtPct(pos.unrealized_pnl_pct)}</div>
        <dl class="pc-meta">
          <div><dt>Qty</dt><dd>${fmtQty(pos.symbol, pos.quantity)}</dd></div>
          <div><dt>Entry</dt><dd>$${fmt(pos.avg_cost)}</dd></div>
          <div><dt>Mark</dt><dd>$${fmt(pos.market_price)}</dd></div>
          <div><dt>Value</dt><dd>${fmtMoney(pos.market_value)}</dd></div>
          <div><dt>Weight</dt><dd>${fmt(pos.weight_pct, 1)}%</dd></div>
        </dl>
      </article>`).join("");
  }

  function renderTicker(quotes, positions) {
    const el = $("#ticker");
    const held = new Set((positions || []).map((p) => p.symbol));
    if (!quotes.length) {
      el.innerHTML = '<span class="tick"><span class="sym">No quotes</span></span>';
      return;
    }
    el.innerHTML = quotes.map((q) => {
      const cls = q.change_pct >= 0 ? "up" : "down";
      const heldCls = held.has(q.symbol) ? " held" : "";
      const pos = (positions || []).find((p) => p.symbol === q.symbol);
      const badge = pos
        ? `<span class="held-badge ${pnlClass(pos.unrealized_pnl)}">${fmtPct(pos.unrealized_pnl_pct)}</span>`
        : "";
      return `<div class="tick${heldCls}">
        <span class="sym">${q.symbol}${held.has(q.symbol) ? " ●" : ""}</span>
        <span class="px">$${fmt(q.price)}</span>
        <span class="chg ${cls}">${fmtPct(q.change_pct)}</span>
        ${badge}
      </div>`;
    }).join("");
  }

  function renderPortfolio(p) {
    $("#nav-value").textContent = fmtMoney(p.nav);
    $("#pnl-value").textContent = fmtPct(p.total_pnl_pct);
    $("#pnl-value").className = "value " + pnlClass(p.total_pnl_pct);
    $("#pnl-pill").className = "stat-pill " + pnlClass(p.total_pnl_pct);

    $("#cash-badge").textContent = "Cash " + fmtMoney(p.cash);
    $("#total-pnl").textContent = fmtMoney(p.total_pnl) + " (" + fmtPct(p.total_pnl_pct) + ")";
    $("#total-pnl").className = "metric-value " + pnlClass(p.total_pnl);
    $("#cycle-pnl").textContent = fmtMoney(p.cycle_pnl) + " (" + fmtPct(p.cycle_pnl_pct) + ")";
    $("#cycle-pnl").className = "metric-value " + pnlClass(p.cycle_pnl);

    const tbody = $("#positions-body");
    renderPositionsStrip(p.positions);
    if (!p.positions.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No positions — see strip above</td></tr>';
    } else {
      tbody.innerHTML = p.positions.map((pos) => `
        <tr class="row-held ${pnlClass(pos.unrealized_pnl)}">
          <td><strong>${pos.symbol}</strong> ${isCrypto(pos.symbol) ? '<span class="asset-tag crypto">C</span>' : ""}</td>
          <td>${fmtQty(pos.symbol, pos.quantity)}</td>
          <td>$${fmt(pos.avg_cost)}</td>
          <td>$${fmt(pos.market_price)}</td>
          <td class="${pnlClass(pos.unrealized_pnl)}"><strong>${fmtMoney(pos.unrealized_pnl)}</strong> <span class="sub-pct">${fmtPct(pos.unrealized_pnl_pct)}</span></td>
          <td>${fmt(pos.weight_pct, 1)}%</td>
        </tr>`).join("");
    }
  }

  function renderEquity(curve) {
    const canvas = $("#equity-chart");
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    canvas.width = w * dpr;
    canvas.height = 80 * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, 80);

    if (!curve || curve.length < 2) {
      ctx.fillStyle = "#7a8a9e";
      ctx.font = "11px IBM Plex Mono, monospace";
      ctx.fillText("Equity curve builds over cycles", 12, 44);
      return;
    }

    const navs = curve.map((c) => c.nav);
    const min = Math.min(...navs) * 0.998;
    const max = Math.max(...navs) * 1.002;
    const pad = 8;

    ctx.beginPath();
    curve.forEach((c, i) => {
      const x = pad + (i / (curve.length - 1)) * (w - pad * 2);
      const y = 80 - pad - ((c.nav - min) / (max - min)) * (80 - pad * 2);
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    const last = navs[navs.length - 1];
    const first = navs[0];
    ctx.strokeStyle = last >= first ? "#3dd68c" : "#f07178";
    ctx.lineWidth = 1.5;
    ctx.stroke();

    ctx.lineTo(pad + (w - pad * 2), 80 - pad);
    ctx.lineTo(pad, 80 - pad);
    ctx.closePath();
    ctx.fillStyle = last >= first ? "rgba(61,214,140,0.08)" : "rgba(240,113,120,0.08)";
    ctx.fill();
  }

  function renderBeliefs(beliefs) {
    const el = $("#belief-list");
    if (!beliefs.length) {
      el.innerHTML = '<li class="empty">No beliefs yet — ingest market data first</li>';
      return;
    }
    el.innerHTML = beliefs.map((b) => `
      <li>
        <div class="belief-row">
          <span class="belief-label">${escapeHtml(b.label)}</span>
          <span class="belief-crs">${b.crs.toFixed(2)}</span>
        </div>
        <div class="belief-meta">
          <span class="status-${b.status}">${b.status}</span>
          <span>ev ${b.supporting_evidence}</span>
          <span>pred ${b.prediction_successes}/${b.prediction_successes + b.prediction_failures}</span>
        </div>
      </li>`).join("");
  }

  function renderTrades(trades) {
    const tbody = $("#trades-body");
    if (!trades.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty">No trades yet</td></tr>';
      return;
    }
    tbody.innerHTML = trades.map((t) => `
      <tr>
        <td>${timeShort(t.created_at)}</td>
        <td class="side-${t.side}">${t.side.toUpperCase()}</td>
        <td>${t.symbol}</td>
        <td>${fmt(t.quantity, 1)}</td>
        <td>$${fmt(t.price)}</td>
        <td>${t.crs_at_trade != null ? t.crs_at_trade.toFixed(2) : "—"}</td>
        <td title="${escapeHtml(t.belief_label || "")}">${escapeHtml((t.belief_label || t.reasoning || "—").slice(0, 40))}</td>
      </tr>`).join("");
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  const PHASE_ICON = { market: "◎", belief: "◆", trade: "▸", cycle: "↻" };

  function renderTrace(trace) {
    if (!trace || !trace.steps.length) {
      $("#trace-timeline").innerHTML = '<span class="trace-empty">Trail builds as cycles run…</span>';
      return;
    }

    const steps = trace.steps;
    const wasOnLatest = traceFollowLive || traceStep >= steps.length - 1;
    if (wasOnLatest && steps.length > lastTraceLen) {
      traceStep = steps.length - 1;
    }
    if (traceStep >= steps.length) traceStep = steps.length - 1;
    lastTraceLen = steps.length;

    renderTraceTimeline(steps, traceStep);
    drawGraph(trace, traceStep);
    renderTraceStep(steps[traceStep]);
  }

  function renderTraceTimeline(steps, activeIdx) {
    const el = $("#trace-timeline");
    el.innerHTML = steps.map((s, i) => {
      const phase = s.phase || "cycle";
      const icon = PHASE_ICON[phase] || "•";
      const active = i === activeIdx ? " active" : "";
      const crs = s.crs != null ? s.crs.toFixed(2) : "—";
      return `<button type="button" class="trace-chip${active}" data-idx="${i}" title="${escapeHtml(s.summary || s.title || "")}">
        <span class="chip-phase phase-${phase}">${icon}</span>
        <span class="chip-body">
          <span class="chip-title">${escapeHtml(s.title || `Step ${i + 1}`)}</span>
          <span class="chip-crs">CRS ${crs}</span>
        </span>
      </button>`;
    }).join("");

    el.querySelectorAll(".trace-chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        traceStep = parseInt(btn.dataset.idx, 10);
        traceFollowLive = traceStep >= steps.length - 1;
        $("#trace-follow-live").checked = traceFollowLive;
        if (state && state.trace) renderTrace(state.trace);
      });
    });

    const active = el.querySelector(".trace-chip.active");
    if (active) active.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
  }

  function renderTraceStep(step) {
    $("#trace-title").textContent = step.title || "—";
    $("#trace-summary").textContent = step.summary || "";
    $("#trace-crs").textContent = "CRS " + (step.crs != null ? step.crs.toFixed(2) : "—");

    const insp = $("#trace-inspector");
    if (step.inspector) {
      const i = step.inspector;
      const stats = i.stats || {};
      insp.innerHTML = `
        <div class="inspector">
          <div class="type type-${(step.phase || "cycle")}">${escapeHtml(i.type || step.phase || "")}</div>
          <h3>${escapeHtml(i.title || "")}</h3>
          <p>${escapeHtml(i.desc || "")}</p>
          <dl>${Object.entries(stats).map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v))}</dd>`).join("")}</dl>
        </div>`;
    } else {
      insp.innerHTML = '<p class="inspector-empty">No detail for this step.</p>';
    }

    const epEl = $("#trace-episodes");
    epEl.innerHTML = (step.episodes || []).map((e) => `
      <div class="ep-card">
        <span class="t">${escapeHtml(e.t || "")}</span>
        <span class="txt">${e.text || ""}</span>
      </div>`).join("");
  }

  function drawGraph(trace, stepIdx) {
    const svg = $("#trace-graph");
    const step = trace.steps[stepIdx];
    const activeNodes = new Set(step.activeNodes || []);
    const activeEdgeKeys = new Set((step.activeEdges || []).map((e) => e.join("→")));

    const nodeMap = {};
    trace.nodes.forEach((n) => { nodeMap[n.id] = n; });

    const colLabels = [
      { x: 100, t: "MARKET" },
      { x: 280, t: "EXTRACT" },
      { x: 480, t: "BELIEF" },
      { x: 680, t: "TRADE" },
    ];

    let html = '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto"><path d="M0,0 L6,3 L0,6 Z" fill="currentColor"/></marker></defs>';
    html += '<g class="g-cols">';
    colLabels.forEach((c) => {
      html += `<text x="${c.x}" y="28" text-anchor="middle" class="g-col-label">${c.t}</text>`;
      html += `<line x1="${c.x}" y1="40" x2="${c.x}" y2="340" class="g-col-line"/>`;
    });
    html += "</g>";

    trace.edges.forEach((e) => {
      const from = nodeMap[e.from];
      const to = nodeMap[e.to];
      if (!from || !to) return;
      const key = e.from + "→" + e.to;
      const active = activeEdgeKeys.has(key) || (activeNodes.has(e.from) && activeNodes.has(e.to));
      html += `<line class="g-edge${active ? " active" : ""}" x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" marker-end="url(#arrow)"/>`;
    });

    trace.nodes.forEach((n) => {
      const kind = n.kind || "obs";
      const active = activeNodes.has(n.id);
      const label = escapeHtml(n.short || n.label || n.id);
      const w = Math.min(120, 14 + label.length * 5.5);
      const h = 36;
      const x = n.x - w / 2;
      const y = n.y - h / 2;
      const crs = n.crs != null ? `<text x="${n.x}" y="${n.y + 4}" class="g-node-crs">${n.crs.toFixed(2)}</text>` : "";
      html += `<g class="g-node ${kind}${active ? " active" : ""}" transform="translate(0,0)">
        <rect x="${x}" y="${y}" width="${w}" height="${h}" rx="8" class="g-node-rect"/>
        <text x="${n.x}" y="${n.y - 2}" text-anchor="middle" class="g-node-label">${label}</text>
        ${crs}
      </g>`;
    });

    svg.innerHTML = html;
  }

  function renderAll(data) {
    state = data;
    $("#cycle-count").textContent = data.cycle_count || 0;
    if (data.scalp_mode) {
      $("#bar-interval").textContent = data.bar_interval || "5m";
    }
    const marketPill = $("#market-pill");
    const marketStatus = $("#market-status");
    if (data.market_label) {
      const crypto = data.crypto_enabled && (data.crypto_symbols || []).length;
      const openLabel = data.market_open ? (crypto ? "24/7" : "Open") : "Closed";
      marketStatus.textContent = crypto && !data.equities_open ? "Crypto" : openLabel;
      marketPill.title = data.market_label;
      marketPill.className = "stat-pill " + (data.market_open ? "market-open" : "market-closed");
    } else {
      marketStatus.textContent = "—";
      marketPill.className = "stat-pill";
    }
    renderTicker(data.quotes, data.portfolio.positions);
    renderPortfolio(data.portfolio);
    renderEquity(data.equity_curve);
    renderBeliefs(data.beliefs);
    renderTrades(data.trades);
    renderTrace(data.trace);
    $("#last-updated").textContent = "Live · " + new Date().toLocaleTimeString();
    $("#signals-export").href = API + "/signals";
  }

  async function refresh() {
    try {
      const data = await fetchState();
      renderAll(data);
    } catch (e) {
      toast("Failed to load dashboard: " + e.message);
    }
  }

  async function runCycle() {
    const btn = $("#btn-cycle");
    btn.disabled = true;
    btn.textContent = "Running…";
    try {
      const r = await fetch(API + "/cycle", { method: "POST" });
      const result = await r.json();
      toast(result.message || "Cycle complete");
      await refresh();
    } catch (e) {
      toast("Cycle failed: " + e.message);
    } finally {
      btn.disabled = false;
      btn.textContent = "Run cycle";
    }
  }

  $("#btn-refresh").addEventListener("click", refresh);
  $("#btn-cycle").addEventListener("click", runCycle);

  $("#trace-follow-live").addEventListener("change", (e) => {
    traceFollowLive = e.target.checked;
    if (traceFollowLive && state && state.trace) {
      traceStep = state.trace.steps.length - 1;
      renderTrace(state.trace);
    }
  });

  $("#trace-latest").addEventListener("click", () => {
    traceFollowLive = true;
    $("#trace-follow-live").checked = true;
    if (state && state.trace) {
      traceStep = state.trace.steps.length - 1;
      renderTrace(state.trace);
    }
  });

  $("#trace-prev").addEventListener("click", () => {
    if (traceStep > 0) {
      traceStep--;
      traceFollowLive = false;
      $("#trace-follow-live").checked = false;
      if (state && state.trace) renderTrace(state.trace);
    }
  });

  $("#trace-next").addEventListener("click", () => {
    if (state && state.trace && traceStep < state.trace.steps.length - 1) {
      traceStep++;
      traceFollowLive = traceStep >= state.trace.steps.length - 1;
      $("#trace-follow-live").checked = traceFollowLive;
      renderTrace(state.trace);
    }
  });

  refresh();
  setInterval(refresh, 3000);
})();
