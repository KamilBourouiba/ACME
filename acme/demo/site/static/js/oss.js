/** Client-side OSS search — used on GitHub Pages where VM TLS is untrusted. */

const UA = "Erebor/1.0 (ACME demo; +https://github.com/KamilBourouiba/ACME)";

export const OSS_CATALOG = {
  sources: [
    {
      id: "github",
      label: "GitHub",
      endpoint: "https://api.github.com",
      license: "MIT Terms",
      description: "Repository metadata, stars, languages — public REST API.",
    },
    {
      id: "openalex",
      label: "OpenAlex",
      endpoint: "https://api.openalex.org",
      license: "CC0",
      description: "Scholarly works graph — papers, citations, institutions.",
    },
    {
      id: "nominatim",
      label: "OpenStreetMap Nominatim",
      endpoint: "https://nominatim.openstreetmap.org",
      license: "ODbL",
      description: "Geocoding and place intelligence from OSM.",
    },
  ],
};

export const SEED_GRAPH = {
  nodes: [
    {
      id: "gh:postgres/postgres",
      kind: "repo",
      label: "postgres/postgres",
      source: "GitHub",
      description: "Advanced open-source relational database.",
      lat: 37.77,
      lng: -122.42,
      score: 98,
      url: "https://github.com/postgres/postgres",
    },
    {
      id: "gh:apache/kafka",
      kind: "repo",
      label: "apache/kafka",
      source: "GitHub",
      description: "Distributed event streaming platform.",
      lat: 51.51,
      lng: -0.12,
      score: 96,
      url: "https://github.com/apache/kafka",
    },
    {
      id: "oa:W2741809807",
      kind: "paper",
      label: "Attention Is All You Need",
      source: "OpenAlex",
      description: "Transformer architecture — foundational ML paper.",
      lat: 52.52,
      lng: 13.4,
      score: 99,
      url: "https://openalex.org/W2741809807",
    },
    {
      id: "geo:berlin",
      kind: "place",
      label: "Berlin, Germany",
      source: "Nominatim",
      description: "EU open-source hub — clusters around Mapbox, Wikimedia.",
      lat: 52.52,
      lng: 13.405,
      score: 72,
    },
    {
      id: "gh:grafana/grafana",
      kind: "repo",
      label: "grafana/grafana",
      source: "GitHub",
      description: "Observability dashboards — AGPL observability stack.",
      lat: 59.33,
      lng: 18.06,
      score: 94,
      url: "https://github.com/grafana/grafana",
    },
  ],
  edges: [
    { from: "gh:postgres/postgres", to: "gh:apache/kafka" },
    { from: "gh:apache/kafka", to: "oa:W2741809807" },
    { from: "oa:W2741809807", to: "geo:berlin" },
    { from: "geo:berlin", to: "gh:grafana/grafana" },
  ],
};

async function githubSearch(q, limit = 6) {
  const url = new URL("https://api.github.com/search/repositories");
  url.searchParams.set("q", q);
  url.searchParams.set("sort", "stars");
  url.searchParams.set("order", "desc");
  url.searchParams.set("per_page", String(limit));
  const res = await fetch(url, { headers: { Accept: "application/vnd.github+json" } });
  if (!res.ok) throw new Error(`github → ${res.status}`);
  const items = (await res.json()).items || [];
  return items.map((it) => ({
    id: `gh:${it.full_name}`,
    kind: "repo",
    label: it.full_name,
    sub: it.description || "",
    description: it.description || "",
    source: "GitHub",
    url: it.html_url,
    score: Math.min(99, Math.floor((it.stargazers_count || 0) / 100)),
    stats: { stars: it.stargazers_count || 0, forks: it.forks_count || 0 },
    lat: 37.77,
    lng: -122.42,
  }));
}

async function openAlexSearch(q, limit = 5) {
  const url = new URL("https://api.openalex.org/works");
  url.searchParams.set("search", q);
  url.searchParams.set("per_page", String(limit));
  const res = await fetch(url, { headers: { "User-Agent": UA } });
  if (!res.ok) throw new Error(`openalex → ${res.status}`);
  const results = (await res.json()).results || [];
  return results.map((w) => {
    const wid = (w.id || "").split("/").pop();
    const author = (w.authorships || [{}])[0]?.author?.display_name || "";
    return {
      id: `oa:${wid}`,
      kind: "paper",
      label: w.display_name || wid,
      sub: author,
      description: w.abstract_inverted_index ? "Abstract available" : "",
      source: "OpenAlex",
      url: w.id,
      score: Math.min(99, Math.floor((w.cited_by_count || 0) / 50)),
      stats: { citations: w.cited_by_count || 0, year: w.publication_year },
      lat: 52.52,
      lng: 13.4,
    };
  });
}

async function nominatimSearch(q, limit = 4) {
  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("q", q);
  url.searchParams.set("format", "json");
  url.searchParams.set("limit", String(limit));
  const res = await fetch(url, { headers: { "User-Agent": UA } });
  if (!res.ok) throw new Error(`nominatim → ${res.status}`);
  const rows = await res.json();
  return rows.map((r) => ({
    id: `geo:${r.place_id}`,
    kind: "place",
    label: r.display_name || "",
    sub: r.type || "",
    description: r.display_name || "",
    source: "Nominatim",
    score: 70,
    lat: parseFloat(r.lat || 0),
    lng: parseFloat(r.lon || 0),
    stats: { type: r.type, importance: Math.round(parseFloat(r.importance || 0) * 1000) / 1000 },
  }));
}

export async function directSearch(q) {
  const groups = [];
  await Promise.all([
    githubSearch(q).then((items) => items.length && groups.push({ source: "GitHub", items })).catch(() => {}),
    openAlexSearch(q).then((items) => items.length && groups.push({ source: "OpenAlex", items })).catch(() => {}),
    nominatimSearch(q).then((items) => items.length && groups.push({ source: "Nominatim", items })).catch(() => {}),
  ]);
  if (!groups.length) throw new Error("All OSS sources unavailable");
  return { query: q, groups };
}

export async function directGithubRepo(owner, repo) {
  const res = await fetch(`https://api.github.com/repos/${owner}/${repo}`, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`github repo → ${res.status}`);
  const it = await res.json();
  return {
    description: it.description || "",
    stats: {
      stars: it.stargazers_count || 0,
      forks: it.forks_count || 0,
      issues: it.open_issues_count || 0,
      language: it.language || "—",
    },
    relations: (it.topics || []).slice(0, 5).map((l) => ({ id: `gh:${l}`, label: l, type: "topic" })),
  };
}

export async function directOpenAlexWork(workId) {
  const res = await fetch(`https://api.openalex.org/works/${encodeURIComponent(workId)}`, {
    headers: { "User-Agent": UA },
  });
  if (!res.ok) throw new Error(`openalex work → ${res.status}`);
  const w = await res.json();
  return {
    description: w.display_name || "",
    stats: {
      citations: w.cited_by_count || 0,
      year: w.publication_year || "—",
      type: w.type || "—",
      oa: w.open_access?.is_oa || false,
    },
    relations: [],
  };
}

export async function directGeoPlace(placeId) {
  const res = await fetch(
    `https://nominatim.openstreetmap.org/lookup?osm_ids=N${encodeURIComponent(placeId)}&format=json`,
    { headers: { "User-Agent": UA } },
  );
  if (!res.ok) throw new Error(`nominatim place → ${res.status}`);
  const rows = await res.json();
  if (!rows.length) return { description: "", stats: {} };
  const r = rows[0];
  return {
    description: r.display_name || "",
    stats: { type: r.type, lat: r.lat, lon: r.lon },
  };
}
