from pathlib import Path


def test_deploy_receiver_has_single_run_compose():
    src = Path("acme/demo/site/deploy_receiver.py").read_text(encoding="utf-8")
    assert src.count("def _run_compose") == 1
    assert "def _deploy_stack" in src
