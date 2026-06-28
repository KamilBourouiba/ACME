import pytest

from acme.demo.improvement import _fallback_plan, plan_improvement
from acme.demo.skills import DemoSkills


def test_fallback_plan_probes_on_failure():
    plan = _fallback_plan(turn=0, observations="[http_probe] FAIL", artifacts={})
    assert plan.action == "probe"
    assert plan.agent_id == "jordan"


def test_fallback_plan_bootstraps_index_when_empty():
    plan = _fallback_plan(turn=0, observations="[http_probe] OK", artifacts={})
    assert plan.action == "edit"
    assert plan.file == "static/index.html"


def test_fallback_plan_deploys_periodically():
    artifacts = {"static/index.html": "<html></html>"}
    plan = _fallback_plan(turn=5, observations="[http_probe] OK", artifacts=artifacts)
    assert plan.action == "deploy"


def test_skills_list_artifacts():
    skills = DemoSkills(artifacts={"static/index.html": "<html>"})
    result = skills.list_artifacts()
    assert result.ok
    assert "static/index.html" in result.detail["paths"]


@pytest.mark.asyncio
async def test_plan_improvement_uses_llm(monkeypatch):
    class FakeLLM:
        async def generate(self, *args, **kwargs):
            return '{"agent_id":"marco","channel":"engineering","action":"edit","message":"Polish globe","file":"static/js/scene.js","lang":"javascript","query":null,"skill":null,"deploy":false}'

    monkeypatch.setattr("acme.demo.improvement.get_llm_client", lambda: FakeLLM())
    plan = await plan_improvement(
        turn=2,
        observations="[http_probe] OK",
        artifacts={"static/index.html": "x"},
        recent_thread="",
    )
    assert plan.agent_id == "marco"
    assert plan.file == "static/js/scene.js"
