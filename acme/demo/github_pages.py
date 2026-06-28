"""Prepare static artifacts for GitHub Pages (root-relative paths)."""

from __future__ import annotations


def github_pages_files(artifacts: dict[str, str]) -> dict[str, str]:
    """Map static/* into repo root for GitHub Pages."""
    out: dict[str, str] = {}
    for path, content in artifacts.items():
        if path.startswith("static/"):
            out[path.removeprefix("static/")] = content
    return out
