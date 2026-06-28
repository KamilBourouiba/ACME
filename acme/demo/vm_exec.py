"""Safe remote command execution on the demo VM via deploy receiver /exec."""

from __future__ import annotations

import re
import shlex
from typing import Any

import httpx

from acme.config import settings

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

SITE_DIR = "/opt/nexus-site"
COMPOSE_FILE = f"{SITE_DIR}/docker-compose.yml"

REMEDIATION_RECIPES: dict[str, str] = {
    "probe_site_health": f"curl -sk https://127.0.0.1/api/health",
    "probe_api_direct": "curl -sf http://127.0.0.1:8080/api/health",
    "probe_receiver": "curl -sf http://127.0.0.1:9090/health",
    "docker_ps": "docker ps -a --format '{{.Names}} {{.Status}}'",
    "compose_ps": f"docker compose -f {COMPOSE_FILE} ps",
    "compose_logs_api": f"docker compose -f {COMPOSE_FILE} logs --no-color --tail=50 api",
    "compose_logs_nginx": f"docker compose -f {COMPOSE_FILE} logs --no-color --tail=30 nginx",
    "compose_restart": f"docker compose -f {COMPOSE_FILE} restart",
    "compose_up": f"docker compose -f {COMPOSE_FILE} up -d --force-recreate",
    "compose_rebuild_api": (
        f"docker compose -f {COMPOSE_FILE} build --no-cache api && "
        f"docker compose -f {COMPOSE_FILE} up -d --force-recreate api nginx"
    ),
    "receiver_status": "systemctl is-active nexus-deploy",
    "receiver_restart": "systemctl restart nexus-deploy",
}


def validate_command(command: str) -> tuple[bool, str]:
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
    if binary == "docker" and len(parts) > 1 and parts[1] not in DOCKER_SUBCOMMANDS:
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


def pick_remediation_recipe(*, signature: str, attempt: int) -> str:
    """Rotate through fix recipes for a failure signature."""
    if "receiver_probe" in signature:
        recipes = ["receiver_status", "receiver_restart", "probe_receiver"]
    elif "container_logs" in signature or "deploy_status" in signature:
        recipes = ["compose_logs_api", "compose_logs_nginx", "compose_restart", "compose_rebuild_api"]
    elif "http_probe" in signature or "http_search" in signature:
        recipes = [
            "probe_site_health",
            "probe_api_direct",
            "docker_ps",
            "compose_ps",
            "compose_logs_api",
            "compose_up",
            "compose_rebuild_api",
        ]
    else:
        recipes = ["docker_ps", "compose_ps", "probe_site_health", "compose_restart"]
    return recipes[attempt % len(recipes)]


async def exec_on_vm(
    command: str,
    *,
    vm_url: str | None = None,
    deploy_key: str | None = None,
    timeout: float = 45.0,
    cwd: str = SITE_DIR,
) -> dict[str, Any]:
    ok, reason = validate_command(command)
    if not ok:
        return {"ok": False, "error": reason, "command": command}

    base = (vm_url or settings.demo_vm_url or "").rstrip("/")
    key = deploy_key or settings.demo_vm_deploy_key
    if not base or not key:
        return {"ok": False, "error": "VM exec not configured", "command": command}

    try:
        async with httpx.AsyncClient(timeout=timeout + 5, verify=False) as client:
            resp = await client.post(
                f"{base}/exec",
                json={"command": command, "cwd": cwd, "timeout": timeout},
                headers={"Authorization": f"Bearer {key}"},
            )
            if resp.status_code == 404:
                return {
                    "ok": False,
                    "error": "receiver has no /exec endpoint — redeploy deploy_receiver.py",
                    "command": command,
                }
            data = resp.json()
            data["command"] = command
            return data
    except Exception as exc:
        return {"ok": False, "error": str(exc), "command": command}


async def run_recipe(
    recipe: str,
    *,
    vm_url: str | None = None,
    deploy_key: str | None = None,
) -> dict[str, Any]:
    cmd = REMEDIATION_RECIPES.get(recipe)
    if not cmd:
        return {"ok": False, "error": f"unknown recipe: {recipe}", "recipe": recipe}
    result = await exec_on_vm(cmd, vm_url=vm_url, deploy_key=deploy_key, timeout=120.0)
    result["recipe"] = recipe
    return result
