from acme.demo.static_assets import github_pages_bundle, merge_static_bundle, normalize_static_asset_paths, vm_static_bundle


def test_normalize_strips_static_prefix():
    html = '<link rel="stylesheet" href="/static/css/base.css" />'
    fixed = normalize_static_asset_paths(html)
    assert 'href="css/base.css"' in fixed
    assert "/static/" not in fixed


def test_github_pages_pins_index_and_injects_api():
    broken = {
        "static/index.html": '<link rel="stylesheet" href="css/layout.css"><script src="js/app.js">',
        "static/js/app.js": "console.log('agent')",
    }
    pages = github_pages_bundle(broken)
    assert "layout.css" not in pages.get("index.html", "")
    assert "css/shell.css" in pages["index.html"]
    assert "EREBOR_DIRECT_OSS" in pages["index.html"]
    assert pages["js/app.js"] == "console.log('agent')"


def test_github_pages_bundle_has_css_at_root():
    artifacts = {
        "static/index.html": '<link rel="stylesheet" href="/static/css/base.css">',
    }
    pages = github_pages_bundle(artifacts)
    assert "index.html" in pages
    assert "css/base.css" in pages
    assert "/static/" not in pages["index.html"]
    assert pages["css/base.css"]


def test_merge_fills_missing_assets():
    merged = merge_static_bundle({"static/index.html": "<html></html>"})
    assert "static/css/base.css" in merged
    assert "static/js/app.js" in merged


def test_vm_static_bundle_pins_broken_index():
    broken = {
        "static/index.html": '<link rel="stylesheet" href="css/layout.css">',
        "static/js/app.js": "console.log('agent')",
    }
    vm = vm_static_bundle(broken)
    assert "layout.css" not in vm["static/index.html"]
    assert "css/shell.css" in vm["static/index.html"]
    assert vm["static/js/app.js"] == "console.log('agent')"
