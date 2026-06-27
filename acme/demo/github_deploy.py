"""Push demo site artifacts to GitHub via Contents API."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger("acme.demo.github")

GITHUB_API = "https://api.github.com"


async def _get_file_sha(
    client: httpx.AsyncClient,
    *,
    token: str,
    repo: str,
    path: str,
    branch: str,
) -> str | None:
    url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
    resp = await client.get(url, headers=_headers(token), params={"ref": branch})
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json().get("sha")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def deploy_files(
    files: dict[str, str],
    *,
    token: str,
    repo: str,
    branch: str = "main",
    commit_message: str = "Deploy Nexus Advisory site from ACME demo",
) -> dict[str, Any]:
    """Create or update files on a GitHub repo branch."""
    if not files:
        raise ValueError("No files to deploy")
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError("repo must be owner/name")

    updated: list[str] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for path, content in files.items():
            sha = await _get_file_sha(client, token=token, repo=repo, path=path, branch=branch)
            body: dict[str, Any] = {
                "message": commit_message if len(updated) == 0 else f"{commit_message} ({path})",
                "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                "branch": branch,
            }
            if sha:
                body["sha"] = sha
            url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
            resp = await client.put(url, headers=_headers(token), json=body)
            if resp.status_code >= 400:
                logger.error("GitHub deploy failed for %s: %s", path, resp.text)
                resp.raise_for_status()
            updated.append(path)

    pages_url = f"https://{repo.split('/')[0]}.github.io/{repo.split('/')[1]}/"
    return {
        "repo": repo,
        "branch": branch,
        "files": updated,
        "pages_url": pages_url,
        "commit_message": commit_message,
    }
