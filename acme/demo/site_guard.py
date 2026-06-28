"""Pin boot-critical site files — agents must not break the VM stack."""

from __future__ import annotations

from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent / "site"

# Never let squad LLM edits override these on deploy.
PROTECTED_SITE_FILES = frozenset(
    {
        "server.py",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml",
        "nginx.conf",
        "deploy_receiver.py",
    }
)


def is_protected_site_file(path: str) -> bool:
    return path.replace("\\", "/") in PROTECTED_SITE_FILES


def reference_site_files(names: frozenset[str] | None = None) -> dict[str, str]:
    """Load canonical infra files from acme/demo/site/."""
    wanted = names or PROTECTED_SITE_FILES
    out: dict[str, str] = {}
    for name in wanted:
        path = SITE_DIR / name
        if path.is_file():
            out[name] = path.read_text(encoding="utf-8")
    return out
