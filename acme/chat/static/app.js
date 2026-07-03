const API = "/api/v1/chat";
const STORAGE_KEY = "acme_chat_session";

const $ = (sel) => document.querySelector(sel);
const messagesEl = $("#messages");
const inputEl = $("#input");
const composer = $("#composer");
const fileInput = $("#file-input");
const fileChips = $("#file-chips");
const sessionIdEl = $("#session-id");
const skillList = $("#skill-list");
const beliefList = $("#belief-list");
const sidebar = $("#sidebar");
const backdrop = $("#sidebar-backdrop");
const memoryPanel = $("#memory-panel");

let sessionId = localStorage.getItem(STORAGE_KEY);
let pendingFiles = [];

function esc(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function isMobile() {
  return window.matchMedia("(max-width: 900px)").matches;
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

function toggleMemoryPanel() {
  if (!memoryPanel) return;
  memoryPanel.classList.toggle("collapsed");
}

async function api(path, opts = {}) {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

async function ensureSession() {
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
  sessionIdEl.textContent = s.session_id;
  skillList.innerHTML = (s.skills || [])
    .map((sk) => `<li>${esc(sk)}</li>`)
    .join("");
}

function renderMessage(m) {
  const div = document.createElement("div");
  div.className = `msg ${m.role}`;
  const tools =
    m.tool_calls?.length
      ? `<div class="tools">${m.tool_calls
          .map((t) => `<span>${esc(t.tool)}: ${esc(t.summary)}</span>`)
          .join("")}</div>`
      : "";
  const attach =
    m.attachments?.length
      ? `<div class="attach">${m.attachments
          .map((a) => `📎 ${esc(a.name)}`)
          .join(", ")}</div>`
      : "";
  div.innerHTML = `<div class="meta">${m.role}</div>${esc(m.content)}${attach}${tools}`;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function loadHistory() {
  if (!sessionId) return;
  const rows = await api(`/sessions/${sessionId}/messages`);
  messagesEl.innerHTML = "";
  rows.forEach(renderMessage);
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
  beliefList.innerHTML = beliefs
    .slice(0, 12)
    .map(
      (b) =>
        `<li>${esc(b.label)} <span class="crs">CRS ${b.crs.toFixed(2)}</span></li>`
    )
    .join("") || "<li style='color:var(--muted)'>No beliefs yet — keep chatting!</li>";
}

function autoResizeInput() {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 140)}px`;
}

fileInput.addEventListener("change", () => {
  pendingFiles = [...fileInput.files];
  fileChips.innerHTML = pendingFiles
    .map((f) => `<span>${esc(f.name)}</span>`)
    .join("");
});

composer.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text && !pendingFiles.length) return;
  const btn = $("#btn-send");
  btn.disabled = true;

  renderMessage({ role: "user", content: text || "(file upload)", attachments: pendingFiles.map((f) => ({ name: f.name })) });
  inputEl.value = "";
  autoResizeInput();

  const typing = document.createElement("div");
  typing.className = "typing";
  typing.textContent = "Agent thinking…";
  messagesEl.appendChild(typing);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  const fd = new FormData();
  fd.append("message", text);
  pendingFiles.forEach((f) => fd.append("files", f));

  try {
    const res = await api(`/sessions/${sessionId}/messages`, { method: "POST", body: fd });
    typing.remove();
    renderMessage(res.message);
    await refreshMemory();
    if (isMobile()) closeSidebar();
  } catch (err) {
    typing.remove();
    renderMessage({ role: "assistant", content: `Error: ${err.message}` });
  } finally {
    pendingFiles = [];
    fileInput.value = "";
    fileChips.innerHTML = "";
    btn.disabled = false;
    inputEl.focus();
  }
});

$("#btn-copy")?.addEventListener("click", async () => {
  if (!sessionId) return;
  try {
    await navigator.clipboard.writeText(sessionId);
  } catch {
    /* ignore */
  }
});

$("#btn-new")?.addEventListener("click", async () => {
  localStorage.removeItem(STORAGE_KEY);
  sessionId = null;
  messagesEl.innerHTML = "";
  await ensureSession();
  await loadHistory();
  await refreshMemory();
});

$("#btn-menu")?.addEventListener("click", openSidebar);
$("#btn-memory")?.addEventListener("click", () => {
  openSidebar();
  memoryPanel?.classList.remove("collapsed");
  memoryPanel?.scrollIntoView({ behavior: "smooth", block: "nearest" });
});
$("#btn-close-sidebar")?.addEventListener("click", closeSidebar);
backdrop?.addEventListener("click", closeSidebar);

inputEl.addEventListener("input", autoResizeInput);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composer.requestSubmit();
  }
});

window.addEventListener("resize", () => {
  if (!isMobile()) closeSidebar();
});

(async function boot() {
  await ensureSession();
  await loadHistory();
  await refreshMemory();
  autoResizeInput();
  if (isMobile()) memoryPanel?.classList.add("collapsed");
})();
