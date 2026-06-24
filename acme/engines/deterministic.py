"""Deterministic helpers — reduce LLM dependency for structured tasks."""

import re
from typing import Any

from acme.schemas import (
    CausalRelationType,
    CognitiveProfile,
    ExtractionResult,
    GraphEntity,
    GraphRelation,
    KnowledgeType,
    SourceType,
)

CAUSAL_KEYWORDS: dict[CausalRelationType, list[str]] = {
    CausalRelationType.CAUSES: ["caused", "causes", "because of", "due to", "led to", "résultat de"],
    CausalRelationType.PRECEDES: ["before", "prior to", "then", "avant", "suivi de"],
    CausalRelationType.CORRELATES: ["associated with", "correlated", "often with", "souvent avec"],
    CausalRelationType.DISPROVES: ["disproves", "contradicts", "refutes", "contredit", "infirme"],
    CausalRelationType.OBSERVED_WITH: ["with", "during", "while", "pendant"],
}

PROFILE_KEYWORDS: dict[CognitiveProfile, list[str]] = {
    CognitiveProfile.PROCEDURAL: ["how to", "step", "process", "workflow", "comment"],
    CognitiveProfile.STRATEGIC: ["strategy", "churn", "retention", "revenue", "client"],
    CognitiveProfile.SOCIAL: ["user prefers", "customer said", "feedback", "utilisateur"],
    CognitiveProfile.FACTUAL: [],
}


def infer_cognitive_profile(content: str, tags: list[str] | None = None) -> CognitiveProfile:
    text = content.lower()
    tag_text = " ".join(tags or []).lower()
    scores = {p: 0 for p in CognitiveProfile}
    for profile, keywords in PROFILE_KEYWORDS.items():
        for kw in keywords:
            if kw in text or kw in tag_text:
                scores[profile] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else CognitiveProfile.FACTUAL


def infer_relation_type(relation_text: str, content: str) -> CausalRelationType:
    """Map relation label + context to causal type without LLM."""
    combined = f"{relation_text} {content}".lower()
    for rel_type, keywords in CAUSAL_KEYWORDS.items():
        if any(kw in combined for kw in keywords):
            return rel_type
    return CausalRelationType.RELATED_TO


def normalize_relation_type(raw: str, content: str = "") -> str:
    """Normalize LLM output to allowed causal types."""
    cleaned = raw.lower().strip().replace(" ", "_").replace("-", "_")
    mapping = {
        "cause": CausalRelationType.CAUSES,
        "caused": CausalRelationType.CAUSES,
        "causes": CausalRelationType.CAUSES,
        "correlate": CausalRelationType.CORRELATES,
        "correlates": CausalRelationType.CORRELATES,
        "precede": CausalRelationType.PRECEDES,
        "precedes": CausalRelationType.PRECEDES,
        "disprove": CausalRelationType.DISPROVES,
        "disproves": CausalRelationType.DISPROVES,
        "observed_with": CausalRelationType.OBSERVED_WITH,
        "related_to": CausalRelationType.RELATED_TO,
    }
    for key, rel in mapping.items():
        if key in cleaned:
            return rel.value
    return infer_relation_type(raw, content).value


def rule_based_extraction(content: str, action: str | None = None) -> ExtractionResult:
    """Lightweight pattern extraction — merged with LLM output upstream."""
    entities: list[GraphEntity] = []
    relations: list[GraphRelation] = []

    capitalized = re.findall(r"\b[A-Z][a-zA-Z0-9]+(?:\s[A-Z][a-zA-Z0-9]+)?\b", content)
    seen: set[str] = set()
    for name in capitalized[:8]:
        if name.lower() in seen:
            continue
        seen.add(name.lower())
        entities.append(
            GraphEntity(
                name=name,
                entity_type="entity",
                knowledge_type=KnowledgeType.OBSERVATION,
            )
        )

    if action:
        entities.append(
            GraphEntity(name=action, entity_type="action", knowledge_type=KnowledgeType.OBSERVATION)
        )

    latency_match = re.search(r"latenc(y|e)|timeout|slow", content, re.I)
    churn_match = re.search(r"churn|left|parti|cancel", content, re.I)
    if latency_match and churn_match and len(entities) >= 2:
        relations.append(
            GraphRelation(
                source=entities[0].name,
                target=entities[1].name if len(entities) > 1 else "Churn",
                relation_type=CausalRelationType.CORRELATES.value,
                causal_type=CausalRelationType.CORRELATES,
                knowledge_type=KnowledgeType.INFERENCE,
                confidence=0.4,
                properties={"deterministic": True},
            )
        )

    return ExtractionResult(entities=entities, relations=relations, summary=None)


def source_credibility(source_type: SourceType) -> float:
    weights = {
        SourceType.HUMAN_EXPERT: 1.0,
        SourceType.DATABASE: 0.95,
        SourceType.API: 0.85,
        SourceType.SENSOR: 0.8,
        SourceType.USER: 0.75,
        SourceType.WEB: 0.6,
        SourceType.SYSTEM: 0.5,
    }
    return weights.get(source_type, 0.7)
