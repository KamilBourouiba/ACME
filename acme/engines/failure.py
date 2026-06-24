"""Failure engine — log and classify mistakes."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import FailureRecord
from acme.schemas import FailureType


class FailureEngine:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        failure_type: FailureType,
        description: str,
        session_id: UUID | None = None,
        predicted: str | None = None,
        actual: str | None = None,
        graph_refs: list[str] | None = None,
    ) -> FailureRecord:
        failure = FailureRecord(
            session_id=session_id,
            failure_type=failure_type.value,
            predicted=predicted,
            actual=actual,
            description=description,
            graph_refs=graph_refs or [],
        )
        self.session.add(failure)
        await self.session.flush()
        return failure

    @staticmethod
    def classify_outcome(outcome: str, has_prediction: bool) -> FailureType | None:
        if outcome.lower() in ("success", "succeeded", "ok"):
            return None
        if has_prediction:
            return FailureType.REASONING
        return FailureType.EXECUTION
