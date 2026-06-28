/** Erebor API client — VM backend or direct OSS on GitHub Pages. */

import {
  OSS_CATALOG,
  SEED_GRAPH,
  directGeoPlace,
  directGithubRepo,
  directOpenAlexWork,
  directSearch,
} from "./oss.js?v=pages2";

const ON_PAGES =
  typeof window !== "undefined" && /\.github\.io$/i.test(window.location.hostname);

const USE_DIRECT_OSS =
  ON_PAGES ||
  (typeof window !== "undefined" && window.EREBOR_DIRECT_OSS === true);

const BASE = (() => {
  if (USE_DIRECT_OSS) return "";
  const root = (typeof window !== "undefined" && window.EREBOR_API_BASE
    ? String(window.EREBOR_API_BASE)
    : ""
  ).replace(/\/$/, "");
  if (root) return `${root}/api`;
  return "/api";
})();

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → ${res.status}`);
  return res.json();
}

export const api = {
  health: () => (USE_DIRECT_OSS ? Promise.resolve({ status: "ok", product: "erebor", mode: "direct-oss" }) : get("/health")),
  catalog: () => (USE_DIRECT_OSS ? Promise.resolve(OSS_CATALOG) : get("/catalog")),
  graph: () => (USE_DIRECT_OSS ? Promise.resolve(SEED_GRAPH) : get("/graph")),
  search: (q) => (USE_DIRECT_OSS ? directSearch(q) : get(`/search?q=${encodeURIComponent(q)}`)),
  githubRepo: (owner, repo) =>
    USE_DIRECT_OSS ? directGithubRepo(owner, repo) : get(`/github/${owner}/${repo}`),
  openAlexWork: (id) =>
    USE_DIRECT_OSS ? directOpenAlexWork(id) : get(`/openalex/works/${encodeURIComponent(id)}`),
  geoPlace: (id) =>
    USE_DIRECT_OSS ? directGeoPlace(id.replace(/^geo:/, "")) : get(`/geo/${encodeURIComponent(id)}`),
  logEvent: (event) =>
    USE_DIRECT_OSS
      ? Promise.resolve({ ok: true, persisted: false })
      : post("/trail", event),
};

export function debounce(fn, ms = 320) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
