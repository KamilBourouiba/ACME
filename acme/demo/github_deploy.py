"""Push demo site artifacts to GitHub via Contents API."""

from __future__ import annotations

import asyncio
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
            "description": "Erebor open intelligence graph — published autonomously by ACME demo squad",
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


async def wait_for_pages_live(
    pages_url: str,
    *,
    attempts: int = 12,
    pause_sec: float = 3.0,
    expected_snippet: str = "Erebor",
) -> dict[str, Any]:
    """Poll the public GitHub Pages URL until the site responds."""
    last_status: int | None = None
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        for attempt in range(1, attempts + 1):
            try:
                resp = await client.get(pages_url)
                last_status = resp.status_code
                if resp.status_code == 200 and expected_snippet in resp.text:
                    return {
                        "ok": True,
                        "pages_url": pages_url,
                        "status_code": resp.status_code,
                        "attempts": attempt,
                    }
            except httpx.HTTPError as exc:
                logger.debug("Pages poll %s attempt %s: %s", pages_url, attempt, exc)
            if attempt < attempts:
                await asyncio.sleep(pause_sec)

    return {
        "ok": False,
        "pages_url": pages_url,
        "status_code": last_status,
        "attempts": attempts,
    }


async def get_pages_info(
    client: httpx.AsyncClient,
    *,
    token: str,
    repo: str,
) -> dict[str, Any] | None:
    resp = await client.get(f"{GITHUB_API}/repos/{repo}/pages", headers=_headers(token))
    if resp.status_code != 200:
        return None
    data = resp.json()
    return {
        "html_url": data.get("html_url"),
        "status": data.get("status"),
        "build_type": data.get("build_type"),
    }


async def deploy_files(
    files: dict[str, str],
    *,
    token: str,
    repo: str,
    branch: str = "main",
    commit_message: str = "Deploy Erebor site from ACME demo",
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

        for path, content in sorted(files.items()):
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
            if resp.status_code == 409:
                fresh_sha = await _get_file_sha(
                    client, token=token, repo=repo, path=path, branch=branch
                )
                if fresh_sha and fresh_sha != sha:
                    body["sha"] = fresh_sha
                    resp = await client.put(url, headers=_headers(token), json=body)
            if resp.status_code >= 400:
                logger.error("GitHub deploy failed for %s: %s", path, resp.text)
                resp.raise_for_status()
            updated.append(path)

        pages_url = pages_url_for(repo)
        pages_info = await get_pages_info(client, token=token, repo=repo)
        live_check = await wait_for_pages_live(pages_url)

    return {
        "repo": repo,
        "branch": branch,
        "files": updated,
        "pages_url": pages_url,
        "pages_info": pages_info,
        "pages_verified": live_check["ok"],
        "pages_status_code": live_check.get("status_code"),
        "pages_poll_attempts": live_check.get("attempts"),
        "commit_message": commit_message,
    }


async def wipe_repo(
    *,
    token: str,
    repo: str,
    branch: str = "main",
    keep_paths: frozenset[str] | None = None,
) -> list[str]:
    """Delete tracked files so the squad can greenfield again."""
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError("repo must be owner/name")
    keep = keep_paths or frozenset()
    deleted: list[str] = []

    async with httpx.AsyncClient(timeout=60.0) as client:
        ref_resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/git/ref/heads/{branch}",
            headers=_headers(token),
        )
        if ref_resp.status_code == 404:
            return deleted
        ref_resp.raise_for_status()
        commit_sha = ref_resp.json()["object"]["sha"]

        tree_resp = await client.get(
            f"{GITHUB_API}/repos/{repo}/git/trees/{commit_sha}",
            headers=_headers(token),
            params={"recursive": "1"},
        )
        tree_resp.raise_for_status()
        entries = tree_resp.json().get("tree", [])

        for item in reversed(entries):
            if item.get("type") != "blob":
                continue
            path = item["path"]
            if path in keep:
                continue
            sha = await _get_file_sha(client, token=token, repo=repo, path=path, branch=branch)
            if not sha:
                continue
            url = f"{GITHUB_API}/repos/{repo}/contents/{path}"
            resp = await client.delete(
                url,
                headers=_headers(token),
                json={
                    "message": f"ACME demo reset — wipe {path}",
                    "sha": sha,
                    "branch": branch,
                },
            )
            if resp.status_code < 400:
                deleted.append(path)
            else:
                logger.warning("GitHub wipe failed for %s: %s", path, resp.text[:200])

    logger.info("Wiped %d files from %s", len(deleted), repo)
    return deleted
