(function () {
  "use strict";

  const API = "/api/v1/quant";
  let state = null;
  let traceStep = 0;

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

  function renderTicker(quotes) {
    const el = $("#ticker");
    if (!quotes.length) {
      el.innerHTML = '<span class="tick"><span class="sym">No quotes</span></span>';
      return;
    }
    el.innerHTML = quotes.map((q) => {
      const cls = q.change_pct >= 0 ? "up" : "down";
      return `<div class="tick">
        <span class="sym">${q.symbol}</span>
        <span class="px">$${fmt(q.price)}</span>
        <span class="chg ${cls}">${fmtPct(q.change_pct)}</span>
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
    $("#daily-pnl").textContent = fmtMoney(p.daily_pnl) + " (" + fmtPct(p.daily_pnl_pct) + ")";
    $("#daily-pnl").className = "metric-value " + pnlClass(p.daily_pnl);

    const tbody = $("#positions-body");
    if (!p.positions.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty">No positions — run a cycle to start</td></tr>';
    } else {
      tbody.innerHTML = p.positions.map((pos) => `
        <tr>
          <td>${pos.symbol}</td>
          <td>${fmt(pos.quantity, 1)}</td>
          <td>$${fmt(pos.avg_cost)}</td>
          <td>$${fmt(pos.market_price)}</td>
          <td class="${pnlClass(pos.unrealized_pnl)}">${fmtMoney(pos.unrealized_pnl)}</td>
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

  function renderTrace(trace) {
    if (!trace || !trace.steps.length) return;
    const slider = $("#trace-slider");
    slider.max = trace.steps.length - 1;
    if (traceStep >= trace.steps.length) traceStep = trace.steps.length - 1;
    slider.value = traceStep;
    drawGraph(trace, traceStep);
    renderTraceStep(trace.steps[traceStep]);
  }

  function renderTraceStep(step) {
    $("#trace-title").textContent = step.title || "—";
    $("#trace-crs").textContent = "CRS " + (step.crs != null ? step.crs.toFixed(2) : "—");

    const insp = $("#trace-inspector");
    if (step.inspector) {
      const i = step.inspector;
      const stats = i.stats || {};
      insp.innerHTML = `
        <div class="inspector">
          <div class="type">${escapeHtml(i.type || "")}</div>
          <h3>${escapeHtml(i.title || "")}</h3>
          <p>${escapeHtml(i.desc || "")}</p>
          <dl>${Object.entries(stats).map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(String(v))}</dd>`).join("")}</dl>
        </div>`;
    } else {
      insp.innerHTML = '<p class="inspector-empty">No inspector detail for this step.</p>';
    }

    const epEl = $("#trace-episodes");
    epEl.innerHTML = (step.episodes || []).map((e) => `
      <div class="ep-item">
        <span class="t">${escapeHtml(e.t || "")}</span>
        <span class="txt">${e.text || ""}</span>
      </div>`).join("");
  }

  function drawGraph(trace, stepIdx) {
    const svg = $("#trace-graph");
    const step = trace.steps[stepIdx];
    const activeNodes = new Set(step.activeNodes || []);
    const activeEdges = new Set((step.activeEdges || []).map((e) => e.join("→")));

    const nodeMap = {};
    trace.nodes.forEach((n) => { nodeMap[n.id] = n; });

    let edgesHtml = "";
    trace.edges.forEach((e) => {
      const from = nodeMap[e.from];
      const to = nodeMap[e.to];
      if (!from || !to) return;
      const key = e.from + "→" + e.to;
      const cls = activeEdges.has(key) || (activeNodes.has(e.from) && activeNodes.has(e.to)) ? "g-edge active" : "g-edge";
      edgesHtml += `<line class="${cls}" x1="${from.x}" y1="${from.y}" x2="${to.x}" y2="${to.y}" />`;
    });

    let nodesHtml = "";
    trace.nodes.forEach((n) => {
      const kind = n.kind || "obs";
      const active = activeNodes.has(n.id) ? " active" : "";
      const label = (n.label || n.id).slice(0, 18);
      nodesHtml += `<g class="g-node ${kind}${active}" transform="translate(${n.x},${n.y})">
        <circle r="${active ? 14 : 11}" />
        <text y="28" text-anchor="middle">${escapeHtml(label)}</text>
      </g>`;
    });

    svg.innerHTML = edgesHtml + nodesHtml;
  }

  function renderAll(data) {
    state = data;
    $("#cycle-count").textContent = data.cycle_count || 0;
    if (data.scalp_mode) {
      $("#bar-interval").textContent = data.bar_interval || "5m";
    }
    renderTicker(data.quotes);
    renderPortfolio(data.portfolio);
    renderEquity(data.equity_curve);
    renderBeliefs(data.beliefs);
    renderTrades(data.trades);
    renderTrace(data.trace);
    $("#last-updated").textContent = "Updated " + new Date().toLocaleTimeString();
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

  $("#trace-slider").addEventListener("input", (e) => {
    traceStep = parseInt(e.target.value, 10);
    if (state && state.trace) renderTrace(state.trace);
  });

  $("#trace-prev").addEventListener("click", () => {
    if (traceStep > 0) {
      traceStep--;
      if (state && state.trace) renderTrace(state.trace);
    }
  });

  $("#trace-next").addEventListener("click", () => {
    if (state && state.trace && traceStep < state.trace.steps.length - 1) {
      traceStep++;
      renderTrace(state.trace);
    }
  });

  refresh();
  setInterval(refresh, 30000);
})();
