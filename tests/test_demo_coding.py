import pytest

from acme.demo.agents import AGENT_BY_ID
from acme.demo.artifacts import REFERENCE_ARTIFACTS, baseline_artifacts, empty_artifacts
from acme.demo.coding import _strip_fences, generate_agent_code
from acme.demo.script import SCRIPT_BEATS


def test_empty_artifacts_on_fresh_start():
    assert empty_artifacts() == {}
    assert "static/index.html" not in baseline_artifacts()


def test_strip_fences():
    assert _strip_fences("```python\nx = 1\n```") == "x = 1"


@pytest.mark.asyncio
async def test_generate_agent_code_uses_llm(monkeypatch):
    beat = next(b for b in SCRIPT_BEATS if b.code_file == "static/css/observatory.css")

    class FakeLLM:
        async def generate(self, *a, **kw):
            return ":root { --accent: #3dd6c6; }"

    monkeypatch.setattr("acme.demo.coding.get_llm_client", lambda: FakeLLM())
    code = await generate_agent_code(AGENT_BY_ID["marco"], beat, artifacts={})
    assert "--accent" in code


@pytest.mark.asyncio
async def test_generate_agent_code_no_fallback(monkeypatch):
    beat = next(b for b in SCRIPT_BEATS if b.code_file == "static/css/observatory.css")

    class FailLLM:
        async def generate(self, *a, **kw):
            raise RuntimeError("offline")

    monkeypatch.setattr("acme.demo.coding.get_llm_client", lambda: FailLLM())
    code = await generate_agent_code(AGENT_BY_ID["marco"], beat, artifacts={})
    assert code != REFERENCE_ARTIFACTS.get("static/css/observatory.css", "")
    assert "pending" in code


def test_script_beats_have_no_preloaded_code():
    for beat in SCRIPT_BEATS:
        if beat.kind == "code":
            assert beat.code_body is None
