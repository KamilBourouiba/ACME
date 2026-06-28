from acme.demo.site_guard import (
    DEPLOY_PINNED_FILES,
    is_protected_site_file,
    python_syntax_ok,
    reference_site_file,
    safe_site_artifact,
)


def test_server_py_is_protected():
    assert is_protected_site_file("server.py")
    assert "server.py" in DEPLOY_PINNED_FILES


def test_reference_server_has_no_http2_boot_trap():
    server = reference_site_file("server.py")
    assert server
    assert "http2=True" not in server
    assert "init_db" in server


def test_rejects_syntax_error_python():
    bad = "def foo(\n"
    good = reference_site_file("api/routes/intelligence.py")
    assert good
    assert not python_syntax_ok("api/routes/intelligence.py", bad)
    fixed = safe_site_artifact("api/routes/intelligence.py", bad, previous=good)
    assert fixed == good
