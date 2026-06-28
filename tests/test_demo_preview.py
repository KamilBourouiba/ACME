from acme.demo.preview import build_staging_preview
from acme.demo.artifacts import load_site_artifacts


def test_staging_preview_erebor():
    arts = load_site_artifacts()
    html = build_staging_preview(arts)
    assert "Erebor" in html
    assert "erebor-canvas" in html
    assert "importmap" in html or "three" in html
