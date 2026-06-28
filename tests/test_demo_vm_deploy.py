from acme.demo.agents import SITE_ARTIFACTS
from acme.demo.vm_deploy import _stack_files


def test_stack_files_include_backend():
    files = _stack_files(dict(SITE_ARTIFACTS))
    assert "server.py" in files
    assert "docker-compose.yml" in files
    assert "index.html" in files
    assert "asyncpg" in files["requirements.txt"]
