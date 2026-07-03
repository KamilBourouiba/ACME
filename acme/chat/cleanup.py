"""Purge legacy Belief Observatory demo tenants."""

from __future__ import annotations

import logging

from acme.config import settings
from acme.db.session import SessionLocal
from acme.demo.reset import ALL_DEMO_TENANT_IDS, cleanup_all_demo_tenants
from acme.graph.neo4j_client import neo4j_client

logger = logging.getLogger("acme.chat.cleanup")


async def purge_legacy_demo_data() -> list[dict]:
    """Remove squad demo memory (demo-belief-*, legacy lumen/nexus/erebor)."""
    if not settings.chat_clean_legacy_demo_on_start:
        return []
    async with SessionLocal() as session:
        results = await cleanup_all_demo_tenants(
            session,
            neo4j_client,
            tenant_ids=ALL_DEMO_TENANT_IDS,
        )
    logger.info("Purged %d legacy demo tenants", len(results))
    return results
