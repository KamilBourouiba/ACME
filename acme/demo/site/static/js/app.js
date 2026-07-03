/** ACME Belief Observatory — interactive belief trace UI. */

const KIND_COLOR = { obs: "#8b98a8", hyp: "#5b8def", bel: "#3dd6c6", clash: "#f87171" };

let NODES = [];
let EDGES = [];
let STEPS = [];
let stepIndex = 0;
let playing = false;
let playTimer = null;

const svg = document.getElementById("belief-svg");
const episodeList = document.getElementById("episode-list");
const scrubSteps = document.getElementById("scrub-steps");
const inspector = document.getElementById("inspector");
const crsValue = document.getElementById("crs-value");
const crsFill = document.getElementById("crs-fill");
const apiPill = document.getElementById("api-pill");

function normalizeEdges(edges) {
  return (edges || []).map((e) => (Array.isArray(e) ? e : [e.from, e.to]));
}

function renderGraph(step) {
  const active = new Set(step.activeNodes || []);
  const edgeActive = new Set((step.activeEdges || []).map((e) => e.join("->")));
  const clash = new Set((step.clashEdges || []).map((e) => e.join("->")));
  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]));

  let edgesSvg = "";
  for (const [from, to] of EDGES) {
    const a = nodeById[from];
    const b = nodeById[to];
    if (!a || !b) continue;
    const key = `${from}->${to}`;
    const cls = clash.has(key) ? "edge clash" : edgeActive.has(key) ? "edge active" : "edge";
    const opacity = edgeActive.has(key) || clash.has(key) ? 1 : 0.2;
    edgesSvg += `<line class="${cls}" x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" opacity="${opacity}"/>`;
  }

  let nodesSvg = "";
  for (const n of NODES) {
    const on = active.has(n.id);
    const r = n.kind === "bel" ? 22 : 18;
    nodesSvg += `
      <g class="node" data-id="${n.id}">
        <circle class="node-circle ${on ? "selected" : ""}" cx="${n.x}" cy="${n.y}" r="${r}"
          fill="${KIND_COLOR[n.kind] || KIND_COLOR.obs}" opacity="${on ? 1 : 0.25}"
          stroke="${on ? "#fff" : "transparent"}" stroke-width="1.5"/>
        <text class="node-label" x="${n.x}" y="${n.y + r + 14}" text-anchor="middle" opacity="${on ? 1 : 0.35}">${n.label}</text>
      </g>`;
  }

  svg.innerHTML = edgesSvg + nodesSvg;
  svg.querySelectorAll(".node").forEach((g) => {
    g.addEventListener("click", () => {
      const id = g.dataset.id;
      const node = NODES.find((x) => x.id === id);
      if (node && step.inspector && step.inspector.id === id) renderInspector(step.inspector);
      else if (node) {
        renderInspector({
          type: node.kind,
          title: node.label,
          desc: "Scrub the trace to see how this node enters the investigation.",
          stats: { state: "preview" },
        });
      }
    });
  });
}

function renderEpisodes(step) {
  episodeList.innerHTML = (step.episodes || [])
    .map((ep) => `<div class="episode active"><time>${ep.t}</time>${ep.text}</div>`)
    .join("");
}

function renderInspector(data) {
  if (!data) {
    inspector.innerHTML = `<p class="inspector-empty">Scrub the trace — select a node to inspect CRS factors.</p>`;
    return;
  }
  const stats = Object.entries(data.stats || {})
    .map(([k, v]) => `<div class="stat"><div class="stat-k">${k}</div><div class="stat-v">${v}</div></div>`)
    .join("");
  inspector.innerHTML = `
    <div class="inspector-type">${data.type}</div>
    <h2 class="inspector-title">${data.title}</h2>
    <p class="inspector-desc">${data.desc}</p>
    <div class="stat-grid">${stats}</div>`;
}

function renderScrubber() {
  scrubSteps.innerHTML = STEPS.map(
    (s, i) => `
    <button type="button" class="scrub-step ${i === stepIndex ? "active" : ""}" data-idx="${i}">
      <em>0${i + 1}</em>${s.title}
    </button>`,
  ).join("");
  scrubSteps.querySelectorAll(".scrub-step").forEach((btn) => {
    btn.addEventListener("click", () => goTo(parseInt(btn.dataset.idx, 10)));
  });
}

function goTo(idx) {
  if (!STEPS.length) return;
  stepIndex = Math.max(0, Math.min(STEPS.length - 1, idx));
  const step = STEPS[stepIndex];
  crsValue.textContent = step.crs.toFixed(2);
  crsFill.style.width = `${step.crs * 100}%`;
  renderEpisodes(step);
  renderGraph(step);
  renderInspector(step.inspector);
  renderScrubber();
}

function play() {
  if (playing) {
    playing = false;
    clearInterval(playTimer);
    document.getElementById("btn-play").textContent = "Play";
    return;
  }
  playing = true;
  document.getElementById("btn-play").textContent = "Pause";
  playTimer = setInterval(() => {
    if (stepIndex >= STEPS.length - 1) {
      play();
      return;
    }
    goTo(stepIndex + 1);
  }, 2200);
}

document.getElementById("btn-prev").addEventListener("click", () => goTo(stepIndex - 1));
document.getElementById("btn-next").addEventListener("click", () => goTo(stepIndex + 1));
document.getElementById("btn-play").addEventListener("click", play);

async function boot() {
  const { data, source } = await window.BeliefObsAPI.loadTrace();
  NODES = data.nodes || [];
  EDGES = normalizeEdges(data.edges);
  STEPS = data.steps || [];
  const labels = { vm: "Live · VM API", api: "Live · API", embedded: "Embedded trace" };
  apiPill.textContent = labels[source] || "Trace loaded";
  goTo(0);
}

boot().catch(() => {
  apiPill.textContent = "Trace unavailable";
});
