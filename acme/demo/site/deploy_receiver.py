"""Host-side deploy receiver — writes artifacts and runs docker compose."""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

SITE_DIR = Path("/opt/nexus-site")
DEPLOY_KEY = os.environ.get("DEPLOY_KEY", "")
PORT = int(os.environ.get("DEPLOY_PORT", "9090"))
EXEC_TIMEOUT_DEFAULT = 45
EXEC_TIMEOUT_MAX = 180

FORBIDDEN_SHELL = re.compile(r"[;&|`$><\n\r]|\$\(|\${")

ALLOWED_BINARIES = frozenset(
    {
        "curl",
        "docker",
        "docker-compose",
        "systemctl",
        "ls",
        "cat",
        "test",
        "python3",
        "head",
        "tail",
        "grep",
        "wc",
    }
)

DOCKER_SUBCOMMANDS = frozenset(
    {"ps", "logs", "inspect", "compose", "rm", "restart", "start", "stop", "images"}
)

SYSTEMCTL_SUBCOMMANDS = frozenset({"status", "is-active", "restart", "start", "stop"})


def _validate_command(command: str) -> tuple[bool, str]:
    cmd = command.strip()
    if not cmd:
        return False, "empty command"
    if FORBIDDEN_SHELL.search(cmd):
        return False, "shell metacharacters not allowed"
    try:
        parts = shlex.split(cmd)
    except ValueError as exc:
        return False, str(exc)
    if not parts:
        return False, "empty command"
    binary = parts[0]
    if binary not in ALLOWED_BINARIES:
        return False, f"binary not allowed: {binary}"
    if binary == "docker" and len(parts) > 1:
        if parts[1] == "system" and len(parts) > 2 and parts[2] == "prune":
            pass
        elif parts[1] not in DOCKER_SUBCOMMANDS:
            return False, f"docker subcommand not allowed: {parts[1]}"
    if binary == "systemctl" and len(parts) > 1 and parts[1] not in SYSTEMCTL_SUBCOMMANDS:
        return False, f"systemctl subcommand not allowed: {parts[1]}"
    if binary == "curl":
        joined = " ".join(parts)
        if not re.search(r"https?://(127\.0\.0\.1|localhost)", joined):
            return False, "curl only allowed to localhost"
    if binary in {"cat", "ls", "head", "tail", "grep", "test"}:
        for arg in parts[1:]:
            if arg.startswith("-") and binary != "grep":
                continue
            if not arg.startswith("/opt/nexus-site"):
                return False, f"path must stay under /opt/nexus-site: {arg}"
    return True, ""


def _run_shell(command: str, *, cwd: Path, timeout: float) -> dict:
    ok, reason = _validate_command(command)
    if not ok:
        return {"ok": False, "error": reason, "returncode": None, "stdout": "", "stderr": ""}
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": (proc.stdout or "")[-12000:],
            "stderr": (proc.stderr or "")[-4000:],
        }
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "error": f"timed out after {timeout}s",
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "returncode": None,
            "stdout": "",
            "stderr": "",
        }


def _compose_cmd() -> list[str]:
    proc = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if proc.returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]


def _services_running(site_dir: Path) -> bool:
    base = _compose_cmd()
    compose_file = str(site_dir / "docker-compose.yml")
    proc = subprocess.run(
        [*base, "-f", compose_file, "ps", "--status", "running", "--services"],
        cwd=site_dir,
        capture_output=True,
        text=True,
    )
    running = {line.strip() for line in (proc.stdout or "").splitlines() if line.strip()}
    return "api" in running and "nginx" in running


def _reload_nginx(site_dir: Path) -> None:
    base = _compose_cmd()
    compose_file = str(site_dir / "docker-compose.yml")
    subprocess.run(
        [*base, "-f", compose_file, "exec", "-T", "nginx", "nginx", "-s", "reload"],
        cwd=site_dir,
        capture_output=True,
        text=True,
    )


def _run_compose(site_dir: Path, *, rebuild_api: bool = True) -> subprocess.CompletedProcess[str]:
    compose_file = str(site_dir / "docker-compose.yml")
    base = _compose_cmd()
    subprocess.run(
        [*base, "-f", compose_file, "down", "--remove-orphans"],
        cwd=site_dir,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["docker", "rm", "-f", "nexus-site_api_1", "nexus-site_nginx_1"],
        capture_output=True,
        text=True,
    )
    if rebuild_api:
        subprocess.run(
            [*base, "-f", compose_file, "build", "api"],
            cwd=site_dir,
            capture_output=True,
            text=True,
        )
    return subprocess.run(
        [*base, "-f", compose_file, "up", "-d", "--force-recreate"],
        cwd=site_dir,
        capture_output=True,
        text=True,
    )


def _deploy_stack(site_dir: Path, *, mode: str = "full") -> subprocess.CompletedProcess[str]:
    """static = nginx reload only when healthy; platform/full = docker compose."""
    if mode == "static" and _services_running(site_dir):
        _reload_nginx(site_dir)
        return subprocess.CompletedProcess(
            args=["static-sync"],
            returncode=0,
            stdout="static sync (nginx reload)",
            stderr="",
        )
    rebuild = mode in ("full", "platform", "auto")
    return _run_compose(site_dir, rebuild_api=rebuild)


def _run_compose(site_dir: Path) -> subprocess.CompletedProcess[str]:
    return _deploy_stack(site_dir, mode="full")


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        auth = self.headers.get("Authorization", "")
        return bool(DEPLOY_KEY) and auth == f"Bearer {DEPLOY_KEY}"

    def do_GET(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path in ("/deploy/status", "/logs"):
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            if path == "/deploy/status":
                status_path = SITE_DIR / "last_deploy.json"
                if not status_path.is_file():
                    self._json(200, {"ok": False, "status": "never"})
                    return
                self._json(200, json.loads(status_path.read_text(encoding="utf-8")))
                return
            qs = parse_qs(urlparse(self.path).query)
            service = (qs.get("service") or ["api"])[0]
            tail = int((qs.get("tail") or ["80"])[0])
            compose_file = str(SITE_DIR / "docker-compose.yml")
            base = _compose_cmd()
            proc = subprocess.run(
                [*base, "-f", compose_file, "logs", "--no-color", f"--tail={tail}", service],
                cwd=SITE_DIR,
                capture_output=True,
                text=True,
            )
            logs = (proc.stdout or "") + (proc.stderr or "")
            self._json(
                200,
                {"service": service, "lines": len(logs.splitlines()), "logs": logs[-8000:]},
            )
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/exec":
            if not self._authorized():
                self._json(401, {"error": "unauthorized"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode())
            command = str(payload.get("command", "")).strip()
            cwd = Path(str(payload.get("cwd", SITE_DIR)))
            if not str(cwd).startswith(str(SITE_DIR)):
                self._json(400, {"error": "cwd must be under /opt/nexus-site"})
                return
            timeout = min(
                float(payload.get("timeout", EXEC_TIMEOUT_DEFAULT)),
                EXEC_TIMEOUT_MAX,
            )
            result = _run_shell(command, cwd=cwd, timeout=timeout)
            code = 200 if result.get("ok") or result.get("returncode") is not None else 500
            self._json(code, result)
            return
        if path != "/deploy":
            self._json(404, {"error": "not found"})
            return
        auth = self.headers.get("Authorization", "")
        if not DEPLOY_KEY or auth != f"Bearer {DEPLOY_KEY}":
            self._json(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode())
        files = payload.get("files", {})
        deploy_mode = str(payload.get("mode", "full")).lower()
        if payload.get("wipe"):
            import shutil

            for sub in ("static", "tests"):
                p = SITE_DIR / sub
                if p.is_dir():
                    shutil.rmtree(p)
            for name in ("server.py", "ARCHITECTURE.md", "README.md"):
                f = SITE_DIR / name
                if f.is_file():
                    f.unlink()
            api_dir = SITE_DIR / "api"
            if api_dir.is_dir():
                for f in api_dir.rglob("*"):
                    if f.is_file() and f.name != "__init__.py" and "routes/__init__" not in str(f):
                        rel = f.relative_to(api_dir)
                        if str(rel) not in ("__init__.py", "routes/__init__.py"):
                            f.unlink()

        static = SITE_DIR / "static"
        static.mkdir(parents=True, exist_ok=True)
        (SITE_DIR / "certs").mkdir(parents=True, exist_ok=True)

        env_path = SITE_DIR / ".env"
        if not env_path.exists():
            db = os.environ.get("DATABASE_URL", "")
            key = os.environ.get("DEPLOY_KEY", DEPLOY_KEY)
            env_path.write_text(f"DATABASE_URL={db}\nDEPLOY_KEY={key}\n", encoding="utf-8")
            os.chmod(env_path, 0o600)

        for name, content in files.items():
            dest = SITE_DIR / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

        def _build() -> None:
            proc = _deploy_stack(SITE_DIR, mode=deploy_mode)
            status_path = SITE_DIR / "last_deploy.json"
            status_path.write_text(
                json.dumps(
                    {
                        "ok": proc.returncode == 0,
                        "stderr": (proc.stderr or "")[-4000:] if proc.returncode else "",
                    }
                ),
                encoding="utf-8",
            )

        threading.Thread(target=_build, daemon=True).start()
        self._json(202, {"status": "deploying", "files": len(files)})

    def log_message(self, fmt: str, *args) -> None:
        return


if __name__ == "__main__":
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
