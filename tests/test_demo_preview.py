from acme.demo.artifacts import SITE_ARTIFACTS, load_site_artifacts
from acme.demo.preview import build_staging_preview


def test_staging_preview_inlines_assets():
    arts = load_site_artifacts()
    html = build_staging_preview(arts)
    assert "Nexus Advisory" in html
    assert "<style>" in html
    assert "Clarity for complex transformations" in html


def test_artifacts_include_architecture():
    assert "static/index.html" in SITE_ARTIFACTS
    assert "api/routes/leads.py" in SITE_ARTIFACTS
    assert "ARCHITECTURE.md" in SITE_ARTIFACTS
    assert len(SITE_ARTIFACTS) >= 15
