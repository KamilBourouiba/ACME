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


def _run_compose(site_dir: Path) -> subprocess.CompletedProcess[str]:
    compose_file = str(site_dir / "docker-compose.yml")
    for cmd in (["docker", "compose"], ["docker-compose"]):
        proc = subprocess.run(
            [*cmd, "-f", compose_file, "up", "-d", "--build"],
            cwd=site_dir,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 or "unknown shorthand flag" not in proc.stderr:
            return proc
    return proc


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
        for name, content in files.items():
            if name in (
                "server.py",
                "requirements.txt",
                "Dockerfile",
                "docker-compose.yml",
                "nginx.conf",
                "deploy_receiver.py",
            ):
                (SITE_DIR / name).write_text(content, encoding="utf-8")
            elif name in ("index.html", "styles.css", "app.js"):
                (static / name).write_text(content, encoding="utf-8")

        def _build() -> None:
            subprocess.run(
                ["docker-compose", "-f", str(SITE_DIR / "docker-compose.yml"), "down"],
                cwd=SITE_DIR,
                capture_output=True,
                text=True,
            )
            proc = _run_compose(SITE_DIR)
            status_path = SITE_DIR / "last_deploy.json"
            status_path.write_text(
                json.dumps(
                    {
                        "ok": proc.returncode == 0,
                        "stderr": proc.stderr[-4000:] if proc.returncode else "",
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
