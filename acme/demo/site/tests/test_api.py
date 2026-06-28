"""Smoke tests for Lumen API."""

def test_features_configured():
    from api.config import FEATURES

    assert len(FEATURES) >= 6
    assert FEATURES[0]["title"]
