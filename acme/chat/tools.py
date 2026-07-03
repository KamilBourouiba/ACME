"""Agent tools — browse, memory search, remember, beliefs."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from acme.config import settings
from acme.graph.neo4j_client import Neo4jClient
from acme.llm.base import BaseLLMClient
from acme.orchestrator import ACMEOrchestrator
from acme.schemas import ExperienceCreate, QueryRequest, SourceType

logger = logging.getLogger("acme.chat.tools")

SKILL_NAMES: tuple[str, ...] = (
    "browse_web",
    "search_memory",
    "remember",
    "list_beliefs",
    "summarize_url",
)

AGENT_SYSTEM = """You are an ACME memory agent with persistent episodic memory, a knowledge graph, and beliefs (CRS-scored).

You can use tools:
- browse_web: fetch a public URL and read its text
- search_memory: query your memory graph for relevant facts
- remember: store an important fact for later
- list_beliefs: show promoted beliefs and confidence scores

Return ONLY valid JSON:
{
  "action": "tool" | "respond",
  "tool": "browse_web|search_memory|remember|list_beliefs",
  "tool_input": { },
  "message": "user-facing reply when action=respond"
}

Use tools when the user asks you to look something up, browse a page, or when memory search would help.
When responding, cite what you recalled from memory when relevant. Be concise and helpful."""


def strip_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


async def browse_web(url: str) -> dict[str, Any]:
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    try:
        async with httpx.AsyncClient(
            timeout=settings.chat_browse_timeout_sec,
            follow_redirects=True,
            headers={"User-Agent": "ACME-Memory-Agent/1.0"},
        ) as client:
            resp = await client.get(url)
            body = resp.text if "text/html" in resp.headers.get("content-type", "") else resp.text
            text = strip_html(body) if "<html" in body.lower()[:500] else body
            return {
                "ok": resp.status_code < 400,
                "url": str(resp.url),
                "status": resp.status_code,
                "text": text[:8000],
            }
    except Exception as exc:
        logger.warning("browse_web failed for %s: %s", url, exc)
        return {"ok": False, "url": url, "error": str(exc)}


async def run_tool(
    name: str,
    tool_input: dict[str, Any],
    *,
    orch: ACMEOrchestrator,
    graph: Neo4jClient,
) -> dict[str, Any]:
    if name == "browse_web":
        url = str(tool_input.get("url", "")).strip()
        if not url:
            return {"ok": False, "error": "url required"}
        result = await browse_web(url)
        return {
            "ok": result.get("ok", False),
            "summary": f"Fetched {result.get('url', url)} ({result.get('status', '?')})",
            "detail": result,
        }

    if name == "search_memory":
        question = str(tool_input.get("question", "")).strip()
        if not question:
            return {"ok": False, "error": "question required"}
        qr = await orch.query(QueryRequest(question=question))
        return {
            "ok": True,
            "summary": f"Memory search — confidence {qr.confidence:.2f}",
            "detail": {
                "answer": qr.answer,
                "reasoning": qr.reasoning,
                "entities": qr.entities_retrieved,
                "beliefs": [b.model_dump() for b in qr.beliefs_used[:8]],
            },
        }

    if name == "remember":
        text = str(tool_input.get("text", "")).strip()
        if not text:
            return {"ok": False, "error": "text required"}
        exp = await orch.ingest_experience(
            ExperienceCreate(
                content=text,
                action="agent_remember",
                tags=["remember", "chat"],
                source_type=SourceType.SYSTEM,
            )
        )
        return {
            "ok": True,
            "summary": f"Stored memory episode {exp.id}",
            "detail": {"episode_id": str(exp.id)},
        }

    if name == "list_beliefs":
        beliefs = await orch.beliefs.list_beliefs(min_confidence=0.0)
        top = beliefs[:15]
        return {
            "ok": True,
            "summary": f"{len(beliefs)} beliefs ({len(top)} shown)",
            "detail": [b.model_dump() for b in top],
        }

    return {"ok": False, "error": f"Unknown tool: {name}"}


def parse_agent_step(raw: str) -> dict[str, Any]:
    from acme.llm.base import BaseLLMClient as _Base

    try:
        data = _Base._parse_json(raw)  # noqa: SLF001
    except Exception:
        return {"action": "respond", "message": raw.strip()}
    if not isinstance(data, dict):
        return {"action": "respond", "message": str(data)}
    action = str(data.get("action", "respond")).lower()
    if action not in ("tool", "respond"):
        action = "respond"
    return {
        "action": action,
        "tool": str(data.get("tool", "")),
        "tool_input": data.get("tool_input") if isinstance(data.get("tool_input"), dict) else {},
        "message": str(data.get("message", "")),
    }


def build_agent_prompt(
    *,
    history: list[dict[str, str]],
    tool_trace: list[dict[str, Any]],
    user_message: str,
    attachment_names: list[str],
) -> str:
    lines = ["Conversation:"]
    for row in history[-settings.chat_message_history_limit :]:
        lines.append(f"{row['role'].upper()}: {row['content'][:1200]}")
    if attachment_names:
        lines.append(f"[User attached: {', '.join(attachment_names)}]")
    lines.append(f"USER: {user_message}")
    if tool_trace:
        lines.append("\nTool results this turn:")
        lines.append(json.dumps(tool_trace, ensure_ascii=False)[:6000])
    lines.append("\nNext JSON action:")
    return "\n".join(lines)
