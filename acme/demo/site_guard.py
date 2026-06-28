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

# API boot path — always deploy canonical copies (agents edit static/ instead).
PINNED_API_FILES = frozenset(
    {
        "api/__init__.py",
        "api/routes/__init__.py",
        "api/config.py",
        "api/models.py",
        "api/db.py",
        "api/oss_clients.py",
        "api/routes/health.py",
        "api/routes/intelligence.py",
    }
)

DEPLOY_PINNED_FILES = PROTECTED_SITE_FILES | PINNED_API_FILES


def is_protected_site_file(path: str) -> bool:
    return path.replace("\\", "/") in PROTECTED_SITE_FILES


def is_pinned_on_deploy(path: str) -> bool:
    return path.replace("\\", "/") in DEPLOY_PINNED_FILES


def reference_site_file(path: str) -> str | None:
    norm = path.replace("\\", "/")
    file_path = SITE_DIR / norm
    if file_path.is_file():
        return file_path.read_text(encoding="utf-8")
    return None


def reference_site_files(names: frozenset[str] | None = None) -> dict[str, str]:
    """Load canonical files from acme/demo/site/."""
    wanted = names or DEPLOY_PINNED_FILES
    out: dict[str, str] = {}
    for name in wanted:
        text = reference_site_file(name)
        if text is not None:
            out[name] = text
    return out


def python_syntax_ok(path: str, source: str) -> bool:
    if not path.endswith(".py"):
        return True
    try:
        compile(source, path, "exec")
        return True
    except SyntaxError:
        return False


def safe_site_artifact(path: str, body: str, *, previous: str | None = None) -> str:
    """Reject broken Python; pinned infra always uses reference."""
    norm = path.replace("\\", "/")
    if is_pinned_on_deploy(norm):
        pinned = reference_site_file(norm)
        if pinned is not None:
            return pinned
    if norm.endswith(".py") and not python_syntax_ok(norm, body):
        if previous and python_syntax_ok(norm, previous):
            return previous
        fallback = reference_site_file(norm)
        if fallback is not None:
            return fallback
    return body
