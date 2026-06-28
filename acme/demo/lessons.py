"""Squad operational lessons — seeded into ACME memory on every reclean."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from acme.demo.registry import SquadRegistry
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.base import BaseLLMClient
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import ExperienceCreate, SourceType

logger = logging.getLogger("acme.demo.lessons")

# Shared across all agents — queryable via acme_query during improvement turns.
SQUAD_LESSONS: tuple[tuple[str, str], ...] = (
    (
        "static-asset-paths",
        "Erebor static deploy: source files live under static/ in the repo (static/css/, static/js/), "
        "but index.html MUST link root-relative assets — href=\"css/tokens.css\" and src=\"js/app.js\". "
        "NEVER use /static/ in HTML. GitHub Pages strips the static/ folder to repo root; "
        "VM nginx mounts ./static as the web root. Using /static/css/… causes 404 and a broken unstyled site.",
    ),
    (
        "pinned-boot-files",
        "Boot-critical files are pinned and must not be edited by agents: server.py, requirements.txt, "
        "Dockerfile, docker-compose.yml, nginx.conf, api/routes/*, api/db.py, api/oss_clients.py. "
        "Patching them with LLM code has crashed the VM (http2 without h2, SyntaxError in intelligence.py). "
        "Improve the product via static/css/, static/js/, static/index.html only.",
    ),
    (
        "deploy-verify",
        "Before calling a deploy done, Jordan verifies http_probe OK and that css/base.css + js/app.js "
        "return HTTP 200 on the live site. Nina publishes only after meaningful static/ changes. "
        "If probes fail, Vera remediates on the VM — do not spam triage or patch server.py in a loop.",
    ),
    (
        "hire-and-channels",
        "Kai can hire specialists or open channels when the squad needs capacity. "
        "Keep improvement turns concrete: one edit, one probe, or one deploy — not endless planning messages.",
    ),
)

SQUAD_LESSONS_PROMPT = "\n".join(f"- {text}" for _key, text in SQUAD_LESSONS)


async def seed_squad_lessons(
    *,
    session: AsyncSession,
    neo4j: Neo4jClient,
    llm: BaseLLMClient,
    registry: SquadRegistry,
) -> int:
    """Ingest one combined lesson doc per agent tenant (queryable via acme_query)."""
    combined = "\n\n".join(f"[{key}] {text}" for key, text in SQUAD_LESSONS)
    count = 0
    for agent in registry.list_agents():
        orch = ACMEOrchestrator(session, neo4j, llm, tenant_id=agent.tenant_id)
        await orch.ingest_experience(
            ExperienceCreate(
                content=f"[squad-lessons] Erebor operational playbook after reclean:\n\n{combined}",
                source_type=SourceType.HUMAN_EXPERT,
                source_id="erebor-reclean",
                tags=["demo", "erebor", "lesson", "playbook"],
                tenant_id=agent.tenant_id,
            )
        )
        count += 1
    logger.info("Seeded squad playbook into %s agent tenants", count)
    return count
