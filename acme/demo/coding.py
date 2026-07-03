"""LLM-driven code generation for demo squad agents — greenfield only."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from acme.config import settings
from acme.demo.site_guard import (
    is_pinned_static_file,
    is_protected_site_file,
    reference_site_file,
    safe_site_artifact,
)
from acme.llm.factory import get_llm_client

if TYPE_CHECKING:
    from acme.demo.agents import DemoAgent
    from acme.demo.script import DemoBeat

BELIEF_OBS_BRIEF = """
Belief Observatory is ACME's product demo. The website IS the product.

Requirements:
- Dark cinematic UI (Instrument Sans + IBM Plex Mono) — not generic AI slop
- Episodic stream, SVG belief graph, CRS meter, investigation scrubber
- Belief lifecycle: observation → hypothesis → contradiction → feedback → promoted belief
- FastAPI serves GET /api/trace with canonical investigation JSON
- Mobile: stack panels vertically below 900px, touch-friendly scrubber
- HTML links: href="css/observatory.css" src="js/app.js" — root-relative, NO /static/ prefix
- Agents edit static/css only — index.html, static/js/*, server.py and api/routes/* are pinned
"""

LANG_HINTS = {
    "css": "Mobile-first; @media (max-width: 900px) for stacked observatory layout.",
    "javascript": "Vanilla JS. BeliefObsAPI.loadTrace() for data. SVG graph rendering.",
    "html": "Link css/observatory.css and js/*.js root-relative. NEVER /static/ prefix.",
    "python": "FastAPI + asyncpg. belief_data.py holds canonical trace.",
    "markdown": "Technical architecture doc for the squad.",
}


def _strip_fences(text: str) -> str:
    text = text.strip()
    fence = re.search(r"```(?:\w+)?\s*([\s\S]*?)```", text)
    if fence:
        return fence.group(1).strip()
    return text


def _related_context(path: str, artifacts: dict[str, str], *, max_chars: int = 6000) -> str:
    parts: list[str] = []
    total = 0
    prefix = "/".join(path.split("/")[:-1])
    for name, body in sorted(artifacts.items()):
        if name == path or not body.strip():
            continue
        same_dir = prefix and name.startswith(prefix + "/")
        shared = path.startswith("static/") and name.startswith("static/")
        api = path.startswith("api/") and name.startswith("api/")
        if not (same_dir or shared or api or name == "static/index.html"):
            continue
        chunk = f"--- {name} ---\n{body[:2000]}\n"
        if total + len(chunk) > max_chars:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n".join(parts)


async def generate_agent_code(
    agent: DemoAgent,
    beat: DemoBeat,
    *,
    artifacts: dict[str, str],
) -> str:
    """Ask the assigned agent to write a file for the current beat."""
    path = beat.code_file or ""
    norm = path.replace("\\", "/")
    if norm and (is_protected_site_file(norm) or is_pinned_static_file(norm)):
        pinned = reference_site_file(norm)
        if pinned:
            return pinned
    lang = beat.code_lang or "text"
    related = _related_context(path, artifacts)
    hint = LANG_HINTS.get(lang, "Write complete, runnable file content only.")

    system = (
        f"{agent.system_prompt}\n\n"
        "You are committing code to the Belief Observatory repo. Output ONLY the raw file contents — "
        "no markdown fences, no explanation before or after."
    )
    prompt = f"""{BELIEF_OBS_BRIEF}

Task: {beat.content}
File: {path}
Language: {lang}
Hint: {hint}

Already committed in this branch:
{related or "(empty repo — you define conventions first)"}

Write the complete `{path}` now:"""

    llm = get_llm_client()
    model = settings.demo_azure_deployment or None
    try:
        raw = await llm.generate(
            prompt,
            system=system,
            model=model,
            temperature=0.25,
            timeout=float(settings.demo_code_timeout_sec),
        )
        code = _strip_fences(raw)
        if code.strip():
            return safe_site_artifact(path, code, previous=artifacts.get(path))
    except Exception:
        pass

    return f"// {agent.name} — pending: {beat.content}\n"
