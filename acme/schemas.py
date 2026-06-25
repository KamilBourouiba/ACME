from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class StrEnum(str, Enum):
    pass


class KnowledgeType(StrEnum):
    OBSERVATION = "observation"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"
    BELIEF = "belief"


class BeliefStatus(StrEnum):
    HYPOTHESIS = "hypothesis"
    BELIEF = "belief"
    CHALLENGED = "challenged"
    DEPRECATED = "deprecated"
    ARCHIVED = "archived"


class CausalRelationType(StrEnum):
    OBSERVED_WITH = "observed_with"
    PRECEDES = "precedes"
    CORRELATES = "correlates"
    CAUSES = "causes"
    DISPROVES = "disproves"
    RELATED_TO = "related_to"


class SourceType(StrEnum):
    USER = "user"
    DATABASE = "database"
    API = "api"
    WEB = "web"
    SENSOR = "sensor"
    HUMAN_EXPERT = "human_expert"
    SYSTEM = "system"


class CognitiveProfile(StrEnum):
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    STRATEGIC = "strategic"
    SOCIAL = "social"


class FailureType(StrEnum):
    DATA = "data_failure"
    REASONING = "reasoning_failure"
    MEMORY = "memory_failure"
    EXECUTION = "execution_failure"


class MemoryTier(StrEnum):
    HOT = "hot"
    WARM = "warm"
    COLD = "cold"
    ARCHIVE = "archive"


class ExperienceCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Raw experience text or event description")
    action: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    source_type: SourceType = Field(default=SourceType.USER)
    source_id: str | None = Field(default=None, description="Independent source identifier")
    source_credibility: float | None = Field(default=None, ge=0.0, le=1.0)
    cognitive_profile: CognitiveProfile | None = None
    tenant_id: str | None = Field(default=None, description="Tenant scope (defaults to X-Tenant-ID header)")


class ExperienceResponse(BaseModel):
    id: UUID
    content: str
    action: str | None
    context: dict[str, Any]
    tags: list[str]
    source_type: SourceType
    source_id: str | None
    cognitive_profile: CognitiveProfile
    created_at: datetime


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    challenge: bool = Field(default=False, description="Run contrarian check on high-confidence answers")


class GraphEntity(BaseModel):
    name: str
    entity_type: str
    knowledge_type: KnowledgeType = KnowledgeType.OBSERVATION
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphRelation(BaseModel):
    source: str
    target: str
    relation_type: str
    causal_type: CausalRelationType = CausalRelationType.RELATED_TO
    knowledge_type: KnowledgeType = KnowledgeType.INFERENCE
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    properties: dict[str, Any] = Field(default_factory=dict)


class ExtractionResult(BaseModel):
    entities: list[GraphEntity]
    relations: list[GraphRelation]
    summary: str | None = None


class BeliefScore(BaseModel):
    entity_or_relation_id: str
    label: str
    knowledge_type: KnowledgeType
    status: BeliefStatus
    confidence: float
    crs: float = Field(description="Cognitive Reliability Score")
    supporting_evidence: int
    contradicting_evidence: int
    strong_contradictions: int = 0
    independent_sources: int = 0
    prediction_successes: int = 0
    prediction_failures: int = 0
    time_windows: int = 1
    cognitive_profile: CognitiveProfile = CognitiveProfile.FACTUAL


class QueryResponse(BaseModel):
    answer: str
    confidence: float
    reasoning: str
    contrarian_view: str | None = None
    beliefs_used: list[BeliefScore] = Field(default_factory=list)
    entities_retrieved: list[str] = Field(default_factory=list)
    session_id: UUID


class FeedbackRequest(BaseModel):
    session_id: UUID
    outcome: str = Field(..., description="success | failed | partial")
    feedback: str | None = None
    failure_type: FailureType | None = None
    predicted: str | None = None
    actual: str | None = None
    contradicts_belief: bool = Field(default=False, description="Mark as strong contradiction")
    belief_graph_id: str | None = Field(default=None, description="Belief to contradict")


class FeedbackResponse(BaseModel):
    session_id: UUID
    confidence_adjustments: list[dict[str, Any]]
    failures_recorded: int
    beliefs_updated: int


class HealthResponse(BaseModel):
    status: str
    postgres: bool
    neo4j: bool
    llm: bool
    llm_provider: str
    version: str


class CompressionRequest(BaseModel):
    tags: list[str] | None = Field(default=None, description="Filter episodes by tags")
    min_episodes: int = Field(default=3, ge=2, description="Min episodes per cluster")
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    limit: int = Field(default=500, ge=10, le=5000)


class AbstractionResponse(BaseModel):
    id: UUID
    label: str
    pattern: str
    episode_count: int
    confidence: float
    source_episode_ids: list[UUID]
    created_at: datetime


class CompressionResponse(BaseModel):
    abstractions_created: int
    episodes_compressed: int
    abstractions: list[AbstractionResponse]


class ForgettingRequest(BaseModel):
    dry_run: bool = Field(default=True, description="Simulate without changes")
    delete_enabled: bool = Field(default=False, description="Allow permanent deletion from archive")
    tier: MemoryTier | None = Field(default=None, description="Process only one tier")
    limit: int = Field(default=1000, ge=1, le=10000)


class ForgettingResponse(BaseModel):
    processed: int
    dry_run: bool
    tier_changes: dict[str, int]
    archived: int
    deleted: int


class EpisodeMemoryStatus(BaseModel):
    id: UUID
    memory_tier: MemoryTier
    importance_score: float
    access_count: int
    last_accessed_at: datetime | None
    created_at: datetime
    archived: bool


class LearningRequest(BaseModel):
    consolidate: bool = Field(default=True, description="Run compression + forgetting + belief promotion")
    generate_hypotheses: bool = Field(default=True, description="Generate new hypotheses from memory")
    create_predictions: bool = Field(default=True, description="Auto-create testable predictions from hypotheses")
    forget_dry_run: bool = Field(default=True, description="Simulate forgetting tier transitions")
    min_episodes_for_compression: int = Field(default=3, ge=2)
    min_abstraction_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    episode_limit: int = Field(default=500, ge=10, le=5000)
    context_limit: int = Field(default=30, ge=5, le=200)


class HypothesisResponse(BaseModel):
    id: UUID
    statement: str
    rationale: str
    testable_prediction: str | None
    confidence: float
    status: str
    created_at: datetime


class LearningResponse(BaseModel):
    cycle_id: UUID
    hypotheses_generated: int
    predictions_created: int = 0
    abstractions_created: int
    episodes_compressed: int
    beliefs_promoted: int
    beliefs_demoted: int = 0
    forgetting: dict[str, int]
    hypotheses: list[HypothesisResponse]
    duration_seconds: float
    meta_learning: dict[str, Any] = Field(default_factory=dict)


class PredictionCreate(BaseModel):
    hypothesis_id: UUID | None = None
    belief_graph_id: str | None = None
    statement: str = Field(..., min_length=1)
    expected_outcome: str = Field(..., min_length=1)
    horizon_days: int = Field(default=30, ge=1, le=365)


class PredictionValidate(BaseModel):
    prediction_id: UUID
    actual_outcome: str
    success: bool


class PredictionResponse(BaseModel):
    id: UUID
    statement: str
    expected_outcome: str
    actual_outcome: str | None
    status: str
    validated: bool
    success: bool | None
    created_at: datetime


class ContradictionRequest(BaseModel):
    belief_graph_id: str
    description: str
    strong: bool = Field(default=False)
    source_type: SourceType = SourceType.USER
    source_id: str | None = None


class MemoryBenchResult(BaseModel):
    retention_score: float
    feedback_correction_score: float
    hallucination_resistance_score: float
    belief_quality_score: float
    overall_score: float
    details: dict[str, Any] = Field(default_factory=dict)


class BenchmarkComparisonResult(BaseModel):
    acme: MemoryBenchResult
    rag_baseline: MemoryBenchResult
    memgpt_baseline: MemoryBenchResult | None = None
    langgraph_baseline: MemoryBenchResult | None = None
    comparison_table: list[dict[str, Any]]
    export: dict[str, Any] = Field(default_factory=dict)


class LongMemEvalAsyncRequest(BaseModel):
    question_types: list[str] | None = None
    limit: int | None = None
    offset: int = 0
    systems: list[str] | None = None
    dataset_path: str | None = None


class CausalValidateRequest(BaseModel):
    belief_graph_id: str | None = None
    prediction_id: UUID | None = None
    intervention: str = Field(..., min_length=1)
    expected_outcome: str = Field(..., min_length=1)
    actual_outcome: str = Field(..., min_length=1)
    success: bool


class CausalValidateResponse(BaseModel):
    success: bool
    causal_upgraded: bool
    belief_graph_id: str | None
    message: str


class ConsolidationResponse(BaseModel):
    learning: LearningResponse
    compression: CompressionResponse | None = None
    forgetting: ForgettingResponse | None = None
    meta_learning: dict[str, Any] = Field(default_factory=dict)
