import pytest

from acme.evaluation.benchmark_gate import BenchmarkGateError, check_memorybench_gate
from acme.schemas import MemoryBenchResult


def _result(**kwargs) -> MemoryBenchResult:
    defaults = {
        "retention_score": 0.95,
        "feedback_correction_score": 1.0,
        "hallucination_resistance_score": 1.0,
        "belief_quality_score": 0.65,
        "overall_score": 0.90,
        "details": {"failures": [], "scenarios_run": 13},
    }
    defaults.update(kwargs)
    return MemoryBenchResult(**defaults)


def test_gate_passes_good_scores():
    check_memorybench_gate(_result(), min_overall=0.85, min_belief_quality=0.55)


def test_gate_fails_low_overall():
    with pytest.raises(BenchmarkGateError, match="overall_score"):
        check_memorybench_gate(_result(overall_score=0.5), min_overall=0.85)


def test_gate_fails_scenario_failures():
    with pytest.raises(BenchmarkGateError, match="failures"):
        check_memorybench_gate(
            _result(details={"failures": ["scenario_a"], "scenarios_run": 13}),
        )


def test_gate_fails_low_belief_quality():
    with pytest.raises(BenchmarkGateError, match="belief_quality"):
        check_memorybench_gate(_result(belief_quality_score=0.3), min_belief_quality=0.55)
