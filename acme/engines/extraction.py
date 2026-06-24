"""Merge LLM and deterministic extractions."""

from acme.schemas import ExtractionResult, GraphEntity, GraphRelation


def merge_extractions(primary: ExtractionResult, secondary: ExtractionResult) -> ExtractionResult:
    entities: dict[str, GraphEntity] = {e.name: e for e in secondary.entities}
    for entity in primary.entities:
        entities[entity.name] = entity

    relation_keys: set[tuple[str, str, str]] = set()
    relations: list[GraphRelation] = []
    for rel in secondary.relations + primary.relations:
        key = (rel.source, rel.target, rel.causal_type.value)
        if key in relation_keys:
            continue
        relation_keys.add(key)
        relations.append(rel)

    return ExtractionResult(
        entities=list(entities.values()),
        relations=relations,
        summary=primary.summary or secondary.summary,
    )
