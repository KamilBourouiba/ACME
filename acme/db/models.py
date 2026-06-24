import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class EventRecord(Base):
    """Immutable event log — single source of truth for memory updates."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class Episode(Base):
    """Episodic memory — raw experiences."""

    __tablename__ = "episodes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str | None] = mapped_column(String(256))
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    source_type: Mapped[str] = mapped_column(String(32), default="user", index=True)
    source_id: Mapped[str | None] = mapped_column(String(256), index=True)
    source_credibility: Mapped[float] = mapped_column(Float, default=0.75)
    cognitive_profile: Mapped[str] = mapped_column(String(32), default="factual", index=True)
    embedding: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)
    memory_tier: Mapped[str] = mapped_column(String(16), default="hot", index=True)
    importance_score: Mapped[float] = mapped_column(Float, default=1.0)
    access_count: Mapped[int] = mapped_column(Integer, default=0)
    last_accessed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_content: Mapped[str | None] = mapped_column(Text)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tier_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class QuerySession(Base):
    """Tracks a reasoning session for outcome feedback."""

    __tablename__ = "query_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    graph_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    outcome: Mapped[str | None] = mapped_column(String(32))
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class FailureRecord(Base):
    """Failure engine — predictions, mistakes, bad assumptions."""

    __tablename__ = "failures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    failure_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    predicted: Mapped[str | None] = mapped_column(Text)
    actual: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    graph_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class BeliefRecord(Base):
    """Belief engine — confidence tracking outside the graph."""

    __tablename__ = "beliefs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    graph_id: Mapped[str] = mapped_column(String(256), unique=True, index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    knowledge_type: Mapped[str] = mapped_column(String(32), default="hypothesis", index=True)
    status: Mapped[str] = mapped_column(String(32), default="hypothesis", index=True)
    cognitive_profile: Mapped[str] = mapped_column(String(32), default="factual")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    crs: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    supporting_evidence: Mapped[int] = mapped_column(Integer, default=0)
    contradicting_evidence: Mapped[int] = mapped_column(Integer, default=0)
    strong_contradictions: Mapped[int] = mapped_column(Integer, default=0)
    independent_source_count: Mapped[int] = mapped_column(Integer, default=0)
    source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    prediction_successes: Mapped[int] = mapped_column(Integer, default=0)
    prediction_failures: Mapped[int] = mapped_column(Integer, default=0)
    time_windows: Mapped[int] = mapped_column(Integer, default=1)
    last_reinforced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AbstractionRecord(Base):
    """Compression engine — distilled patterns from episode clusters."""

    __tablename__ = "abstractions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    pattern: Mapped[str] = mapped_column(String(256), index=True, nullable=False)
    source_episode_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    episode_count: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[float] = mapped_column(Float, default=0.5, index=True)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class HypothesisRecord(Base):
    """Autonomous learning — self-generated testable hypotheses."""

    __tablename__ = "hypotheses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cycle_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    testable_prediction: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    source_refs: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class LearningCycleRecord(Base):
    """Tracks autonomous learning / consolidation runs."""

    __tablename__ = "learning_cycles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    hypotheses_generated: Mapped[int] = mapped_column(Integer, default=0)
    abstractions_created: Mapped[int] = mapped_column(Integer, default=0)
    episodes_compressed: Mapped[int] = mapped_column(Integer, default=0)
    beliefs_promoted: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PredictionRecord(Base):
    """Testable predictions linked to hypotheses or beliefs."""

    __tablename__ = "predictions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hypothesis_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    belief_graph_id: Mapped[str | None] = mapped_column(String(256), index=True)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    expected_outcome: Mapped[str] = mapped_column(Text, nullable=False)
    actual_outcome: Mapped[str | None] = mapped_column(Text)
    horizon_days: Mapped[int] = mapped_column(Integer, default=30)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    success: Mapped[bool | None] = mapped_column()
    validated: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MetaLearningRecord(Base):
    """Tracks what ACME learns about its own learning process."""

    __tablename__ = "meta_learning"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, default=0.0)
    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BenchmarkRunRecord(Base):
    """Persisted MemoryBench / compare run results."""

    __tablename__ = "benchmark_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    version: Mapped[str] = mapped_column(String(32), default="0.1.0")
    revision: Mapped[str | None] = mapped_column(String(64))
    overall_score: Mapped[float] = mapped_column(Float, default=0.0, index=True)
    retention_score: Mapped[float] = mapped_column(Float, default=0.0)
    feedback_score: Mapped[float] = mapped_column(Float, default=0.0)
    groundedness_score: Mapped[float] = mapped_column(Float, default=0.0)
    belief_quality_score: Mapped[float] = mapped_column(Float, default=0.0)
    scenarios_run: Mapped[int] = mapped_column(Integer, default=0)
    failures: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
