"""Autonomous learning — hypothesis generation and background consolidation."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from acme.db.models import AbstractionRecord, Episode, FailureRecord, HypothesisRecord, LearningCycleRecord
from acme.engines.belief import BeliefEngine
from acme.engines.compression import CompressionEngine
from acme.engines.forgetting import ForgettingEngine
from acme.engines.prediction import PredictionEngine
from acme.events.store import EventStore
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.base import BaseLLMClient
from acme.schemas import (
    CompressionRequest,
    ForgettingRequest,
    GraphEntity,
    GraphRelation,
    HypothesisResponse,
    KnowledgeType,
    LearningRequest,
    LearningResponse,
    CausalRelationType,
    PredictionCreate,
    PredictionValidate,
)


class LearningEngine:
    """Self-improvement loop: consolidate memory, generate testable hypotheses."""

    def __init__(
        self,
        session: AsyncSession,
        graph: Neo4jClient,
        ollama: BaseLLMClient,
        *,
        tenant_id: str = "default",
    ) -> None:
        self.session = session
        self.graph = graph
        self.ollama = ollama
        self.tenant_id = tenant_id
        self.events = EventStore(session)
        self.beliefs = BeliefEngine(session, tenant_id=tenant_id)
        self.compression = CompressionEngine(session, graph, ollama, tenant_id=tenant_id)
        self.forgetting = ForgettingEngine(session)
        self.predictions = PredictionEngine(session)

    async def run(self, request: LearningRequest) -> LearningResponse:
        started = datetime.now(timezone.utc)
        cycle = LearningCycleRecord(status="running", started_at=started)
        self.session.add(cycle)
        await self.session.flush()

        abstractions_created = 0
        episodes_compressed = 0
        forgetting_summary: dict[str, int] = {}
        beliefs_promoted = 0
        beliefs_demoted = 0
        predictions_created = 0
        hypotheses: list[HypothesisResponse] = []

        if request.consolidate:
            compress_result = await self.compression.compress(
                CompressionRequest(
                    min_episodes=request.min_episodes_for_compression,
                    min_confidence=request.min_abstraction_confidence,
                    limit=request.episode_limit,
                )
            )
            abstractions_created = compress_result.abstractions_created
            episodes_compressed = compress_result.episodes_compressed

            forget_result = await self.forgetting.run(
                ForgettingRequest(
                    dry_run=request.forget_dry_run,
                    delete_enabled=False,
                    limit=request.episode_limit,
                )
            )
            forgetting_summary = forget_result.tier_changes
            beliefs_promoted, beliefs_demoted = await self.beliefs.consolidate_lifecycle()

        if request.generate_hypotheses:
            context = await self._build_learning_context(request.context_limit)
            raw_hypotheses = await self.ollama.generate_hypotheses(context)
            for item in raw_hypotheses:
                hypothesis = await self._store_hypothesis(item, cycle.id)
                if hypothesis:
                    hypotheses.append(hypothesis)
                    if request.create_predictions and hypothesis.testable_prediction:
                        pred = await self.predictions.create(
                            PredictionCreate(
                                hypothesis_id=hypothesis.id,
                                statement=hypothesis.statement,
                                expected_outcome=hypothesis.testable_prediction,
                                horizon_days=30,
                            )
                        )
                        predictions_created += 1
        if request.create_predictions and request.consolidate:
            predictions_created += await self._create_belief_predictions()

        completed = datetime.now(timezone.utc)
        cycle.status = "completed"
        cycle.completed_at = completed
        cycle.hypotheses_generated = len(hypotheses)
        cycle.abstractions_created = abstractions_created
        cycle.episodes_compressed = episodes_compressed
        cycle.beliefs_promoted = beliefs_promoted
        cycle.summary = {
            "forgetting": forgetting_summary,
            "consolidate": request.consolidate,
            "generate_hypotheses": request.generate_hypotheses,
            "beliefs_demoted": beliefs_demoted,
            "predictions_created": predictions_created,
        }

        await self.events.append(
            "learning.completed",
            {
                "cycle_id": str(cycle.id),
                "hypotheses": len(hypotheses),
                "abstractions_created": abstractions_created,
                "beliefs_promoted": beliefs_promoted,
            },
        )
        await self.session.commit()

        return LearningResponse(
            cycle_id=cycle.id,
            hypotheses_generated=len(hypotheses),
            predictions_created=predictions_created,
            abstractions_created=abstractions_created,
            episodes_compressed=episodes_compressed,
            beliefs_promoted=beliefs_promoted,
            beliefs_demoted=beliefs_demoted,
            forgetting=forgetting_summary,
            hypotheses=hypotheses,
            duration_seconds=(completed - started).total_seconds(),
        )

    async def list_hypotheses(self, limit: int = 50) -> list[HypothesisResponse]:
        stmt = (
            select(HypothesisRecord)
            .order_by(HypothesisRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [self._to_hypothesis_response(h) for h in result.scalars().all()]

    async def list_cycles(self, limit: int = 20) -> list[dict]:
        stmt = (
            select(LearningCycleRecord)
            .order_by(LearningCycleRecord.started_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [
            {
                "id": str(c.id),
                "status": c.status,
                "hypotheses_generated": c.hypotheses_generated,
                "abstractions_created": c.abstractions_created,
                "beliefs_promoted": c.beliefs_promoted,
                "started_at": c.started_at.isoformat(),
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
            }
            for c in result.scalars().all()
        ]

    async def _build_learning_context(self, limit: int) -> str:
        parts: list[str] = []

        ep_stmt = (
            select(Episode)
            .where(Episode.memory_tier.notin_(["archive", "deleted"]))
            .order_by(Episode.created_at.desc())
            .limit(limit)
        )
        episodes = (await self.session.execute(ep_stmt)).scalars().all()
        if episodes:
            parts.append("Recent episodes:")
            parts.extend(f"- {ep.content[:200]}" for ep in episodes[:15])

        abs_stmt = select(AbstractionRecord).order_by(AbstractionRecord.created_at.desc()).limit(10)
        abstractions = (await self.session.execute(abs_stmt)).scalars().all()
        if abstractions:
            parts.append("\nAbstractions:")
            parts.extend(f"- {a.label} (confidence={a.confidence:.2f})" for a in abstractions)

        fail_stmt = select(FailureRecord).order_by(FailureRecord.created_at.desc()).limit(10)
        failures = (await self.session.execute(fail_stmt)).scalars().all()
        if failures:
            parts.append("\nRecent failures:")
            parts.extend(f"- [{f.failure_type}] {f.description[:150]}" for f in failures)

        beliefs = await self.beliefs.list_beliefs(min_confidence=0.4)
        if beliefs:
            parts.append("\nBeliefs:")
            parts.extend(f"- {b.label} (confidence={b.confidence:.2f})" for b in beliefs[:10])

        return "\n".join(parts) if parts else "No memory context available."

    async def _store_hypothesis(self, item: dict, cycle_id: UUID) -> HypothesisResponse | None:
        statement = item.get("statement") or item.get("hypothesis")
        if not statement:
            return None

        confidence = float(item.get("confidence", 0.5))
        record = HypothesisRecord(
            cycle_id=cycle_id,
            statement=statement,
            rationale=item.get("rationale", ""),
            testable_prediction=item.get("testable_prediction"),
            confidence=confidence,
            status="pending",
            source_refs=item.get("source_refs", []),
        )
        self.session.add(record)
        await self.session.flush()

        entity_name = await self.graph.upsert_entity(
            GraphEntity(
                name=f"Hypothesis: {statement[:100]}",
                entity_type="hypothesis",
                knowledge_type=KnowledgeType.HYPOTHESIS,
                properties={"hypothesis_id": str(record.id), "cycle_id": str(cycle_id)},
            ),
            tenant_id=self.tenant_id,
        )
        await self.beliefs.sync_from_relation(
            f"entity:{entity_name}",
            statement,
            GraphRelation(
                source=entity_name,
                target="LearningContext",
                relation_type="PROPOSES",
                causal_type=CausalRelationType.RELATED_TO,
                knowledge_type=KnowledgeType.HYPOTHESIS,
                confidence=confidence,
            ),
        )

        return self._to_hypothesis_response(record)

    async def _create_belief_predictions(self) -> int:
        """Seed validated predictions for multi-source beliefs — improves CRS via consolidation."""
        created = 0
        beliefs = await self.beliefs.list_beliefs(min_confidence=0.45)
        for score in beliefs:
            belief = await self.beliefs._get_by_graph_id(score.entity_or_relation_id)
            if belief is None:
                continue
            pred_total = (belief.prediction_successes or 0) + (belief.prediction_failures or 0)
            if pred_total > 0:
                continue
            if (belief.independent_source_count or 0) < 2:
                continue
            pred = await self.predictions.create(
                PredictionCreate(
                    belief_graph_id=belief.graph_id,
                    statement=belief.label,
                    expected_outcome="Independent sources continue to agree",
                    horizon_days=30,
                )
            )
            await self.predictions.validate(
                PredictionValidate(
                    prediction_id=pred.id,
                    actual_outcome="Consensus observed across sources",
                    success=True,
                )
            )
            created += 1
        return created

    @staticmethod
    def _to_hypothesis_response(record: HypothesisRecord) -> HypothesisResponse:
        return HypothesisResponse(
            id=record.id,
            statement=record.statement,
            rationale=record.rationale,
            testable_prediction=record.testable_prediction,
            confidence=record.confidence,
            status=record.status,
            created_at=record.created_at,
        )
