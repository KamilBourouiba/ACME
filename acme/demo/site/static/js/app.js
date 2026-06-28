/** App bootstrap — wires scene, search, panels, timeline. */
import { EreborScene } from "./scene.js?v=pages2";
import { api, debounce } from "./api.js?v=pages2";
import {
  renderSourceChips,
  renderEntityList,
  renderInspector,
  renderSearchResults,
} from "./panels.js?v=pages2";
import { pushEvent, render as renderTimeline } from "./timeline.js?v=pages2";

const state = {
  nodes: [],
  selected: null,
  catalog: [],
  activeSource: "multi",
};

let scene;

async function boot() {
  const canvas = document.getElementById("erebor-canvas");
  scene = new EreborScene(canvas);
  scene.onSelect(handleSelect);

  document.getElementById("btn-reset-view")?.addEventListener("click", () => {
    scene.setAutoRotate(true);
    document.getElementById("btn-rotate")?.classList.add("active");
  });

  document.getElementById("btn-rotate")?.addEventListener("click", (e) => {
    const on = !e.target.classList.contains("active");
    e.target.classList.toggle("active", on);
    scene.setAutoRotate(on);
  });

  document.getElementById("btn-arcs")?.addEventListener("click", (e) => {
    const on = !e.target.classList.contains("active");
    e.target.classList.toggle("active", on);
    scene.setShowArcs(on);
  });

  const form = document.getElementById("search-form");
  const input = document.getElementById("search-input");
  form?.addEventListener("submit", (e) => {
    e.preventDefault();
    runSearch(input.value.trim());
  });
  input?.addEventListener("input", debounce((e) => runSearch(e.target.value.trim()), 400));

  try {
    const [catalog, graph] = await Promise.all([api.catalog(), api.graph()]);
    state.catalog = catalog.sources || [];
    renderSourceChips(state.catalog, state.activeSource);
    mergeGraph(graph);
  } catch (err) {
    console.warn("boot partial", err);
  } finally {
    document.getElementById("loading-veil")?.classList.add("hidden");
  }

  renderTimeline();
  updateHud();
}

function mergeGraph(graph) {
  const byId = new Map(state.nodes.map((n) => [n.id, n]));
  for (const n of graph.nodes || []) byId.set(n.id, n);
  state.nodes = [...byId.values()];
  scene.setGraph({ nodes: state.nodes, edges: graph.edges || [] });
  renderEntityList(state.nodes, state.selected?.id, handleSelect);
  updateHud();
}

async function runSearch(q) {
  if (q.length < 2) {
    renderSearchResults([], () => {});
    return;
  }
  document.getElementById("hud-source").textContent = "search";
  try {
    const data = await api.search(q);
    renderSearchResults(data.groups || [], (item) => ingestSearchHit(item, q));
    pushEvent(`Search: ${q}`, `${(data.groups || []).reduce((a, g) => a + g.items.length, 0)} hits`);
    api.logEvent({ type: "search", query: q }).catch(() => {});
  } catch (err) {
    console.warn("search failed", err);
  }
}

function ingestSearchHit(item, query) {
  const node = {
    id: item.id,
    kind: item.kind,
    label: item.label,
    description: item.description || "",
    source: item.source,
    url: item.url,
    lat: item.lat,
    lng: item.lng,
    score: item.score,
    stats: item.stats || {},
  };
  const exists = state.nodes.find((n) => n.id === node.id);
  if (!exists) state.nodes.push(node);
  mergeGraph({ nodes: state.nodes, edges: buildEdges(state.nodes) });
  handleSelect(node);
  pushEvent(`Opened ${item.kind}`, item.label, node.id);
}

function buildEdges(nodes) {
  const edges = [];
  for (let i = 0; i < nodes.length - 1; i++) {
    if (nodes[i].kind === nodes[i + 1].kind) continue;
    edges.push({ from: nodes[i].id, to: nodes[i + 1].id });
  }
  return edges.slice(0, 32);
}

async function handleSelect(node) {
  state.selected = node;
  scene.selectNode(node.id);
  renderEntityList(state.nodes, node.id, handleSelect);

  let detail = {};
  try {
    if (node.kind === "repo" && node.id.includes("/")) {
      const [owner, repo] = node.id.replace("gh:", "").split("/");
      detail = await api.githubRepo(owner, repo);
    } else if (node.kind === "paper") {
      detail = await api.openAlexWork(node.id.replace("oa:", ""));
    } else if (node.kind === "place") {
      detail = await api.geoPlace(node.id.replace("geo:", ""));
    }
  } catch (_) {}

  renderInspector(node, detail);
  pushEvent(`Inspect ${node.kind}`, node.label, node.id);
  api.logEvent({ type: "inspect", entity_id: node.id, kind: node.kind }).catch(() => {});
}

function updateHud() {
  const el = document.getElementById("hud-nodes");
  if (el) el.textContent = String(state.nodes.length);
}

boot();
