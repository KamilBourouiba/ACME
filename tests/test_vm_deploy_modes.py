from acme.demo.vm_deploy import _payload_for_mode


def test_static_mode_payload():
    artifacts = {
        "static/index.html": "<html></html>",
        "static/css/base.css": "body{}",
        "server.py": "broken",
    }
    files, mode = _payload_for_mode(artifacts, "static")
    assert mode == "static"
    assert all(k.startswith("static/") for k in files)
    assert "server.py" not in files


def test_platform_mode_includes_pinned_stack():
    artifacts = {"static/index.html": "<html></html>"}
    files, mode = _payload_for_mode(artifacts, "platform")
    assert mode == "platform"
    assert "server.py" in files
    assert "static/index.html" in files
