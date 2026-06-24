"""CI / release gate for MemoryBench scores."""

from acme.config import settings
from acme.schemas import MemoryBenchResult


class BenchmarkGateError(Exception):
    """Raised when benchmark scores fall below configured thresholds."""


def check_memorybench_gate(
    result: MemoryBenchResult,
    *,
    min_overall: float | None = None,
    min_belief_quality: float | None = None,
    max_failures: int = 0,
) -> None:
    min_overall = settings.benchmark_min_overall if min_overall is None else min_overall
    min_belief = settings.benchmark_min_belief_quality if min_belief_quality is None else min_belief_quality
    failures = result.details.get("failures") or []

    if len(failures) > max_failures:
        raise BenchmarkGateError(
            f"MemoryBench failures ({len(failures)}): {failures}"
        )
    if result.overall_score < min_overall:
        raise BenchmarkGateError(
            f"overall_score {result.overall_score:.4f} < {min_overall}"
        )
    if result.belief_quality_score < min_belief:
        raise BenchmarkGateError(
            f"belief_quality_score {result.belief_quality_score:.4f} < {min_belief}"
        )
