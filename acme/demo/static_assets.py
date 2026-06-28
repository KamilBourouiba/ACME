"""Static front-end bundle helpers — correct asset paths for VM + GitHub Pages."""

from __future__ import annotations

import re
from pathlib import Path

from acme.demo.artifacts import load_site_artifacts

SITE_ROOT = Path(__file__).resolve().parent / "site" / "static"

_STATIC_PREFIX = re.compile(r"""((?:href|src)\s*=\s*["'])/static/""", re.IGNORECASE)


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
    merged = merge_static_bundle(artifacts)
    out: dict[str, str] = {}
    for path, content in merged.items():
        if not path.startswith("static/"):
            continue
        dest = path.removeprefix("static/")
        if dest.endswith(".html"):
            content = normalize_static_asset_paths(content)
        out[dest] = content
    return out


def vm_static_bundle(artifacts: dict[str, str]) -> dict[str, str]:
    """VM nginx root mounts ./static — normalize index.html asset URLs."""
    merged = merge_static_bundle(artifacts)
    if "static/index.html" in merged:
        merged["static/index.html"] = normalize_static_asset_paths(merged["static/index.html"])
    return merged
