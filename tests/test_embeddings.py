from acme.llm.embeddings import cosine_similarity, deterministic_embed


def test_deterministic_embed_normalized():
    vec = deterministic_embed("latency causes churn in enterprise segment")
    assert len(vec) == 256
    assert abs(sum(v * v for v in vec) - 1.0) < 0.01


def test_cosine_similarity_identical():
    a = deterministic_embed("customer churn latency")
    b = deterministic_embed("customer churn latency")
    assert cosine_similarity(a, b) == 1.0


def test_cosine_similarity_different():
    a = deterministic_embed("latency timeout api")
    b = deterministic_embed("dark mode feature shipped")
    assert cosine_similarity(a, b) < 0.5
