(function () {
  const API = (window.ACME_DEMO_API || "").replace(/\/$/, "");
  let state = null;
  let selectedChannel = "general";
  let selectedAgent = null;
  let agentBeliefs = null;
  let lastBeliefFetch = 0;
  let eventSource = null;

  const STORAGE_KEY = "acme_demo_visitor_secret";
  let visitorSecret = sessionStorage.getItem(STORAGE_KEY) || "";
  let visitorUnlocked = Boolean(visitorSecret);
  let visitorSending = false;

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
    previewPanel: document.getElementById("preview-panel"),
    sitePreview: document.getElementById("site-preview"),
    livePreviewTab: document.getElementById("live-preview-tab"),
    mobileMenuBtn: document.getElementById("mobile-menu-btn"),
    mobileBottomNav: document.getElementById("mobile-bottom-nav"),
    sidebar: document.getElementById("sidebar"),
    sidebarBackdrop: document.getElementById("sidebar-backdrop"),
    membersPanel: document.getElementById("members-panel"),
    mobileChannels: document.getElementById("mobile-channels"),
    mainPanel: document.getElementById("main-panel"),
    visitorCompose: document.getElementById("visitor-compose"),
    visitorInput: document.getElementById("visitor-input"),
    visitorSend: document.getElementById("visitor-send"),
  };

  function updateVisitorComposeUi() {
    if (!els.visitorInput || !els.visitorCompose) return;
    if (visitorUnlocked) {
      els.visitorCompose.classList.add("is-unlocked");
      els.visitorInput.type = "text";
      const ch = selectedChannel || "general";
      els.visitorInput.placeholder = `Message #${ch}…`;
    } else {
      els.visitorCompose.classList.remove("is-unlocked");
      els.visitorInput.type = "password";
      els.visitorInput.placeholder = "Enter access code to chat…";
    }
    syncVisitorSendButton();
  }

  function syncVisitorSendButton() {
    if (!els.visitorSend || !els.visitorInput) return;
    const text = els.visitorInput.value.trim();
    if (visitorSending) {
      els.visitorSend.disabled = true;
      return;
    }
    els.visitorSend.disabled = text.length === 0;
  }

  async function unlockVisitor(secret) {
    const res = await fetch(`${API}/api/v1/demo/unlock`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ secret }),
    });
    if (res.status === 403) throw new Error("Wrong code — try again.");
    if (!res.ok) throw new Error(`Unlock failed (${res.status})`);
    visitorSecret = secret;
    visitorUnlocked = true;
    sessionStorage.setItem(STORAGE_KEY, secret);
    if (els.visitorInput) els.visitorInput.value = "";
    updateVisitorComposeUi();
  }

  async function sendVisitorMessage(text) {
    visitorSending = true;
    syncVisitorSendButton();
    if (els.visitorSend) els.visitorSend.textContent = "…";
    try {
      const res = await fetch(`${API}/api/v1/demo/say`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          secret: visitorSecret,
          channel: selectedChannel || "general",
          message: text,
        }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.status === 403) {
        visitorUnlocked = false;
        visitorSecret = "";
        sessionStorage.removeItem(STORAGE_KEY);
        updateVisitorComposeUi();
        throw new Error(data.detail || "Session expired — enter your access code again.");
      }
      if (!res.ok) throw new Error(data.detail || `Send failed (${res.status})`);
      if (data.state) render(data.state);
      if (els.visitorInput) els.visitorInput.value = "";
    } finally {
      visitorSending = false;
      if (els.visitorSend) els.visitorSend.textContent = "Send";
      syncVisitorSendButton();
    }
  }

  function initVisitorCompose() {
    els.visitorInput?.addEventListener("input", syncVisitorSendButton);
    els.visitorCompose?.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const text = (els.visitorInput?.value || "").trim();
      if (!text || visitorSending) return;
      clearError();
      try {
        if (!visitorUnlocked) {
          await unlockVisitor(text);
          return;
        }
        await sendVisitorMessage(text);
      } catch (err) {
        showError(err.message || "Could not send message.");
      }
    });
    updateVisitorComposeUi();
  }

  function isMobileLayout() {
    return window.matchMedia("(max-width: 960px)").matches;
  }

  function closeSidebar() {
    els.sidebar?.classList.remove("is-open");
    if (els.sidebarBackdrop) els.sidebarBackdrop.hidden = true;
  }

  function openSidebar() {
    els.sidebar?.classList.add("is-open");
    if (els.sidebarBackdrop) els.sidebarBackdrop.hidden = false;
  }

  function setMobilePanel(panel) {
    mobilePanel = panel;
    document.body.classList.remove("panel-chat", "panel-preview", "panel-team");
    document.body.classList.add(`panel-${panel}`);
    els.mobileBottomNav?.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
      const active = btn.dataset.panel === panel;
      btn.classList.toggle("active", active);
      btn.setAttribute("aria-current", active ? "page" : "false");
    });
    if (panel !== "team") {
      els.membersPanel?.classList.remove("is-open");
    }
    if (panel === "preview" && state) {
      renderPreview(state);
      requestAnimationFrame(() => els.messages?.scrollTo?.(0, 0));
    }
  }

  function initMobileNav() {
    els.mobileMenuBtn?.addEventListener("click", () => {
      if (els.sidebar?.classList.contains("is-open")) closeSidebar();
      else openSidebar();
    });

    els.sidebarBackdrop?.addEventListener("click", closeSidebar);

    els.mobileBottomNav?.querySelectorAll(".mobile-nav-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        setMobilePanel(btn.dataset.panel || "chat");
        closeSidebar();
      });
    });

    els.channelList?.addEventListener("click", (ev) => {
      if (isMobileLayout() && ev.target.closest(".channel-btn")) closeSidebar();
    });

    window.addEventListener("resize", () => {
      if (!isMobileLayout()) {
        document.body.classList.remove("panel-chat", "panel-preview", "panel-team");
        closeSidebar();
      } else {
        setMobilePanel(mobilePanel);
      }
    });

    if (isMobileLayout()) setMobilePanel("chat");
  }

  let previewMode = "staging";
  let mobilePanel = "chat";

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
    const html = (channels || [])
      .map(
        (c) => `
      <button type="button" class="channel-btn ${c.id === selectedChannel ? "active" : ""}" data-channel="${c.id}">
        <span class="hash">#</span>${escapeHtml(c.name)}
      </button>`
      )
      .join("");

    els.channelList.innerHTML = html;

    const chipHtml = (channels || [])
      .map(
        (c) => `
      <button type="button" class="mobile-channel-chip ${c.id === selectedChannel ? "active" : ""}" data-channel="${c.id}">
        #${escapeHtml(c.name)}
      </button>`
      )
      .join("");
    if (els.mobileChannels) {
      els.mobileChannels.innerHTML = chipHtml || `
        <button type="button" class="mobile-channel-chip active" data-channel="general">#general</button>`;
    }

    function onChannelPick(btn) {
      selectedChannel = btn.dataset.channel;
      const ch = (state?.channels || channels || []).find((x) => x.id === selectedChannel);
      els.channelTitle.textContent = `#${ch?.name || selectedChannel}`;
      els.channelTopic.textContent = ch?.topic || "";
      render(state);
      updateVisitorComposeUi();
      closeSidebar();
    }

    els.channelList.querySelectorAll(".channel-btn").forEach((btn) => {
      btn.addEventListener("click", () => onChannelPick(btn));
    });

    els.mobileChannels?.querySelectorAll(".mobile-channel-chip").forEach((btn) => {
      btn.addEventListener("click", () => onChannelPick(btn));
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

  function renderPreview(next) {
    if (!els.previewPanel || !els.sitePreview) return;
    const artifactsReady = Boolean(
      next.artifacts && (next.artifacts["static/index.html"] || next.artifacts["index.html"])
    );
    const show = next.preview_ready || next.live_preview_url || artifactsReady;
    const mobilePreviewTab = isMobileLayout() && mobilePanel === "preview";

    if (mobilePreviewTab) {
      els.previewPanel.hidden = false;
      if (!show) {
        els.sitePreview.removeAttribute("src");
        els.sitePreview.srcdoc =
          '<!DOCTYPE html><html><body style="font-family:system-ui;display:grid;place-items:center;height:100%;margin:0;color:#616061;background:#fafafa"><p>Squad is still coding — check back soon.</p></body></html>';
      }
    } else {
      els.previewPanel.hidden = !show;
    }

    if (!show && !mobilePreviewTab) return;

    if (els.livePreviewTab) {
      els.livePreviewTab.disabled = !next.live_preview_url;
    }

    if (show) {
      if (previewMode === "live" && next.live_preview_url) {
        els.sitePreview.src = next.live_preview_url;
        els.sitePreview.removeAttribute("srcdoc");
      } else {
        els.sitePreview.src = `${API}/api/v1/demo/preview?t=${next.tick || 0}`;
        els.sitePreview.removeAttribute("srcdoc");
      }
    }
  }

  document.querySelectorAll(".preview-tab").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (btn.disabled) return;
      previewMode = btn.dataset.preview;
      document.querySelectorAll(".preview-tab").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      if (state) renderPreview(state);
    });
  });

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
        const badge = !["message", "reply"].includes(m.kind)
          ? `<span class="kind-badge">${escapeHtml(m.kind)}</span>`
          : "";
        const replyTag = m.reply_to_name
          ? `<div class="reply-tag">↩ replying to <strong>@${escapeHtml(m.reply_to_name)}</strong></div>`
          : "";
        const rowClass =
          m.kind === "visitor"
            ? "msg-row is-visitor"
            : m.kind === "query"
              ? "msg-row is-query"
              : m.kind === "reply"
                ? "msg-row is-reply"
                : "msg-row";
        const avatarStyle =
          m.kind === "visitor" ? ' style="background:#2eb67d"' : ` style="background:${color}"`;
        const avatarContent = m.kind === "visitor" ? "Y" : escapeHtml(initials);
        let code = "";
        if (m.code_body) {
          code = `
          <div class="code-block">
            <div class="code-head"><span>${escapeHtml(m.code_file || "file")}</span><span>${escapeHtml(m.code_lang || "")}</span></div>
            <pre>${escapeHtml(m.code_body)}</pre>
          </div>`;
        }
        const answer = m.answer
          ? `<div class="acme-answer"><strong>ACME:</strong> ${escapeHtml(m.answer)}</div>`
          : "";
        return `
        <article class="${rowClass}">
          <div class="avatar"${avatarStyle}>${avatarContent}</div>
          <div class="msg-body">
            <div class="msg-meta">
              <strong>${escapeHtml(m.agent_name)}</strong>
              <span class="role">${escapeHtml(m.role)}</span>
              <time>${formatTime(m.timestamp)}</time>${badge}
            </div>
            ${replyTag}
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
    els.tickLabel.textContent = `${next.tick || 0}${next.phase ? ` · ${next.phase}` : ""}`;
    if (next.paused) {
      els.livePill.textContent = "Paused";
      els.livePill.classList.remove("on");
    } else if (next.running) {
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
    renderPreview(next);
  }

  function maybeRefreshBeliefs() {
    if (!selectedAgent) return;
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
    initMobileNav();
    initVisitorCompose();
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

  bootstrap();
})();
