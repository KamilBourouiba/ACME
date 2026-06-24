from acme.engines.deterministic import (
    infer_cognitive_profile,
    normalize_relation_type,
    rule_based_extraction,
    source_credibility,
)
from acme.schemas import CausalRelationType, CognitiveProfile, SourceType


def test_infer_cognitive_profile_strategic():
    profile = infer_cognitive_profile("Customer churn increased after latency spikes", ["churn"])
    assert profile == CognitiveProfile.STRATEGIC


def test_normalize_causal_type_causes():
    assert normalize_relation_type("caused by latency") == CausalRelationType.CAUSES.value


def test_source_credibility_ordering():
    assert source_credibility(SourceType.HUMAN_EXPERT) > source_credibility(SourceType.WEB)


def test_rule_based_extraction_latency_churn():
    result = rule_based_extraction(
        "Customer A churned after API latency incidents.",
        action="analyze",
    )
    assert len(result.entities) >= 1
    if result.relations:
        assert result.relations[0].causal_type == CausalRelationType.CORRELATES
