"""Prediction engine — hypothesis → prediction → validation → belief."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import BeliefRecord, HypothesisRecord, PredictionRecord
from acme.engines.belief import BeliefEngine
from acme.engines.meta_learning import MetaLearningEngine
from acme.schemas import PredictionCreate, PredictionResponse, PredictionValidate


class PredictionEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.beliefs = BeliefEngine(session)
        self.meta = MetaLearningEngine(session)

    async def create(self, data: PredictionCreate) -> PredictionResponse:
        record = PredictionRecord(
            hypothesis_id=data.hypothesis_id,
            belief_graph_id=data.belief_graph_id,
            statement=data.statement,
            expected_outcome=data.expected_outcome,
            horizon_days=data.horizon_days,
            status="pending",
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.commit()
        return self._to_response(record)

    async def validate(self, data: PredictionValidate) -> PredictionResponse:
        stmt = select(PredictionRecord).where(PredictionRecord.id == data.prediction_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if record is None:
            raise ValueError(f"Prediction {data.prediction_id} not found")

        record.actual_outcome = data.actual_outcome
        record.success = data.success
        record.validated = True
        record.status = "validated"
        record.validated_at = datetime.now(timezone.utc)

        if record.belief_graph_id:
            belief = await self.beliefs._get_by_graph_id(record.belief_graph_id)
            if belief:
                if data.success:
                    belief.prediction_successes += 1
                    belief.supporting_evidence += 1
                    belief.confidence = min(1.0, belief.confidence + 0.05)
                else:
                    belief.prediction_failures += 1
                    belief.contradicting_evidence += 1
                    belief.confidence = max(0.0, belief.confidence - 0.1)
                await self.beliefs._apply_lifecycle(belief)
                belief.crs = BeliefEngine.compute_crs(belief)

        if record.hypothesis_id and data.success:
            stmt_h = select(HypothesisRecord).where(HypothesisRecord.id == record.hypothesis_id)
            hyp = (await self.session.execute(stmt_h)).scalar_one_or_none()
            if hyp:
                hyp.status = "validated"

        await self.meta.record("prediction_success_rate", 1.0 if data.success else 0.0)
        await self.session.commit()
        return self._to_response(record)

    async def list_predictions(self, limit: int = 50) -> list[PredictionResponse]:
        stmt = (
            select(PredictionRecord)
            .order_by(PredictionRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._to_response(r) for r in result.scalars().all()]

    @staticmethod
    def _to_response(record: PredictionRecord) -> PredictionResponse:
        return PredictionResponse(
            id=record.id,
            statement=record.statement,
            expected_outcome=record.expected_outcome,
            actual_outcome=record.actual_outcome,
            status=record.status,
            validated=record.validated,
            success=record.success,
            created_at=record.created_at,
        )
