"""Stage programs: the data-plane that the Dev agent executes.

Each function takes a :class:`RunContext`, performs one stage of the reasoning
template with real database queries and real statistics, writes artefacts to the
run directory, and returns a structured result the critic can review.

The control plane (which stages run, with which parameters, and whether a stage is
re-run after a tool has been created) lives in :mod:`mochi.core` and is
driven by the manager/critic agents.  This separation is deliberate: an LLM must
never be the component that computes a p-value.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .. import stats
from ..tools import registry
from ..tools.cbioportal import (
    fetch_alterations_batch,
    fetch_clinical,
    fetch_expression_matrix,
    survival_from_matrix,
)
from ..tools.pathways import load_library


# ---------------------------------------------------------------------------
# run context
# ---------------------------------------------------------------------------
@dataclass
class RunContext:
    run_dir: Path
    target: str
    disease: str
    disease_id: str
    study: str
    params: dict = field(default_factory=dict)
    state: dict = field(default_factory=dict)
    logger: Callable[[str], None] | None = None
    scenario: str = "target_discovery"

    def log(self, msg: str) -> None:
        if self.logger:
            self.logger(msg)

    def path(self, name: str) -> Path:
        p = Path(self.run_dir) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def save_json(self, name: str, obj: Any) -> Path:
        p = self.path(name)
        p.write_text(json.dumps(obj, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        return p

    def save_csv(self, name: str, rows: list[dict]) -> Path:
        p = self.path(name)
        if not rows:
            p.write_text("", encoding="utf-8")
            return p
        keys = list(rows[0].keys())
        lines = [",".join(keys)]
        for r in rows:
            vals = []
            for k in keys:
                v = r.get(k)
                if isinstance(v, (list, dict)):
                    v = json.dumps(v, ensure_ascii=False)
                s = "" if v is None else str(v)
                if any(c in s for c in ',"\n'):
                    s = '"' + s.replace('"', '""') + '"'
                vals.append(s)
            lines.append(",".join(vals))
        p.write_text("\n".join(lines), encoding="utf-8")
        return p


def _call(name: str, **kwargs) -> dict:
    res = registry.call_tool(name, **kwargs)
    return res if isinstance(res, dict) else {"ok": False, "error": str(res)}


# ---------------------------------------------------------------------------
# candidate panel construction
# ---------------------------------------------------------------------------
SIGNALING_PATHWAY_PATTERNS = (
    "Wnt", "Notch", "TGF", "Hippo", "ErbB", "Jak-STAT", "NF-kappa", "Hedgehog",
    "VEGF", "Cytokine", "Chemokine", "Ras", "Rap1", "MAPK", "PI3K", "Calcium",
    "cAMP", "Phosphatidylinositol", "Sphingolipid", "TNF", "Toll-like", "B cell receptor",
    "T cell receptor", "FC epsilon", "RIG-I", "NOD-like", "C-type lectin",
)

# Receptor-level developmental / oncogenic pathways whose members must not be
# truncated away by a hub-based cap: the effector of a GPI-anchored protein is
# far more likely to sit in Wnt/Notch/TGF-beta/Hippo/Hedgehog/ErbB than to be a
# promiscuous signalling hub.
CORE_RECEPTOR_PATHWAYS = ("Wnt", "Notch", "TGF", "Hippo", "Hedgehog", "ErbB")


def build_signaling_panel(target: str, cap: int = 600) -> dict:
    """A deterministic, biologically motivated co-expression panel.

    1. every gene annotated to a core receptor pathway (Wnt, Notch, TGF-beta,
       Hippo, Hedgehog, ErbB);
    2. filled up with signalling-pathway hubs (members of many signalling
       pathways) until ``cap`` is reached.
    """
    lib = load_library("KEGG_2021_Human")
    core: set[str] = set()
    core_terms = []
    counts: dict[str, int] = {}
    terms = []
    for term, genes in lib.items():
        if not any(p.lower() in term.lower() for p in SIGNALING_PATHWAY_PATTERNS):
            continue
        terms.append(term)
        members = {g.upper() for g in genes if g.upper() != target.upper()}
        if any(p.lower() in term.lower() for p in CORE_RECEPTOR_PATHWAYS):
            core_terms.append(term)
            core |= members
        for g in members:
            counts[g] = counts.get(g, 0) + 1

    panel = sorted(core)
    if len(panel) < cap:
        hubs = [g for g, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])) if g not in core]
        panel += hubs[: cap - len(panel)]
    panel = panel[:cap]
    return {
        "panel": panel,
        "n_pathway_terms": len(terms),
        "n_core_terms": len(core_terms),
        "core_terms": sorted(core_terms),
        "terms": sorted(terms)[:30],
        "n_candidates_in_library": len(counts),
        "cap": cap,
    }


# ---------------------------------------------------------------------------
# stage 1 —anchor functional profile
# ---------------------------------------------------------------------------
def stage_profile(ctx: RunContext) -> dict:
    t0 = time.time()
    target = ctx.target
    ctx.log(f"stage 1: profiling {target}")

    uni = _call("query_uniprot", protein=target)
    ot_target = _call("query_opentargets_target", gene=target)
    ot_assoc = _call("query_opentargets_associations", gene=target, disease_efo=ctx.disease_id)
    expr = _call("query_cbioportal_expression", gene=target, study=ctx.study)
    alt = _call("query_cbioportal_alterations", gene=target, study=ctx.study)
    pm = _call("query_pubmed", query=f'"{target}" AND ("{ctx.disease}" OR CRC OR "colon cancer")', retmax=5)
    kegg = _call("query_kegg_pathways", gene=target)
    go = _call("query_quickgo", gene=target)
    domains = _call("query_interpro", gene=target)

    topo = (uni.get("topology") or {}) if uni.get("ok") else {}
    gpi = bool(topo.get("gpi_anchored"))
    n_tm = int(topo.get("n_transmembrane") or 0)
    icd = int(topo.get("intracellular_residues") or 0)
    signalling = bool(uni.get("signaling_competent_by_topology"))

    if gpi and n_tm == 0:
        constraint = (
            f"{target} is GPI-anchored with no transmembrane helix and no intracellular domain "
            f"({icd} intracellular residues). It cannot transduce a signal itself, so the effector "
            f"target must be a membrane protein with an intracellular signalling output that "
            f"physically or functionally couples to it."
        )
    elif not signalling and n_tm == 0:
        constraint = (
            f"{target} lacks a transmembrane helix and an intracellular domain; its effector must be "
            f"a signal-transducing membrane protein."
        )
    else:
        constraint = (
            f"{target} has {n_tm} transmembrane segment(s) and {icd} intracellular residues; it may act "
            f"directly, but a downstream effector is still plausible."
        )

    findings = []
    if uni.get("ok"):
        findings.append(f"{target} = {uni.get('accession')}, {uni.get('length')} aa; {uni.get('architecture')}.")
    if ot_assoc.get("disease_score") is not None:
        findings.append(
            f"Open Targets CRC association score = {ot_assoc['disease_score']:.3f} "
            f"({ot_assoc.get('disease_name')}); {ot_assoc.get('n_associated_diseases')} associated diseases."
        )
    if expr.get("ok"):
        findings.append(
            f"TCGA-COADREAD: mean mRNA z vs normal = {expr.get('mean_z_vs_normal')}, "
            f"{expr.get('n_overexpressed')} tumours with z>2 (n={expr.get('n_z')})."
        )
    if alt.get("ok"):
        findings.append(
            f"Alterations: {alt.get('n_mutated_samples')} mutated samples, "
            f"{alt.get('frac_amplified')} amplified, {alt.get('frac_deep_deleted')} deep-deleted."
        )
    if pm.get("ok"):
        findings.append(f"PubMed hits for {target}+disease: {pm.get('count')}.")
    if domains.get("ok") and domains.get("signalling_families"):
        findings.append(f"Signalling domain families: {domains['signalling_families']}.")

    profile = {
        "target": target,
        "disease": ctx.disease,
        "disease_id": ctx.disease_id,
        "uniprot": uni,
        "opentargets_target": ot_target,
        "opentargets_associations": ot_assoc,
        "expression": expr,
        "alterations": alt,
        "pubmed": pm,
        "kegg": kegg,
        "go": go,
        "interpro": domains,
        "topology": {
            "gpi_anchored": gpi,
            "n_transmembrane": n_tm,
            "intracellular_residues": icd,
            "signaling_competent": signalling,
            "architecture": uni.get("architecture"),
        },
        "effector_constraint": constraint,
        "findings": findings,
    }
    ctx.save_json("stage1_profile.json", profile)
    ctx.state["profile"] = profile

    status = "ok" if (uni.get("ok") and expr.get("ok")) else ("partial" if uni.get("ok") else "failed")
    return {
        "stage": "stage_1",
        "name": "Profile construction",
        "status": status,
        "duration_s": round(time.time() - t0, 1),
        "findings": findings,
        "artefacts": {"profile": "stage1_profile.json"},
        "key_facts": {
            "topology": profile["topology"],
            "effector_constraint": constraint,
            "crc_association": ot_assoc.get("disease_score"),
            "expression_z": expr.get("mean_z_vs_normal"),
        },
        "tool_calls": ["query_uniprot", "query_opentargets_target", "query_opentargets_associations",
                       "query_cbioportal_expression", "query_cbioportal_alterations", "query_pubmed",
                       "query_kegg_pathways", "query_quickgo", "query_interpro"],
    }


# ---------------------------------------------------------------------------
# stage 2 —candidate generation
# ---------------------------------------------------------------------------
def stage_candidates(ctx: RunContext) -> dict:
    t0 = time.time()
    target = ctx.target
    p = ctx.params
    ctx.log(f"stage 2: candidate generation for {target}")

    ppi = _call("build_ppi_union", protein=target, limit=int(p.get("ppi_limit", 60)))
    ppi_partners = {r["gene"]: r for r in (ppi.get("partners") or []) if r.get("gene")}

    panel_info = build_signaling_panel(target, cap=int(p.get("panel_cap", 260)))
    panel = panel_info["panel"]
    ctx.log(f"  co-expression panel: {len(panel)} KEGG signalling genes")

    matrix, unresolved = fetch_expression_matrix(ctx.study, [target] + panel)
    samples = [s for s, g in matrix.items() if target in g]
    coexpr: dict[str, dict] = {}
    if len(samples) >= 30:
        x = [matrix[s][target] for s in samples]
        pvals = {}
        for g in panel:
            y = [matrix[s].get(g) for s in samples]
            r, pv, n = stats.pearson(x, y)
            coexpr[g] = {"r": round(r, 4), "p": pv, "n": n}
            pvals[g] = pv
        adjusted = stats.bh_fdr([pvals[g] for g in coexpr])
        for g, q in zip(coexpr, adjusted):
            coexpr[g]["fdr"] = q

    min_r = float(p.get("min_abs_r", 0.25))
    fdr_cut = float(p.get("coexpr_fdr", 0.05))
    coexpr_hits = {
        g: v for g, v in coexpr.items()
        if abs(v["r"]) >= min_r and v.get("fdr", 1.0) <= fdr_cut
    }
    ctx.log(f"  co-expressed candidates (|r|>={min_r}, FDR<={fdr_cut}): {len(coexpr_hits)}")

    pathway = _call("pathway_coannotation", anchor=target,
                    genes=(panel[:200] + [g for g in ppi_partners if g not in panel])[:260],
                    library="Reactome_2022")
    pathway_map = pathway.get("genes", {}) if pathway.get("ok") else {}

    union = set(ppi_partners) | set(coexpr_hits)
    union |= {g for g, v in pathway_map.items() if v.get("n_shared", 0) >= 1}
    union.discard(target)

    # ---- prior-knowledge candidates -------------------------------------
    # `--seed-genes` / `--expect` inject hypothesis genes (e.g. known Wnt
    # receptors) that the data alone may not nominate. They are carried through
    # the same scoring pipeline so their evidence can be compared on equal terms,
    # and they are marked as prior-driven in every table.
    prior_genes = [g.strip().upper() for g in (p.get("seed_genes") or []) + (p.get("expect_genes") or [])
                   if g and g.strip() and g.strip().upper() != target.upper()]
    prior_genes = list(dict.fromkeys(prior_genes))
    union |= set(prior_genes)
    ctx.log(f"  candidate union (PPI|co-expression|pathway|prior): {len(union)}"
            + (f" [prior: {', '.join(prior_genes)}]" if prior_genes else ""))

    # expression is needed for every union member, not only for the panel
    merged = {s: dict(g) for s, g in matrix.items()}
    missing_expr = [g for g in sorted(union) if not any(g in gv for gv in matrix.values())]
    if missing_expr:
        extra_matrix, _ = fetch_expression_matrix(ctx.study, missing_expr)
        for s, gv in extra_matrix.items():
            merged.setdefault(s, {}).update(gv)
        ctx.log(f"  fetched expression for {len(missing_expr)} additional union genes")

    # co-expression is also computed for the union members that were not in the panel
    x = [merged[s][target] for s in samples]
    for g in sorted(union):
        if g in coexpr:
            continue
        y = [merged[s].get(g) for s in samples]
        r, pv, n = stats.pearson(x, y)
        coexpr[g] = {"r": round(r, 4), "p": pv, "n": n, "fdr": 1.0}
    coexpr_hits = {
        g: v for g, v in coexpr.items()
        if abs(v["r"]) >= min_r and v.get("fdr", 1.0) <= fdr_cut
    }

    # literature co-mention on the union (capped, cached; NCBI allows 3 req/s)
    lit_genes = sorted(union)[: int(p.get("literature_limit", 45))]
    lit = _call("query_pubmed_cooccurrence", anchor=target, genes=lit_genes)
    lit_map = {g: v.get("cooccurrence", 0) for g, v in (lit.get("cooccurrence") or {}).items()}

    rows = []
    for g in sorted(union):
        ppi_rec = ppi_partners.get(g, {})
        ce = coexpr.get(g, {})
        pw = pathway_map.get(g, {})
        lit_n = lit_map.get(g, 0)
        ppi_score = float(ppi_rec.get("association", 0) or 0)
        intact_n = int(ppi_rec.get("n_intact", 0) or 0)
        pathway_ic = float(pw.get("information_content", 0) or 0)
        prelim = max(
            ppi_score,
            min(1.0, abs(ce.get("r", 0) or 0) / 0.6),
            min(1.0, lit_n / 5.0),
            min(1.0, pathway_ic / 15.0),
        )
        channels = sum((
            ppi_score >= 0.4 or intact_n >= 1,
            g in coexpr_hits,
            (pw.get("n_shared", 0) or 0) >= 1,
            lit_n >= 1,
        ))
        rows.append(
            {
                "gene": g,
                "ppi_score": round(ppi_score, 3),
                "ppi_experimental": round(float(ppi_rec.get("string_experimental", 0) or 0), 3),
                "intact_interactions": intact_n,
                "coexpr_r": round(float(ce.get("r", 0) or 0), 3),
                "coexpr_fdr": ce.get("fdr"),
                "shared_pathways": int(pw.get("n_shared", 0) or 0),
                "pathway_jaccard": pw.get("jaccard", 0),
                "pathway_information_content": round(pathway_ic, 2),
                "lit_cooccurrence": lit_n,
                "n_channels": channels,
                "prior": g in prior_genes,
                "sources": "|".join(
                    s for s, on in (
                        ("PPI", g in ppi_partners),
                        ("coexpr", g in coexpr_hits),
                        ("pathway", (pw.get("n_shared", 0) or 0) >= 1),
                        ("literature", lit_n > 0),
                        ("prior", g in prior_genes),
                    ) if on
                ),
                "preliminary_association": round(prelim, 3),
                "expressed_median_mrna": round(stats.median([merged[s][g] for s in samples if g in merged[s]]), 2)
                if any(g in merged[s] for s in samples) else None,
            }
        )
    matrix = merged

    # ---- admission rule (the critic's ">=2 independent sources" standard) ----
    # A candidate is admitted when it is nominated by at least two independent
    # channels, or by one strong channel: a confident physical interaction, a
    # replicated literature co-mention, or a specific (high-information) pathway.
    def admitted(r: dict) -> bool:
        return (
            r.get("prior")  # hypothesis genes are carried through by design
            or r["n_channels"] >= 2
            or r["ppi_score"] >= 0.4
            or abs(r["coexpr_r"]) >= 0.40
            or r["lit_cooccurrence"] >= 2
            or r["pathway_information_content"] >= 5.0
        )

    expressed = [
        r for r in rows
        if (r["expressed_median_mrna"] or 0) > 1.0 and admitted(r)
    ]
    expressed.sort(key=lambda r: -r["preliminary_association"])
    max_c = int(p.get("max_candidates", 60))
    kept = expressed[:max_c]

    ctx.save_json("stage2_candidates.json", {"panel_info": panel_info, "n_union": len(union), "candidates": kept})
    ctx.save_csv("stage2_candidates.csv", kept)
    ctx.state["candidates"] = kept
    ctx.state["coexpression"] = coexpr
    ctx.state["expression_matrix"] = matrix
    ctx.state["panel_info"] = panel_info

    findings = [
        f"PPI partners of {target}: {len(ppi_partners)} (STRING+IntAct union, score>=0.4).",
        f"Co-expression panel: {len(panel)} KEGG signalling genes; {len(coexpr_hits)} correlated with "
        f"{target} in TCGA-COADREAD (|r|>={min_r}, FDR<={fdr_cut}).",
        f"Reactome co-annotation: {sum(1 for v in pathway_map.values() if (v.get('n_shared') or 0) >= 1)} "
        f"candidates share at least one pathway with {target}.",
        f"Literature co-mentions retrieved for {len(lit_map)} candidates "
        f"({sum(1 for v in lit_map.values() if v > 0)} with >=1 co-mention).",
        f"Candidate table: {len(kept)} expressed candidates retained for scoring.",
    ]
    top = kept[:10]
    return {
        "stage": "stage_2",
        "name": "Candidate generation",
        "status": "ok" if kept else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": findings,
        "artefacts": {"candidates": "stage2_candidates.csv", "detail": "stage2_candidates.json"},
        "n_candidates": len(kept),
        "top_candidates": [{"gene": r["gene"], "association": r["preliminary_association"]} for r in top],
        "sources_breakdown": {
            "ppi": sum(1 for r in kept if "PPI" in r["sources"]),
            "coexpr": sum(1 for r in kept if "coexpr" in r["sources"]),
            "pathway": sum(1 for r in kept if "pathway" in r["sources"]),
            "literature": sum(1 for r in kept if "literature" in r["sources"]),
        },
        "tool_calls": ["build_ppi_union", "query_cbioportal_coexpression", "pathway_coannotation",
                       "query_pubmed_cooccurrence"],
    }


# ---------------------------------------------------------------------------
# stage 3 —signalling competence
# ---------------------------------------------------------------------------
def stage_signaling(ctx: RunContext) -> dict:
    t0 = time.time()
    cands = ctx.state.get("candidates") or []
    genes = [c["gene"] for c in cands]
    ctx.log(f"stage 3: signalling competence for {len(genes)} candidates")

    tool_name = "score_signaling_potential"
    if tool_name not in registry.TOOLS:
        ctx.log("  !! signalling scorer not registered - capability gap")
        return {
            "stage": "stage_3",
            "name": "Signalling competence scoring",
            "status": "failed",
            "duration_s": 0.0,
            "findings": ["No signalling-competence tool available in the Tool Ocean."],
            "capability_gap": True,
            "missing_tool": tool_name,
            "artefacts": {},
            "tool_calls": [],
        }

    res = _call(tool_name, genes=genes)
    scores = {r["gene"]: r for r in res.get("scores", [])} if res.get("ok") else {}
    for c in cands:
        s = scores.get(c["gene"], {})
        c["signaling_score"] = s.get("signaling_score")
        c["signaling_families"] = s.get("signalling_families", [])
        c["topology_reason"] = s.get("topology_reason")

    min_sig = float(ctx.params.get("min_signaling", 0.35))
    competent = [c for c in cands if (c.get("signaling_score") or 0) >= min_sig]
    competent.sort(key=lambda c: -(c.get("signaling_score") or 0))

    ctx.save_csv("stage3_signaling.csv", cands)
    ctx.state["signaling"] = scores

    findings = [
        f"Scored {res.get('n_scored', 0)} candidates with {tool_name} "
        f"({res.get('n_missing', 0)} without UniProt records).",
        f"{len(competent)} candidates reach the signalling-competence threshold ({min_sig}).",
    ]
    if competent:
        top3 = ", ".join(f"{c['gene']}={c['signaling_score']}" for c in competent[:3])
        findings.append(f"Top signalling-competent candidates: {top3}.")
    return {
        "stage": "stage_3",
        "name": "Signalling competence scoring",
        "status": "ok" if scores else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": findings,
        "artefacts": {"signaling": "stage3_signaling.csv"},
        "n_scored": len(scores),
        "n_competent": len(competent),
        "tool_calls": [tool_name],
    }


# ---------------------------------------------------------------------------
# stage 4 —multi-evidence scoring
# ---------------------------------------------------------------------------
def stage_scoring(ctx: RunContext) -> dict:
    t0 = time.time()
    from ..tools.scoring import score_association

    min_sig = float(ctx.params.get("min_signaling", 0.35))
    pool = [
        c for c in (ctx.state.get("candidates") or [])
        if (c.get("signaling_score") or 0) >= min_sig
    ]
    if len(pool) < 5:  # never starve the ranking; degrade explicitly
        ctx.log(f"  signalling filter relaxed: only {len(pool)} candidates passed {min_sig}")
        pool = [c for c in (ctx.state.get("candidates") or []) if c.get("signaling_score") is not None]
    pool.sort(key=lambda c: (-(c.get("signaling_score") or 0), -c["preliminary_association"]))

    # ---- relevance gate -------------------------------------------------
    # An effector must first be *linked* to the anchor. "Linked" means at least
    # one strong association channel (physical interaction, expression
    # co-variation, literature co-mention or a specific shared pathway);
    # candidates admitted on weak, diffuse evidence are excluded from priority
    # ranking even if they are attractive drug targets on their own.
    gate = float(ctx.params.get("min_association_evidence", 0.5))

    def association_evidence(c: dict) -> float:
        return max(
            float(c.get("ppi_score") or 0),
            min(1.0, abs(c.get("coexpr_r") or 0) / 0.6),
            min(1.0, (c.get("lit_cooccurrence") or 0) / 5.0),
            min(1.0, (c.get("pathway_information_content") or 0) / 15.0),
        )

    gated = [c for c in pool if association_evidence(c) >= gate or c.get("prior")]
    if len(gated) < 5:  # never starve the ranking; degrade explicitly
        gated = pool
        ctx.log(f"  relevance gate relaxed: only {len(gated)} candidates were linked to the anchor")
    else:
        ctx.log(f"  relevance gate: {len(gated)}/{len(pool)} candidates are linked to {ctx.target} "
                f"(strongest association channel >= {gate}); prior genes bypass the gate")

    limit = int(ctx.params.get("scoring_limit", 40))
    priors = [c for c in gated if c.get("prior")]
    rest = [c for c in gated if not c.get("prior")]
    cands = (priors + rest)[: max(limit, len(priors))]
    ctx.log(f"stage 4: multi-evidence scoring for {len(cands)} candidates "
            f"({len(priors)} prior-driven)")

    genes = [c["gene"] for c in cands]
    matrix = ctx.state.get("expression_matrix") or {}
    clinical = fetch_clinical(ctx.study)
    zmatrix, _ = fetch_expression_matrix(ctx.study, genes + [ctx.target],
                                         "rna_seq_v2_mrna_median_all_sample_ref_normal_Zscores")
    alterations = fetch_alterations_batch(ctx.study, genes)

    # survival for every candidate (local computation over the cached matrices)
    surv: dict[str, dict] = {}
    for g in genes:
        surv[g] = survival_from_matrix(g, matrix, clinical, "OS")

    # novelty + druggability (network-bound -> thread pool)
    def novelty(g: str) -> tuple[str, dict]:
        return g, _call("query_pubmed_novelty", gene=g, disease=ctx.disease)

    def druggability(g: str) -> tuple[str, dict]:
        return g, _call("druggability_score", gene=g)

    drug_genes = genes[: int(ctx.params.get("druggability_limit", 20))]
    nov: dict[str, dict] = {}
    drug: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for g, r in pool.map(novelty, genes):
            nov[g] = r
        for g, r in pool.map(druggability, drug_genes):
            drug[g] = r

    evidence = {}
    for c in cands:
        g = c["gene"]
        zvals = [v[g] for v in zmatrix.values() if g in v]
        s = surv.get(g, {})
        n = nov.get(g, {})
        d = drug.get(g, {})
        evidence[g] = {
            "gene": g,
            "ppi_association": c.get("ppi_score"),
            "ppi_experimental": c.get("ppi_experimental"),
            "intact_interactions": c.get("intact_interactions"),
            "ppi_degree": c.get("intact_interactions", 0) + (1 if c.get("ppi_score") else 0),
            "coexpr_r": c.get("coexpr_r"),
            "coexpr_fdr": c.get("coexpr_fdr"),
            "lit_cooccurrence": c.get("lit_cooccurrence"),
            "pathway_jaccard": c.get("pathway_jaccard"),
            "n_shared_pathways": c.get("shared_pathways"),
            "pathway_information_content": c.get("pathway_information_content"),
            "signaling_score": c.get("signaling_score"),
            "n_tm": (ctx.state.get("signaling", {}).get(g) or {}).get("n_tm"),
            "topology_reason": c.get("topology_reason"),
            "signalling_families": c.get("signaling_families"),
            "expr_mean_z": round(stats.mean(zvals), 3) if zvals else None,
            "survival_p": s.get("p_value") if s.get("ok") else None,
            "survival_hr": s.get("hazard_ratio_high_vs_low") if s.get("ok") else None,
            "mutation_freq": (alterations.get(g) or {}).get("frac_mut"),
            "cna_amp_freq": (alterations.get(g) or {}).get("frac_amp"),
            "novelty_score": n.get("novelty_score") if n.get("ok") else None,
            "druggability_score": d.get("score") if d.get("ok") else None,
            "n_pubmed_crc": n.get("n_gene_disease") if n.get("ok") else None,
        }

    weights = ctx.params.get("weights")
    scored = _call("multi_evidence_scoring", candidates=list(evidence.values()), weights=weights)
    ranking = scored.get("ranking", []) if scored.get("ok") else []
    for row in ranking:
        ev = evidence.get(row["gene"], {})
        row["evidence"] = ev
        row["survival"] = {
            k: surv.get(row["gene"], {}).get(k)
            for k in ("p_value", "hazard_ratio_high_vs_low", "median_survival_high", "median_survival_low", "n_patients")
        }
        row["n_pubmed_crc"] = ev.get("n_pubmed_crc")
        row["druggability"] = drug.get(row["gene"], {}).get("tractability_buckets")

    ctx.save_json("stage4_evidence.json", {"weights": scored.get("weights"), "ranking": ranking,
                                          "evidence": evidence})
    flat = []
    for r in ranking:
        flat.append(
            {
                "rank": r["rank"],
                "gene": r["gene"],
                "composite": r["composite"],
                **{f"dim_{k}": v for k, v in (r.get("dimensions") or {}).items()},
                "n_supporting": r.get("n_supporting_dimensions"),
                "supporting": "|".join(r.get("supporting_dimensions") or []),
                "weak": "|".join(r.get("weak_dimensions") or []),
                "coverage": r.get("coverage"),
                "os_p": (r.get("survival") or {}).get("p_value"),
                "os_hr": (r.get("survival") or {}).get("hazard_ratio_high_vs_low"),
                "n_pubmed_crc": r.get("n_pubmed_crc"),
            }
        )
    ctx.save_csv("stage4_ranking.csv", flat)
    ctx.state["ranking"] = ranking
    ctx.state["evidence"] = evidence
    ctx.state["weights"] = scored.get("weights")
    ctx.state["survival"] = surv

    findings = [
        f"Scored {len(ranking)} candidates on 6 dimensions with initial weights "
        f"{json.dumps(scored.get('weights', {}), ensure_ascii=False)} (the critic may re-calibrate them).",
        f"Coverage: {sum(1 for r in ranking if r['coverage'] >= 0.8)} candidates have >=80% of dimensions populated.",
        f"Consistency: {sum(1 for r in ranking if r.get('consistent'))} candidates are supported by >=3 dimensions.",
    ]
    if ranking:
        t = ranking[0]
        findings.append(
            f"Leader: {t['gene']} (composite {t['composite']}, dimensions "
            f"{ {k: v for k, v in t['dimensions'].items() if v is not None} })."
        )
    return {
        "stage": "stage_4",
        "name": "Multi-evidence scoring",
        "status": "ok" if ranking else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": findings,
        "artefacts": {"ranking": "stage4_ranking.csv", "evidence": "stage4_evidence.json"},
        "weights": scored.get("weights"),
        "top_ranking": [
            {"gene": r["gene"], "composite": r["composite"],
             "dimensions": r.get("dimensions"), "consistent": r.get("consistent")}
            for r in ranking[:10]
        ],
        "tool_calls": ["multi_evidence_scoring", "query_cbioportal_survival",
                       "query_pubmed_novelty", "druggability_score"],
    }


STAGE_PROGRAMS = {
    "stage_1": stage_profile,
    "stage_2": stage_candidates,
    "stage_3": stage_signaling,
    "stage_4": stage_scoring,
}


def rebuild_ranking(ctx: RunContext, weights: dict) -> list[dict]:
    """Re-rank stored evidence with new weights (dynamic weight calibration)."""
    evidence = ctx.state.get("evidence") or {}
    survival = ctx.state.get("survival") or {}
    if not evidence:
        return ctx.state.get("ranking", [])
    scored = _call("multi_evidence_scoring", candidates=list(evidence.values()), weights=weights)
    ranking = scored.get("ranking", []) if scored.get("ok") else []
    for row in ranking:
        row["evidence"] = evidence.get(row["gene"], {})
        row["survival"] = {
            k: (survival.get(row["gene"], {}) or {}).get(k)
            for k in ("p_value", "hazard_ratio_high_vs_low", "median_survival_high",
                      "median_survival_low", "n_patients")
        }
        row["n_pubmed_crc"] = (evidence.get(row["gene"]) or {}).get("n_pubmed_crc")
    ctx.state["ranking"] = ranking
    ctx.state["weights"] = weights
    flat = []
    for r in ranking:
        flat.append(
            {
                "rank": r["rank"],
                "gene": r["gene"],
                "composite": r["composite"],
                **{f"dim_{k}": v for k, v in (r.get("dimensions") or {}).items()},
                "n_supporting": r.get("n_supporting_dimensions"),
                "supporting": "|".join(r.get("supporting_dimensions") or []),
                "weak": "|".join(r.get("weak_dimensions") or []),
                "coverage": r.get("coverage"),
                "os_p": (r.get("survival") or {}).get("p_value"),
                "os_hr": (r.get("survival") or {}).get("hazard_ratio_high_vs_low"),
                "n_pubmed_crc": r.get("n_pubmed_crc"),
            }
        )
    ctx.save_csv("stage4_ranking.csv", flat)
    return ranking

