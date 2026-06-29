import pytest

from acme.demo.vm_exec import REMEDIATION_RECIPES, pick_remediation_recipe, validate_command


def test_validate_allows_local_curl():
    ok, _ = validate_command("curl -sk https://127.0.0.1/api/health")
    assert ok


def test_validate_blocks_shell_injection():
    ok, reason = validate_command("curl -sk https://127.0.0.1/api/health; rm -rf /")
    assert not ok
    assert "metacharacters" in reason


def test_validate_blocks_external_curl():
    ok, reason = validate_command("curl -sk https://evil.com/")
    assert not ok
    assert "localhost" in reason


def test_validate_allows_docker_compose():
    ok, _ = validate_command(
        "docker-compose -f /opt/nexus-site/docker-compose.yml ps"
    )
    assert ok


def test_remediation_uses_docker_compose_binary():
    assert "docker-compose -f" in REMEDIATION_RECIPES["compose_restart"]
    assert "docker compose -f" not in REMEDIATION_RECIPES["compose_restart"]


def test_pick_recipe_rotates():
    a = pick_remediation_recipe(signature="http_probe|http_search", attempt=0)
    b = pick_remediation_recipe(signature="http_probe|http_search", attempt=1)
    assert a != b
    assert a in REMEDIATION_RECIPES


@pytest.mark.asyncio
async def test_exec_on_vm_not_configured():
    from acme.demo.vm_exec import exec_on_vm

    result = await exec_on_vm("curl -sf http://127.0.0.1:9090/health", vm_url="", deploy_key="")
    assert result["ok"] is False
