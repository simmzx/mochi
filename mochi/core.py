"""Orchestration engine: the manager loop that drives the four agents.

Flow of one run
---------------
1. retrieve the most similar reasoning template from the library (TF-IDF)
2. manager.plan  -> four executable stages with goals, tools and success criteria
3. for each stage:
      dev.execute           (real data pipeline, artefacts written)
      critic.review         (deterministic audit + LLM judgement)
      if verdict == evolve  -> tool_creation.create -> dev.execute again
      if verdict == revise  -> tighten parameters -> dev.execute again
4. critic.calibrate weights -> re-rank the stored evidence
5. report generation (figures + markdown + evidence dossier + wet-lab plan)
6. manager writes the successful workflow back into the template library

Every step is appended to ``transcript.jsonl`` / ``llm_calls.jsonl`` /
``provenance.jsonl`` inside the run directory.
"""

from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import report as report_mod
from .agents.critic import CriticAgent
from .agents.dev import DevAgent
from .agents.manager import ManagerAgent
from .agents.tool_creation import ToolCreationAgent
from .knowledge import TemplateLibrary
from .llm import AgentLLM, get_llm
from .memory import MemoryManager
from .settings import SETTINGS, Settings
from .tools import TOOLS, dump_manifest, list_tools, load_dynamic_tools
from .tools import http as http_tools
from .tools.registry import call_tool
from .workflows.stages import RunContext, rebuild_ranking


@dataclass
class RunResult:
    run_id: str
    run_dir: Path
    plan: dict
    stage_results: list[dict]
    critiques: list[dict]
    ranking: list[dict]
    weights: dict
    tool_creation: dict | None = None
    report_path: Path | None = None
    summary_path: Path | None = None
    figures: list[str] = field(default_factory=list)
    narrative: str = ""
    elapsed_s: float = 0.0
    engine: str = "offline"
    task: str = ""
    task_source: str = "default"
    scenario: str = "target_discovery"

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "engine": self.engine,
            "scenario": self.scenario,
            "elapsed_s": round(self.elapsed_s, 1),
            "template": self.plan.get("template_id"),
            "task": self.task,
            "task_source": self.task_source,
            "stages": [
                {"stage": r.get("stage"), "name": r.get("name"), "status": r.get("status"),
                 "attempt": r.get("attempt", 1), "duration_s": r.get("duration_s"),
                 "findings": r.get("findings", [])}
                for r in self.stage_results
            ],
            "critiques": [
                {"stage": c.get("stage"), "verdict": c.get("verdict"),
                 "failed_checks": [x["claim"] for x in c.get("evidence_checks", []) if not x.get("supported")]}
                for c in self.critiques
            ],
            "weights": self.weights,
            "ranking": [
                {"rank": r["rank"], "gene": r["gene"], "composite": r["composite"],
                 "dimensions": r.get("dimensions"), "support": r.get("n_supporting_dimensions")}
                for r in self.ranking[:15]
            ],
            "tool_creation": {
                "tool": self.tool_creation.get("tool_name"),
                "registered": bool(self.tool_creation.get("registered_as")),
                "validation_passed": self.tool_creation.get("validation", {}).get("passed"),
            } if self.tool_creation else None,
            "files": {
                "report": str(self.report_path) if self.report_path else None,
                "summary": str(self.summary_path) if self.summary_path else None,
                "figures": self.figures,
                "run_dir": str(self.run_dir),
            },
            "narrative": self.narrative,
        }


class Mochi:
    """The multi-agent target-discovery system."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        verbose: bool = True,
        force_offline: bool = False,
        params: dict | None = None,
    ) -> None:
        self.settings = settings or SETTINGS
        self.verbose = verbose
        self.params = params or {}
        self.settings.outputs_dir.mkdir(parents=True, exist_ok=True)

        # Tool Ocean
        load_dynamic_tools(self.settings.created_tools_dir)
        self.initial_tools = sorted(TOOLS)

        # LLM
        if not force_offline:
            self.settings.validate()
        base_llm = get_llm(force_offline=force_offline)
        self.llm = AgentLLM(base_llm)
        self.engine = base_llm.name
        self.engine_banner = self.settings.engine_banner() if self.engine != "offline" else base_llm.name

        # Knowledge / memory
        self.library = TemplateLibrary(self.settings.templates_dir)
        self.memory: MemoryManager | None = None

        # Agents are (re)bound in run() once the run directory exists
        self.manager: ManagerAgent | None = None
        self.dev: DevAgent | None = None
        self.critic: CriticAgent | None = None
        self.toolmaker: ToolCreationAgent | None = None

    # ------------------------------------------------------------------
    def _bind_run(self, run_dir: Path) -> None:
        prompts_dir = self.settings.root / "mochi" / "prompts"
        self.memory = MemoryManager(self.library, session_path=run_dir / "transcript.jsonl")

        def record_llm(rec: dict) -> None:
            with open(run_dir / "llm_calls.jsonl", "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

        self.llm._recorder = record_llm  # attach the run-scoped recorder

        common = dict(llm=self.llm, memory=self.memory, prompts_dir=prompts_dir, run_dir=run_dir,
                      verbose=self.verbose)
        self.manager = ManagerAgent(**common)
        self.dev = DevAgent(**common)
        self.critic = CriticAgent(**common)
        self.toolmaker = ToolCreationAgent(
            blueprint_dir=self.settings.root / "mochi" / "toolblueprints",
            created_dir=self.settings.created_tools_dir,
            **common,
        )

    # ------------------------------------------------------------------
    def run(
        self,
        target: str,
        *,
        disease: str | None = None,
        disease_id: str | None = None,
        task: str | None = None,
        run_id: str | None = None,
        scenario: str = "target_discovery",
    ) -> RunResult:
        t_start = time.time()
        from .scenarios import get as get_scenario

        sc = get_scenario(scenario)
        disease = disease or self.settings.disease_name
        disease_id = disease_id or self.settings.disease_efo
        run_id = run_id or f"{time.strftime('%Y%m%d_%H%M%S')}_{scenario}_{target}".replace("/", "_")
        run_dir = self.settings.outputs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        http_tools.configure(cache_dir=self.settings.cache_dir, provenance_path=run_dir / "provenance.jsonl")
        load_dynamic_tools(self.settings.created_tools_dir)
        self._bind_run(run_dir)

        print(f"\n{'#' * 78}")
        print(f"# MOCHI-AIDD  run {run_id}")
        print(f"# scenario: {scenario} ({sc.label}) | target: {target} | tools: {len(TOOLS)}")
        print(f"# engine: {self.engine_banner}")
        print(f"{'#' * 78}")

        default_task = sc.default_task.replace("the anchor protein", target).replace("the enzyme", target) \
            .replace("the target molecule", target)
        task_text = (task or "").strip() or default_task
        task_source = "user" if (task or "").strip() else "default"
        (run_dir / "task.txt").write_text(
            f"task_source: {task_source}\nscenario: {scenario}\ntarget: {target}\ndisease: {disease}\n\n{task_text}\n",
            encoding="utf-8",
        )
        print(f"# task ({task_source}): {task_text[:160]}{'...' if len(task_text) > 160 else ''}")

        # ---- template retrieval ---------------------------------------
        # target discovery retrieves from the whole library; the other scenarios own their
        # template, so retrieval cannot drag a target-discovery workflow into their plan
        if self.settings.use_templates and sc.key == "target_discovery":
            templates = self.library.retrieve(task_text, top_k=3)
        else:
            templates = []
        # guarantee that the scenario's own template is available to the manager
        own = self.library.get(sc.template_id)
        if own is not None and all(t["skill_id"] != sc.template_id for t in templates):
            templates = [{"skill_id": own.skill_id, "name": own.name, "score": 1.0,
                          "similarity": 1.0, "success_rate": own.success_rate, "template": own}] + templates
        if self.verbose:
            print(f"\n[manager] retrieved {len(templates)} template(s): "
                  f"{[t['skill_id'] for t in templates]}")

        # ---- plan ------------------------------------------------------
        plan = self.manager.plan(target=target, disease=disease, templates=templates, task=task_text)
        if sc.stage_names:
            for i, name in enumerate(sc.stage_names):
                if i < len(plan.get("stages", [])):
                    plan["stages"][i]["name"] = name

        # ---- run context ----------------------------------------------
        ctx = RunContext(
            run_dir=run_dir,
            target=target,
            disease=disease,
            disease_id=disease_id,
            study=self.settings.cbioportal_study,
            scenario=scenario,
            params={
                "ppi_limit": 60,
                "panel_cap": 600,
                "min_abs_r": 0.30,
                "coexpr_fdr": 0.10,
                "max_candidates": 60,
                "literature_limit": 45,
                "min_signaling": 0.35,
                "scoring_limit": 40,
                "druggability_limit": 40,
                **self.params,
            },
            logger=print if self.verbose else None,
        )
        ctx.state["task"] = task_text

        stage_results: list[dict] = []
        critiques: list[dict] = []
        tool_creation: dict | None = None

        # ---- stage loop ------------------------------------------------
        for step in plan["stages"]:
            sid = step["id"]
            attempt = 0
            while True:
                attempt += 1
                result = self.dev.execute(sid, ctx, step)
                result["attempt"] = attempt
                stage_results.append(result)
                note = ""
                if result.get("capability_gap"):
                    note = f" (capability gap: {result.get('missing_tool')})"
                print(f"\n[manager] {sid} {result.get('status')}{note}")
                for f in (result.get("findings") or [])[:6]:
                    print(f"   - {f}")

                review = self.critic.review(sid, result, ctx)
                critiques.append(review)
                ctx.state.setdefault("critiques", []).append(review)
                print(f"[critic] {sid}: verdict={review['verdict']} "
                      f"(llm={review['llm_verdict']}, failed checks="
                      f"{sum(1 for c in review['evidence_checks'] if not c.get('supported'))})")

                action = self.manager.decide(review, attempt, sid)
                if action == "accept" or action == "accept_with_gaps":
                    break
                if action == "evolve" and self.settings.enable_tool_creation and tool_creation is None:
                    req = review["tool_requests"][0]
                    print(f"[manager] delegating tool creation to tool_creation_agent: {req.get('name')}")
                    tool_creation = self.toolmaker.create(req, ctx)
                    print(f"[tool_creation] {'registered' if tool_creation.get('ok') else 'FAILED'} "
                          f"{tool_creation.get('tool_name')} "
                          f"(validation={tool_creation.get('validation', {}).get('passed')})")
                    if tool_creation.get("ok"):
                        step["tools"] = list(dict.fromkeys(list(step.get("tools") or []) + [req["name"]]))
                    continue
                if action == "revise":
                    self._tighten(sid, ctx)
                    continue
                break

        # ---- dynamic weight calibration --------------------------------
        ranking = ctx.state.get("ranking", [])
        weights = ctx.state.get("weights") or {}
        if ranking and self.critic is not None:
            cal = self.critic.calibrate(ranking, ctx)
            if cal.get("weights"):
                weights = cal["weights"]
                ranking = rebuild_ranking(ctx, weights)
                print(f"[critic] weights re-calibrated -> {weights}")

        # ---- known-answer check (hindcast) ------------------------------
        expected = [g.strip().upper() for g in (ctx.params.get("expect_genes") or []) if g and g.strip()]
        known_answer: dict = {}
        if expected:
            cand_by_gene = {c["gene"]: c for c in ctx.state.get("candidates", [])}
            rank_by_gene = {r["gene"]: r for r in ranking}
            min_sig = float(ctx.params.get("min_signaling", 0.35))
            checks = []
            for g in expected:
                c = cand_by_gene.get(g) or {}
                r = rank_by_gene.get(g) or {}
                checks.append(
                    {
                        "gene": g,
                        "nominated_at_stage2": g in cand_by_gene,
                        "sources": c.get("sources"),
                        "coexpression_r": c.get("coexpr_r"),
                        "pathway_information_content": c.get("pathway_information_content"),
                        "signaling_score": c.get("signaling_score"),
                        "passed_signalling_threshold": (c.get("signaling_score") or 0) >= min_sig,
                        "scored_at_stage4": g in rank_by_gene,
                        "rank": r.get("rank"),
                        "composite": r.get("composite"),
                        "n_supporting_dimensions": r.get("n_supporting_dimensions"),
                        "dimensions": r.get("dimensions"),
                    }
                )
            known_answer = {
                "expected": expected,
                "recall_at_stage2": round(sum(1 for c in checks if c["nominated_at_stage2"]) / len(checks), 3),
                "recall_at_stage4": round(sum(1 for c in checks if c["scored_at_stage4"]) / len(checks), 3),
                "checks": checks,
            }
            (run_dir / "known_answer.json").write_text(
                json.dumps(known_answer, indent=1, ensure_ascii=False), encoding="utf-8")
            print(f"[manager] known-answer check: " + ", ".join(
                f"{c['gene']} nominated={c['nominated_at_stage2']} rank={c['rank']}" for c in checks))

        # ---- self-evolution: learn a template --------------------------
        # Gate mirrors MOCHI's critic_score >= 0.6 rule: the run must have produced
        # usable artefacts and the critic's average score must clear 3.5/5.
        scores = [
            v for c in critiques for v in (c.get("scores") or {}).values()
            if isinstance(v, (int, float))
        ]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        all_ok = all(r.get("status") in ("ok", "partial") for r in stage_results)
        accepted = bool(all_ok and avg_score >= 3.5 and ranking)
        learned = None
        if accepted:
            learned = self.manager.save_skill(
                target=target, disease=disease, plan=plan, stage_results=stage_results,
                critiques=critiques, library=self.library,
            )
            if learned:
                print(f"[manager] learned template saved: {learned.skill_id} (critic avg {avg_score:.2f}/5)")
                self.library.record_outcome(learned.skill_id, True, avg_score / 5.0)

        # ---- report ----------------------------------------------------
        prov = http_tools.PROVENANCE.summary()
        run_meta = {
            "run_id": run_id,
            "engine": self.engine,
            "date": time.strftime("%Y-%m-%d %H:%M"),
            "n_tool_calls": prov.get("n_calls", 0),
            "provenance_summary": prov,
            "case_script": "dpep1_crc_effector_target.py",
            "learned_template": learned.skill_id if learned else None,
            "known_answer": known_answer,
            "task": task_text,
            "task_source": task_source,
            "scenario": scenario,
        }
        if sc.report is not None:
            from . import report_generic

            figures = report_generic.make_figures(ctx, scenario)
            body = sc.report(ctx, stage_results, ranking, weights=weights)
            md = report_generic.build_scenario_report(
                ctx=ctx, scenario=scenario, plan=plan, stage_results=stage_results,
                critiques=critiques, figures=figures, run_meta=run_meta,
                body=body, scenario_def=sc,
            )
            narrative = ""
        else:
            survival = (ctx.state.get("survival") or {}).get(ranking[0]["gene"], {}) if ranking else None
            figures = report_mod.make_figures(run_dir, ranking, weights, survival,
                                              ranking[0]["gene"] if ranking else None)
            narrative = self.manager.synthesize(
                target=target, ranking=ranking, weights=weights,
                critiques=[{"verdict": c.get("verdict")} for c in critiques],
            ) if ranking else ""
            md = report_mod.build_report(
                ctx=ctx,
                plan=plan,
                stage_results=[r for r in stage_results],
                critiques=critiques,
                ranking=ranking,
                weights=weights,
                profile=ctx.state.get("profile", {}),
                tool_creation=tool_creation,
                figures=figures,
                run_meta=run_meta,
            )
        (run_dir / "report.md").write_text(md, encoding="utf-8")

        result = RunResult(
            run_id=run_id,
            run_dir=run_dir,
            plan=plan,
            stage_results=stage_results,
            critiques=critiques,
            ranking=ranking,
            weights=weights,
            tool_creation=tool_creation,
            report_path=run_dir / "report.md",
            figures=figures,
            narrative=narrative,
            elapsed_s=time.time() - t_start,
            engine=self.engine,
            task=task_text,
            task_source=task_source,
            scenario=scenario,
        )

        summary_path = run_dir / "run_summary.json"
        summary_path.write_text(
            json.dumps(result.to_dict() | {"memory": self.memory.summary() if self.memory else {}},
                       indent=1, ensure_ascii=False),
            encoding="utf-8",
        )
        result.summary_path = summary_path
        dump_manifest(self.settings.root)

        print(f"\n[manager] run complete in {result.elapsed_s:.0f}s -> {run_dir}")
        if ranking:
            top = ranking[0]
            print(f"[manager] top target: {top['gene']} (composite {top['composite']:.3f}, "
                  f"{top['n_supporting_dimensions']}/6 dimensions)")
        return result

    # ------------------------------------------------------------------
    def _tighten(self, stage_id: str, ctx: RunContext) -> None:
        """Parameter revision when the critic asks for a better analysis."""
        p = ctx.params
        if stage_id == "stage_2":
            p["min_abs_r"] = max(0.15, p.get("min_abs_r", 0.30) - 0.05)
            p["panel_cap"] = min(500, int(p.get("panel_cap", 260) * 1.4))
            p["max_candidates"] = min(100, int(p.get("max_candidates", 60) * 1.3))
        elif stage_id == "stage_4":
            p["scoring_limit"] = min(60, int(p.get("scoring_limit", 30) * 1.5))
            p["druggability_limit"] = min(40, int(p.get("druggability_limit", 20) * 1.5))
        elif stage_id == "stage_3":
            p["min_signaling"] = max(0.2, p.get("min_signaling", 0.35) - 0.05)
        else:
            p["retry"] = int(p.get("retry", 0)) + 1
        print(f"[manager] revised parameters for {stage_id}: "
              f"{json.dumps({k: v for k, v in p.items() if k in ('min_abs_r', 'panel_cap', 'max_candidates', 'min_signaling', 'scoring_limit')})}")
