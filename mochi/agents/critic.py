"""Critic agent: deterministic evidence audit + LLM judgement.

Design note: the audit (``_audit``) is pure Python and cannot be talked out of a
failure by the model; the LLM contributes the *judgement*, the proposed tool
requests and the weight calibration, and the agent reconciles the two. A
scientific pipeline should never let a language model alone decide that a missing
control is acceptable.
"""

from __future__ import annotations

import json
from typing import Any

from ..tools import TOOLS, list_tools
from ..tools.scoring import DEFAULT_WEIGHTS, normalise_weights
from ..workflows.stages import RunContext
from .base import BaseAgent, load_prompt, render


class CriticAgent(BaseAgent):
    name = "critic_agent"
    role = "critic"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.system_prompt = load_prompt("critic", self.prompts_dir)

    # ------------------------------------------------------------------
    def _audit(self, stage: str, result: dict, ctx: RunContext) -> dict:
        """Hard, deterministic evidence checks. Returns severity + findings."""
        # scenario-specific audit when the scenario ships one
        from ..scenarios import get as get_scenario

        try:
            sc = get_scenario(ctx.scenario)
        except KeyError:
            sc = None
        if sc is not None and sc.audit is not None:
            checks: list[dict] = []
            severity = 0
            for c in sc.audit(stage, result, ctx):
                checks.append({"claim": c["claim"], "supported": bool(c["supported"]), "why": c.get("why", "")})
                if not c["supported"] and c.get("hard", True):
                    severity = max(severity, 1)
            verdict = ["accept", "revise", "evolve"][min(severity, 2)]
            return {"verdict": verdict, "checks": checks, "severity": severity}

        checks: list[dict] = []
        severity = 0  # 0 accept, 1 revise, 2 evolve

        def check(claim: str, ok: bool, why: str, hard: bool = True) -> None:
            nonlocal severity
            checks.append({"claim": claim, "supported": bool(ok), "why": why})
            if not ok and hard:
                severity = max(severity, 1)

        if stage == "stage_1":
            prof = ctx.state.get("profile", {})
            check("Anchor protein resolved in UniProt",
                  bool(prof.get("uniprot", {}).get("ok")),
                  "topology cannot be established without a UniProt entry")
            check("Topology constraint derived",
                  bool(prof.get("topology", {}).get("architecture")),
                  "the effector hypothesis depends on the anchor's topology",
                  hard=False)
            check("Disease association retrieved",
                  prof.get("opentargets_associations", {}).get("disease_score") is not None,
                  "no Open Targets score for the disease", hard=False)
            check("Tumour expression retrieved",
                  bool(prof.get("expression", {}).get("ok")), "no cBioPortal expression data")
            check("At least 3 independent evidence types",
                  sum(1 for k in ("uniprot", "opentargets_associations", "expression", "alterations", "pubmed")
                      if (prof.get(k) or {}).get("ok")) >= 3,
                  "the profile must not rest on a single source")

            # proactive capability gap: a non-signalling anchor forces a competence test
            topo = prof.get("topology", {}) or {}
            if not topo.get("signaling_competent") and "score_signaling_potential" not in TOOLS:
                severity = max(severity, 2)
                checks.append({
                    "claim": "Tool Ocean can test whether a candidate can transduce a signal",
                    "supported": False,
                    "why": (
                        f"{ctx.target} cannot transduce a signal itself "
                        f"({topo.get('architecture', 'no intracellular domain')}), so every candidate must be "
                        f"scored for intrinsic signalling competence, and the ocean has no such tool"
                    ),
                })

        elif stage == "stage_2":
            cands = ctx.state.get("candidates", [])
            check("Candidate pool is non-trivial", len(cands) >= 10, f"only {len(cands)} candidates")
            src = {s for c in cands for s in (c.get("sources") or "").split("|") if s}
            check("Candidates come from >=2 independent sources", len(src) >= 2, f"sources used: {sorted(src)}")
            coexpr = [c for c in cands if (c.get("coexpr_r") or 0) != 0]
            check("Co-expression branch is represented", len(coexpr) >= 5, f"{len(coexpr)} candidates with r")
            check("Physical interaction branch is represented",
                  any("PPI" in (c.get("sources") or "") for c in cands),
                  "no PPI partner in the pool", hard=False)

        elif stage == "stage_3":
            if result.get("capability_gap"):
                severity = 2
                checks.append({
                    "claim": "Tool Ocean covers signalling competence",
                    "supported": False,
                    "why": "no tool can quantify intrinsic signalling competence",
                })
            else:
                scored = [c for c in ctx.state.get("candidates", []) if c.get("signaling_score") is not None]
                check("Signalling scores computed", len(scored) >= 5, f"{len(scored)} scored")
                check("Scorer discriminates",
                      bool(scored) and max(c["signaling_score"] for c in scored) >= 0.6,
                      "no candidate reaches the signalling threshold, so the scorer may be miscalibrated")
                check("Scorer validated",
                      bool(ctx.state.get("scorer_validation", {}).get("passed")),
                      "positive/negative controls were not re-run in this session", hard=False)

        elif stage == "stage_4":
            ranking = ctx.state.get("ranking", [])
            check("Ranking produced", len(ranking) >= 5, f"{len(ranking)} ranked candidates")
            if ranking:
                top = ranking[0]
                dims = {k: v for k, v in (top.get("dimensions") or {}).items() if v is not None}
                check("Top candidate has >=5 dimensions", len(dims) >= 5, f"{len(dims)} dimensions")
                check("Top candidate is consistent", bool(top.get("consistent")),
                      "the top candidate's evidence dimensions disagree")
                check("Ranking is not a single-dimension artefact",
                      (top.get("n_supporting_dimensions") or 0) >= 3,
                      f"top candidate supported by {top.get('n_supporting_dimensions')} dimensions")
                check("Weights sum to 1",
                      abs(sum((ctx.state.get("weights") or {}).values()) - 1.0) < 1e-6,
                      "weights are not normalised")

        verdict = ["accept", "revise", "evolve"][min(severity, 2)]
        return {"verdict": verdict, "checks": checks, "severity": severity}

    # ------------------------------------------------------------------
    def review(self, stage_id: str, result: dict, ctx: RunContext) -> dict:
        audit = self._audit(stage_id, result, ctx)
        metrics = {
            "status": result.get("status"),
            "findings": result.get("findings", []),
            "n_candidates": result.get("n_candidates"),
            "weights": result.get("weights"),
            "top_ranking": (result.get("top_ranking") or [])[:3],
            "capability_gap": result.get("capability_gap", False),
            "audit": audit,
        }
        user = render(
            """Review this completed stage of a target-discovery workflow.

TARGET: {target}     DISEASE: {disease}
STAGE: {stage_id}
HARD AUDIT (deterministic, cannot be overridden): {audit}
STAGE RESULT: {metrics}
TOOL OCEAN (names only): {tools}

Decide the verdict, and - only if a capability is genuinely missing - specify a new tool.
You may also calibrate dimension weights for the final ranking (they must sum to 1.0).
Return the JSON object defined in your system prompt.""",
            target=ctx.target,
            disease=ctx.disease,
            stage_id=stage_id,
            audit=json.dumps(audit, ensure_ascii=False),
            metrics=json.dumps(metrics, ensure_ascii=False)[:6000],
            tools=", ".join(sorted(t.name for t in list_tools())),
        )
        llm = self.ask(kind="critic.review", user=user,
                       context={"stage": stage_id, "audit": audit, "metrics": metrics})
        self.log("critic.review", {k: llm.get(k) for k in ("verdict", "scores", "gaps")})

        # reconcile: the audit has veto power
        verdict = str(llm.get("verdict", "accept")).lower()
        if verdict not in ("accept", "revise", "evolve"):
            verdict = "accept"
        order = {"accept": 0, "revise": 1, "evolve": 2}
        final_verdict = max([verdict, audit["verdict"]], key=lambda v: order[v])

        weights = llm.get("weight_adjustments")
        if isinstance(weights, dict) and weights:
            weights = normalise_weights(weights)
        else:
            weights = None

        review = {
            "stage": stage_id,
            "verdict": final_verdict,
            "llm_verdict": verdict,
            "scores": llm.get("scores") or {},
            "gaps": llm.get("gaps") or [],
            "evidence_checks": audit["checks"],
            "tool_requests": llm.get("tool_requests") or [],
            "weight_adjustments": weights,
            "reasoning": llm.get("reasoning") or llm.get("_text", ""),
        }
        self.memory.collaboration.put(f"{stage_id}.critique", review, author=self.name)
        self.memory.auto.record(self.name, stage_id, final_verdict == "accept", 0.0)
        if final_verdict == "evolve" and not review["tool_requests"]:
            review["tool_requests"] = [_default_tool_request(stage_id)]
        return review

    # ------------------------------------------------------------------
    def calibrate(self, ranking: list[dict], ctx: RunContext) -> dict:
        """Final weight calibration before the report is written."""
        summary = [
            {
                "gene": r["gene"],
                "composite": r["composite"],
                "dimensions": r.get("dimensions"),
                "n_supporting": r.get("n_supporting_dimensions"),
            }
            for r in ranking[:10]
        ]
        user = render(
            """Calibrate the six evidence weights for the final ranking.

CANDIDATE SCORES: {summary}
CURRENT WEIGHTS: {weights}
STAGE CRITIQUES: {critiques}

Rules: novelty and druggability matter for a discovery project; association and signalling are the
biological core; a dimension with poor coverage should receive less weight. Return JSON:
{{"weights": {{"association": 0.24, "signaling": 0.22, "crc_evidence": 0.20,
"pathway_centrality": 0.10, "novelty": 0.10, "druggability": 0.14}}, "reasoning": "..."}}""",
            summary=json.dumps(summary, ensure_ascii=False)[:4000],
            weights=json.dumps(ctx.state.get("weights") or DEFAULT_WEIGHTS),
            critiques=json.dumps([c for c in ctx.state.get("critiques", [])][-2:], ensure_ascii=False)[:2500],
        )
        res = self.ask(kind="manager.weights", user=user, context={"ranking": summary})
        weights = res.get("weights") if isinstance(res.get("weights"), dict) else None
        weights = normalise_weights(weights or ctx.state.get("weights") or DEFAULT_WEIGHTS)
        self.log("weights.calibrated", weights)
        return {"weights": weights, "reasoning": res.get("reasoning", "")}


def _default_tool_request(stage: str) -> dict:
    return {
        "name": "score_signaling_potential",
        "purpose": "Quantify whether a candidate protein can transduce a signal by itself.",
        "why_existing_tools_fail": (
            "The Tool Ocean can retrieve topology and domains, but nothing converts them into a "
            "calibrated, batch-computable signalling-competence score with control-based validation."
        ),
        "inputs": ["genes: list[str]"],
        "outputs": ["signaling_score per gene", "component scores", "topology reason"],
        "algorithm": (
            "Weighted combination of (a) UniProt topology (TM segments + intracellular residues), "
            "(b) Pfam/InterPro signalling domain families, (c) function-annotation keywords, "
            "(d) subcellular localisation, with hard caps for GPI-anchored and secreted proteins."
        ),
        "validation": {
            "positive_controls": ["LRP6", "FZD1", "EGFR", "TNFRSF1A", "TGFBR1", "NOTCH1", "IL6ST"],
            "negative_controls": ["DPEP1", "CEACAM5", "ALB", "INS", "GAPDH", "LYZ"],
            "acceptance": "every positive >= 0.60 and every negative <= 0.35",
        },
    }
