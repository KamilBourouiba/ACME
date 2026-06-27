"""Push demo site artifacts to GitHub via Contents API."""

from __future__ import annotations

import base64
import logging
from typing import Any

import httpx

logger = logging.getLogger("acme.demo.github")

GITHUB_API = "https://api.github.com"


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def pages_url_for(repo: str) -> str:
    owner, name = repo.split("/", 1)
    return f"https://{owner}.github.io/{name}/"


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


async def ensure_repo(
    client: httpx.AsyncClient,
    *,
    token: str,
    repo: str,
    branch: str = "main",
) -> None:
    """Create the target repo if it does not exist (user-owned)."""
    resp = await client.get(f"{GITHUB_API}/repos/{repo}", headers=_headers(token))
    if resp.status_code == 200:
        return
    if resp.status_code != 404:
        resp.raise_for_status()

    owner, name = repo.split("/", 1)
    create = await client.post(
        f"{GITHUB_API}/user/repos",
        headers=_headers(token),
        json={
            "name": name,
            "private": False,
            "auto_init": True,
            "description": "Nexus Advisory marketing site — published autonomously by ACME demo squad",
        },
    )
    if create.status_code >= 400:
        logger.error("GitHub create repo failed: %s", create.text)
        create.raise_for_status()
    logger.info("Created GitHub repo %s", repo)


async def ensure_pages(
    client: httpx.AsyncClient,
    *,
    token: str,
    repo: str,
    branch: str = "main",
) -> None:
    """Enable GitHub Pages from branch root if not already configured."""
    resp = await client.get(f"{GITHUB_API}/repos/{repo}/pages", headers=_headers(token))
    if resp.status_code == 200:
        return
    if resp.status_code not in (404, 403):
        resp.raise_for_status()

    pages = await client.post(
        f"{GITHUB_API}/repos/{repo}/pages",
        headers=_headers(token),
        json={"source": {"branch": branch, "path": "/"}},
    )
    if pages.status_code in (201, 409):
        return
    if pages.status_code >= 400:
        logger.warning("GitHub Pages enable skipped (%s): %s", pages.status_code, pages.text)


async def deploy_files(
    files: dict[str, str],
    *,
    token: str,
    repo: str,
    branch: str = "main",
    commit_message: str = "Deploy Nexus Advisory site from ACME demo",
    bootstrap_repo: bool = True,
    enable_pages: bool = True,
) -> dict[str, Any]:
    """Create or update files on a GitHub repo branch."""
    if not files:
        raise ValueError("No files to deploy")
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError("repo must be owner/name")

    updated: list[str] = []
    async with httpx.AsyncClient(timeout=90.0) as client:
        if bootstrap_repo:
            await ensure_repo(client, token=token, repo=repo, branch=branch)
        if enable_pages:
            await ensure_pages(client, token=token, repo=repo, branch=branch)

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

    return {
        "repo": repo,
        "branch": branch,
        "files": updated,
        "pages_url": pages_url_for(repo),
        "commit_message": commit_message,
    }
