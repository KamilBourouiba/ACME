(function () {
  const API = (window.ACME_DEMO_API || "").replace(/\/$/, "");
  let selectedAgent = "analyst";
  let state = null;
  let eventSource = null;

  const els = {
    agentList: document.getElementById("agent-list"),
    messages: document.getElementById("messages"),
    beliefList: document.getElementById("belief-list"),
    beliefTitle: document.getElementById("belief-title"),
    beliefSubtitle: document.getElementById("belief-subtitle"),
    statusText: document.getElementById("status-text"),
    liveDot: document.getElementById("live-dot"),
    modelLabel: document.getElementById("model-label"),
    tickLabel: document.getElementById("tick-label"),
    error: document.getElementById("demo-error"),
    resetBtn: document.getElementById("reset-btn"),
  };

  function showError(msg) {
    els.error.hidden = false;
    els.error.textContent = msg;
    els.statusText.textContent = "Offline";
    els.liveDot.classList.add("off");
  }

  function clearError() {
    els.error.hidden = true;
  }

  function initials(name) {
    return name.slice(0, 1).toUpperCase();
  }

  function renderAgents(agents) {
    els.agentList.innerHTML = agents
      .map(
        (a) => `
      <button type="button" class="agent-card ${a.id === selectedAgent ? "active" : ""}" data-agent="${a.id}">
        <div class="agent-avatar" style="background:${a.color}">${initials(a.name)}</div>
        <div class="meta">
          <strong>${escapeHtml(a.name)}</strong>
          <span>${escapeHtml(a.role)} · ${a.belief_count} beliefs</span>
        </div>
      </button>`
      )
      .join("");

    els.agentList.querySelectorAll(".agent-card").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedAgent = btn.dataset.agent;
        render(state);
      });
    });
  }

  function renderMessages(messages) {
    if (!messages.length) {
      els.messages.innerHTML = '<div class="demo-empty">Waiting for the first turn…</div>';
      return;
    }
    els.messages.innerHTML = messages
      .map((m) => {
        const agent = state.agents.find((a) => a.id === m.agent_id) || {};
        const color = agent.color || "#0f4c5c";
        const answer = m.answer
          ? `<div class="answer"><strong>ACME answer:</strong> ${escapeHtml(m.answer)}</div>`
          : "";
        return `
        <article class="msg" style="border-left: 3px solid ${color}">
          <div class="msg-head">
            <strong>${escapeHtml(m.agent_name)}</strong>
            <span class="kind">${escapeHtml(m.kind)}</span>
          </div>
          <p>${escapeHtml(m.content)}</p>
          ${answer}
        </article>`;
      })
      .join("");
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function renderBeliefs(agents) {
    const agent = agents.find((a) => a.id === selectedAgent);
    if (!agent) {
      els.beliefTitle.textContent = "Beliefs";
      els.beliefSubtitle.textContent = "Select an agent.";
      els.beliefList.innerHTML = '<div class="demo-empty">No agent selected.</div>';
      return;
    }
    els.beliefTitle.textContent = `${agent.name}'s beliefs`;
    els.beliefSubtitle.textContent = `Tenant ${agent.tenant_id} · CRS-governed lifecycle`;
    if (!agent.top_beliefs.length) {
      els.beliefList.innerHTML = '<div class="demo-empty">No promoted beliefs yet — keep watching.</div>';
      return;
    }
    els.beliefList.innerHTML = agent.top_beliefs
      .map(
        (b) => `
      <div class="belief-item">
        <div class="label">${escapeHtml(b.label)}</div>
        <div class="belief-meta">
          <span class="crs">CRS ${Number(b.crs).toFixed(2)}</span>
          <span>${escapeHtml(b.status)}</span>
          <span>conf ${Number(b.confidence).toFixed(2)}</span>
        </div>
      </div>`
      )
      .join("");
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function render(next) {
    if (!next) return;
    state = next;
    els.modelLabel.textContent = next.model || "—";
    els.tickLabel.textContent = String(next.tick || 0);
    if (next.running) {
      els.statusText.textContent = "Live";
      els.liveDot.classList.remove("off");
    }
    renderAgents(next.agents || []);
    renderMessages(next.messages || []);
    renderBeliefs(next.agents || []);
  }

  function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`${API}/api/v1/demo/events`);

    eventSource.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.state) render(data.state);
        else if ((data.type === "turn" || data.type === "reset") && data.state) render(data.state);
      } catch (e) {
        console.warn("demo event parse error", e);
      }
    };

    eventSource.onerror = () => {
      els.statusText.textContent = "Reconnecting…";
      els.liveDot.classList.add("off");
    };
  }

  async function resetDemo() {
    if (!els.resetBtn || els.resetBtn.disabled) return;
    els.resetBtn.disabled = true;
    const prev = els.resetBtn.textContent;
    els.resetBtn.textContent = "Resetting…";
    try {
      const res = await fetch(`${API}/api/v1/demo/reset`, { method: "POST" });
      if (res.status === 429) {
        const body = await res.json().catch(() => ({}));
        showError(body.detail || "Reset cooldown — try again in a minute.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      clearError();
      const stateRes = await fetch(`${API}/api/v1/demo/state`);
      if (stateRes.ok) render(await stateRes.json());
    } catch (err) {
      showError(`Reset failed: ${err.message}`);
    } finally {
      els.resetBtn.textContent = prev;
      els.resetBtn.disabled = false;
    }
  }

  async function bootstrap() {
    try {
      const res = await fetch(`${API}/api/v1/demo/state?agent=${selectedAgent}`);
      if (res.status === 503) {
        showError(
          "Live demo is not enabled on this API deployment yet. Set DEMO_ENABLED=true (and optionally DEMO_AZURE_DEPLOYMENT=gpt-5.4) on the server."
        );
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      clearError();
      render(await res.json());
      connectSSE();
    } catch (err) {
      showError(`Could not reach demo API at ${API}: ${err.message}`);
    }
  }

  bootstrap();

  if (els.resetBtn) {
    els.resetBtn.addEventListener("click", resetDemo);
  }
})();
