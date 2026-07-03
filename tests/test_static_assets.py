from acme.demo.static_assets import github_pages_bundle, merge_static_bundle, normalize_static_asset_paths, vm_static_bundle


def test_normalize_strips_static_prefix():
    html = '<link rel="stylesheet" href="/static/css/observatory.css" />'
    fixed = normalize_static_asset_paths(html)
    assert 'href="css/observatory.css"' in fixed
    assert "/static/" not in fixed


def test_github_pages_pins_index_and_cache_busts_js():
    broken = {
        "static/index.html": '<link rel="stylesheet" href="css/layout.css"><script src="js/app.js">',
        "static/js/app.js": "console.log('agent')",
    }
    pages = github_pages_bundle(broken)
    assert "layout.css" not in pages.get("index.html", "")
    assert "css/observatory.css" in pages["index.html"]
    assert "js/app.js?v=" in pages["index.html"]
    assert "BeliefObsAPI" in pages["js/app.js"] or "loadTrace" in pages["js/app.js"]
    assert pages["js/app.js"] != "console.log('agent')"


def test_github_pages_bundle_has_css_at_root():
    artifacts = {
        "static/index.html": '<link rel="stylesheet" href="/static/css/observatory.css">',
    }
    pages = github_pages_bundle(artifacts)
    assert "index.html" in pages
    assert "css/observatory.css" in pages
    assert pages["css/observatory.css"]


def test_merge_fills_missing_assets():
    merged = merge_static_bundle({"static/index.html": "<html></html>"})
    assert "static/css/observatory.css" in merged
    assert "static/js/app.js" in merged


def test_publish_artifact_bundle_pins_js():
    from acme.demo.static_assets import publish_artifact_bundle

    broken = {
        "static/js/app.js": "console.log('agent')",
        "static/js/api.js": "export default {}",
        "static/css/observatory.css": "body { color: red; }",
    }
    bundle = publish_artifact_bundle(broken)
    assert "loadTrace" in bundle["static/js/app.js"]
    assert bundle["static/js/app.js"] != "console.log('agent')"
    assert bundle["static/css/observatory.css"] == "body { color: red; }"


def test_github_pages_force_pins_js():
    broken = {
        "static/js/app.js": "export default { broken: true }",
        "static/js/api.js": "export default {}",
    }
    pages = github_pages_bundle(broken)
    assert "loadTrace" in pages["js/app.js"]
    assert "export default" not in pages["js/app.js"]


def test_api_js_skips_vm_trace_on_github_pages():
    from pathlib import Path

    api = (Path(__file__).resolve().parents[1] / "acme/demo/site/static/js/api.js").read_text()
    assert "isGitHubPagesHost" in api
    assert 'bases.push("/api/trace")' in api
    assert "if (!isGitHubPagesHost())" in api


def test_vm_static_bundle_pins_broken_index():
    broken = {
        "static/index.html": '<link rel="stylesheet" href="css/layout.css">',
        "static/js/app.js": "console.log('agent')",
    }
    vm = vm_static_bundle(broken)
    assert "layout.css" not in vm["static/index.html"]
    assert "css/observatory.css" in vm["static/index.html"]
    assert "loadTrace" in vm["static/js/app.js"]
    assert vm["static/js/app.js"] != "console.log('agent')"
