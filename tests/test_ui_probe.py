import pytest

from acme.demo.improvement import _fallback_plan
from acme.demo.ui_probe import _fix_tasks_for_issues, format_ui_audit_message
from acme.demo.ui_probe import UiAuditReport


def test_fix_tasks_for_css_issues():
    tasks = _fix_tasks_for_issues(["Asset 404: css/layout.css"])
    agents = {t.agent_id for t in tasks}
    assert "priya" in agents


def test_format_ui_audit_message_includes_screenshots():
    report = UiAuditReport(
        ok=False,
        summary="[pages] UI audit FAIL",
        issues=["Missing selector"],
        screenshots={"pages-landing": b"png"},
        fix_tasks=[],
    )
    text = format_ui_audit_message(report)
    assert "pages-landing" in text
    assert "ui-screenshot" in text


def test_fallback_schedules_taylor_ui_audit():
    plan = _fallback_plan(
        turn=6,
        observations="[http_probe] OK",
        artifacts={"static/index.html": "<html></html>"},
        deploy_allowed=True,
    )
    assert plan.agent_id == "taylor"
    assert plan.action == "ui_audit"
    assert plan.channel == "qa"
