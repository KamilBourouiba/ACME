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
    demo_interval_sec: int = 0  # legacy throttle when pipeline_mode=false
    demo_pipeline_mode: bool = True  # next turn starts immediately when previous finishes
    demo_turn_yield_ms: int = 0  # optional event-loop breathe between turns
    demo_probe_refresh_sec: int = 8  # background VM/site probes (decoupled from agent turns)
    demo_observations_max_age_sec: float = 12.0
    demo_startup_delay_sec: int = 0
    demo_reset_cooldown_sec: int = 3
    demo_azure_deployment: str = ""  # e.g. gpt-5.4; empty = use AZURE_OPENAI_DEPLOYMENT
    demo_llm_paraphrase: bool = False
    demo_llm_code: bool = True  # agents write files via LLM on code beats
    demo_code_fallback: bool = False  # greenfield — no reference site/ copy
    demo_code_timeout_sec: int = 65
    demo_channel_hearsay: bool = True
    demo_github_token: str = ""
    demo_github_repo: str = "KamilBourouiba/erebor-site-demo"
    demo_github_branch: str = "main"
    demo_auto_publish: bool = True
    demo_publish_cooldown_sec: int = 15
    demo_clean_on_start: bool = False
    demo_wipe_on_clean: bool = False  # wipe VM/GitHub only on explicit POST /reset
    demo_clean_repo_on_reset: bool = False
    demo_auto_recycle: bool = False
    demo_continuous_improvement: bool = True
    demo_deploy_failure_cap: int = 3
    demo_deploy_cooldown_after_fail_sec: int = 120
    demo_improvement_deploy_interval: int = 8
    demo_message_dedup_ticks: int = 10
    demo_agent_message_cooldown_sec: int = 15
    demo_triage_interval_ticks: int = 30
    demo_remediation_attempt_cap: int = 2
    demo_belief_refresh_ticks: int = 3
    demo_vector_search_limit: int = 50
    demo_message_cap: int = 400
    demo_state_message_cap: int = 150
    demo_vm_url: str = ""  # e.g. http://1.2.3.4:9090
    demo_vm_deploy_key: str = ""
    demo_vm_site_url: str = ""  # e.g. https://1.2.3.4
    demo_vm_auto_deploy: bool = True
    demo_static_only_deploy: bool = True  # routine publish syncs static/ only — no docker rebuild
    demo_platform_reconcile_sec: int = 45  # auto-heal VM from reference when probes fail
    demo_platform_reconcile_cooldown_sec: int = 180
    demo_visitor_secret: str = "LeanLean"
    demo_visitor_say_cooldown_sec: int = 3
    demo_ui_audit_interval: int = 5  # Taylor browser audit every N improvement turns

    # Public memory chat demo (replaces Belief Observatory squad)
    chat_demo_enabled: bool = True
    chat_max_upload_bytes: int = 5_242_880  # 5 MB
    chat_max_tool_rounds: int = 5
    chat_browse_timeout_sec: float = 20.0
    chat_message_history_limit: int = 24
    chat_clean_legacy_demo_on_start: bool = True

    # Quant belief-driven paper trading demo
    quant_demo_enabled: bool = False
    quant_scalp_mode: bool = True
    quant_tenant_id: str = "quant-demo"
    quant_symbols: str = "AAPL,MSFT,NVDA,GOOGL,AMZN,META,SPY,QQQ"
    quant_crypto_enabled: bool = True
    quant_crypto_symbols: str = "BTC-USD,ETH-USD,SOL-USD,BNB-USD"
    quant_crypto_intraday_period: str = "2d"
    quant_intraday_period: str = "1d"
    quant_crypto_momentum_floor_pct: float = 0.01
    quant_crypto_momentum_threshold_pct: float = 0.035
    quant_crypto_position_pct: float = 0.04
    quant_starting_cash: float = 1_000_000.0
    quant_cycle_interval_sec: int = 3
    quant_cycle_startup_delay_sec: int = 2
    quant_bar_interval: str = "5m"
    quant_max_position_pct: float = 0.15
    quant_scalp_position_pct: float = 0.06
    quant_scalp_max_hold_sec: int = 180
    quant_scalp_take_profit_pct: float = 0.18
    quant_scalp_stop_loss_pct: float = 0.12
    quant_scalp_trail_stop_pct: float = 0.10
    quant_scalp_breakeven_trigger_pct: float = 0.06
    quant_scalp_tp_roe_pct: float = 0.45
    quant_scalp_sl_roe_pct: float = 0.30
    quant_crypto_take_profit_pct: float = 0.12
    quant_crypto_stop_loss_pct: float = 0.08
    quant_crypto_max_hold_sec: int = 120
    quant_scalp_momentum_threshold_pct: float = 0.05
    quant_scalp_momentum_floor_pct: float = 0.015
    quant_trade_only_market_hours: bool = True
    quant_cycle_interval_closed_sec: int = 3
    quant_min_belief_crs: float = 0.55
    quant_news_per_symbol: int = 1
    quant_news_every_n_cycles: int = 90
    quant_max_trades_per_cycle: int = 6
    quant_quote_cache_sec: int = 2
    quant_ingest_every_n_cycles: int = 6
    quant_ingest_background: bool = True
    quant_ingest_interval_sec: int = 45
    quant_light_ingest: bool = True
    quant_leverage_enabled: bool = True
    quant_max_leverage: float = 5.0
    quant_equity_leverage: float = 2.0
    quant_crypto_leverage: float = 3.0
    quant_equity_commission_bps: float = 1.0
    quant_equity_min_commission: float = 0.35
    quant_crypto_taker_fee_bps: float = 6.0
    quant_margin_interest_apy: float = 6.5
    quant_crypto_funding_apy: float = 10.0


settings = Settings()
