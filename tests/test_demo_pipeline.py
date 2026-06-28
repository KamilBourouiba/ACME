from acme.config import settings


def test_pipeline_mode_defaults():
    assert settings.demo_pipeline_mode is True
    assert settings.demo_interval_sec == 0
    assert settings.demo_probe_refresh_sec >= 2
