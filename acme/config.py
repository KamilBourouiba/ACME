from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://acme:acme@localhost:5432/acme"
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "acmepassword"

    # LLM provider: ollama | azure_openai
    llm_provider: str = "ollama"

    ollama_base_url: str = "http://localhost:11434"
    ollama_extraction_model: str = "qwen3.5:latest"
    ollama_reasoning_model: str = "qwen3.5:latest"
    ollama_compression_model: str = "qwen3.5:latest"
    ollama_learning_model: str = "qwen3.5:latest"

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment: str = "gpt-4.1"
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_max_tokens: int = 4096

    hybrid_retrieval_enabled: bool = True
    vector_search_limit: int = 5
    pgvector_enabled: bool = True

    # Multi-tenant — default tenant when header X-Tenant-ID is absent
    default_tenant_id: str = "default"
    api_key: str = ""
    benchmark_rate_limit_per_hour: int = 10
    benchmark_min_overall: float = 0.85
    benchmark_min_belief_quality: float = 0.55

    # Ablation toggles (research / paper experiments)
    ablation_disable_contrarian: bool = False
    ablation_disable_belief_sync: bool = False
    ablation_disable_vector: bool = False

    belief_min_observations: int = 2
    belief_min_time_windows: int = 1
    belief_min_confidence: float = 0.60
    belief_min_prediction_rate: float = 0.5
    belief_min_independent_sources: int = 1
    belief_consensus_prediction_boost: bool = True
    belief_strong_contradiction_penalty: float = 0.15
    belief_demote_contradictions: int = 3
    belief_archive_contradictions: int = 5

    crs_weight_prediction: float = 0.4
    crs_weight_temporal: float = 0.2
    crs_weight_contradiction: float = 0.2
    crs_weight_sources: float = 0.2

    compression_min_episodes: int = 3
    compression_min_confidence: float = 0.6
    compression_episode_limit: int = 500

    forgetting_hot_threshold: float = 0.6
    forgetting_warm_threshold: float = 0.3
    forgetting_cold_threshold: float = 0.1
    forgetting_delete_threshold: float = 0.03
    forgetting_delete_after_days: int = 30
    forgetting_usage_cap: int = 5
    forgetting_recency_full_days: int = 7
    forgetting_recency_decay_days: float = 45.0

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "INFO"

    # Public multi-agent demo (website)
    demo_enabled: bool = False
    demo_interval_sec: int = 90
    demo_azure_deployment: str = ""  # e.g. gpt-5.4; empty = use AZURE_OPENAI_DEPLOYMENT
    demo_llm_paraphrase: bool = True


settings = Settings()
