const API = "/api/v1/chat";
const STORAGE_KEY = "acme_chat_session";

const SKILL_LABELS = {
  browse_web: "Browse web",
  search_memory: "Search memory",
  remember: "Remember",
  list_beliefs: "Beliefs",
  summarize_url: "Summarize URL",
};

const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const emptyState = $("#empty-state");
const inputEl = $("#input");
const composer = $("#composer");
const fileInput = $("#file-input");
const fileChips = $("#file-chips");
const sessionIdEl = $("#session-id");
const skillList = $("#skill-list");
const beliefList = $("#belief-list");
const sidebar = $("#sidebar");
const backdrop = $("#sidebar-backdrop");
const topbarStatus = $("#topbar-status");
const btnSend = $("#btn-send");
const toastEl = $("#toast");

let sessionId = localStorage.getItem(STORAGE_KEY);
let pendingFiles = [];

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function isMobile() {
  return window.matchMedia("(max-width: 768px)").matches;
}

function showToast(msg) {
  if (!toastEl) return;
  toastEl.textContent = msg;
  toastEl.hidden = false;
  toastEl.classList.add("show");
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => {
    toastEl.classList.remove("show");
    setTimeout(() => { toastEl.hidden = true; }, 200);
  }, 2200);
}

function openSidebar() {
  if (!isMobile()) return;
  sidebar?.classList.add("open");
  backdrop?.removeAttribute("hidden");
  backdrop?.classList.add("visible");
  document.body.classList.add("sidebar-open");
}

function closeSidebar() {
  sidebar?.classList.remove("open");
  backdrop?.classList.remove("visible");
  backdrop?.setAttribute("hidden", "");
  document.body.classList.remove("sidebar-open");
}

function updateEmptyState(hasMessages) {
  if (!emptyState) return;
  emptyState.hidden = hasMessages;
}

function updateComposerState() {
  const hasText = inputEl.value.trim().length > 0;
  const hasFiles = pendingFiles.length > 0;
  btnSend.disabled = !(hasText || hasFiles);
}

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    let err = res.statusText;
    try {
      const j = await res.json();
      err = j.detail || err;
    } catch {
      err = (await res.text()) || err;
    }
    throw new Error(typeof err === "string" ? err : JSON.stringify(err));
  }
  return res.json();
}

async function ensureSession() {
  topbarStatus.textContent = "Connecting…";
  if (sessionId) {
    try {
      const s = await api(`/sessions/${sessionId}`);
      renderSession(s);
      return s;
    } catch {
      sessionId = null;
    }
  }
  const s = await api("/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({}),
  });
  sessionId = s.session_id;
  localStorage.setItem(STORAGE_KEY, sessionId);
  renderSession(s);
  return s;
}

function renderSession(s) {
  const short = `${s.session_id.slice(0, 8)}…${s.session_id.slice(-4)}`;
  sessionIdEl.textContent = s.session_id;
  sessionIdEl.title = s.session_id;
  topbarStatus.textContent = `Agent ${short}`;
  skillList.innerHTML = (s.skills || [])
    .map((sk) => `<li>${esc(SKILL_LABELS[sk] || sk.replace(/_/g, " "))}</li>`)
    .join("");
}

function renderMessage(m) {
  const isUser = m.role === "user";
  const row = document.createElement("div");
  row.className = `msg-row ${isUser ? "user" : "assistant"}`;

  const avatar = document.createElement("div");
  avatar.className = "msg-avatar";
  avatar.textContent = isUser ? "You" : "A";
  avatar.setAttribute("aria-hidden", "true");

  const bubble = document.createElement("div");
  bubble.className = "msg-bubble";
  bubble.textContent = m.content || "";

  if (m.attachments?.length) {
    const attach = document.createElement("div");
    attach.className = "msg-attach";
    attach.innerHTML = m.attachments
      .map((a) => `<span>📎 ${esc(a.name)}</span>`)
      .join("");
    bubble.appendChild(attach);
  }

  if (m.tool_calls?.length) {
    const tools = document.createElement("div");
    tools.className = "msg-tools";
    tools.innerHTML = m.tool_calls
      .map((t) => {
        const cls = t.ok === false ? "tool-chip fail" : "tool-chip";
        const label = SKILL_LABELS[t.tool] || t.tool;
        return `<span class="${cls}">${esc(label)} · ${esc(t.summary || "")}</span>`;
      })
      .join("");
    bubble.appendChild(tools);
  }

  row.appendChild(avatar);
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  updateEmptyState(true);
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "typing-row";
  row.id = "typing-indicator";
  row.innerHTML = `
    <div class="msg-avatar" aria-hidden="true">A</div>
    <div class="typing-dots" aria-label="Agent thinking"><span></span><span></span><span></span></div>
  `;
  messagesEl.appendChild(row);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function hideTyping() {
  document.getElementById("typing-indicator")?.remove();
}

async function loadHistory() {
  if (!sessionId) return;
  const rows = await api(`/sessions/${sessionId}/messages`);
  messagesEl.innerHTML = "";
  const visible = rows.filter((r) => r.role === "user" || r.role === "assistant");
  visible.forEach(renderMessage);
  updateEmptyState(visible.length > 0);
}

async function refreshMemory() {
  if (!sessionId) return;
  const [stats, beliefs] = await Promise.all([
    api(`/sessions/${sessionId}/memory`),
    api(`/sessions/${sessionId}/beliefs`),
  ]);
  $("#stat-episodes").textContent = stats.episode_count;
  $("#stat-beliefs").textContent = stats.belief_count;
  $("#stat-graph").textContent = stats.graph_entities;
  $("#stat-promoted").textContent = stats.promoted_beliefs;
  beliefList.innerHTML =
    beliefs
      .slice(0, 10)
      .map(
        (b) =>
          `<li>${esc(b.label)}<span class="crs">CRS ${b.crs.toFixed(2)}</span></li>`
      )
      .join("") || '<li class="empty-beliefs">Chat to grow beliefs…</li>';
}

function renderFileChips() {
  fileChips.innerHTML = pendingFiles
    .map(
      (f, i) =>
        `<span>${esc(f.name)}<button type="button" data-idx="${i}" aria-label="Remove">×</button></span>`
    )
    .join("");
  fileChips.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const idx = Number(btn.dataset.idx);
      pendingFiles = pendingFiles.filter((_, j) => j !== idx);
      renderFileChips();
      updateComposerState();
    });
  });
  updateComposerState();
}

function autoResizeInput() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 140)}px`;
}

fileInput.addEventListener("change", () => {
  pendingFiles = [...pendingFiles, ...fileInput.files];
  fileInput.value = "";
  renderFileChips();
});

inputEl.addEventListener("input", () => {
  autoResizeInput();
  updateComposerState();
});

document.querySelectorAll(".prompt-chip").forEach((btn) => {
  btn.addEventListener("click", () => {
    inputEl.value = btn.dataset.prompt || "";
    autoResizeInput();
    updateComposerState();
    inputEl.focus();
  });
});

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text && !pendingFiles.length) return;

  btnSend.disabled = true;
  renderMessage({
    role: "user",
    content: text || "Shared files",
    attachments: pendingFiles.map((f) => ({ name: f.name })),
  });
  inputEl.value = "";
  autoResizeInput();
  updateComposerState();

  showTyping();

  const fd = new FormData();
  fd.append("message", text);
  pendingFiles.forEach((f) => fd.append("files", f));
  const filesSent = [...pendingFiles];
  pendingFiles = [];
  renderFileChips();

  try {
    const res = await api(`/sessions/${sessionId}/messages`, { method: "POST", body: fd });
    hideTyping();
    renderMessage(res.message);
    await refreshMemory();
    if (isMobile()) closeSidebar();
  } catch (err) {
    hideTyping();
    renderMessage({ role: "assistant", content: `Something went wrong: ${err.message}` });
    pendingFiles = filesSent;
    renderFileChips();
  } finally {
    btnSend.disabled = false;
    updateComposerState();
    inputEl.focus();
  }
});

$("#btn-copy")?.addEventListener("click", async () => {
  if (!sessionId) return;
  try {
    await navigator.clipboard.writeText(sessionId);
    showToast("Agent ID copied");
  } catch {
    showToast("Could not copy");
  }
});

$("#btn-new")?.addEventListener("click", async () => {
  if (!confirm("Start a fresh agent? Current memory stays on the server but this browser will get a new ID.")) return;
  localStorage.removeItem(STORAGE_KEY);
  sessionId = null;
  messagesEl.innerHTML = "";
  updateEmptyState(false);
  await ensureSession();
  await loadHistory();
  await refreshMemory();
  showToast("New agent ready");
  if (isMobile()) closeSidebar();
});

$("#btn-menu")?.addEventListener("click", openSidebar);
$("#btn-memory")?.addEventListener("click", openSidebar);
$("#btn-close-sidebar")?.addEventListener("click", closeSidebar);
backdrop?.addEventListener("click", closeSidebar);

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (!btnSend.disabled) composer.requestSubmit();
  }
});

window.addEventListener("resize", () => {
  if (!isMobile()) closeSidebar();
});

(async function boot() {
  try {
    await ensureSession();
    await loadHistory();
    await refreshMemory();
    autoResizeInput();
    updateComposerState();
  } catch (err) {
    topbarStatus.textContent = "Offline";
    if (emptyState) {
      emptyState.hidden = false;
      emptyState.querySelector("p").textContent = `Could not reach the API: ${err.message}`;
    }
  }
})();
