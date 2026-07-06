from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from acme.config import settings
from acme.db.models import Base

engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

_SCHEMA_PATCHES: tuple[str, ...] = (
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS source_type VARCHAR(32) DEFAULT 'user'",
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS source_id VARCHAR(256)",
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS source_credibility DOUBLE PRECISION DEFAULT 0.75",
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS cognitive_profile VARCHAR(32) DEFAULT 'factual'",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'hypothesis'",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS crs DOUBLE PRECISION DEFAULT 0.0",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS strong_contradictions INTEGER DEFAULT 0",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS independent_source_count INTEGER DEFAULT 0",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS source_ids JSONB DEFAULT '[]'::jsonb",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS cognitive_profile VARCHAR(32) DEFAULT 'factual'",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS prediction_successes INTEGER DEFAULT 0",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS prediction_failures INTEGER DEFAULT 0",
    "UPDATE beliefs SET status = 'hypothesis' WHERE status IS NULL",
    "UPDATE beliefs SET crs = 0.0 WHERE crs IS NULL",
    "UPDATE beliefs SET strong_contradictions = 0 WHERE strong_contradictions IS NULL",
    "UPDATE beliefs SET independent_source_count = 0 WHERE independent_source_count IS NULL",
    "UPDATE beliefs SET source_ids = '[]'::jsonb WHERE source_ids IS NULL",
    "UPDATE beliefs SET prediction_successes = 0 WHERE prediction_successes IS NULL",
    "UPDATE beliefs SET prediction_failures = 0 WHERE prediction_failures IS NULL",
    "UPDATE episodes SET source_type = 'user' WHERE source_type IS NULL",
    "UPDATE episodes SET source_credibility = 0.75 WHERE source_credibility IS NULL",
    "UPDATE episodes SET cognitive_profile = 'factual' WHERE cognitive_profile IS NULL",
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS embedding JSONB",
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) DEFAULT 'default'",
    "ALTER TABLE query_sessions ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) DEFAULT 'default'",
    "ALTER TABLE beliefs ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) DEFAULT 'default'",
    "UPDATE episodes SET tenant_id = 'default' WHERE tenant_id IS NULL",
    "UPDATE query_sessions SET tenant_id = 'default' WHERE tenant_id IS NULL",
    "UPDATE beliefs SET tenant_id = 'default' WHERE tenant_id IS NULL",
    "CREATE EXTENSION IF NOT EXISTS vector",
    "ALTER TABLE episodes ADD COLUMN IF NOT EXISTS embedding_vec vector(256)",
    """
    CREATE TABLE IF NOT EXISTS benchmark_runs (
        id UUID PRIMARY KEY,
        run_type VARCHAR(32) NOT NULL,
        tenant_id VARCHAR(64) DEFAULT 'default',
        version VARCHAR(32) DEFAULT '0.1.0',
        revision VARCHAR(64),
        overall_score DOUBLE PRECISION DEFAULT 0.0,
        retention_score DOUBLE PRECISION DEFAULT 0.0,
        feedback_score DOUBLE PRECISION DEFAULT 0.0,
        groundedness_score DOUBLE PRECISION DEFAULT 0.0,
        belief_quality_score DOUBLE PRECISION DEFAULT 0.0,
        scenarios_run INTEGER DEFAULT 0,
        failures JSONB DEFAULT '[]'::jsonb,
        payload JSONB DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS benchmark_runs_created_idx ON benchmark_runs (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS benchmark_runs_type_idx ON benchmark_runs (run_type, tenant_id)",
    """
    CREATE TABLE IF NOT EXISTS chat_sessions (
        id UUID PRIMARY KEY,
        tenant_id VARCHAR(80) UNIQUE NOT NULL,
        title VARCHAR(256) DEFAULT 'New conversation',
        created_at TIMESTAMPTZ DEFAULT now(),
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS chat_sessions_tenant_idx ON chat_sessions (tenant_id)",
    """
    CREATE TABLE IF NOT EXISTS chat_messages (
        id UUID PRIMARY KEY,
        session_id UUID NOT NULL,
        role VARCHAR(16) NOT NULL,
        content TEXT NOT NULL DEFAULT '',
        attachments JSONB DEFAULT '[]'::jsonb,
        tool_calls JSONB DEFAULT '[]'::jsonb,
        beliefs_used JSONB DEFAULT '[]'::jsonb,
        query_session_id UUID,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS chat_messages_session_idx ON chat_messages (session_id, created_at)",
    """
    CREATE TABLE IF NOT EXISTS paper_accounts (
        id UUID PRIMARY KEY,
        tenant_id VARCHAR(80) UNIQUE NOT NULL,
        cash DOUBLE PRECISION DEFAULT 1000000,
        starting_cash DOUBLE PRECISION DEFAULT 1000000,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS paper_accounts_tenant_idx ON paper_accounts (tenant_id)",
    """
    CREATE TABLE IF NOT EXISTS paper_positions (
        id UUID PRIMARY KEY,
        account_id UUID NOT NULL,
        tenant_id VARCHAR(80) NOT NULL,
        symbol VARCHAR(16) NOT NULL,
        quantity DOUBLE PRECISION DEFAULT 0,
        avg_cost DOUBLE PRECISION DEFAULT 0,
        updated_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS paper_positions_account_idx ON paper_positions (account_id, symbol)",
    """
    CREATE TABLE IF NOT EXISTS paper_trades (
        id UUID PRIMARY KEY,
        account_id UUID NOT NULL,
        tenant_id VARCHAR(80) NOT NULL,
        symbol VARCHAR(16) NOT NULL,
        side VARCHAR(8) NOT NULL,
        quantity DOUBLE PRECISION NOT NULL,
        price DOUBLE PRECISION NOT NULL,
        notional DOUBLE PRECISION NOT NULL,
        belief_graph_id VARCHAR(256),
        belief_label VARCHAR(512),
        reasoning TEXT DEFAULT '',
        crs_at_trade DOUBLE PRECISION,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS paper_trades_tenant_idx ON paper_trades (tenant_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS portfolio_snapshots (
        id UUID PRIMARY KEY,
        tenant_id VARCHAR(80) NOT NULL,
        nav DOUBLE PRECISION NOT NULL,
        total_pnl_pct DOUBLE PRECISION DEFAULT 0,
        positions_json JSONB DEFAULT '[]'::jsonb,
        created_at TIMESTAMPTZ DEFAULT now()
    )
    """,
    "CREATE INDEX IF NOT EXISTS portfolio_snapshots_tenant_idx ON portfolio_snapshots (tenant_id, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS quant_cycle_state (
        id UUID PRIMARY KEY,
        tenant_id VARCHAR(80) UNIQUE NOT NULL,
        cycle_count INTEGER DEFAULT 0,
        last_cycle_at TIMESTAMPTZ,
        last_ingested INTEGER DEFAULT 0,
        trace_steps JSONB DEFAULT '[]'::jsonb,
        trace_nodes JSONB DEFAULT '[]'::jsonb,
        trace_edges JSONB DEFAULT '[]'::jsonb
    )
    """,
    "CREATE INDEX IF NOT EXISTS quant_cycle_state_tenant_idx ON quant_cycle_state (tenant_id)",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ",
    "ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS fees_paid DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS funding_paid DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE paper_accounts ADD COLUMN IF NOT EXISTS last_carry_at TIMESTAMPTZ",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS leverage DOUBLE PRECISION DEFAULT 1",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS margin_used DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS borrowed DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS fee DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS leverage DOUBLE PRECISION DEFAULT 1",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS peak_price DOUBLE PRECISION",
    "ALTER TABLE paper_positions ADD COLUMN IF NOT EXISTS stop_floor DOUBLE PRECISION",
)


async def _pgvector_available(conn) -> bool:
    try:
        result = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        return result.scalar_one_or_none() is not None
    except Exception:
        return False


async def migrate_db() -> None:
    for stmt in _SCHEMA_PATCHES:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(stmt))
        except Exception:
            if "vector" not in stmt and "ivfflat" not in stmt:
                raise


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_db()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
