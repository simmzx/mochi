"""Manager agent — plans, delegates, reconciles critic feedback and closes the run."""

from __future__ import annotations

import json
from typing import Any

from ..knowledge import Template
from ..tools import tool_arsenal_text
from .base import BaseAgent, load_prompt, render

STAGE_SEQUENCE = ["stage_1", "stage_2", "stage_3", "stage_4"]


class ManagerAgent(BaseAgent):
    name = "manager_agent"
    role = "manager"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.system_prompt = load_prompt("manager", self.prompts_dir)

    # ------------------------------------------------------------------
    def plan(self, *, target: str, disease: str, templates: list[dict], extra_context: str = "",
             task: str | None = None) -> dict:
        user = render(
            """Plan the investigation.

USER TASK: {task}
ANCHOR TARGET: {target}
DISEASE: {disease}
CONTEXT: {extra}

The reasoning templates have already been retrieved and are listed in your system prompt.
Use the most similar one, adapt its steps to this anchor/disease pair, and return the JSON plan
defined in your system prompt. The stages MUST map in order onto the four executable stage
programs (profile -> candidate generation -> signalling competence -> multi-evidence scoring);
you may rename them and refine goals, but do not add or drop executable stages.""",
            task=(task or "").strip() or f"Discover the unreported downstream effector target of {target} in {disease}",
            target=target,
            disease=disease,
            extra=extra_context or "none",
        )
        summary = []
        for t in templates:
            tpl_obj: Template = t["template"]
            summary.append(
                {
                    "skill_id": tpl_obj.skill_id,
                    "name": tpl_obj.name,
                    "similarity": round(t["similarity"], 3),
                    "workflow": [
                        {
                            "action": s.get("action", ""),
                            "description": (s.get("description") or "")[:260],
                            "tools": [
                                x.get("tool_id") if isinstance(x, dict) else x
                                for x in (s.get("tools_required") or [])
                            ],
                        }
                        for s in tpl_obj.workflow
                    ],
                }
            )
        plan = self.ask(
            kind="manager.plan",
            user=user,
            context={"target": target, "disease": disease, "task": task,
                     "templates": [t["skill_id"] for t in templates],
                     "template_summary": summary},
        )
        plan = self._reconcile(plan, templates, target, disease)
        self.log("plan", {
            "template_id": plan.get("template_id"),
            "stages": [s["name"] for s in plan["stages"]],
            "hypotheses": plan.get("hypotheses"),
        })
        self.memory.collaboration.put("plan", plan, author=self.name)
        return plan

    # ------------------------------------------------------------------
    def _reconcile(self, plan: dict, templates: list[dict], target: str, disease: str) -> dict:
        """Force a usable plan even if the LLM output is incomplete."""
        tpl: Template | None = templates[0]["template"] if templates else None
        stages = plan.get("stages") if isinstance(plan.get("stages"), list) else []
        if len(stages) != len(STAGE_SEQUENCE):
            stages = []
            for i, sid in enumerate(STAGE_SEQUENCE):
                step = (tpl.workflow[i] if tpl and i < len(tpl.workflow) else {})
                stages.append(
                    {
                        "id": sid,
                        "name": step.get("action") or f"Stage {i + 1}",
                        "goal": step.get("description", ""),
                        "tools": [t.get("tool_id") for t in (step.get("tools_required") or []) if isinstance(t, dict)]
                        or step.get("tools_required", []),
                        "deliverable": "see template",
                        "success_criteria": ["evidence retrieved", "critic accepts"],
                    }
                )
        for i, st in enumerate(stages):
            st["id"] = STAGE_SEQUENCE[i]
        return {
            "target": plan.get("target") or target,
            "disease": plan.get("disease") or disease,
            "template_id": plan.get("template_id") or (tpl.skill_id if tpl else "none"),
            "reasoning": plan.get("reasoning") or (tpl.description if tpl else ""),
            "stages": stages,
            "hypotheses": plan.get("hypotheses") or [],
            "risks": plan.get("risks") or [],
            "expected_failure_modes": plan.get("expected_failure_modes") or [],
        }

    # ------------------------------------------------------------------
    def decide(self, review: dict, attempt: int, stage_id: str = "") -> str:
        """Turn a critic verdict into an orchestration action."""
        verdict = review.get("verdict", "accept")
        if verdict == "accept":
            return "accept"
        if verdict == "evolve" and review.get("tool_requests"):
            return "evolve"
        if stage_id == "stage_4":
            # Re-running the scoring stage cannot repair a weak candidate pool; the
            # honest response is to accept with a documented caveat and let the
            # critic's weight calibration and the report's limitations section carry it.
            return "accept_with_gaps"
        return "revise" if attempt < 2 else "accept_with_gaps"

    # ------------------------------------------------------------------
    def save_skill(self, *, target: str, disease: str, plan: dict, stage_results: list[dict],
                   critiques: list[dict], library) -> Template | None:
        """Write the successful run back into the template library (self-evolution)."""
        tools_used = sorted({t for r in stage_results for t in (r.get("tool_calls") or [])})
        total_time = sum(r.get("duration_s", 0) for r in stage_results)
        # keep the last attempt of each stage (a stage may be re-run after tool creation)
        latest: dict[str, dict] = {}
        for r in stage_results:
            latest[r.get("stage", r.get("name", "?"))] = r
        ordered = list(latest.values())
        tpl = Template(
            skill_id=f"auto_{target.lower()}_{disease.split()[0].lower()}_discovery",
            name=f"Learned workflow: {target} effector target discovery in {disease}",
            domain="oncology_target_discovery",
            description=(
                f"Workflow learned from a successful run: {target} in {disease}. Stages: "
                + " -> ".join(r.get("name", r.get("stage", "")) for r in ordered)
            ),
            workflow=[
                {
                    "step": i + 1,
                    "action": r.get("name", r.get("stage")),
                    "description": "; ".join((r.get("findings") or [])[:3]),
                    "tools_required": r.get("tool_calls", []),
                    "agent": "dev" if r.get("stage") != "stage_4" else "dev+critic",
                }
                for i, r in enumerate(ordered)
            ],
            tools_required=[{"tool_id": t, "version": ">=1.0.0", "optional": False} for t in tools_used],
            tags=[target.lower(), disease.lower(), "learned", "effector target"],
            applicable_queries=[f"discover the downstream effector target of {target.lower()}"],
            quality_metrics={
                "success_count": 1,
                "failure_count": 0,
                "avg_completion_time_sec": round(total_time, 1),
                "avg_critic_score": round(
                    sum(1 for c in critiques if c.get("verdict") == "accept") / max(1, len(critiques)), 3
                ),
                "last_used": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
                "created_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
            },
            provenance={
                "created_by": "auto_summarizer",
                "source_run_id": None,
                "parent_skill_id": plan.get("template_id"),
                "changelog": [{"version": "1.0.0", "date": "", "changes": "summarised from a successful run"}],
            },
            status="experimental",
        )
        try:
            path = library.save_template(tpl, overwrite=True)
            self.log("skill.saved", str(path))
            return tpl
        except Exception as exc:  # noqa: BLE001
            self.log("skill.save_failed", str(exc))
            return None

    # ------------------------------------------------------------------
    def synthesize(self, *, target: str, ranking: list[dict], weights: dict, critiques: list[dict]) -> str:
        """Short narrative used in the run summary and the report header."""
        top = ranking[0] if ranking else None
        if not top:
            return f"No candidate could be prioritised for {target}."
        user = render(
            """Write the final scientific conclusion (6-10 sentences, no bullet points).

TARGET: {target}
TOP CANDIDATE: {top}
WEIGHTS: {weights}
CRITIQUES: {critiques}

Be explicit about what is established versus hypothesised, and name the decisive experiment.""",
            target=target,
            top=json.dumps({k: top.get(k) for k in ("gene", "composite", "dimensions", "supporting_dimensions")},
                           ensure_ascii=False),
            weights=json.dumps(weights, ensure_ascii=False),
            critiques=json.dumps([c.get("verdict") for c in critiques], ensure_ascii=False),
        )
        res = self.ask(
            kind="manager.synthesize",
            user=user,
            context={
                "top": {
                    "gene": top.get("gene"),
                    "composite": top.get("composite"),
                    "dimensions": top.get("dimensions"),
                    "supporting_dimensions": top.get("supporting_dimensions"),
                }
            },
        )
        text = res.get("text") or res.get("_text") or ""
        return text.strip()
