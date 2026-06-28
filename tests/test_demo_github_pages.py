from acme.demo.github_pages import github_pages_files


def test_github_pages_flattens_static():
    files = github_pages_files(
        {
            "static/index.html": "<html></html>",
            "static/css/tokens.css": ":root{}",
            "api/server.py": "x",
            "README.md": "doc",
        }
    )
    assert "index.html" in files
    assert "css/tokens.css" in files
    assert "api/server.py" not in files
