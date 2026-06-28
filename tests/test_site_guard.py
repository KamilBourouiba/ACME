from acme.demo.site_guard import PROTECTED_SITE_FILES, is_protected_site_file, reference_site_files


def test_server_py_is_protected():
    assert is_protected_site_file("server.py")
    assert "server.py" in PROTECTED_SITE_FILES


def test_reference_server_has_no_http2_boot_trap():
    refs = reference_site_files()
    server = refs["server.py"]
    assert "http2=True" not in server
    assert "init_db" in server
