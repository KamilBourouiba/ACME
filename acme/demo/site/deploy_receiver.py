"""Host-side deploy receiver — writes artifacts and runs docker compose."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SITE_DIR = Path("/opt/nexus-site")
DEPLOY_KEY = os.environ.get("DEPLOY_KEY", "")
PORT = int(os.environ.get("DEPLOY_PORT", "9090"))


def _compose_cmd() -> list[str]:
    proc = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if proc.returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]


def _run_compose(site_dir: Path) -> subprocess.CompletedProcess[str]:
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
    subprocess.run(
        [*base, "-f", compose_file, "build", "--no-cache", "api"],
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


class Handler(BaseHTTPRequestHandler):
    def _json(self, code: int, body: dict) -> None:
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._json(200, {"status": "ok"})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/deploy":
            self._json(404, {"error": "not found"})
            return
        auth = self.headers.get("Authorization", "")
        if not DEPLOY_KEY or auth != f"Bearer {DEPLOY_KEY}":
            self._json(401, {"error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode())
        files = payload.get("files", {})
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
            proc = _run_compose(SITE_DIR)
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
