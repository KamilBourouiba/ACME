from acme.demo.artifacts import SITE_ARTIFACTS, load_site_artifacts
from acme.demo.preview import build_staging_preview


def test_staging_preview_lumen():
    arts = load_site_artifacts()
    html = build_staging_preview(arts)
    assert "Lumen" in html
    assert "Revenue clarity" in html
    assert "<style>" in html


def test_artifacts_impressive_stack():
    assert "static/index.html" in SITE_ARTIFACTS
    assert "static/css/dashboard-mock.css" in SITE_ARTIFACTS
    assert "static/js/pricing.js" in SITE_ARTIFACTS
    assert "api/routes/platform.py" in SITE_ARTIFACTS
    assert len(SITE_ARTIFACTS) >= 20
