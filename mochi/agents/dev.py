"""Dev agent — plans a stage, executes the data pipeline, reports artefacts."""

from __future__ import annotations

import json
import time
from typing import Any

from ..tools import list_tools
from ..workflows.stages import STAGE_PROGRAMS, RunContext
from .base import BaseAgent, load_prompt, render

SAFE_PARAM_KEYS = {
    "ppi_limit", "panel_cap", "min_abs_r", "coexpr_fdr", "max_candidates", "literature_limit",
    "min_signaling", "scoring_limit", "druggability_limit", "weights",
}


class DevAgent(BaseAgent):
    name = "dev_agent"
    role = "developer"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.system_prompt = load_prompt("dev", self.prompts_dir)

    # ------------------------------------------------------------------
    def plan_stage(self, stage_id: str, plan_step: dict, ctx: RunContext, tool_names: list[str]) -> dict:
        user = render(
            """Plan the analysis for one stage of the target-discovery workflow.

TARGET: {target}
DISEASE: {disease}
STAGE: {stage_id} - {name}
GOAL: {goal}
TEMPLATE STEP: {template_step}
AVAILABLE TOOLS (you may only use these): {tools}
CURRENT PARAMETERS: {params}

Decide the concrete analysis: which tools to call, in what order, which statistics to compute,
and whether any parameter should be changed. Return JSON with keys:
{"steps": ["..."], "tools": ["..."], "params": {...}, "expected_outputs": ["..."]}""",
            target=ctx.target,
            disease=ctx.disease,
            stage_id=stage_id,
            name=plan_step.get("name", ""),
            goal=plan_step.get("goal", ""),
            template_step=json.dumps(plan_step, ensure_ascii=False)[:1500],
            tools=", ".join(sorted(tool_names)),
            params=json.dumps(ctx.params, ensure_ascii=False),
        )
        res = self.ask(kind="dev.plan", user=user, context={"stage": stage_id, "plan_step": plan_step})
        self.log("dev.plan", res)
        return res

    # ------------------------------------------------------------------
    def execute(self, stage_id: str, ctx: RunContext, plan_step: dict | None = None) -> dict:
        plan_step = plan_step or {}
        tool_names = [t.name for t in list_tools()]
        advice = self.plan_stage(stage_id, plan_step, ctx, tool_names)

        # apply only whitelisted parameter overrides suggested by the agent
        overrides = {k: v for k, v in (advice.get("params") or {}).items() if k in SAFE_PARAM_KEYS}
        if overrides:
            ctx.params.update(overrides)
            self.log("params.override", overrides)

        from ..scenarios import get as get_scenario

        stages = get_scenario(ctx.scenario).stages
        fn = stages.get(stage_id)
        if fn is None:
            return {"stage": stage_id, "status": "failed", "error": f"no stage program for {stage_id}"}

        t0 = time.time()
        self.banner(f"executing {stage_id}")
        try:
            result = fn(ctx)
        except Exception as exc:  # noqa: BLE001
            self.log("stage.error", f"{type(exc).__name__}: {exc}")
            return {
                "stage": stage_id,
                "name": plan_step.get("name", stage_id),
                "status": "failed",
                "error": f"{type(exc).__name__}: {exc}",
                "duration_s": round(time.time() - t0, 1),
                "findings": [],
                "tool_calls": [],
                "artefacts": {},
            }

        result["agent_plan"] = {
            "steps": advice.get("steps", []),
            "tools": advice.get("tools", []),
            "rationale": advice.get("rationale", ""),
        }
        result["code"] = advice.get("code", "") or _pseudo_code(stage_id, result)
        self.log("stage.result", {
            "stage": stage_id,
            "status": result.get("status"),
            "findings": result.get("findings", [])[:6],
        })
        self.memory.collaboration.put(f"{stage_id}.result", {
            "status": result.get("status"),
            "findings": result.get("findings", []),
            "artefacts": result.get("artefacts", {}),
        }, author=self.name)
        self.memory.auto.record(self.name, stage_id, result.get("status") == "ok", time.time() - t0)
        return result


def _pseudo_code(stage_id: str, result: dict) -> str:
    tools = result.get("tool_calls", [])
    lines = [f"# {stage_id}: executed by the stage program registry"]
    for t in tools:
        lines.append(f"#   {t}(...)")
    return "\n".join(lines)
