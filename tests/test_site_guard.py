from acme.demo.site_guard import (
    javascript_syntax_ok,
    is_pinned_static_file,
    python_syntax_ok,
    reference_site_file,
    safe_site_artifact,
)


def test_server_py_is_protected():
    from acme.demo.site_guard import DEPLOY_PINNED_FILES, is_protected_site_file

    assert is_protected_site_file("server.py")
    assert "server.py" in DEPLOY_PINNED_FILES


def test_pinned_static_js():
    assert is_pinned_static_file("static/js/app.js")
    assert is_pinned_static_file("static/js/api.js")


def test_rejects_broken_javascript():
    good = reference_site_file("static/js/app.js")
    assert good
    bad = "export default function() {\n"
    assert not javascript_syntax_ok("static/js/app.js", bad)
    fixed = safe_site_artifact("static/js/app.js", bad, previous=good)
    assert fixed == good


def test_rejects_syntax_error_python():
    bad = "def foo(\n"
    good = reference_site_file("api/routes/beliefs.py")
    assert good
    assert not python_syntax_ok("api/routes/beliefs.py", bad)
    fixed = safe_site_artifact("api/routes/beliefs.py", bad, previous=good)
    assert fixed == good
