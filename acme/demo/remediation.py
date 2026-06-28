"""Remediation loop guard — pick VM fixes and stop useless repeats."""

from __future__ import annotations

from dataclasses import dataclass, field

from acme.demo.skills import SkillResult
from acme.demo.vm_exec import REMEDIATION_RECIPES, pick_remediation_recipe, run_recipe


@dataclass
class RemediationState:
    attempts_by_key: dict[str, int] = field(default_factory=dict)
    last_outputs: list[str] = field(default_factory=list)

    def attempt_key(self, signature: str, recipe: str) -> str:
        return f"{signature}::{recipe}"

    def bump(self, signature: str, recipe: str) -> int:
        key = self.attempt_key(signature, recipe)
        self.attempts_by_key[key] = self.attempts_by_key.get(key, 0) + 1
        return self.attempts_by_key[key]

    def exhausted(self, signature: str, recipe: str, *, cap: int = 2) -> bool:
        return self.attempts_by_key.get(self.attempt_key(signature, recipe), 0) >= cap

    def reset_signature(self, signature: str) -> None:
        drop = [k for k in self.attempts_by_key if k.startswith(f"{signature}::")]
        for k in drop:
            del self.attempts_by_key[k]


def format_remediation_message(
    *,
    recipe: str,
    command: str,
    result: dict,
    signature: str,
) -> str:
    ok = result.get("ok", False)
    rc = result.get("returncode")
    stdout = (result.get("stdout") or "")[:1200]
    stderr = (result.get("stderr") or "")[:600]
    err = result.get("error")
    lines = [
        f"*VM remediation* — `{recipe}` on signature `{signature}`",
        f"```\n$ {command}\n```",
    ]
    if err:
        lines.append(f"Error: {err}")
    else:
        lines.append(f"exit={rc} ok={ok}")
    if stdout.strip():
        lines.append(f"```stdout\n{stdout.strip()}\n```")
    if stderr.strip():
        lines.append(f"```stderr\n{stderr.strip()}\n```")
    return "\n".join(lines)


async def execute_remediation(
    *,
    signature: str,
    state: RemediationState,
    attempt_cap: int = 2,
    recipe: str | None = None,
    command: str | None = None,
) -> tuple[SkillResult, str, str]:
    if recipe and recipe in REMEDIATION_RECIPES:
        chosen_recipe = recipe
    elif command:
        chosen_recipe = "custom"
    else:
        attempt_idx = sum(
            1 for k in state.attempts_by_key if k.startswith(f"{signature}::")
        )
        chosen_recipe = pick_remediation_recipe(signature=signature, attempt=attempt_idx)

    if state.exhausted(signature, chosen_recipe, cap=attempt_cap):
        return (
            SkillResult(
                skill="vm_remediate",
                ok=False,
                summary=f"recipe {chosen_recipe} exhausted for {signature}",
                detail={"signature": signature, "recipe": chosen_recipe},
            ),
            chosen_recipe,
            command or REMEDIATION_RECIPES.get(chosen_recipe, ""),
        )

    state.bump(signature, chosen_recipe)

    if command and chosen_recipe == "custom":
        from acme.demo.vm_exec import exec_on_vm

        result = await exec_on_vm(command)
    else:
        result = await run_recipe(chosen_recipe)

    cmd = result.get("command") or REMEDIATION_RECIPES.get(chosen_recipe, command or "")
    ok = bool(result.get("ok")) and result.get("returncode", 1) == 0
    if not ok and "HTTP/" in (result.get("stdout") or ""):
        ok = "200" in (result.get("stdout") or "") or '"status":"ok"' in (result.get("stdout") or "")

    skill = SkillResult(
        skill="vm_remediate",
        ok=ok,
        summary=f"{chosen_recipe} exit={result.get('returncode')} ok={ok}",
        detail=result,
    )
    return skill, chosen_recipe, cmd
