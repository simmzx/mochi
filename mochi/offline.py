"""Deterministic reference engine.

Purpose
-------
The framework must be usable and auditable **without** an LLM API key: a reviewer
can run the whole four-stage workflow and inspect exactly which decisions were
taken.  This engine replays the *same* agent contracts as an LLM would fill in,
but derives every value from the run's own evidence (counts, coverage, threshold
checks) using explicit rules.

It is not a language model and does not pretend to be one: every artefact it
produces is tagged ``engine="offline"``, and the prompts it answers are the same
ones a real model receives.  With ``MOCHI_ENGINE=openai`` (and a key) the exact
same agent classes call the real model instead - nothing else changes.

Rule design principles
----------------------
* Never invent a number: cite the counts and scores present in the context.
* Prefer a conservative verdict: if a hard audit check fails, the critic asks for
  revision or tool creation, exactly like the prompt demands.
* Keep outputs schema-valid so downstream parsing is identical in both modes.
"""

from __future__ import annotations

import json

from .llm import BaseLLM, LLMResult

DEFAULT_STAGES = [
    ("Profile construction", "Build the anchor's functional profile and derive its topological constraint."),
    ("Candidate generation", "Nominate candidate effectors from PPI, co-expression, pathway co-annotation and literature."),
    ("Signalling competence", "Score candidates for intrinsic signal-transduction capability."),
    ("Multi-evidence scoring", "Rank candidates on six dimensions with calibrated weights."),
]


def _j(x) -> str:
    return json.dumps(x, ensure_ascii=False)


class DeterministicEngine(BaseLLM):
    name = "offline"
    model = "deterministic-reference-engine"

    def complete(self, *, kind, system, user, context=None, schema=None, temperature=None, max_tokens=None) -> LLMResult:
        ctx = context or {}
        handler = {
            "manager.plan": self._manager_plan,
            "manager.weights": self._manager_weights,
            "manager.synthesize": self._manager_synthesize,
            "dev.plan": self._dev_plan,
            "critic.review": self._critic_review,
            "tool_creation.design": self._tool_design,
            "tool_creation.code": self._tool_code,
        }.get(kind)
        if handler is None:
            data = {"_text": f"[offline engine] no handler for kind={kind}"}
            return LLMResult(text=data["_text"], data=data, engine=self.name, model=self.model)
        data = handler(ctx)
        text = data.pop("_text", "") or _j(data)
        return LLMResult(text=text, data=data, engine=self.name, model=self.model)

    # ------------------------------------------------------------------
    def _manager_plan(self, ctx: dict) -> dict:
        target = ctx.get("target", "the anchor")
        disease = ctx.get("disease", "the disease")
        tpls = ctx.get("template_summary") or []
        tpl = tpls[0] if tpls else None
        steps = (tpl or {}).get("workflow") or []
        stages = []
        for i, (name, goal) in enumerate(DEFAULT_STAGES):
            if i < len(steps):
                name = steps[i].get("action") or name
                goal = steps[i].get("description") or goal
            stages.append(
                {
                    "id": f"stage_{i + 1}",
                    "name": name,
                    "goal": goal[:400],
                    "tools": steps[i].get("tools") if i < len(steps) else [],
                    "deliverable": "artefact table + numeric findings",
                    "success_criteria": [
                        "all required evidence types retrieved",
                        "critic audit passes",
                    ],
                }
            )
        reasoning = (
            f"{target} is investigated in {disease}. "
            + (
                f"The closest reasoning template ('{tpl.get('name')}', similarity {tpl.get('similarity', 0):.2f}) "
                f"decomposes the problem into {len(stages)} stages: "
                if tpl
                else "No close template was found, so the canonical four-stage effector-discovery plan is used: "
            )
            + "first establish what the anchor protein can and cannot do (topology, localisation, disease "
              "association), then generate candidates from four independent evidence channels rather than one, "
              "then score signalling competence - because an effector must be able to transduce a signal - "
              "and finally integrate six orthogonal evidence dimensions so that a single strong correlation "
              "cannot dominate the ranking. The critic reviews every stage and may force a tool to be built "
              "when a capability is missing."
        )
        return {
            "target": target,
            "disease": disease,
            "template_id": (tpl or {}).get("skill_id", "none"),
            "reasoning": reasoning,
            "stages": stages,
            "hypotheses": [
                f"{target} acts through a signal-transducing membrane partner rather than directly.",
                "The effector is co-expressed with the anchor in the disease cohort.",
                "The effector is a novel target rather than a heavily studied one.",
            ],
            "risks": [
                "public PPI databases are sparse for GPI-anchored proteins",
                "co-expression can reflect shared cell-type composition rather than regulation",
            ],
            "expected_failure_modes": [
                "no candidate passes the signalling-competence threshold",
                "survival data too sparse for some candidates",
            ],
            "_text": reasoning[:400],
        }

    # ------------------------------------------------------------------
    def _dev_plan(self, ctx: dict) -> dict:
        stage = ctx.get("stage", "stage")
        step = ctx.get("plan_step") or {}
        tools = step.get("tools") or []
        if isinstance(tools, list) and tools and isinstance(tools[0], dict):
            tools = [t.get("tool_id") for t in tools]
        names = {
            "stage_1": ["query_uniprot", "query_opentargets_associations", "query_cbioportal_expression",
                        "query_pubmed"],
            "stage_2": ["build_ppi_union", "query_cbioportal_coexpression", "pathway_coannotation"],
            "stage_3": ["score_signaling_potential"],
            "stage_4": ["multi_evidence_scoring", "query_cbioportal_survival", "query_pubmed_novelty",
                        "druggability_score"],
        }.get(stage, [])
        steps = {
            "stage_1": "Retrieve UniProt topology/domains, Open Targets disease association, TCGA expression and "
                       "PubMed counts; derive the topological constraint the effector must satisfy.",
            "stage_2": "Union of STRING/IntAct partners, KEGG-signalling-panel co-expression, Reactome "
                       "co-annotation and literature co-mention; filter to expressed genes.",
            "stage_3": "Score every candidate for intrinsic signalling competence and keep those above threshold.",
            "stage_4": "Assemble six evidence dimensions, run survival and druggability, and rank with "
                       "calibrated weights.",
        }
        return {
            "steps": [steps.get(stage, "execute the stage program")],
            "tools": names,
            "params": {},
            "expected_outputs": [f"{stage}_*.csv", f"{stage}_*.json"],
            "_text": steps.get(stage, ""),
        }

    # ------------------------------------------------------------------
    def _critic_review(self, ctx: dict) -> dict:
        audit = ctx.get("audit") or {}
        checks = audit.get("checks") or []
        failed = [c for c in checks if not c.get("supported")]
        severity = audit.get("severity", 0)
        verdict = ["accept", "revise", "evolve"][severity] if severity <= 2 else "evolve"
        stage = ctx.get("stage", "stage")

        base = {"tool_adequacy": 4, "evidence_sufficiency": 4, "directionality": 4,
                "statistical_validity": 4, "biological_plausibility": 4}
        if failed:
            base["evidence_sufficiency"] = 2
            base["tool_adequacy"] = 2 if severity >= 2 else 3
            base["directionality"] = 3
        gaps = [f"{c['claim']}: {c['why']}" for c in failed]

        tool_requests = []
        if severity >= 2 or (stage == "stage_3" and any("signalling" in c["claim"].lower() for c in failed)):
            tool_requests = [{
                "name": "score_signaling_potential",
                "purpose": "Quantify whether a candidate protein can transduce a signal by itself.",
                "why_existing_tools_fail": (
                    "The Tool Ocean retrieves topology and domain annotations but cannot convert them into a "
                    "calibrated, batch-computable signalling-competence score; without it the effector "
                    "criterion (must transduce a signal) cannot be enforced."
                ),
                "inputs": ["genes: list[str]"],
                "outputs": ["signaling_score", "component scores", "topology reason"],
                "algorithm": "Weighted UniProt topology + Pfam family + annotation + localisation, with hard caps "
                             "for GPI-anchored and secreted proteins.",
                "validation": {
                    "positive_controls": ["LRP6", "FZD1", "EGFR", "TNFRSF1A", "TGFBR1", "NOTCH1", "IL6ST"],
                    "negative_controls": ["DPEP1", "CEACAM5", "ALB", "INS", "GAPDH", "LYZ"],
                    "acceptance": "positives >= 0.60, negatives <= 0.35",
                },
            }]

        weights = None
        if stage == "stage_4":
            weights = {"association": 0.24, "signaling": 0.22, "crc_evidence": 0.20,
                       "pathway_centrality": 0.10, "novelty": 0.10, "druggability": 0.14}

        reasoning = (
            f"{len(checks)} hard checks were run; {len(failed)} failed. "
            + ("; ".join(gaps) if gaps else "All checks passed: the evidence is sufficient to accept the stage.")
        )
        return {
            "stage": stage,
            "verdict": verdict,
            "scores": base,
            "gaps": gaps,
            "evidence_checks": checks,
            "tool_requests": tool_requests,
            "weight_adjustments": weights,
            "reasoning": reasoning,
            "_text": reasoning,
        }

    # ------------------------------------------------------------------
    def _manager_weights(self, ctx: dict) -> dict:
        ranking = ctx.get("ranking") or []
        n = len(ranking) or 1
        coverage = {}
        for dim in ("association", "signaling", "crc_evidence", "pathway_centrality", "novelty", "druggability"):
            present = sum(1 for r in ranking if (r.get("dimensions") or {}).get(dim) is not None)
            coverage[dim] = present / n
        base = {"association": 0.24, "signaling": 0.22, "crc_evidence": 0.20,
                "pathway_centrality": 0.10, "novelty": 0.10, "druggability": 0.14}
        # dimensions that are widely missing lose weight; the freed mass goes to association + signalling
        weights = {k: base[k] * (0.5 + 0.5 * coverage.get(k, 0.0)) for k in base}
        total = sum(weights.values()) or 1.0
        weights = {k: round(v / total, 4) for k, v in weights.items()}
        missing = [k for k, v in coverage.items() if v < 0.6]
        reasoning = (
            "Weights were calibrated against evidence coverage: "
            + ", ".join(f"{k}={coverage[k]:.0%}" for k in coverage)
            + ". "
            + (f"Dimensions with poor coverage ({', '.join(missing)}) were down-weighted so the ranking is not "
               f"dominated by missing data." if missing else
               "All dimensions are well covered, so the prior biological weighting is kept.")
        )
        return {"weights": weights, "reasoning": reasoning, "_text": reasoning}

    # ------------------------------------------------------------------
    def _manager_synthesize(self, ctx: dict) -> dict:
        top = ctx.get("top") or {}
        if isinstance(top, str):
            top = {"gene": top}
        gene = top.get("gene", "the top candidate")
        dims = top.get("dimensions") or {}
        supported = [k for k, v in dims.items() if v is not None and v >= 0.6]
        text = (
            f"{gene} is the highest-ranked effector candidate (composite {top.get('composite', 0):.3f}). "
            f"Its support comes from {len(supported)} dimensions: {', '.join(supported) if supported else 'none above threshold'}. "
            "The causal direction is not established by co-expression or text mining; it rests on the topology "
            "argument (the anchor cannot transduce a signal) plus the candidate's own signalling competence. "
            "The decisive experiment is a reciprocal co-immunoprecipitation between the anchor and the candidate, "
            "followed by epistasis: loss of the anchor should reduce pathway output, and that reduction should be "
            "rescued by the candidate or abolished by its knockdown."
        )
        return {"text": text, "_text": text}

    # ------------------------------------------------------------------
    def _tool_design(self, ctx: dict) -> dict:
        spec = ctx.get("spec") or {}
        return {
            "tool_name": spec.get("name", "new_tool"),
            "algorithm": spec.get("algorithm", ""),
            "implementation_notes": "implemented from the vetted blueprint; validation via positive/negative controls",
            "validation_plan": spec.get("validation", {}),
            "_text": "design taken from the critic's tool request",
        }

    # ------------------------------------------------------------------
    def _tool_code(self, ctx: dict) -> dict:
        return {"code": "", "notes": "offline engine uses the blueprint implementation", "_text": ""}
