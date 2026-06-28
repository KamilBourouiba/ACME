from acme.demo.artifacts import SITE_ARTIFACTS, load_site_artifacts
from acme.demo.vm_deploy import _stack_files


def test_stack_files_include_full_architecture():
    files = _stack_files(dict(SITE_ARTIFACTS))
    assert "server.py" in files
    assert "static/index.html" in files
    assert "api/db.py" in files
    assert "docker-compose.yml" in files
    assert len(files) >= 15


def test_load_site_artifacts_has_backend():
    arts = load_site_artifacts()
    assert "api/routes/health.py" in arts
