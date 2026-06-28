"""ACME orchestrator — self-improvement loop entry point."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from acme.config import settings
from acme.db.models import Episode, QuerySession
from acme.engines.belief import BeliefEngine
from acme.engines.causal import CausalEngine
from acme.engines.compression import CompressionEngine
from acme.engines.deterministic import infer_cognitive_profile, source_credibility
from acme.engines.extraction import merge_extractions
from acme.engines.deterministic import rule_based_extraction
from acme.engines.failure import FailureEngine
from acme.engines.forgetting import ForgettingEngine
from acme.engines.hybrid_retrieval import HybridRetrievalEngine
from acme.engines.learning import LearningEngine
from acme.engines.meta_learning import MetaLearningEngine
from acme.engines.prediction import PredictionEngine
from acme.engines.retrieval import RetrievalEngine
from acme.engines.vector_retrieval import VectorRetrievalEngine
from acme.events.store import EventStore
from acme.evaluation.sandbox import BENCHMARK_TAG
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.base import BaseLLMClient
from acme.llm.embeddings import EmbeddingClient
from acme.schemas import (
    BenchmarkComparisonResult,
    CausalValidateRequest,
    CausalValidateResponse,
    CompressionRequest,
    CompressionResponse,
    ConsolidationResponse,
    ContradictionRequest,
    ExperienceCreate,
    ExperienceResponse,
    FeedbackRequest,
    FeedbackResponse,
    ForgettingRequest,
    ForgettingResponse,
    LearningRequest,
    LearningResponse,
    PredictionCreate,
    PredictionResponse,
    PredictionValidate,
    QueryRequest,
    QueryResponse,
)


class ACMEOrchestrator:
    """Coordinates episodic memory, graph, belief, and failure engines."""

    def __init__(
        self,
        session: AsyncSession,
        graph: Neo4jClient,
        ollama: BaseLLMClient,
        *,
        tenant_id: str | None = None,
    ) -> None:
        self.session = session
        self.graph = graph
        self.ollama = ollama
        self.tenant_id = tenant_id or settings.default_tenant_id
        self.events = EventStore(session)
        self.beliefs = BeliefEngine(session, tenant_id=self.tenant_id)
        self.compression = CompressionEngine(session, graph, ollama, tenant_id=self.tenant_id)
        self.forgetting = ForgettingEngine(session)
        self.learning = LearningEngine(session, graph, ollama, tenant_id=self.tenant_id)
        self.predictions = PredictionEngine(session)
        self.meta = MetaLearningEngine(session)
        self.failures = FailureEngine(session)
        self.embedder = EmbeddingClient()
        self.vector = VectorRetrievalEngine(session, self.embedder)
        if settings.hybrid_retrieval_enabled:
            self.retrieval = HybridRetrievalEngine(
                graph, session, self.embedder, tenant_id=self.tenant_id
            )
        else:
            self.retrieval = RetrievalEngine(graph, tenant_id=self.tenant_id)
        self.causal = CausalEngine(session, graph)

    async def ingest_experience(self, data: ExperienceCreate) -> ExperienceResponse:
        profile = data.cognitive_profile or infer_cognitive_profile(data.content, data.tags)
        credibility = data.source_credibility or source_credibility(data.source_type)
        tenant_id = data.tenant_id or self.tenant_id

        episode = Episode(
            content=data.content,
            action=data.action,
            context=data.context,
            tags=data.tags,
            source_type=data.source_type.value,
            source_id=data.source_id,
            source_credibility=credibility,
            cognitive_profile=profile.value,
            tenant_id=tenant_id,
        )
        self.session.add(episode)
        await self.session.flush()
        await self.vector.embed_episode(episode)

        if settings.ablation_disable_vector:
            episode.embedding = None

        await self.events.append(
            "experience.ingested",
            {
                "episode_id": str(episode.id),
                "action": data.action,
                "tags": data.tags,
                "source_type": data.source_type.value,
                "cognitive_profile": profile.value,
            },
        )

        llm_extraction = await self.ollama.extract_knowledge(data.content, data.action)
        rule_extraction = rule_based_extraction(data.content, data.action)
        extraction = merge_extractions(llm_extraction, rule_extraction)

        from acme.evaluation.sandbox import LONGMEMEVAL_TAG

        if LONGMEMEVAL_TAG in data.tags:
            benchmark_tag = LONGMEMEVAL_TAG
        elif BENCHMARK_TAG in data.tags:
            benchmark_tag = BENCHMARK_TAG
        else:
            benchmark_tag = None
        entity_refs, relation_refs = await self.graph.apply_extraction(
            extraction.entities,
            extraction.relations,
            tenant_id=tenant_id,
            benchmark_tag=benchmark_tag,
        )

        if not settings.ablation_disable_belief_sync:
            for relation, graph_id in relation_refs:
                await self.beliefs.sync_from_relation(
                    graph_id,
                    f"{relation.source} -[{relation.causal_type.value}]-> {relation.target}",
                    relation,
                    source_id=data.source_id,
                    source_credibility=credibility,
                    cognitive_profile=profile.value,
                    tenant_id=tenant_id,
                )

        await self.events.append(
            "knowledge.extracted",
            {
                "episode_id": str(episode.id),
                "entities": len(extraction.entities),
                "relations": len(extraction.relations),
                "summary": extraction.summary,
            },
        )

        await self.session.commit()

        return ExperienceResponse(
            id=episode.id,
            content=episode.content,
            action=episode.action,
            context=episode.context,
            tags=episode.tags,
            source_type=data.source_type,
            source_id=data.source_id,
            cognitive_profile=profile,
            created_at=episode.created_at,
        )

    async def query(self, data: QueryRequest) -> QueryResponse:
        belief_scores = await self.beliefs.list_beliefs(min_confidence=0.3)
        demo_mode = self.tenant_id.startswith("demo-erebor") or self.tenant_id.startswith(("demo-lumen", "demo-nexus"))
        memory_context, entities = await self.retrieval.build_context(
            data.question, belief_scores, demo_mode=demo_mode
        )

        result = await self.ollama.reason(
            question=data.question,
            memory_context=memory_context,
            extra_context=data.context,
        )

        contrarian_view = None
        run_contrarian = (data.challenge or result["confidence"] >= 0.8) and not settings.ablation_disable_contrarian
        if run_contrarian and not demo_mode:
            contrarian_view = await self.ollama.contrarian_check(result["answer"], memory_context)

        query_session = QuerySession(
            question=data.question,
            answer=str(result["answer"]),
            confidence=float(result["confidence"]),
            reasoning=str(result.get("reasoning", "")),
            graph_refs=[str(ref) for ref in entities],
            tenant_id=self.tenant_id,
        )
        self.session.add(query_session)
        await self.session.flush()

        await self.events.append(
            "query.answered",
            {
                "session_id": str(query_session.id),
                "confidence": result["confidence"],
                "entities": entities,
            },
        )
        await self.session.commit()

        belief_limit = 0 if self.tenant_id.startswith(("demo-erebor", "demo-lumen", "demo-nexus")) else 5
        beliefs_out = belief_scores if belief_limit == 0 else belief_scores[:belief_limit]

        return QueryResponse(
            answer=str(result["answer"]),
            confidence=float(result["confidence"]),
            reasoning=str(result.get("reasoning", "")),
            contrarian_view=contrarian_view,
            beliefs_used=beliefs_out,
            entities_retrieved=entities,
            session_id=query_session.id,
        )

    async def feedback(self, data: FeedbackRequest) -> FeedbackResponse:
        from sqlalchemy import select

        stmt = select(QuerySession).where(QuerySession.id == data.session_id)
        result = await self.session.execute(stmt)
        query_session = result.scalar_one_or_none()
        if query_session is None:
            raise ValueError(f"Session {data.session_id} not found")

        query_session.outcome = data.outcome
        query_session.feedback = data.feedback

        supporting = data.outcome.lower() in ("success", "succeeded", "ok")
        adjustments: list[dict] = []
        failures_recorded = 0
        beliefs_updated = 0

        for ref in query_session.graph_refs:
            graph_id = f"entity:{ref}" if not ref.startswith("entity:") else ref
            belief = await self.beliefs.reinforce(
                graph_id,
                supporting=supporting,
                strong_contradiction=data.contradicts_belief,
            )
            if belief:
                beliefs_updated += 1
                adjustments.append(
                    {
                        "graph_id": belief.graph_id,
                        "confidence": belief.confidence,
                        "status": belief.status,
                        "crs": belief.crs,
                    }
                )

        if data.belief_graph_id and not supporting:
            belief = await self.beliefs.record_contradiction(
                data.belief_graph_id,
                strong=data.contradicts_belief,
            )
            if belief:
                beliefs_updated += 1
                adjustments.append(
                    {
                        "graph_id": belief.graph_id,
                        "confidence": belief.confidence,
                        "status": belief.status,
                        "crs": belief.crs,
                    }
                )

        failure_type = self.failures.classify_outcome(
            data.outcome, has_prediction=bool(data.predicted)
        )
        if failure_type:
            await self.failures.record(
                failure_type=failure_type,
                description=data.feedback or f"Outcome: {data.outcome}",
                session_id=data.session_id,
                predicted=data.predicted or query_session.answer,
                actual=data.actual,
                graph_refs=query_session.graph_refs,
            )
            failures_recorded = 1

        await self.events.append(
            "feedback.received",
            {
                "session_id": str(data.session_id),
                "outcome": data.outcome,
                "supporting": supporting,
                "failures_recorded": failures_recorded,
            },
        )
        await self.session.commit()

        return FeedbackResponse(
            session_id=data.session_id,
            confidence_adjustments=adjustments,
            failures_recorded=failures_recorded,
            beliefs_updated=beliefs_updated,
        )

    async def compress(self, data: CompressionRequest) -> CompressionResponse:
        return await self.compression.compress(data)

    async def run_forgetting(self, data: ForgettingRequest) -> ForgettingResponse:
        return await self.forgetting.run(data)

    async def run_learning(self, data: LearningRequest) -> LearningResponse:
        response = await self.learning.run(data)
        meta = await self.meta.analyze_belief_outcomes()
        response.meta_learning = meta
        return response

    async def create_prediction(self, data: PredictionCreate) -> PredictionResponse:
        return await self.predictions.create(data)

    async def validate_prediction(self, data: PredictionValidate) -> PredictionResponse:
        return await self.predictions.validate(data)

    async def record_contradiction(self, data: ContradictionRequest) -> dict:
        belief = await self.beliefs.record_contradiction(
            data.belief_graph_id,
            strong=data.strong,
            source_id=data.source_id,
        )
        if belief is None:
            raise ValueError(f"Belief {data.belief_graph_id} not found")
        await self.meta.record("contradiction_recorded", 1.0 if data.strong else 0.5)
        await self.session.commit()
        return BeliefEngine._to_score(belief).model_dump()

    async def validate_causal_intervention(self, data: CausalValidateRequest) -> CausalValidateResponse:
        return await self.causal.validate_intervention(data)

    async def run_consolidation(self, data: LearningRequest) -> ConsolidationResponse:
        learning = await self.run_learning(data)
        return ConsolidationResponse(
            learning=learning,
            meta_learning=learning.meta_learning,
        )

    async def run_benchmark_comparison(self) -> BenchmarkComparisonResult:
        from acme.evaluation.comparison import run_benchmark_comparison

        return await run_benchmark_comparison(self, self.ollama)
