import pytest

from acme.demo.github_deploy import wipe_repo


@pytest.mark.asyncio
async def test_wipe_repo_deletes_blobs(monkeypatch):
    calls: list[str] = []

    class FakeResp:
        def __init__(self, status_code: int, payload: dict | None = None, text: str = ""):
            self.status_code = status_code
            self._payload = payload or {}
            self.text = text

        def json(self):
            return self._payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(self.text)

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            if url.endswith("/git/ref/heads/main"):
                return FakeResp(200, {"object": {"sha": "abc123"}})
            if "/git/trees/abc123" in url:
                return FakeResp(
                    200,
                    {
                        "tree": [
                            {"type": "blob", "path": "static/index.html"},
                            {"type": "blob", "path": "README.md"},
                        ]
                    },
                )
            if "/contents/static/index.html" in url:
                return FakeResp(200, {"sha": "sha-index"})
            if "/contents/README.md" in url:
                return FakeResp(200, {"sha": "sha-readme"})
            return FakeResp(404)

        async def delete(self, url, **kwargs):
            calls.append(url)
            return FakeResp(204)

    monkeypatch.setattr("acme.demo.github_deploy.httpx.AsyncClient", lambda **kw: FakeClient())
    deleted = await wipe_repo(token="tok", repo="owner/repo", branch="main")
    assert "static/index.html" in deleted
    assert "README.md" in deleted
    assert len(calls) == 2
