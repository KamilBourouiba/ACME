"""Event store — append-only log driving all memory projections."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import EventRecord


class EventStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, event_type: str, payload: dict[str, Any]) -> UUID:
        event = EventRecord(event_type=event_type, payload=payload)
        self.session.add(event)
        await self.session.flush()
        return event.id

    async def list_recent(self, event_type: str | None = None, limit: int = 50) -> list[EventRecord]:
        from sqlalchemy import select

        stmt = select(EventRecord).order_by(EventRecord.created_at.desc()).limit(limit)
        if event_type:
            stmt = stmt.where(EventRecord.event_type == event_type)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
