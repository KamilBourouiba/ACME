from acme.engines.failure import FailureEngine
from acme.schemas import FailureType


def test_classify_success():
    assert FailureEngine.classify_outcome("success", has_prediction=True) is None


def test_classify_reasoning_failure():
    assert FailureEngine.classify_outcome("failed", has_prediction=True) == FailureType.REASONING


def test_classify_execution_failure():
    assert FailureEngine.classify_outcome("failed", has_prediction=False) == FailureType.EXECUTION
