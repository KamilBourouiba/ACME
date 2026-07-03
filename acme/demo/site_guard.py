"""Pin boot-critical site files — agents must not break the VM stack."""

from __future__ import annotations

import hashlib
import re
import subprocess
import tempfile
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

# API boot path — always deploy canonical copies (agents edit static/css instead).
PINNED_API_FILES = frozenset(
    {
        "api/__init__.py",
        "api/routes/__init__.py",
        "api/config.py",
        "api/models.py",
        "api/db.py",
        "api/belief_data.py",
        "api/routes/health.py",
        "api/routes/beliefs.py",
    }
)

# Trace UI — agent rewrites have shipped SyntaxError-ridden JS to prod.
PINNED_STATIC_FILES = frozenset(
    {
        "static/index.html",
        "static/js/api.js",
        "static/js/app.js",
        "static/js/trace-fallback.json",
    }
)

DEPLOY_PINNED_FILES = PROTECTED_SITE_FILES | PINNED_API_FILES

_JS_MODULE_MARKERS = re.compile(r"\bexport\s+(default|{|class|function|const|let|var)\b")


def is_protected_site_file(path: str) -> bool:
    return path.replace("\\", "/") in PROTECTED_SITE_FILES


def is_pinned_on_deploy(path: str) -> bool:
    return path.replace("\\", "/") in DEPLOY_PINNED_FILES


def is_pinned_static_file(path: str) -> bool:
    return path.replace("\\", "/") in PINNED_STATIC_FILES


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


def javascript_syntax_ok(path: str, source: str) -> bool:
    if not path.endswith(".js"):
        return True
    if not source.strip():
        return False
    if _JS_MODULE_MARKERS.search(source):
        return False
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tmp:
            tmp.write(source)
            tmp_path = tmp.name
        proc = subprocess.run(
            ["node", "--check", tmp_path],
            capture_output=True,
            timeout=8,
            check=False,
        )
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # No node in env — reject obvious corruption only.
        return "Unexpected token" not in source and source.count("(") == source.count(")")


def canon_file_hash(path: str) -> str | None:
    text = reference_site_file(path)
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def live_matches_canon(live_body: str, path: str) -> bool:
    canon = reference_site_file(path)
    if not canon:
        return True
    return hashlib.sha256(live_body.encode("utf-8")).hexdigest() == hashlib.sha256(
        canon.encode("utf-8")
    ).hexdigest()


def safe_site_artifact(path: str, body: str, *, previous: str | None = None) -> str:
    """Reject broken Python/JS; pinned infra and trace JS always use reference."""
    norm = path.replace("\\", "/")
    if is_pinned_on_deploy(norm) or is_pinned_static_file(norm):
        pinned = reference_site_file(norm)
        if pinned is not None:
            return pinned
    if norm.endswith(".py") and not python_syntax_ok(norm, body):
        if previous and python_syntax_ok(norm, previous):
            return previous
        fallback = reference_site_file(norm)
        if fallback is not None:
            return fallback
    if norm.endswith(".js") and not javascript_syntax_ok(norm, body):
        if previous and javascript_syntax_ok(norm, previous):
            return previous
        fallback = reference_site_file(norm)
        if fallback is not None:
            return fallback
    return body
