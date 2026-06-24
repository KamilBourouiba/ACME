import pytest

from acme.evaluation.compare_mutex import (
    CompareAlreadyRunningError,
    compare_slot,
    is_compare_running,
    reset_compare_mutex_for_tests,
)
from acme.evaluation.comparison import _build_export


@pytest.fixture(autouse=True)
def _clear_mutex():
    reset_compare_mutex_for_tests()
    yield
    reset_compare_mutex_for_tests()


@pytest.mark.asyncio
async def test_compare_slot_blocks_concurrent_tenant():
    async with compare_slot("default"):
        assert is_compare_running("default")
        with pytest.raises(CompareAlreadyRunningError):
            async with compare_slot("default"):
                pass
    assert not is_compare_running("default")


@pytest.mark.asyncio
async def test_compare_slot_allows_different_tenants():
    async with compare_slot("tenant-a"):
        async with compare_slot("tenant-b"):
            assert is_compare_running("tenant-a")
            assert is_compare_running("tenant-b")


def test_build_export_benchmark_version_v3():
    export = _build_export(None, _fake_result(), _fake_result(), _fake_result(), _fake_result())
    assert export["benchmark_version"] == "v3"


def _fake_result():
    from acme.schemas import MemoryBenchResult

    return MemoryBenchResult(
        retention_score=1.0,
        feedback_correction_score=1.0,
        hallucination_resistance_score=1.0,
        belief_quality_score=0.7,
        overall_score=0.925,
        details={"benchmark_version": "v3", "scenarios_run": 13, "failures": []},
    )
