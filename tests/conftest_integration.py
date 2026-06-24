import subprocess
import sys
import time

import httpx
import pytest


@pytest.fixture(scope="module")
def api_server():
    """Start uvicorn once for the module — avoids async loop conflicts."""
    import os
    import signal

    # Ensure port is free
    os.system("lsof -ti:8765 | xargs kill -9 2>/dev/null")

    log = open("/tmp/acme-test-server.log", "w")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "acme.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ],
        cwd="/Users/apprenant122/Documents/ACME",
        env={**os.environ, "PYTHONPATH": "/Users/apprenant122/Documents/ACME"},
        stdout=log,
        stderr=subprocess.STDOUT,
    )
    base = "http://127.0.0.1:8765"
    for _ in range(60):
        try:
            r = httpx.get(f"{base}/api/v1/health", timeout=2.0)
            if r.status_code == 200 and r.json().get("postgres"):
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        proc.kill()
        pytest.fail("API server did not become healthy in time")

    yield base
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)
    log.close()
