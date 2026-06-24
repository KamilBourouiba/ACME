import pytest

from acme.config import settings
from acme.db.models import BeliefRecord
from acme.engines.belief import BeliefEngine
from acme.schemas import BeliefStatus, KnowledgeType


def _belief(**kwargs) -> BeliefRecord:
    defaults = {
        "graph_id": "rel:test",
        "label": "A correlates B",
        "knowledge_type": KnowledgeType.HYPOTHESIS.value,
        "status": BeliefStatus.HYPOTHESIS.value,
        "confidence": 0.6,
        "supporting_evidence": 0,
        "contradicting_evidence": 0,
        "strong_contradictions": 0,
        "independent_source_count": 0,
        "prediction_successes": 0,
        "prediction_failures": 0,
        "time_windows": 1,
    }
    defaults.update(kwargs)
    return BeliefRecord(**defaults)


def test_compute_crs_balanced():
    belief = _belief(
        supporting_evidence=5,
        contradicting_evidence=1,
        independent_source_count=3,
        prediction_successes=3,
        prediction_failures=1,
        time_windows=2,
    )
    crs = BeliefEngine.compute_crs(belief)
    assert 0.0 <= crs <= 1.0
    assert crs > 0.5


@pytest.mark.asyncio
async def test_belief_demotion_on_contradictions():
    engine = BeliefEngine(session=None)  # type: ignore[arg-type]
    belief = _belief(
        status=BeliefStatus.BELIEF.value,
        knowledge_type=KnowledgeType.BELIEF.value,
        supporting_evidence=10,
        contradicting_evidence=settings.belief_demote_contradictions - 1,
    )
    belief.contradicting_evidence += 1
    await engine._apply_lifecycle(belief)
    assert belief.status == BeliefStatus.DEPRECATED.value


@pytest.mark.asyncio
async def test_belief_archived_after_many_contradictions():
    engine = BeliefEngine(session=None)  # type: ignore[arg-type]
    belief = _belief(
        contradicting_evidence=settings.belief_archive_contradictions,
        supporting_evidence=2,
    )
    await engine._apply_lifecycle(belief)
    assert belief.status == BeliefStatus.ARCHIVED.value
    assert belief.confidence <= 0.1


@pytest.mark.asyncio
async def test_belief_challenged_on_strong_contradiction():
    engine = BeliefEngine(session=None)  # type: ignore[arg-type]
    belief = _belief(
        status=BeliefStatus.BELIEF.value,
        knowledge_type=KnowledgeType.BELIEF.value,
        strong_contradictions=1,
        contradicting_evidence=1,
    )
    await engine._apply_lifecycle(belief)
    assert belief.status in (
        BeliefStatus.CHALLENGED.value,
        BeliefStatus.DEPRECATED.value,
        BeliefStatus.ARCHIVED.value,
    )
