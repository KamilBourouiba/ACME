from acme.demo.artifacts import SITE_ARTIFACTS
from acme.demo.vm_deploy import _stack_files


def test_stack_files_lumen_architecture():
    files = _stack_files(dict(SITE_ARTIFACTS))
    assert "static/css/hero.css" in files
    assert "static/css/dashboard-mock.css" in files
    assert "api/routes/platform.py" in files
    assert len(files) >= 20
