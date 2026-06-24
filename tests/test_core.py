import pytest

from acme.schemas import KnowledgeType
from acme.llm.base import BaseLLMClient
from acme.llm.ollama import OllamaClient


def test_parse_json_with_fence():
    raw = 'Here is the result:\n```json\n{"answer": "test", "confidence": 0.9}\n```'
    parsed = OllamaClient._parse_json(raw)
    assert parsed["answer"] == "test"
    assert parsed["confidence"] == 0.9


def test_parse_json_bare():
    raw = '{"entities": [], "relations": []}'
    parsed = OllamaClient._parse_json(raw)
    assert parsed["entities"] == []


def test_to_extraction_result_defaults():
    data = {
        "entities": [{"name": "Customer A", "entity_type": "customer"}],
        "relations": [{"source": "A", "target": "B", "relation_type": "CAUSED"}],
        "summary": "test",
    }
    result = OllamaClient._to_extraction_result(data)
    assert len(result.entities) == 1
    assert result.entities[0].knowledge_type == KnowledgeType.OBSERVATION
    assert len(result.relations) == 1
    assert result.relations[0].knowledge_type == KnowledgeType.INFERENCE
    assert result.relations[0].causal_type.value == "causes"


def test_sanitize_rel_type():
    from acme.graph.neo4j_client import Neo4jClient

    assert Neo4jClient._sanitize_rel_type("caused by") == "CAUSED_BY"
    assert Neo4jClient._sanitize_rel_type("") == "RELATED_TO"
