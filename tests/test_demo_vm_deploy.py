from acme.demo.artifacts import load_site_artifacts


def test_stack_files_belief_observatory():
    files = load_site_artifacts()
    assert "static/js/app.js" in files
    assert "api/routes/beliefs.py" in files
    assert "static/css/observatory.css" in files
