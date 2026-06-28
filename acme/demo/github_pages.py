"""Prepare static artifacts for GitHub Pages (root-relative paths)."""

from __future__ import annotations

from acme.demo.static_assets import github_pages_bundle


def github_pages_files(artifacts: dict[str, str]) -> dict[str, str]:
    """Map static/* into repo root for GitHub Pages."""
    return github_pages_bundle(artifacts)
