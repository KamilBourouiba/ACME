/** Belief Observatory API client — VM /api/trace with JSON fallback for GitHub Pages. */

function isGitHubPagesHost() {
  if (typeof window === "undefined" || !window.location) return false;
  return /\.github\.io$/i.test(window.location.hostname);
}

async function loadTrace() {
  const bases = [];
  if (typeof window !== "undefined" && window.BELIEF_OBS_API_BASE) {
    bases.push(`${String(window.BELIEF_OBS_API_BASE).replace(/\/$/, "")}/api/trace`);
  }
  if (!isGitHubPagesHost()) {
    bases.push("/api/trace");
  }
  for (const url of bases) {
    try {
      const res = await fetch(url);
      if (!res.ok) continue;
      const data = await res.json();
      if (data.nodes?.length && data.steps?.length) {
        return { data, source: url.includes("/api/trace") && !url.startsWith("/") ? "api" : "vm" };
      }
    } catch (_) {}
  }
  try {
    const res = await fetch("js/trace-fallback.json");
    if (res.ok) {
      const data = await res.json();
      return { data, source: "embedded" };
    }
  } catch (_) {}
  return { data: { nodes: [], edges: [], steps: [] }, source: "empty" };
}

window.BeliefObsAPI = { loadTrace };
