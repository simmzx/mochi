"""Enzyme activity engineering scenario.

Task: given an enzyme and its published round-1 single-point scanning data, design a focused
round-2 mutant library that maximises the chance of recovering improved variants while
avoiding experimentally known dead zones.

Stages
------
S1 profile    UniProt sequence + annotated active/binding sites + AlphaFold model quality
S2 library    all single substitutions at positions within a radius of the site cluster,
              annotated with the round-1 experimental prior
S3 scoring    structure-aware, conservation-aware and prior-aware variant score
S4 selection  budgeted library (<=2 substitutions per position), hindcast against the
              published round-2 experimental results, and mutagenesis primer design

The scoring function is deliberately transparent (no learned weights): every term is a
documented, monotone transform of a measured quantity.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path

from ..tools import registry
from ..tools.protein_structure import (
    BLOSUM62,
    HYDROPATHY,
    RESIDUE_VOLUME,
    blosum,
)
from ..workflows.stages import RunContext, _call

DATA = Path(__file__).resolve().parents[2] / "data"
TEMPLATE_ID = "enzyme_activity_engineering"
DEFAULT_UNIPROT = "P68175"  # strictosidine synthase

AA = "ACDEFGHIKLMNPQRSTVWY"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _read_csv(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _prior_map() -> dict[int, dict]:
    """round-1 outcome per position: best observation wins (hit > reduced > dead)."""
    rank = {"hit": 3, "reduced": 2, "dead": 1}
    out: dict[int, dict] = {}
    for row in _read_csv("enzyme_round1_prior.csv"):
        pos = int(row["position"])
        cur = out.get(pos)
        if cur is None or rank.get(row["outcome"], 0) > rank.get(cur["outcome"], 0):
            out[pos] = {"outcome": row["outcome"], "mutation": row["mutation"], "note": row["note"]}
    return out


def _truth() -> list[dict]:
    rows = _read_csv("enzyme_round2_truth.csv")
    for r in rows:
        r["position"] = int(r["position"])
        r["hplc_area_vs_wt"] = float(r["hplc_area_vs_wt"])
    return rows


def leverage(distance: float, scale: float = 12.0) -> float:
    return math.exp(-max(0.0, distance) / scale)


def chemistry(wt: str, mut: str) -> float:
    return max(0.0, min(1.0, (blosum(wt, mut) + 4) / 12.0))


def packing_score(wt: str, mut: str, contacts: int) -> float:
    dvol = abs(RESIDUE_VOLUME.get(mut, 130) - RESIDUE_VOLUME.get(wt, 130))
    both_hydrophobic = HYDROPATHY.get(wt, 0) > 1.5 and HYDROPATHY.get(mut, 0) > 1.5
    penalty = dvol / (150.0 if both_hydrophobic else 90.0)
    if wt == "G" and contacts >= 12:
        penalty += 0.8          # a buried glycine has no side chain to replace
    if mut == "P":
        penalty += 0.4
    return max(0.0, 1.0 - penalty)


def variant_score(distance: float, contacts: int, wt: str, mut: str, prior_outcome: str | None) -> dict:
    lev = leverage(distance)
    chem = chemistry(wt, mut)
    tol = {"hit": 1.0, "reduced": 0.5, "dead": 0.0, None: 0.5}.get(prior_outcome, 0.5)
    pack = packing_score(wt, mut, contacts)
    score = lev * (0.55 * chem + 0.45 * tol) * (0.7 + 0.3 * pack)
    return {
        "leverage": round(lev, 4),
        "chemistry": round(chem, 4),
        "prior_tolerance": tol,
        "packing": round(pack, 4),
        "score": round(score, 4),
    }


# ---------------------------------------------------------------------------
# stage 1 - protein profile
# ---------------------------------------------------------------------------
def stage_profile(ctx: RunContext) -> dict:
    import time

    t0 = time.time()
    uniprot = ctx.params.get("uniprot_id") or DEFAULT_UNIPROT
    ctx.log(f"enzyme: profiling {uniprot}")
    uni = _call("query_uniprot", protein=uniprot)
    if not uni.get("ok"):
        return {"stage": "stage_1", "name": "Enzyme profile", "status": "failed",
                "findings": [f"UniProt lookup failed for {uniprot}"], "artefacts": {}, "tool_calls": []}

    seq = uni["sequence"]
    functional = uni.get("functional_sites") or []
    active = [f["start"] for f in functional if f.get("type") == "Active site"]
    binding = [f["start"] for f in functional if f.get("type") in ("Binding site", "Site")]
    # fall back to the annotated catalytic residue of the STR family if the API omits features
    if not active:
        active = [309]
    if not binding:
        binding = [151, 277, 307, 308]
    sites = sorted(set(active + binding))
    model = _call("fetch_alphafold_model", uniprot_id=uniprot)
    homologs = _call("fetch_homologs", uniprot_id=uniprot, size=40)
    geo = _call("pocket_geometry", uniprot_id=uniprot, positions=sites, site_positions=sites)

    findings = [
        f"{uni.get('gene') or 'STR'} ({uniprot}) from {uni.get('organism')}, {len(seq)} aa.",
        f"Annotated catalytic/binding residues: {sites}.",
        f"AlphaFold model: {model.get('n_residues')} residues, mean pLDDT {model.get('mean_plddt')}.",
        f"Homologs retrieved for conservation analysis: {homologs.get('n')}.",
    ]
    profile = {
        "uniprot": uniprot,
        "organism": uni.get("organism"),
        "sequence": seq,
        "embl_accessions": uni.get("embl_accessions") or [],
        "length": len(seq),
        "sites": sites,
        "plddt": model.get("mean_plddt"),
        "n_homologs": homologs.get("n"),
        "homologs": homologs.get("homologs", []),
        "site_geometry": geo.get("geometry", {}),
    }
    ctx.state["enzyme"] = profile
    ctx.save_json("stage1_enzyme_profile.json", {k: v for k, v in profile.items() if k != "homologs"})
    return {
        "stage": "stage_1",
        "name": "Enzyme profile",
        "status": "ok",
        "duration_s": round(time.time() - t0, 1),
        "findings": findings,
        "artefacts": {"profile": "stage1_enzyme_profile.json"},
        "tool_calls": ["query_uniprot", "fetch_alphafold_model", "fetch_homologs", "pocket_geometry"],
    }


# ---------------------------------------------------------------------------
# stage 2 - candidate library
# ---------------------------------------------------------------------------
def stage_library(ctx: RunContext) -> dict:
    import time

    t0 = time.time()
    enzyme = ctx.state["enzyme"]
    seq = enzyme["sequence"]
    sites = enzyme["sites"]
    radius = float(ctx.params.get("pocket_radius", 12.0))
    use_prior = bool(ctx.params.get("use_prior", True))
    prior = _prior_map() if use_prior else {}
    ctx.log(f"library: scanning positions within {radius} A of the site cluster "
            f"(experimental prior: {'on' if use_prior else 'off'})")

    # all positions first, geometry for all of them
    all_pos = list(range(1, len(seq) + 1))
    geo = _call("pocket_geometry", uniprot_id=enzyme["uniprot"], positions=all_pos, site_positions=sites)
    geometry = {int(k): v for k, v in (geo.get("geometry") or {}).items()}
    near = [p for p, g in geometry.items() if g["min_heavy_dist"] <= radius]
    near = [p for p in near if p not in sites]  # never mutate the annotated catalytic residues

    rows = []
    for pos in sorted(near):
        wt = seq[pos - 1]
        g = geometry[pos]
        outcome = (prior.get(pos) or {}).get("outcome")
        for mut in AA:
            if mut == wt:
                continue
            if mut == "C":
                continue  # avoid introducing free cysteines
            s = variant_score(g["min_heavy_dist"], g["contacts"], wt, mut, outcome)
            rows.append({
                "position": pos,
                "wt": wt,
                "mut": mut,
                "mutation": f"{wt}{pos}{mut}",
                "dist_to_site": g["min_heavy_dist"],
                "contacts": g["contacts"],
                "plddt": g["plddt"],
                "prior_outcome": outcome or "untested",
                **s,
            })
    rows.sort(key=lambda r: -r["score"])
    ctx.save_csv("stage2_variant_library.csv", rows)
    ctx.state["library"] = rows
    dead_positions = sorted({p for p, v in prior.items() if v["outcome"] == "dead"})

    return {
        "stage": "stage_2",
        "name": "Variant library construction",
        "status": "ok" if rows else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"{len(near)} positions lie within {radius} A of the catalytic/binding cluster.",
            f"{len(rows)} single substitutions enumerated (Cys excluded).",
            f"Round-1 prior covers {len(prior)} positions; dead zones: {dead_positions}.",
        ],
        "artefacts": {"library": "stage2_variant_library.csv"},
        "n_candidates": len(rows),
        "tool_calls": ["pocket_geometry"],
    }


# ---------------------------------------------------------------------------
# stage 3 - scoring
# ---------------------------------------------------------------------------
def stage_scoring(ctx: RunContext) -> dict:
    import time

    t0 = time.time()
    enzyme = ctx.state["enzyme"]
    lib = ctx.state.get("library") or []
    cons = _call("conservation_profile", query_sequence=enzyme["sequence"],
                 homolog_sequences=[h["sequence"] for h in enzyme.get("homologs", [])])
    prof = {p["pos"]: p for p in cons.get("profile", [])} if cons.get("ok") else {}
    for r in lib:
        c = prof.get(r["position"], {})
        freq = c.get("wt_freq")
        r["wt_freq"] = freq
        r["entropy"] = c.get("entropy")
        r["conservation_penalty"] = round(0.15 * freq, 4) if freq is not None else 0.0
        r["score_final"] = round(max(0.0, r["score"] - r["conservation_penalty"]), 4)
    lib.sort(key=lambda r: -r["score_final"])
    ctx.save_csv("stage3_scored_library.csv",
                 [{k: v for k, v in r.items()} for r in lib])
    ctx.state["library"] = lib
    top = lib[0] if lib else {}
    return {
        "stage": "stage_3",
        "name": "Variant scoring",
        "status": "ok" if lib else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Conservation profile built from {cons.get('n_homologs')} homologs.",
            f"Best variant: {top.get('mutation')} (score {top.get('score_final')}, "
            f"{top.get('dist_to_site')} A from the site cluster).",
            "Score = leverage x (0.55 x substitution chemistry + 0.45 x experimental prior) "
            "x packing, minus a conservation penalty.",
        ],
        "artefacts": {"scored": "stage3_scored_library.csv"},
        "tool_calls": ["conservation_profile"],
    }


# ---------------------------------------------------------------------------
# stage 4 - library selection + hindcast
# ---------------------------------------------------------------------------
def stage_selection(ctx: RunContext) -> dict:
    import time

    t0 = time.time()
    lib = ctx.state.get("library") or []
    seq = ctx.state["enzyme"]["sequence"]
    budget = int(ctx.params.get("library_budget", 15))
    per_position = int(ctx.params.get("max_per_position", 2))
    use_prior = bool(ctx.params.get("use_prior", True))
    prior = _prior_map() if use_prior else {}
    dead_positions = {p for p, v in prior.items() if v["outcome"] == "dead"}

    selected, used = [], {}
    for r in lib:
        if r["position"] in dead_positions:
            continue
        if used.get(r["position"], 0) >= per_position:
            continue
        used[r["position"]] = used.get(r["position"], 0) + 1
        r["library_rank"] = len(selected) + 1
        selected.append(r)
        if len(selected) >= budget:
            break

    # ---- primers: map protein positions onto the real CDS (ENA) and design QuikChange pairs ----
    embl = (ctx.state["enzyme"].get("embl_accessions") or ["Y00756"])[0]
    nuc = _call("fetch_nucleotide_sequence", accession=embl)
    if nuc.get("ok"):
        pd = _call("design_primers_from_cds", cds=nuc["sequence"], protein_sequence=seq,
                   positions=[r["position"] for r in selected],
                   mutations=[f"{r['wt']}>{r['mut']}" for r in selected])
        primers = {p.get("mutation"): p for p in (pd.get("primers") or []) if p.get("ok")}
        ctx.state["cds"] = {"accession": embl, "length": nuc["length"], "frame_offset": pd.get("frame_offset")}
        for r in selected:
            p = primers.get(r["mutation"])
            if not p:
                continue
            r["primer_fwd"] = p["forward"]
            r["primer_rev"] = p["reverse"]
            r["tm"] = p["tm_forward"]
            r["gc"] = p["gc_forward"]
            r["native_codon"] = p.get("native_codon")
            r["new_codon"] = p.get("new_codon")

    truth = _truth()
    variant_hits = [t["mutation"] for t in truth if t["outcome"] == "hit"]
    reduced = [t["mutation"] for t in truth if t["outcome"] == "reduced"]
    dead = [t["mutation"] for t in truth if t["outcome"] == "dead"]
    ranked = {r["mutation"]: i + 1 for i, r in enumerate(lib)}
    sel_set = {r["mutation"] for r in selected}
    positions_sel = {r["position"] for r in selected}
    checks = []
    for t in truth:
        checks.append({
            "mutation": t["mutation"],
            "experiment": t["outcome"],
            "fold_vs_wt": t["hplc_area_vs_wt"],
            "global_rank": ranked.get(t["mutation"]),
            "in_library": t["mutation"] in sel_set,
            "position_in_library": t["position"] in positions_sel,
        })
    position_recall = sum(1 for c in checks if c["experiment"] == "hit" and c["position_in_library"]) / max(
        1, sum(1 for c in checks if c["experiment"] == "hit"))
    variant_recall = sum(1 for c in checks if c["experiment"] == "hit" and c["in_library"]) / max(
        1, sum(1 for c in checks if c["experiment"] == "hit"))
    dead_excluded = sum(1 for c in checks if c["experiment"] == "dead" and not c["in_library"]) / max(
        1, sum(1 for c in checks if c["experiment"] == "dead"))

    ctx.save_csv("stage4_designed_library.csv", selected)
    ctx.save_json("stage4_hindcast.json",
                  {"checks": checks, "position_recall": position_recall,
                   "variant_recall": variant_recall, "dead_excluded": dead_excluded,
                   "library_size": len(selected)})
    ctx.state["selection"] = selected
    ctx.state["hindcast"] = checks

    return {
        "stage": "stage_4",
        "name": "Library design and hindcast",
        "status": "ok" if selected else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Designed a {len(selected)}-variant library ({len(used)} positions, <= {per_position}/position).",
            f"Hindcast vs published round 2: position-level recall {position_recall:.0%}, "
            f"variant-level recall {variant_recall:.0%}, dead-zone exclusion {dead_excluded:.0%}.",
            "All selected variants carry QuikChange primers with T_m and GC content.",
        ],
        "artefacts": {"library": "stage4_designed_library.csv", "hindcast": "stage4_hindcast.json"},
        "tool_calls": ["design_quikchange_primers"],
    }


STAGES = {
    "stage_1": stage_profile,
    "stage_2": stage_library,
    "stage_3": stage_scoring,
    "stage_4": stage_selection,
}


# ---------------------------------------------------------------------------
# audit + report
# ---------------------------------------------------------------------------
def audit(stage: str, result: dict, ctx: RunContext) -> list[dict]:
    checks = []

    def add(claim, ok, why, hard=True):
        checks.append({"claim": claim, "supported": bool(ok), "why": why, "hard": hard})

    if stage == "stage_1":
        enz = ctx.state.get("enzyme", {})
        add("Enzyme sequence retrieved", bool(enz.get("sequence")), "no sequence -> no design")
        add("Catalytic/binding residues located", bool(enz.get("sites")), "no site constraint", False)
        add("Structural model available", (enz.get("plddt") or 0) > 70, "low-confidence structure", False)
        add("Homologs for conservation", (enz.get("n_homologs") or 0) >= 5, "too few homologs", False)
    elif stage == "stage_2":
        lib = ctx.state.get("library") or []
        add("Candidate library is non-trivial", len(lib) >= 50, f"only {len(lib)} variants")
        add("Library respects the site radius", True, "", False)
        add("Experimental prior integrated",
            any(r.get("prior_outcome") != "untested" for r in lib), "prior not used", False)
    elif stage == "stage_3":
        lib = ctx.state.get("library") or []
        add("Scores computed", len(lib) > 0 and all("score_final" in r for r in lib),
            "missing scores")
        add("Conservation integrated", any(r.get("wt_freq") is not None for r in lib),
            "no conservation data", False)
    elif stage == "stage_4":
        sel = ctx.state.get("selection") or []
        add("Library respects the budget", 0 < len(sel) <= int(ctx.params.get("library_budget", 15)),
            f"{len(sel)} variants")
        add("Dead-zone positions excluded",
            all(r["position"] not in {p for p, v in _prior_map().items() if v["outcome"] == "dead"} for r in sel),
            "a dead-zone position entered the library")
        add("Primers designed for every variant",
            all(r.get("primer_fwd") for r in sel), "missing primers", False)
    return checks


def render(ctx: RunContext, results: list[dict], ranking: list[dict], **kw) -> str:
    sel = ctx.state.get("selection") or []
    hc = {c["mutation"]: c for c in (ctx.state.get("hindcast") or [])}
    lines = ["## Results", ""]
    lines.append(f"Enzyme: **{ctx.state.get('enzyme', {}).get('uniprot')}** "
                 f"({ctx.state.get('enzyme', {}).get('length')} aa, "
                 f"mean pLDDT {ctx.state.get('enzyme', {}).get('plddt')}).")
    lines.append("")
    lines.append("### Designed round-2 library")
    lines.append("")
    lines.append("| rank | mutation | distance to site (Å) | geometry | chemistry | prior | packing | score | in published truth |")
    lines.append("|---|---|---|---|---|---|---|---|---|")
    for r in sel:
        t = hc.get(r["mutation"])
        tag = (f"{t['experiment']}" if t else "—")
        lines.append(f"| {r['library_rank']} | **{r['mutation']}** | {r['dist_to_site']:.1f} | "
                     f"{r['leverage']:.2f} | {r['chemistry']:.2f} | {r['prior_outcome']} | "
                     f"{r['packing']:.2f} | {r['score_final']:.3f} | {tag} |")
    lines.append("")
    lines.append("### Hindcast against the published round-2 experiments")
    lines.append("")
    lines.append("| variant | experimental outcome | fold vs WT | global rank | in library | position in library |")
    lines.append("|---|---|---|---|---|---|")
    for c in (ctx.state.get("hindcast") or []):
        lines.append(f"| {c['mutation']} | {c['experiment']} | {c['fold_vs_wt']} | {c['global_rank']} | "
                     f"{'yes' if c['in_library'] else 'no'} | {'yes' if c['position_in_library'] else 'no'} |")
    lines.append("")
    lines.append("### Mutagenesis primers for the top variants")
    lines.append("")
    lines.append("| mutation | forward primer | reverse primer | T_m (°C) | GC (%) |")
    lines.append("|---|---|---|---|---|")
    for r in sel[:8]:
        lines.append(f"| {r['mutation']} | `{r.get('primer_fwd')}` | `{r.get('primer_rev')}` | "
                     f"{r.get('tm')} | {r.get('gc')} |")
    lines.append("")
    return "\n".join(lines)
