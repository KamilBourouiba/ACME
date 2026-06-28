"""Incident triage — dedupe spam and format Vera debug reports."""

from __future__ import annotations

import re
from typing import Any

from acme.demo.skills import SkillResult

_SPAM_PREFIXES = (
    "publish cooldown",
    "publish blocked",
    "redeploying",
    "github pages reachable",
    "fetched https://",
    "vm stack live",
    "shipping latest",
    "validating the suspected nginx",
    "validating nginx sensitive",
    "i'm validating the suspected nginx",
)

_DEDUP_AGENTS = frozenset({"nina", "sam", "jordan", "chen", "kai"})


def normalize_message(content: str) -> str:
    text = content.lower().strip()
    text = re.sub(r"https?://\S+", "<url>", text)
    text = re.sub(r"\s+", " ", text)
    return text[:220]


def message_fingerprint(content: str) -> str:
    """Stable topic stem for near-duplicate skill chatter."""
    text = content.lower().strip()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"/[\w.\-]+", "", text)
    words = sorted(set(re.findall(r"[a-z]{5,}", text)))
    return " ".join(words[:10])


def _word_set(content: str) -> set[str]:
    text = content.lower()
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"/[\w.\-]+", "", text)
    return set(re.findall(r"[a-z]{5,}", text))


def is_near_duplicate(content: str, recent: list[str], *, threshold: float = 0.5) -> bool:
    words = _word_set(content)
    if len(words) < 4:
        return False
    for prev in recent[-10:]:
        prev_words = _word_set(prev)
        if len(prev_words) < 4:
            continue
        overlap = len(words & prev_words) / len(words | prev_words)
        if overlap >= threshold:
            return True
    return False


def is_spam_duplicate(content: str, recent: list[str]) -> bool:
    norm = normalize_message(content)
    if not norm:
        return False
    for prefix in _SPAM_PREFIXES:
        if norm.startswith(prefix) and any(r.startswith(prefix) for r in recent):
            return True
    if norm in recent:
        return True
    if is_near_duplicate(content, recent):
        return True
    fp = message_fingerprint(content)
    if not fp or len(fp) < 20:
        return False
    recent_fps = [message_fingerprint(r) for r in recent[-12:]]
    return fp in recent_fps


def should_dedup_agent(agent_id: str) -> bool:
    return agent_id in _DEDUP_AGENTS


def failure_signature(observations: str, skill_results: list[SkillResult]) -> str:
    fails = [r.skill for r in skill_results if not r.ok]
    if not fails:
        return "ok"
    return "|".join(sorted(set(fails)))


def format_triage_report(
    *,
    observations: str,
    skill_results: list[SkillResult],
    deploy_block_reason: str | None = None,
    signature: str | None = None,
) -> str:
    fails = [r for r in skill_results if not r.ok]
    lines = ["*Incident triage* — consolidated status (no repeat spam):"]
    if deploy_block_reason:
        lines.append(f"• Deploy gate: {deploy_block_reason}")
    if signature and signature != "ok":
        lines.append(f"• Active failure set: `{signature}`")
    for result in fails[:6]:
        lines.append(f"• `{result.skill}` — {result.summary[:120]}")
    if not fails and deploy_block_reason:
        lines.append("• Probes green; deploy blocked by policy/cooldown.")
    elif not fails:
        lines.append("• All runtime probes passed.")
    lines.append("Next: fix root cause once, then single deploy — not blind retries.")
    return "\n".join(lines)


def triage_detail(skill_results: list[SkillResult]) -> dict[str, Any]:
    return {
        "failing_skills": [r.skill for r in skill_results if not r.ok],
        "observations_preview": skill_results[0].summary if skill_results else "",
    }
