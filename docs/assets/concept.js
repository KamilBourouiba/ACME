/** ACME Belief Observatory — concept demo (mock trace, no API). */

const NODES = [
  { id: "e1", kind: "obs", label: "API p99 > 2s", x: 120, y: 200 },
  { id: "e2", kind: "obs", label: "3 logos churned", x: 120, y: 280 },
  { id: "h1", kind: "hyp", label: "Latency → churn?", x: 280, y: 240 },
  { id: "b1", kind: "bel", label: "Latency drives churn", x: 440, y: 200 },
  { id: "c1", kind: "clash", label: "Onboarding email theory", x: 440, y: 300 },
  { id: "b2", kind: "bel", label: "Latency (confirmed)", x: 560, y: 240 },
];

const EDGES = [
  ["e1", "h1"],
  ["e2", "h1"],
  ["h1", "b1"],
  ["h1", "c1"],
  ["b1", "b2"],
  ["c1", "b2"],
];

const STEPS = [
  {
    title: "Ingest",
    crs: 0.42,
    episodes: [
      { t: "09:14", text: "Support ticket: <strong>checkout timeouts</strong> during peak." },
      { t: "09:22", text: "Monitoring: API <strong>p99 latency 2.4s</strong> on /orders." },
    ],
    activeNodes: ["e1"],
    activeEdges: [],
    inspector: null,
  },
  {
    title: "Extract",
    crs: 0.51,
    episodes: [
      { t: "09:14", text: "Support ticket: <strong>checkout timeouts</strong> during peak." },
      { t: "09:22", text: "Monitoring: API <strong>p99 latency 2.4s</strong> on /orders." },
      { t: "09:31", text: "CRM: <strong>3 enterprise logos</strong> churned post-incident." },
    ],
    activeNodes: ["e1", "e2"],
    activeEdges: [["e1", "h1"]],
    inspector: null,
  },
  {
    title: "Hypothesize",
    crs: 0.58,
    episodes: [
      { t: "09:31", text: "CRM: <strong>3 enterprise logos</strong> churned post-incident." },
      { t: "09:35", text: "Graph link: performance incident ↔ churn event." },
    ],
    activeNodes: ["e1", "e2", "h1"],
    activeEdges: [
      ["e1", "h1"],
      ["e2", "h1"],
    ],
    inspector: {
      id: "h1",
      type: "Hypothesis",
      title: "Latency causes enterprise churn",
      desc: "Provisional inference from correlated episodes. Not yet promoted — needs prediction test.",
      stats: { confidence: "0.58", sources: "2", contradictions: "0" },
    },
  },
  {
    title: "Contradict",
    crs: 0.44,
    episodes: [
      { t: "10:02", text: "Slack rumor: churn blamed on <strong>onboarding emails</strong>." },
      { t: "10:04", text: "Contrarian pass: no episode supports email theory." },
    ],
    activeNodes: ["e1", "e2", "h1", "b1", "c1"],
    activeEdges: [
      ["e1", "h1"],
      ["e2", "h1"],
      ["h1", "b1"],
      ["h1", "c1"],
    ],
    clashEdges: [["h1", "c1"]],
    inspector: {
      id: "c1",
      type: "Contradiction",
      title: "Onboarding email theory",
      desc: "Competing narrative with zero grounded episodes. CRS penalized for weak provenance.",
      stats: { confidence: "0.12", sources: "0", status: "demoted" },
    },
  },
  {
    title: "Feedback",
    crs: 0.61,
    episodes: [
      { t: "10:18", text: "Outcome log: post-fix <strong>latency down 40%</strong> — churn stabilized." },
      { t: "10:20", text: "Prediction loop: hypothesis <strong>supported</strong>." },
    ],
    activeNodes: ["e1", "e2", "h1", "b2"],
    activeEdges: [
      ["e1", "h1"],
      ["e2", "h1"],
      ["h1", "b2"],
      ["b1", "b2"],
    ],
    inspector: {
      id: "b2",
      type: "Belief",
      title: "Latency drives enterprise churn",
      desc: "Promoted after prediction success + contradiction resistance. Auditable CRS factors below.",
      stats: { CRS: "0.70", predictions: "3/3", stability: "high" },
    },
  },
  {
    title: "Belief",
    crs: 0.7,
    episodes: [
      { t: "10:20", text: "Belief promoted to graph — available for downstream reasoning." },
      { t: "10:21", text: "MemoryBench: <strong>feedback 1.0</strong> · belief quality <strong>0.70</strong>." },
    ],
    activeNodes: ["b2"],
    activeEdges: [],
    inspector: {
      id: "b2",
      type: "Belief · promoted",
      title: "Latency drives enterprise churn",
      desc: "This is what ACME sells: not a chunk in a vector DB — a scored, revisable belief with a trail.",
      stats: { CRS: "0.70", retention: "1.00", feedback: "1.00" },
    },
  },
];

const KIND_COLOR = {
  obs: "#8b98a8",
  hyp: "#5b8def",
  bel: "#3dd6c6",
  clash: "#f87171",
};

let stepIndex = 0;
let playing = false;
let playTimer = null;

const svg = document.getElementById("belief-svg");
const episodeList = document.getElementById("episode-list");
const scrubSteps = document.getElementById("scrub-steps");
const inspector = document.getElementById("inspector");
const crsValue = document.getElementById("crs-value");
const crsFill = document.getElementById("crs-fill");

function renderGraph(step) {
  const active = new Set(step.activeNodes || []);
  const edgeActive = new Set((step.activeEdges || []).map((e) => e.join("->")));
  const clash = new Set((step.clashEdges || []).map((e) => e.join("->")));

  const nodeById = Object.fromEntries(NODES.map((n) => [n.id, n]));

  let edgesSvg = "";
  for (const [from, to] of EDGES) {
    const a = nodeById[from];
    const b = nodeById[to];
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
          fill="${KIND_COLOR[n.kind]}" opacity="${on ? 1 : 0.25}" stroke="${on ? "#fff" : "transparent"}" stroke-width="1.5"/>
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
          desc: "Scrub forward to see how this node enters the investigation.",
          stats: { state: "preview" },
        });
      }
    });
  });
}

function renderEpisodes(step) {
  episodeList.innerHTML = (step.episodes || [])
    .map((ep, i) => `<div class="episode active"><time>${ep.t}</time>${ep.text}</div>`)
    .join("");
}

function renderInspector(data) {
  if (!data) {
    inspector.innerHTML = `<p class="inspector-empty">Scrub the trace below — select a node to inspect CRS factors.</p>`;
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
  scrubSteps.innerHTML = STEPS.map((s, i) => `
    <button type="button" class="scrub-step ${i === stepIndex ? "active" : ""}" data-idx="${i}">
      <em>0${i + 1}</em>${s.title}
    </button>`).join("");

  scrubSteps.querySelectorAll(".scrub-step").forEach((btn) => {
    btn.addEventListener("click", () => goTo(parseInt(btn.dataset.idx, 10)));
  });
}

function goTo(idx) {
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

goTo(0);
