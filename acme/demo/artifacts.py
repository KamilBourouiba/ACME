"""Load demo site artifacts from the site/ tree."""

from __future__ import annotations

from pathlib import Path

SITE_ROOT = Path(__file__).resolve().parent / "site"
SKIP_NAMES = frozenset({"deploy_receiver.py", "Dockerfile.deploy"})
SKIP_DIRS = frozenset({"certs", "__pycache__"})
TEXT_SUFFIXES = frozenset({".py", ".md", ".html", ".css", ".js", ".txt", ".yml", ".conf", ".example", ".json"})


def load_site_artifacts() -> dict[str, str]:
    artifacts: dict[str, str] = {}
    if not SITE_ROOT.is_dir():
        return artifacts
    for path in sorted(SITE_ROOT.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(SITE_ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if path.name in SKIP_NAMES:
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in ("Dockerfile",):
            continue
        artifacts[str(rel).replace("\\", "/")] = path.read_text(encoding="utf-8")
    return artifacts


def artifact(name: str, store: dict[str, str] | None = None) -> str:
    data = store if store is not None else SITE_ARTIFACTS
    if name not in data:
        raise KeyError(f"Missing demo artifact: {name}")
    return data[name]


SITE_ARTIFACTS: dict[str, str] = load_site_artifacts()
