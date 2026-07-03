from acme.demo.preview import build_staging_preview
from acme.demo.static_assets import reference_static_files


def test_staging_preview_belief_observatory():
    arts = reference_static_files()
    html = build_staging_preview(arts)
    assert "Belief Observatory" in html
    assert "belief-svg" in html
    assert "observatory" in html.lower()
