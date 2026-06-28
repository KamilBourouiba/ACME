/** Erebor API client — proxies to OSS intelligence backend. */

const BASE = "/api";

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
  health: () => get("/health"),
  catalog: () => get("/catalog"),
  graph: () => get("/graph"),
  search: (q) => get(`/search?q=${encodeURIComponent(q)}`),
  githubRepo: (owner, repo) => get(`/github/${owner}/${repo}`),
  openAlexWork: (id) => get(`/openalex/works/${encodeURIComponent(id)}`),
  geoPlace: (id) => get(`/geo/${encodeURIComponent(id)}`),
  logEvent: (event) => post("/trail", event),
};

export function debounce(fn, ms = 320) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}
