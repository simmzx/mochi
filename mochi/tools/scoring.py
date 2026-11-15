"""Evidence scoring: dimension normalisation, dynamic weighting, consistency checks.

The six dimensions follow the reasoning template:

    association          - how strongly is the candidate tied to the anchor?
    signaling            - can it transduce a signal at all?
    crc_evidence         - is it dysregulated / prognostic in the disease cohort?
    pathway_centrality   - is it central to the disease-relevant pathway module?
    novelty              - is this actually a discovery (not a known target)?
    druggability         - can it be drugged?

Every raw feature is mapped to [0,1] by a documented, monotone transform (never by
min-max over the candidate set alone, which would make scores depend on who else
happened to be in the list).  Missing evidence re-normalises the weights instead
of contributing a zero - absence of data is not absence of evidence.
"""

from __future__ import annotations

import math

from .. import stats
from .registry import tool

DIMENSIONS = ["association", "signaling", "crc_evidence", "pathway_centrality", "novelty", "druggability"]

DEFAULT_WEIGHTS = {
    "association": 0.24,
    "signaling": 0.20,
    "crc_evidence": 0.20,
    "pathway_centrality": 0.10,
    "novelty": 0.10,
    "druggability": 0.16,
}


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def _logistic(x: float, midpoint: float, slope: float) -> float:
    return 1.0 / (1.0 + math.exp(-slope * (x - midpoint)))


# ---------------------------------------------------------------------------
# dimension transforms
# ---------------------------------------------------------------------------
# How much a single positive channel contributes to the belief that the candidate
# is genuinely linked to the anchor.  Combined with noisy-OR, so that one strong
# channel is enough to establish association, while absent channels (no PPI
# record, no co-mention) do not dilute a strong result the way a weighted mean
# would.
CHANNEL_RELIABILITY = {"ppi": 0.90, "coexpr": 0.70, "literature": 0.50, "pathway": 0.50}


def score_association(ev: dict) -> float | None:
    channels: list[float] = []
    if ev.get("ppi_association") is not None:
        channels.append(CHANNEL_RELIABILITY["ppi"] * _clip(ev["ppi_association"]))
    if ev.get("coexpr_r") is not None:
        channels.append(CHANNEL_RELIABILITY["coexpr"] * _clip(abs(ev["coexpr_r"]) / 0.6))
    if ev.get("lit_cooccurrence") is not None:
        channels.append(CHANNEL_RELIABILITY["literature"] * _clip(ev["lit_cooccurrence"] / 5.0))
    if ev.get("pathway_jaccard") is not None or ev.get("pathway_information_content") is not None:
        p = max(
            _clip((ev.get("pathway_jaccard") or 0.0) / 0.30),
            _clip((ev.get("pathway_information_content") or 0.0) / 20.0),
        )
        channels.append(CHANNEL_RELIABILITY["pathway"] * p)
    if not channels:
        return None
    prod = 1.0
    for c in channels:
        prod *= 1.0 - c
    return _clip(1.0 - prod)



def score_signaling(ev: dict) -> float | None:
    if ev.get("signaling_score") is None:
        return None
    return _clip(ev["signaling_score"])


def score_crc(ev: dict) -> float | None:
    parts = []
    if ev.get("expr_mean_z") is not None:
        # z = 0 (tumour == normal) -> 0.5 ; z = +2 -> ~0.88 ; z = -2 -> ~0.12
        parts.append((0.45, _logistic(ev["expr_mean_z"], 0.0, 1.1)))
    if ev.get("survival_p") is not None:
        p = max(ev["survival_p"], 1e-6)
        hr = ev.get("survival_hr") or 1.0
        strength = _clip((-math.log10(p)) / 3.0)
        direction = 1.0 if hr > 1 else 0.45  # poor prognosis is the discovery-relevant direction
        parts.append((0.25, strength * direction))
    if ev.get("mutation_freq") is not None:
        parts.append((0.12, _clip(ev["mutation_freq"] / 0.10)))
    if ev.get("cna_amp_freq") is not None:
        parts.append((0.18, _clip(ev["cna_amp_freq"] / 0.25)))
    if not parts:
        return None
    total_w = sum(w for w, _ in parts)
    return sum(w * v for w, v in parts) / total_w


def score_pathway(ev: dict) -> float | None:
    parts = []
    if ev.get("n_shared_pathways") is not None:
        parts.append((0.35, _clip(ev["n_shared_pathways"] / 3.0)))
    if ev.get("pathway_information_content") is not None:
        # one highly specific shared pathway (IC ~ 8 bits) is worth as much as
        # three generic ones; 20 bits saturates the component
        parts.append((0.35, _clip(ev["pathway_information_content"] / 20.0)))
    if ev.get("ppi_degree") is not None:
        parts.append((0.20, _clip(ev["ppi_degree"] / 10.0)))
    if ev.get("pathway_centrality_raw") is not None:
        parts.append((0.10, _clip(ev["pathway_centrality_raw"])))
    if not parts:
        return None
    total_w = sum(w for w, _ in parts)
    return sum(w * v for w, v in parts) / total_w


def score_novelty(ev: dict) -> float | None:
    if ev.get("novelty_score") is None:
        return None
    return _clip(ev["novelty_score"])


def score_druggability(ev: dict) -> float | None:
    if ev.get("druggability_score") is None:
        return None
    return _clip(ev["druggability_score"])


TRANSFORMS = {
    "association": score_association,
    "signaling": score_signaling,
    "crc_evidence": score_crc,
    "pathway_centrality": score_pathway,
    "novelty": score_novelty,
    "druggability": score_druggability,
}


def normalise_weights(weights: dict | None) -> dict:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        for k, v in weights.items():
            if k in w and isinstance(v, (int, float)) and v >= 0:
                w[k] = float(v)
    total = sum(w.values()) or 1.0
    return {k: round(v / total, 4) for k, v in w.items()}


# ---------------------------------------------------------------------------
# composite scoring
# ---------------------------------------------------------------------------
def score_candidate(evidence: dict, weights: dict | None = None) -> dict:
    """Turn one candidate's raw evidence into dimension scores + composite."""
    w = normalise_weights(weights)
    dims: dict[str, float | None] = {}
    for dim, fn in TRANSFORMS.items():
        try:
            dims[dim] = None if fn(evidence) is None else round(_clip(fn(evidence)), 4)
        except Exception:
            dims[dim] = None

    present = {d: v for d, v in dims.items() if v is not None}
    w_present = {d: w[d] for d in present}
    total_w = sum(w_present.values()) or 1.0
    composite = sum(present[d] * w_present[d] for d in present) / total_w

    # consistency: how many independent dimensions support the candidate
    support = sorted([d for d, v in present.items() if v >= 0.6])
    weak = [d for d, v in present.items() if v < 0.35]
    coverage = len(present) / len(DIMENSIONS)
    # penalise thin evidence a little (max 12%) but never zero it out
    composite_adj = composite * (0.88 + 0.12 * coverage)
    dispersion = stats.stdev(list(present.values())) if len(present) > 1 else 0.0

    return {
        "dimensions": dims,
        "weights": w,
        "composite": round(composite_adj, 4),
        "coverage": round(coverage, 3),
        "n_supporting_dimensions": len(support),
        "supporting_dimensions": support,
        "weak_dimensions": weak,
        "dimension_dispersion": round(dispersion, 3),
        "consistent": len(support) >= 3 and len(weak) <= 1,
    }


def rank_candidates(evidence_by_gene: dict[str, dict], weights: dict | None = None) -> list[dict]:
    rows = []
    for gene, ev in evidence_by_gene.items():
        scored = score_candidate(ev, weights)
        rows.append({"gene": gene, **scored, "evidence": ev})
    rows.sort(key=lambda r: (-r["composite"], -r["n_supporting_dimensions"], r["gene"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


@tool(
    "multi_evidence_scoring",
    "scoring",
    "Rank candidate effector targets on six evidence dimensions (association, signalling "
    "competence, disease expression/prognosis, pathway centrality, novelty, druggability) with "
    "critic-calibrated weights, coverage-aware renormalisation and a consistency check.",
    candidates="list of evidence dicts, each with a 'gene' key",
    weights="optional dimension weights (must sum to 1)",
)
def multi_evidence_scoring(candidates: list[dict], weights: dict | None = None) -> dict:
    if not candidates:
        return {"ok": False, "error": "no candidates"}
    by_gene = {}
    for c in candidates:
        gene = c.get("gene")
        if gene:
            by_gene[gene] = c
    rows = rank_candidates(by_gene, weights)
    return {
        "ok": True,
        "source": "mochi multi-evidence scorer",
        "weights": normalise_weights(weights),
        "n_candidates": len(rows),
        "ranking": [
            {
                "rank": r["rank"],
                "gene": r["gene"],
                "composite": r["composite"],
                "dimensions": r["dimensions"],
                "n_supporting_dimensions": r["n_supporting_dimensions"],
                "supporting_dimensions": r["supporting_dimensions"],
                "weak_dimensions": r["weak_dimensions"],
                "coverage": r["coverage"],
                "consistent": r["consistent"],
            }
            for r in rows
        ],
        "top": rows[0] if rows else None,
    }
