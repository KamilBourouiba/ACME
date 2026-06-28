from acme.demo.static_assets import github_pages_bundle, merge_static_bundle, normalize_static_asset_paths


def test_normalize_strips_static_prefix():
    html = '<link rel="stylesheet" href="/static/css/base.css" />'
    fixed = normalize_static_asset_paths(html)
    assert 'href="css/base.css"' in fixed
    assert "/static/" not in fixed


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
