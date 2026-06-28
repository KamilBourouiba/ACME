/** Investigation timeline trail. */

const events = [];

export function pushEvent(label, detail, nodeId) {
  const ev = {
    id: `ev-${Date.now()}`,
    ts: new Date().toISOString(),
    label,
    detail,
    nodeId,
  };
  events.unshift(ev);
  if (events.length > 24) events.pop();
  render();
  return ev;
}

export function render() {
  const track = document.getElementById("timeline-track");
  const count = document.getElementById("trail-count");
  if (count) count.textContent = `${events.length} events`;
  if (!track) return;
  if (!events.length) {
    track.innerHTML = `<div class="empty-state" style="flex:1">Investigation events appear here as you explore.</div>`;
    return;
  }
  track.innerHTML = events
    .map(
      (e, i) => `
    <div class="timeline-event${i === 0 ? " active" : ""}" data-node="${e.nodeId || ""}">
      <div class="timeline-time">${formatTime(e.ts)}</div>
      <div class="timeline-label">${escapeHtml(e.label)}</div>
      <div class="timeline-detail">${escapeHtml(e.detail || "")}</div>
    </div>`
    )
    .join("");
}

function formatTime(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

export function getEvents() {
  return [...events];
}
