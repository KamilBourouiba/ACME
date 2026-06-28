from acme.demo.artifacts import SITE_ARTIFACTS
from acme.demo.vm_deploy import _stack_files


def test_stack_files_erebor_architecture():
    files = _stack_files(dict(SITE_ARTIFACTS))
    assert "static/js/scene.js" in files
    assert "api/oss_clients.py" in files
    assert "api/routes/intelligence.py" in files
    assert len(files) >= 25
