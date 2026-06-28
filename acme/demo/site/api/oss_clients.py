"""HTTP clients for open-source intelligence APIs."""

from __future__ import annotations

import httpx

UA = "Erebor/1.0 (ACME demo; +https://github.com/KamilBourouiba/ACME)"


async def github_search(q: str, *, limit: int = 6) -> list[dict]:
    url = "https://api.github.com/search/repositories"
    params = {"q": q, "sort": "stars", "order": "desc", "per_page": limit}
    async with httpx.AsyncClient(timeout=12.0, headers={"Accept": "application/vnd.github+json", "User-Agent": UA}) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    out = []
    for it in items:
        out.append(
            {
                "id": f"gh:{it['full_name']}",
                "kind": "repo",
                "label": it["full_name"],
                "sub": it.get("description") or "",
                "description": it.get("description") or "",
                "source": "GitHub",
                "url": it.get("html_url"),
                "score": min(99, int(it.get("stargazers_count", 0) // 100)),
                "stats": {"stars": it.get("stargazers_count", 0), "forks": it.get("forks_count", 0)},
                "lat": 37.77,
                "lng": -122.42,
            }
        )
    return out


async def github_repo(owner: str, repo: str) -> dict:
    url = f"https://api.github.com/repos/{owner}/{repo}"
    async with httpx.AsyncClient(timeout=12.0, headers={"Accept": "application/vnd.github+json", "User-Agent": UA}) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        it = resp.json()
    return {
        "description": it.get("description") or "",
        "stats": {
            "stars": it.get("stargazers_count", 0),
            "forks": it.get("forks_count", 0),
            "issues": it.get("open_issues_count", 0),
            "language": it.get("language") or "—",
        },
        "relations": [
            {"id": f"gh:{l}", "label": l, "type": "topic"}
            for l in (it.get("topics") or [])[:5]
        ],
    }


async def openalex_search(q: str, *, limit: int = 5) -> list[dict]:
    url = "https://api.openalex.org/works"
    params = {"search": q, "per_page": limit}
    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": UA}) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        results = resp.json().get("results", [])
    out = []
    for w in results:
        wid = w.get("id", "").rsplit("/", 1)[-1]
        out.append(
            {
                "id": f"oa:{wid}",
                "kind": "paper",
                "label": w.get("display_name") or wid,
                "sub": (w.get("authorships") or [{}])[0].get("author", {}).get("display_name", ""),
                "description": w.get("abstract_inverted_index") and "Abstract available" or "",
                "source": "OpenAlex",
                "url": w.get("id"),
                "score": min(99, int((w.get("cited_by_count") or 0) // 50)),
                "stats": {"citations": w.get("cited_by_count", 0), "year": w.get("publication_year")},
                "lat": 52.52,
                "lng": 13.40,
            }
        )
    return out


async def openalex_work(work_id: str) -> dict:
    url = f"https://api.openalex.org/works/{work_id}"
    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": UA}) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        w = resp.json()
    return {
        "description": w.get("display_name") or "",
        "stats": {
            "citations": w.get("cited_by_count", 0),
            "year": w.get("publication_year") or "—",
            "type": w.get("type") or "—",
            "oa": (w.get("open_access") or {}).get("is_oa", False),
        },
        "relations": [
            {"id": f"oa:{c.get('id', '').rsplit('/', 1)[-1]}", "label": c.get("display_name", ""), "type": "cited_by"}
            for c in (w.get("referenced_works") or [])[:3]
            if isinstance(c, str)
        ],
    }


async def nominatim_search(q: str, *, limit: int = 4) -> list[dict]:
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": q, "format": "json", "limit": limit}
    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": UA}) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        rows = resp.json()
    out = []
    for r in rows:
        out.append(
            {
                "id": f"geo:{r.get('place_id')}",
                "kind": "place",
                "label": r.get("display_name", ""),
                "sub": r.get("type", ""),
                "description": r.get("display_name", ""),
                "source": "Nominatim",
                "score": 70,
                "lat": float(r.get("lat", 0)),
                "lng": float(r.get("lon", 0)),
                "stats": {"type": r.get("type"), "importance": round(float(r.get("importance", 0)), 3)},
            }
        )
    return out


async def nominatim_place(place_id: str) -> dict:
    url = "https://nominatim.openstreetmap.org/lookup"
    params = {"osm_ids": f"N{place_id}", "format": "json"}
    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": UA}) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        rows = resp.json()
    if not rows:
        return {"description": "", "stats": {}}
    r = rows[0]
    return {
        "description": r.get("display_name", ""),
        "stats": {"type": r.get("type"), "lat": r.get("lat"), "lon": r.get("lon")},
    }
