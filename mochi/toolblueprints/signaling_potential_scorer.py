"""BLUEPRINT — instantiated by the Tool Creation Agent into ``tools_created/``.

signaling_potential_scorer
==========================
Quantify whether a candidate protein can transduce a signal *by itself*.

Why this tool had to be created
-------------------------------
The anchor protein of this study is a GPI-anchored ectoenzyme: it has no
transmembrane helix and no intracellular domain, so it cannot be the effector.
The effector must be a membrane protein with an intracellular signalling output.
No tool in the Tool Ocean could answer "which candidate is signalling-competent?"
in a quantitative, batch, reproducible way, so the critic requested one.

Algorithm (transparent, auditable, no black boxes)
--------------------------------------------------
1. **Topology** (weight 0.50) - from UniProt: transmembrane segment count and the
   number of intracellular residues (cytoplasmic topological domains).
2. **Domain family** (weight 0.30) - from Pfam cross-references and the curated
   function description: kinase / 7TM-GPCR / Frizzled / LDL-receptor / TNFR /
   death domain / cytokine receptor / ion channel.
3. **Annotation** (weight 0.12) - GO-style keywords in the UniProt function text.
4. **Localisation** (weight 0.08) - plasma membrane vs other membranes vs soluble.

Hard constraints: a GPI-anchored protein without a transmembrane helix, or a
secreted protein, is capped at 0.15 no matter what its domains say - that is the
biology the score must respect.

Validation
----------
``validate()`` runs positive controls (established signal-transducing receptors)
and negative controls (GPI-anchored / secreted / cytosolic proteins). Acceptance
requires every positive control >= 0.60 and every negative control <= 0.35.

Limitations
-----------
- The score measures *competence*, not activity: a competent receptor can be
  silent in a given tumour.
- Domain inference relies on UniProt Pfam cross-references; proteins without
  reviewed entries fall back to topology only.
- It cannot tell which ligand activates the receptor, nor the direction of the
  signalling axis - those need expression/perturbation evidence.
"""

from __future__ import annotations

from typing import Any

from mochi.tools.registry import tool
from mochi.tools.uniprot import query_uniprot_batch

# ---------------------------------------------------------------------------
# domain family knowledge
# ---------------------------------------------------------------------------
FAMILY_WEIGHTS = {
    "kinase": 0.34,
    "seven_tm_gpcr": 0.32,
    "frizzled": 0.30,
    "ldl_receptor": 0.26,
    "tnfr": 0.30,
    "death_domain": 0.22,
    "cytokine_receptor": 0.24,
    "phosphatase": 0.18,
    "ion_channel": 0.16,
}

FAMILY_PATTERNS = {
    "kinase": ("kinase", "phosphotransferase"),
    "seven_tm_gpcr": ("7tm", "rhodopsin", "gpcr", "g protein-coupled"),
    "frizzled": ("frizzled",),
    "ldl_receptor": ("ldl", "low-density lipoprotein", "low density lipoprotein"),
    "tnfr": ("tumor necrosis factor receptor", "tnfr"),
    "death_domain": ("death",),
    "cytokine_receptor": ("cytokine receptor", "hematopoietin", "fibronectin type iii"),
    "phosphatase": ("phosphatase",),
    "ion_channel": ("channel",),
}

POSITIVE_SIGNAL = ("signal", "receptor", "transduction", "cascade", "ligand", "activates")
NEGATIVE_SIGNAL = ("hydrolase", "peptidase", "protease", "transferase", "isomerase", "oxidase")


def _family_flags(pfam: list[str], function: str) -> dict[str, bool]:
    blob = (" ".join(pfam or []) + " " + (function or "")).lower()
    return {fam: any(p in blob for p in pats) for fam, pats in FAMILY_PATTERNS.items()}


def _topology_score(feat: dict) -> tuple[float, str]:
    n_tm = int(feat.get("n_tm") or 0)
    icd = int(feat.get("intracellular_residues") or 0)
    gpi = bool(feat.get("gpi"))
    secreted = bool(feat.get("has_signal_peptide")) and n_tm == 0 and not gpi

    if n_tm >= 1 and icd >= 20:
        return 1.0, f"{n_tm}-pass transmembrane with {icd} intracellular residues"
    if n_tm >= 1 and icd > 0:
        return 0.72, f"{n_tm}-pass transmembrane with a short intracellular segment ({icd} aa)"
    if n_tm >= 1:
        return 0.45, f"{n_tm}-pass transmembrane without a cytoplasmic domain"
    if gpi:
        return 0.04, "GPI-anchored ectoprotein: no transmembrane helix, no intracellular domain"
    if secreted:
        return 0.02, "secreted protein: no membrane anchor"
    return 0.10, "soluble / intracellular protein"


def score_one(gene: str, feat: dict) -> dict:
    topo, reason = _topology_score(feat)
    n_tm = int(feat.get("n_tm") or 0)
    gpi = bool(feat.get("gpi"))
    membrane_embedded = n_tm >= 1 or gpi

    # A domain family only counts as a *receptor* feature when the protein is
    # actually membrane-embedded: a soluble kinase annotated with "GPCR signalling"
    # is an intracellular transducer, not a cell-surface effector.
    flags = _family_flags(feat.get("pfam", []), feat.get("function", "")) if membrane_embedded else {
        k: False for k in FAMILY_PATTERNS
    }
    domain = min(1.0, sum(FAMILY_WEIGHTS[f] for f, on in flags.items() if on))

    fn = (feat.get("function") or "").lower()
    pos = sum(1 for k in POSITIVE_SIGNAL if k in fn)
    neg = sum(1 for k in NEGATIVE_SIGNAL if k in fn)
    annotation = max(0.0, min(1.0, 0.35 + 0.15 * pos - 0.10 * neg))

    locs = " ".join(feat.get("locations") or []).lower()
    if "plasma membrane" in locs or "cell membrane" in locs:
        localisation = 1.0
    elif "membrane" in locs:
        localisation = 0.75
    else:
        localisation = 0.35

    raw = 0.50 * topo + 0.30 * domain + 0.12 * annotation + 0.08 * localisation

    # A transmembrane helix is necessary but not sufficient: transporters,
    # glycosyltransferases and channels embedded in the ER/Golgi are membrane
    # proteins without a signalling output. Without a signalling domain family or
    # receptor-like annotation, the topology credit is halved.
    receptor_like = bool(domain > 0) or any(
        k in fn for k in ("receptor", "signal transduction", "signalling", "signaling", "cytokine")
    )
    if membrane_embedded and not receptor_like:
        raw = min(raw, 0.45)

    # hard biological constraints
    gpi_only = gpi and n_tm == 0
    if gpi_only:
        raw = min(raw, 0.15)
    elif not membrane_embedded:
        raw = min(raw, 0.20)

    families = [f for f, on in flags.items() if on]
    return {
        "gene": gene,
        "signaling_score": round(max(0.0, min(1.0, raw)), 4),
        "components": {
            "topology": round(topo, 3),
            "domain": round(domain, 3),
            "annotation": round(annotation, 3),
            "localisation": round(localisation, 3),
        },
        "topology_reason": reason,
        "signalling_families": families,
        "gpi_anchored": bool(feat.get("gpi")),
        "n_tm": int(feat.get("n_tm") or 0),
        "intracellular_residues": int(feat.get("intracellular_residues") or 0),
        "uniprot": feat.get("accession"),
    }


@tool(
    "score_signaling_potential",
    "scoring",
    "Score proteins for intrinsic signalling competence (0-1) from UniProt topology, Pfam domain "
    "family, function annotation and localisation. GPI-anchored and secreted proteins are capped.",
    genes="gene symbols to score",
)
def score_signaling_potential(genes: list[str]) -> dict:
    genes = [g for g in dict.fromkeys(genes) if g]
    if not genes:
        return {"ok": False, "error": "no genes supplied"}
    batch = query_uniprot_batch(genes)
    proteins = batch.get("proteins", {}) if batch.get("ok") else {}
    scored = []
    for gene in genes:
        feat = proteins.get(gene)
        if not feat:
            scored.append({"gene": gene, "signaling_score": None, "error": "no UniProt feature record"})
            continue
        scored.append(score_one(gene, feat))
    scored.sort(key=lambda r: -(r.get("signaling_score") or 0))
    valid = [r for r in scored if r.get("signaling_score") is not None]
    return {
        "ok": True,
        "source": "UniProt topology + Pfam + function text (signaling competence heuristic)",
        "n_scored": len(valid),
        "n_missing": len(scored) - len(valid),
        "scores": scored,
        "top": valid[0] if valid else None,
    }


def validate() -> dict:
    """Positive / negative control acceptance test."""
    positives = ["LRP6", "FZD1", "EGFR", "TNFRSF1A", "TGFBR1", "NOTCH1", "IL6ST"]
    negatives = ["DPEP1", "CEACAM5", "ALB", "INS", "GAPDH", "LYZ"]
    res = score_signaling_potential(positives + negatives)
    by_gene = {r["gene"]: r for r in res.get("scores", [])}
    cases = []
    passed = True
    for g in positives:
        s = (by_gene.get(g) or {}).get("signaling_score")
        ok = s is not None and s >= 0.60
        passed &= ok
        cases.append({"case": g, "expected": ">=0.60 (signalling receptor)", "observed": s, "pass": ok})
    for g in negatives:
        s = (by_gene.get(g) or {}).get("signaling_score")
        ok = s is not None and s <= 0.35
        passed &= ok
        cases.append({"case": g, "expected": "<=0.35 (non-signalling)", "observed": s, "pass": ok})
    return {"passed": bool(passed), "cases": cases}
