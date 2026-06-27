(function () {
  const API = (window.ACME_DEMO_API || "").replace(/\/$/, "");
  let state = null;
  let selectedChannel = "general";
  let selectedAgent = null;
  let agentBeliefs = null;
  let lastBeliefFetch = 0;
  let eventSource = null;

  const els = {
    channelList: document.getElementById("channel-list"),
    channelTitle: document.getElementById("channel-title"),
    channelTopic: document.getElementById("channel-topic"),
    messages: document.getElementById("messages"),
    memberList: document.getElementById("member-list"),
    beliefTitle: document.getElementById("belief-title"),
    beliefSubtitle: document.getElementById("belief-subtitle"),
    beliefList: document.getElementById("belief-list"),
    artifactList: document.getElementById("artifact-list"),
    livePill: document.getElementById("live-pill"),
    modelLabel: document.getElementById("model-label"),
    tickLabel: document.getElementById("tick-label"),
    error: document.getElementById("demo-error"),
    deployBanner: document.getElementById("deploy-banner"),
    liveSiteLink: document.getElementById("live-site-link"),
    resetBtn: document.getElementById("reset-btn"),
  };

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function formatTime(iso) {
    if (!iso) return "";
    try {
      return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } catch {
      return "";
    }
  }

  function formatText(text) {
    return escapeHtml(text).replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }

  function showError(msg) {
    els.error.hidden = false;
    els.error.textContent = msg;
    els.livePill.textContent = "Offline";
    els.livePill.classList.remove("on");
  }

  function clearError() {
    els.error.hidden = true;
  }

  function showDeployBanner(deploy) {
    if (!deploy || !deploy.pages_url) {
      els.deployBanner.hidden = true;
      if (els.liveSiteLink) els.liveSiteLink.hidden = true;
      return;
    }
    const verified = deploy.pages_verified ? "verified live" : "deployed";
    els.deployBanner.hidden = false;
    els.deployBanner.innerHTML =
      `Squad published (${verified}) → <a href="${escapeHtml(deploy.pages_url)}" target="_blank" rel="noopener">${escapeHtml(deploy.pages_url)}</a>`;
    if (els.liveSiteLink) {
      els.liveSiteLink.hidden = false;
      els.liveSiteLink.href = deploy.pages_url;
    }
  }

  function renderChannels(channels) {
    els.channelList.innerHTML = (channels || [])
      .map(
        (c) => `
      <button type="button" class="channel-btn ${c.id === selectedChannel ? "active" : ""}" data-channel="${c.id}">
        <span class="hash">#</span>${escapeHtml(c.name)}
      </button>`
      )
      .join("");

    els.channelList.querySelectorAll(".channel-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedChannel = btn.dataset.channel;
        const ch = (state.channels || []).find((x) => x.id === selectedChannel);
        els.channelTitle.textContent = `#${ch?.name || selectedChannel}`;
        els.channelTopic.textContent = ch?.topic || "";
        render(state);
      });
    });
  }

  function renderMembers(agents) {
    els.memberList.innerHTML = (agents || [])
      .map(
        (a) => `
      <button type="button" class="member-btn ${a.id === selectedAgent ? "active" : ""}" data-agent="${a.id}">
        <div class="avatar" style="background:${a.color}">${escapeHtml(a.initials || a.name.slice(0, 2))}</div>
        <div class="info">
          <strong>${escapeHtml(a.name)}</strong>
          <span>${escapeHtml(a.role)} · ${a.belief_count} beliefs</span>
        </div>
      </button>`
      )
      .join("");

    els.memberList.querySelectorAll(".member-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        selectedAgent = btn.dataset.agent;
        agentBeliefs = null;
        lastBeliefFetch = 0;
        loadAgentBeliefs(selectedAgent);
        render(state);
      });
    });
  }

  function renderBeliefs(agent, beliefs) {
    if (!agent) {
      els.beliefTitle.textContent = "Select a teammate";
      els.beliefSubtitle.textContent = "Each role keeps an isolated belief graph.";
      els.beliefList.innerHTML = '<div class="empty-state" style="padding:1rem">Click a team member.</div>';
      return;
    }
    const list = beliefs || [];
    els.beliefTitle.textContent = `${agent.name} · ${list.length} beliefs`;
    els.beliefSubtitle.textContent = `${agent.role} · tenant ${agent.tenant_id}`;
    if (!list.length) {
      els.beliefList.innerHTML = '<div class="empty-state" style="padding:1rem">No beliefs yet — keep watching.</div>';
      return;
    }
    els.beliefList.innerHTML = list
      .map(
        (b) => `
      <div class="belief-item">
        <div class="label">${escapeHtml(b.label)}</div>
        <div class="belief-meta">
          <span class="crs">CRS ${Number(b.crs).toFixed(2)}</span>
          <span>${escapeHtml(b.status)}</span>
          <span>conf ${Number(b.confidence).toFixed(2)}</span>
          <span>+${b.supporting_evidence || 0}/-${b.contradicting_evidence || 0}</span>
        </div>
      </div>`
      )
      .join("");
  }

  async function loadAgentBeliefs(agentId) {
    if (!agentId) return;
    try {
      const res = await fetch(`${API}/api/v1/demo/agents/${agentId}`);
      if (!res.ok) return;
      agentBeliefs = await res.json();
      lastBeliefFetch = Date.now();
      const agent = (state?.agents || []).find((a) => a.id === agentId);
      renderBeliefs(agent, agentBeliefs.beliefs);
    } catch (e) {
      console.warn("belief fetch failed", e);
    }
  }

  function renderArtifacts(artifacts) {
    const files = Object.keys(artifacts || {});
    els.artifactList.innerHTML = files.length
      ? files.map((f) => `<li>${escapeHtml(f)}</li>`).join("")
      : "<li>No files yet</li>";
  }

  function renderMessages(messages, agents) {
    const filtered = (messages || []).filter((m) => m.channel === selectedChannel);
    if (!filtered.length) {
      els.messages.innerHTML = '<div class="empty-state">No messages in this channel yet.</div>';
      return;
    }

    els.messages.innerHTML = filtered
      .map((m) => {
        const agent = (agents || []).find((a) => a.id === m.agent_id) || {};
        const color = agent.color || "#611f69";
        const initials = agent.initials || m.agent_name.slice(0, 2);
        const badge = m.kind !== "message" ? `<span class="kind-badge">${escapeHtml(m.kind)}</span>` : "";
        let code = "";
        if (m.code_body) {
          code = `
          <div class="code-block">
            <div class="code-head"><span>${escapeHtml(m.code_file || "file")}</span><span>${escapeHtml(m.code_lang || "")}</span></div>
            <pre>${escapeHtml(m.code_body.slice(0, 1200))}${m.code_body.length > 1200 ? "\n…" : ""}</pre>
          </div>`;
        }
        const answer = m.answer
          ? `<div class="acme-answer"><strong>ACME:</strong> ${escapeHtml(m.answer)}</div>`
          : "";
        return `
        <article class="msg-row">
          <div class="avatar" style="background:${color}">${escapeHtml(initials)}</div>
          <div class="msg-body">
            <div class="msg-meta">
              <strong>${escapeHtml(m.agent_name)}</strong>
              <span class="role">${escapeHtml(m.role)}</span>
              <time>${formatTime(m.timestamp)}</time>${badge}
            </div>
            <div class="msg-text">${formatText(m.content)}</div>
            ${code}${answer}
          </div>
        </article>`;
      })
      .join("");
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function render(next) {
    if (!next) return;
    state = next;

    els.modelLabel.textContent = next.model || "—";
    els.tickLabel.textContent = String(next.tick || 0);
    if (next.running) {
      els.livePill.textContent = "Live";
      els.livePill.classList.add("on");
    }

    const ch = (next.channels || []).find((c) => c.id === selectedChannel) || next.channels?.[0];
    if (ch && !selectedChannel) selectedChannel = ch.id;
    if (ch) {
      els.channelTitle.textContent = `#${ch.name}`;
      els.channelTopic.textContent = ch.topic;
    }

    renderChannels(next.channels);
    renderMembers(next.agents);
    renderMessages(next.messages, next.agents);
    const agent = selectedAgent ? (next.agents || []).find((a) => a.id === selectedAgent) : null;
    renderBeliefs(agent, agentBeliefs?.id === selectedAgent ? agentBeliefs.beliefs : null);
    renderArtifacts(next.artifacts);
    showDeployBanner(next.last_deploy);
  }

  function maybeRefreshBeliefs() {
    if (!selectedAgent) return;
    const now = Date.now();
    if (now - lastBeliefFetch < 15000) return;
    lastBeliefFetch = now;
    loadAgentBeliefs(selectedAgent);
  }

  function connectSSE() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource(`${API}/api/v1/demo/events`);
    eventSource.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.state) {
          render(data.state);
          maybeRefreshBeliefs();
        }
      } catch (e) {
        console.warn("demo parse error", e);
      }
    };
    eventSource.onerror = () => {
      els.livePill.textContent = "Reconnecting";
      els.livePill.classList.remove("on");
    };
  }

  async function bootstrap() {
    try {
      const res = await fetch(`${API}/api/v1/demo/state`);
      if (res.status === 503) {
        showError("Live demo is not enabled on this API deployment.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      clearError();
      render(await res.json());
      connectSSE();
    } catch (err) {
      showError(`Could not reach demo API: ${err.message}`);
    }
  }

  async function resetDemo() {
    els.resetBtn.disabled = true;
    try {
      const res = await fetch(`${API}/api/v1/demo/reset`, { method: "POST" });
      if (res.status === 429) {
        const body = await res.json().catch(() => ({}));
        showError(body.detail || "Reset cooldown active.");
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      clearError();
      agentBeliefs = null;
      const stateRes = await fetch(`${API}/api/v1/demo/state`);
      if (stateRes.ok) render(await stateRes.json());
      if (selectedAgent) loadAgentBeliefs(selectedAgent);
    } catch (err) {
      showError(`Reset failed: ${err.message}`);
    } finally {
      els.resetBtn.disabled = false;
    }
  }

  els.resetBtn?.addEventListener("click", resetDemo);

  bootstrap();
})();
