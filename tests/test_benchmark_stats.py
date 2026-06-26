"""Tests for benchmark statistics helpers."""

import pytest

from acme.evaluation.benchmark_stats import bootstrap_ci, pearson_r


def test_bootstrap_ci_bounds():
    mean, lo, hi = bootstrap_ci([0.8, 0.9, 1.0, 0.85, 0.95])
    assert lo <= mean <= hi
    assert 0.8 <= mean <= 1.0


def test_pearson_perfect_correlation():
    assert pearson_r([1.0, 0.5, 0.0], [1.0, 0.5, 0.0]) == pytest.approx(1.0)
