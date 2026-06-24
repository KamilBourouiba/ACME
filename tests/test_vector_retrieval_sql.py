"""Regression: PostgreSQL cast syntax must not break SQLAlchemy bind params."""

from sqlalchemy import text
from sqlalchemy.dialects import postgresql


def test_pgvector_update_uses_cast_not_double_colon():
    stmt = text(
        "UPDATE episodes SET embedding_vec = CAST(:vec AS vector) WHERE id = :id"
    )
    assert set(stmt._bindparams.keys()) == {"vec", "id"}


def test_pgvector_search_uses_cast_not_double_colon():
    stmt = text(
        """
        SELECT id FROM episodes
        WHERE embedding_vec IS NOT NULL
        ORDER BY embedding_vec <=> CAST(:query_vec AS vector)
        LIMIT :limit
        """
    )
    assert set(stmt._bindparams.keys()) == {"query_vec", "limit"}
    compiled = str(stmt.compile(dialect=postgresql.dialect()))
    assert "CAST" in compiled
    assert "::vector" not in compiled.split("CAST")[0]
