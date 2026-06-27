from acme.demo.preview import build_staging_preview
from acme.demo.agents import SITE_ARTIFACTS


def test_staging_preview_inlines_assets():
    html = build_staging_preview(dict(SITE_ARTIFACTS))
    assert "Nexus Advisory" in html
    assert "<style>" in html
    assert "<script>" in html
    assert 'href="styles.css"' not in html
