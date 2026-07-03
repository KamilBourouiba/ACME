"""Static front-end bundle helpers — correct asset paths for VM + GitHub Pages."""

from __future__ import annotations

import re
from pathlib import Path

from acme.demo.artifacts import load_site_artifacts

SITE_ROOT = Path(__file__).resolve().parent / "site" / "static"

_STATIC_PREFIX = re.compile(r"""((?:href|src)\s*=\s*["'])/static/""", re.IGNORECASE)
_ASSET_HREF = re.compile(r"""href=["'](css/[^"']+)["']""", re.IGNORECASE)
_ASSET_SRC = re.compile(r"""src=["'](js/[^"']+)["']""", re.IGNORECASE)

# Always publish canonical shell + trace JS — agents broke index and corrupted app.js.
PAGES_PINNED_STATIC = frozenset(
    {
        "index.html",
        "js/api.js",
        "js/app.js",
        "js/trace-fallback.json",
    }
)
VM_PINNED_STATIC = PAGES_PINNED_STATIC


def publish_artifact_bundle(agent_artifacts: dict[str, str] | None = None) -> dict[str, str]:
    """Canon site tree from disk; only agent CSS overrides may ship."""
    canon = load_site_artifacts()
    css_overrides = {
        k: v
        for k, v in (agent_artifacts or {}).items()
        if k.replace("\\", "/").startswith("static/css/")
    }
    return {**canon, **css_overrides}


def normalize_static_asset_paths(content: str) -> str:
    """VM nginx and GitHub Pages both serve static/ contents at the site root."""
    return _STATIC_PREFIX.sub(r"\1", content)


def reference_static_files() -> dict[str, str]:
    """Canonical css/js/html from acme/demo/site/static/."""
    out: dict[str, str] = {}
    if not SITE_ROOT.is_dir():
        return out
    for path in sorted(SITE_ROOT.rglob("*")):
        if path.is_file() and path.suffix in {".css", ".js", ".html", ".json"}:
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
    """GitHub Pages: cache-bust static JS after deploy."""
    import time

    v = int(time.time())
    html = index_html
    html = html.replace('src="js/api.js"', f'src="js/api.js?v={v}"')
    html = html.replace('src="js/app.js"', f'src="js/app.js?v={v}"')
    return html


def merge_static_bundle(artifacts: dict[str, str]) -> dict[str, str]:
    """Ensure css/js exist — agents sometimes ship index.html without assets."""
    merged = dict(reference_static_files())
    for path, content in artifacts.items():
        if not path.startswith("static/"):
            continue
        base = path.removeprefix("static/")
        if base in VM_PINNED_STATIC:
            continue
        merged[path] = content
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

    return _with_pages_extras(_force_pinned_pages(out))


def _force_pinned_pages(out: dict[str, str]) -> dict[str, str]:
    """Last line of defense — pinned trace assets always from disk reference."""
    refs = reference_static_files()
    for path, content in refs.items():
        if not path.startswith("static/"):
            continue
        base = path.removeprefix("static/")
        if base in PAGES_PINNED_STATIC:
            if base == "index.html":
                out[base] = normalize_static_asset_paths(inject_pages_api_base(content))
            else:
                out[base] = content
    return out


def _with_pages_extras(out: dict[str, str]) -> dict[str, str]:
    """GitHub Pages: skip Jekyll processing."""
    out = dict(out)
    out[".nojekyll"] = ""
    return out


def is_agent_editable_file(path: str) -> bool:
    """After bootstrap, agents may only change static css — not index or trace JS."""
    norm = path.replace("\\", "/")
    if norm in ("static/index.html", "index.html"):
        return False
    if norm.startswith("static/js/"):
        return False
    return norm.startswith("static/")


def static_artifact_keys(artifacts: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in artifacts.items() if k.startswith("static/")}


def platform_reference_artifacts() -> dict[str, str]:
    """Full canonical site tree for platform reconcile (API + static)."""
    return load_site_artifacts()


def vm_static_bundle(artifacts: dict[str, str]) -> dict[str, str]:
    """VM nginx root mounts ./static — pin index.html, merge agent css/js."""
    refs = reference_static_files()
    merged = merge_static_bundle(artifacts)
    for path, content in artifacts.items():
        if not path.startswith("static/"):
            continue
        base = path.removeprefix("static/")
        if base in VM_PINNED_STATIC:
            continue
        merged[path] = content
    if "static/index.html" in refs:
        index = normalize_static_asset_paths(refs["static/index.html"])
        available = {k.removeprefix("static/") for k in merged if k.startswith("static/")}
        missing = _index_assets_missing(index, available)
        if missing:
            merged.update(refs)
            index = normalize_static_asset_paths(refs["static/index.html"])
        merged["static/index.html"] = index
    for path, content in reference_static_files().items():
        if not path.startswith("static/"):
            continue
        base = path.removeprefix("static/")
        if base in VM_PINNED_STATIC:
            merged[path] = content
    return merged
