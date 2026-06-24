"""Deterministic semantic scoring fallback for MemoryBench."""

import re

CONCEPT_SYNONYMS: dict[str, list[str]] = {
    "latency": ["latency", "slow", "timeout", "timeouts", "performance", "loading", "lenteur", "délai"],
    "churn": ["churn", "churned", "left", "leave", "leaving", "cancel", "cancelled", "canceled", "parti", "attrition"],
    "performance": ["performance", "slow", "latency", "timeout", "speed", "lenteur"],
    "causal_link": ["cause", "causes", "caused", "because", "due to", "lead to", "drives", "résultat"],
}


def expand_concept(concept: str) -> list[str]:
    key = concept.lower().strip().replace(" ", "_")
    if key in CONCEPT_SYNONYMS:
        return CONCEPT_SYNONYMS[key]
    return [concept.lower()]


def keyword_retention_score(answer: str, concepts: list[str]) -> float:
    """Legacy keyword overlap — kept for comparison in benchmark details."""
    if not concepts:
        return 0.0
    text = answer.lower()
    hits = 0
    for concept in concepts:
        tokens = expand_concept(concept)
        if any(token in text for token in tokens):
            hits += 1
    return hits / len(concepts)


def semantic_retention_score(answer: str, concepts: list[str]) -> float:
    """Rule-based semantic coverage — synonyms and related terms count."""
    return keyword_retention_score(answer, concepts)


def groundedness_score(answer: str, source_episodes: list[str]) -> float:
    """Estimate whether the answer is anchored in ingested episodes."""
    if not answer.strip():
        return 0.0

    answer_lower = answer.lower()
    if "insufficient" in answer_lower and "memory" in answer_lower:
        return 0.5

    source_text = " ".join(source_episodes).lower()
    source_tokens = set(re.findall(r"[a-z]{4,}", source_text))
    answer_tokens = set(re.findall(r"[a-z]{4,}", answer_lower))
    if not source_tokens or not answer_tokens:
        return 0.5

    overlap = len(source_tokens & answer_tokens)
    coverage = overlap / max(1, min(len(answer_tokens), len(source_tokens)))
    return min(1.0, max(0.35, coverage * 1.5))
