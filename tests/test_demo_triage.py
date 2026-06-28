from acme.demo.agents import AGENT_BY_ID, DEMO_AGENTS
from acme.demo.improvement import _fallback_plan
from acme.demo.skills import SkillResult
from acme.demo.triage import (
    format_triage_report,
    is_spam_duplicate,
    message_fingerprint,
    normalize_message,
    should_dedup_agent,
)


def test_vera_agent_exists():
    assert "vera" in AGENT_BY_ID
    vera = AGENT_BY_ID["vera"]
    assert vera.name == "Vera"
    assert "ops" in vera.channels
    assert len(DEMO_AGENTS) == 11


def test_spam_dedup():
    a = normalize_message("GitHub Pages reachable — site live at https://example.com/foo")
    b = normalize_message("GitHub Pages reachable — site live at https://other.com/bar")
    assert a == b
    assert is_spam_duplicate(b, [a])
    assert should_dedup_agent("nina")
    assert not should_dedup_agent("vera")


def test_near_duplicate_skill_chatter():
    m1 = (
        "Validating nginx sensitive-file exposure on the VM by fetching "
        "/.git/config, /.env, /.htaccess before a hardening edit."
    )
    m2 = (
        "I'm validating the suspected nginx sensitive-file exposure directly on the live VM "
        "by fetching /.git/config, /.env, /docker-compose.yml, /nginx.conf."
    )
    fp1 = message_fingerprint(m1)
    fp2 = message_fingerprint(m2)
    assert fp1  # non-empty topic stem
    assert is_spam_duplicate(m2, [m1])


def test_fallback_routes_vm_failure_to_vera_remediate():
    plan = _fallback_plan(
        turn=1,
        observations="[http_probe] FAIL\n[receiver_probe] FAIL",
        artifacts={"static/index.html": "<html>"},
        failure_sig="http_probe|receiver_probe",
    )
    assert plan.agent_id == "vera"
    assert plan.action == "remediate"
    assert plan.channel == "ops"


def test_fallback_triage_every_fifth_turn():
    plan = _fallback_plan(
        turn=5,
        observations="[http_probe] FAIL",
        artifacts={"static/index.html": "<html>"},
        failure_sig="http_probe",
    )
    assert plan.action == "triage"


def test_triage_report_includes_failures():
    results = [
        SkillResult(skill="http_probe", ok=False, summary="health down", detail={}),
        SkillResult(skill="receiver_probe", ok=True, summary="ok", detail={}),
    ]
    report = format_triage_report(
        observations="[http_probe] FAIL",
        skill_results=results,
        deploy_block_reason="VM probes failing",
        signature="http_probe",
    )
    assert "Incident triage" in report
    assert "http_probe" in report
    assert "Deploy gate" in report
