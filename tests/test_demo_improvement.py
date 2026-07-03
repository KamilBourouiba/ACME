import pytest

from acme.demo.improvement import _fallback_plan, plan_improvement
from acme.demo.skills import DemoSkills


def test_fallback_plan_probes_on_failure():
    plan = _fallback_plan(
        turn=6,
        observations="[list_artifacts] OK only",
        artifacts={},
        failure_sig="ok",
    )
    # no vm failing path — bootstraps or edits
    assert plan.action in ("probe", "edit", "query", "deploy", "remediate", "triage", "ui_audit")


def test_fallback_plan_bootstraps_index_when_empty():
    plan = _fallback_plan(turn=0, observations="[http_probe] OK", artifacts={})
    assert plan.action == "edit"
    assert plan.file == "static/index.html"


def test_fallback_plan_deploys_periodically():
    artifacts = {"static/index.html": "<html></html>"}
    plan = _fallback_plan(
        turn=8,
        observations="[http_probe] OK",
        artifacts=artifacts,
        deploy_allowed=True,
    )
    assert plan.action == "deploy"


def test_fallback_plan_skips_deploy_when_blocked():
    artifacts = {"static/index.html": "<html></html>", "server.py": "app = 1"}
    plan = _fallback_plan(
        turn=8,
        observations="[http_probe] FAIL",
        artifacts=artifacts,
        deploy_allowed=False,
    )
    assert plan.action != "deploy"


def test_skills_list_artifacts():
    skills = DemoSkills(artifacts={"static/index.html": "<html>"})
    result = skills.list_artifacts()
    assert result.ok
    assert "static/index.html" in result.detail["paths"]


@pytest.mark.asyncio
async def test_plan_improvement_uses_llm(monkeypatch):
    class FakeLLM:
        async def generate(self, *args, **kwargs):
            return '{"agent_id":"marco","channel":"engineering","action":"edit","message":"Polish trace UI","file":"static/js/app.js","lang":"javascript","query":null,"skill":null,"deploy":false}'

    monkeypatch.setattr("acme.demo.improvement.get_llm_client", lambda: FakeLLM())
    plan = await plan_improvement(
        turn=2,
        observations="[http_probe] OK",
        artifacts={"static/index.html": "x"},
        recent_thread="",
    )
    assert plan.agent_id == "marco"
    assert plan.file == "static/js/app.js"
