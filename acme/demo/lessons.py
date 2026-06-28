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
        "static-only-deploy",
        "Routine deploy syncs static/ only (css, js, html) — nginx reload, no docker rebuild. "
        "Platform API (server.py, api/*) is pinned from reference. If VM probes fail, "
        "watchdog auto-reconciles the full pinned stack; agents must not edit backend files.",
    ),
    (
        "github-pages-publish",
        "GitHub Pages (erebor-site-demo) is NOT the VM. On publish, index.html is PINNED from "
        "acme/demo/site/static/index.html — agents must not ship a custom index that references "
        "css/layout.css, css/components.css, or other files that do not exist. Valid CSS names only: "
        "tokens, base, shell, omnibar, panels, canvas, inspector, timeline. "
        "Pages has no /api backend; publish injects EREBOR_DIRECT_OSS and search runs via js/oss.js "
        "(GitHub, OpenAlex, Nominatim from the browser). Do not wire Pages to VM HTTPS — self-signed "
        "TLS is blocked by browsers. Improve Pages by editing static/css/ and static/js/ only; "
        "leave index.html structure to the reference shell.",
    ),
    (
        "ui-audit-workflow",
        "Taylor (UI/UX QA) runs ui_audit every few improvement turns: loads live GitHub Pages, "
        "clicks search + controls, captures screenshots at /api/v1/demo/ui-screenshot/{id}.png, "
        "reads console errors. Taylor does NOT ship code — findings queue builder tasks for "
        "Marco (JS/globe), Priya (CSS), Chen (api.js). Jordan keeps http_probe/API checks. "
        "After Taylor posts in #qa, builders edit on subsequent turns automatically.",
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
