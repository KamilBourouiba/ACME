"""Static front-end bundle helpers — correct asset paths for VM + GitHub Pages."""

from __future__ import annotations

import re
from pathlib import Path

from acme.demo.artifacts import load_site_artifacts

SITE_ROOT = Path(__file__).resolve().parent / "site" / "static"

_STATIC_PREFIX = re.compile(r"""((?:href|src)\s*=\s*["'])/static/""", re.IGNORECASE)
_ASSET_HREF = re.compile(r"""href=["'](css/[^"']+)["']""", re.IGNORECASE)
_ASSET_SRC = re.compile(r"""src=["'](js/[^"']+)["']""", re.IGNORECASE)

# Always publish canonical shell on GitHub Pages — agents broke index with missing css/layout.css.
PAGES_PINNED_STATIC = frozenset({"index.html"})


def normalize_static_asset_paths(content: str) -> str:
    """VM nginx and GitHub Pages both serve static/ contents at the site root."""
    return _STATIC_PREFIX.sub(r"\1", content)


def reference_static_files() -> dict[str, str]:
    """Canonical css/js/html from acme/demo/site/static/."""
    out: dict[str, str] = {}
    if not SITE_ROOT.is_dir():
        return out
    for path in sorted(SITE_ROOT.rglob("*")):
        if path.is_file() and path.suffix in {".css", ".js", ".html"}:
            rel = f"static/{path.relative_to(SITE_ROOT).as_posix()}"
            out[rel] = path.read_text(encoding="utf-8")
    return out


def _index_asset_refs(index_html: str) -> set[str]:
    refs = set(_ASSET_HREF.findall(index_html))
    refs.update(_ASSET_SRC.findall(index_html))
    return {r.split("?", 1)[0] for r in refs}


def _index_assets_missing(index_html: str, available: set[str]) -> list[str]:
    missing = []
    for ref in _index_asset_refs(index_html):
        if ref not in available:
            missing.append(ref)
    return missing


def inject_pages_api_base(index_html: str) -> str:
    """GitHub Pages: use direct OSS APIs (VM TLS is self-signed and blocked by browsers)."""
    if "EREBOR_DIRECT_OSS" in index_html:
        html = index_html
    else:
        snippet = '  <script>window.EREBOR_DIRECT_OSS=true;</script>\n'
        if "</head>" in index_html:
            html = index_html.replace("</head>", f"{snippet}</head>", 1)
        else:
            html = snippet + index_html
    # Bust module cache after deploy — browsers keep stale api.js otherwise.
    import time

    v = int(time.time())
    html = html.replace('src="js/scene.js"', f'src="js/scene.js?v={v}"')
    html = html.replace('src="js/app.js"', f'src="js/app.js?v={v}"')
    return html


def merge_static_bundle(artifacts: dict[str, str]) -> dict[str, str]:
    """Ensure css/js exist — agents sometimes ship index.html without assets."""
    merged = dict(reference_static_files())
    merged.update(artifacts)
    index_key = "static/index.html" if "static/index.html" in merged else "index.html"
    if index_key in merged:
        merged[index_key] = normalize_static_asset_paths(merged[index_key])
    return merged


def github_pages_bundle(artifacts: dict[str, str]) -> dict[str, str]:
    """Pages repo root = former static/ — paths must be css/… not /static/css/…"""
    refs = reference_static_files()
    merged = dict(refs)
    for path, content in artifacts.items():
        if not path.startswith("static/"):
            continue
        base = path.removeprefix("static/")
        if base in PAGES_PINNED_STATIC:
            continue
        merged[path] = content

    index = refs.get("static/index.html", merged.get("static/index.html", ""))
    index = normalize_static_asset_paths(inject_pages_api_base(index))

    out: dict[str, str] = {}
    for path, content in merged.items():
        if not path.startswith("static/"):
            continue
        dest = path.removeprefix("static/")
        if dest.endswith(".html") and dest == "index.html":
            content = index
        elif dest.endswith(".html"):
            content = normalize_static_asset_paths(content)
        out[dest] = content

    available = set(out.keys())
    missing = _index_assets_missing(out.get("index.html", ""), available)
    if missing:
        for path, content in refs.items():
            if path.startswith("static/"):
                out[path.removeprefix("static/")] = content
        out["index.html"] = normalize_static_asset_paths(inject_pages_api_base(refs["static/index.html"]))

    return out


def is_agent_editable_file(path: str) -> bool:
    """After bootstrap, agents may only change the static front-end."""
    norm = path.replace("\\", "/")
    return norm.startswith("static/")


def static_artifact_keys(artifacts: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in artifacts.items() if k.startswith("static/")}


def platform_reference_artifacts() -> dict[str, str]:
    """Full canonical site tree for platform reconcile (API + static)."""
    return load_site_artifacts()


def vm_static_bundle(artifacts: dict[str, str]) -> dict[str, str]:
    """VM nginx root mounts ./static — normalize index.html asset URLs."""
    merged = merge_static_bundle(artifacts)
    if "static/index.html" in merged:
        merged["static/index.html"] = normalize_static_asset_paths(merged["static/index.html"])
    return merged
