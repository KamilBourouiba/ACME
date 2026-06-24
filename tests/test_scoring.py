from acme.evaluation.scoring import (
    groundedness_score,
    keyword_retention_score,
    semantic_retention_score,
)


def test_semantic_retention_matches_synonyms():
    answer = "Customers leave because of slow API response and checkout timeouts."
    score = semantic_retention_score(answer, ["latency", "churn"])
    assert score == 1.0


def test_keyword_retention_with_synonym_expansion():
    answer = "Customers leave because of slow API response."
    score = keyword_retention_score(answer, ["latency", "timeout", "churn", "slow"])
    assert score == 0.75


def test_groundedness_uses_episode_overlap():
    answer = "Churn follows repeated API latency incidents for several customers."
    episodes = [
        "Customer A churned after API latency incidents.",
        "Customer B left following checkout timeouts.",
    ]
    score = groundedness_score(answer, episodes)
    assert score >= 0.4
