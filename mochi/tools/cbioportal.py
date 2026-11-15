"""cBioPortal tools: tumour expression, alterations, co-expression and survival.

Data source: public cBioPortal REST API v2, TCGA PanCancer Atlas COADREAD
(``coadread_tcga_pan_can_atlas_2018``) by default.  All statistics are computed
locally (pure Python, see :mod:`mochi.stats`) so the numbers in the report
are reproducible and auditable.
"""

from __future__ import annotations

import math
from statistics import NormalDist

from .. import stats
from .http import request_json
from .identifiers import exact_ids
from .registry import tool

CBIO = "https://www.cbioportal.org/api"
STUDY = "coadread_tcga_pan_can_atlas_2018"


def _profile(study: str, suffix: str) -> str:
    return f"{study}_{suffix}"


def _fetch_matrix(study: str, genes: list[str], profile_suffix: str) -> tuple[dict[str, dict[str, float]], list[str]]:
    """Return {sampleId: {symbol: value}} for the requested genes (chunked requests)."""
    ids, back, missing = exact_ids(genes)
    if not ids:
        return {}, list(genes)
    matrix: dict[str, dict[str, float]] = {}
    for i in range(0, len(ids), 120):
        chunk = ids[i : i + 120]
        records = request_json(
            "POST",
            f"{CBIO}/molecular-profiles/{_profile(study, profile_suffix)}/molecular-data/fetch?projection=SUMMARY",
            service="cbioportal",
            json_body={"entrezGeneIds": chunk, "sampleListId": f"{study}_all"},
            timeout=240,
        )
        for rec in records or []:
            sym = back.get(rec.get("entrezGeneId"))
            val = rec.get("value")
            if sym is None or val is None:
                continue
            matrix.setdefault(rec["sampleId"], {})[sym] = float(val)
    return matrix, missing


def fetch_expression_matrix(study: str, genes: list[str], profile_suffix: str = "rna_seq_v2_mrna"):
    """Public helper used by the workflow stages (not a registered tool)."""
    return _fetch_matrix(study, genes, profile_suffix)


def fetch_clinical(study: str) -> dict[str, dict[str, str]]:
    return _clinical(study)


def fetch_alterations_batch(study: str, genes: list[str]) -> dict[str, dict]:
    """Mutation / CNA frequencies for many genes in two batched requests."""
    ids, back, missing = exact_ids(genes)
    if not ids:
        return {}
    muts = request_json(
        "POST",
        f"{CBIO}/molecular-profiles/{_profile(study, 'mutations')}/mutations/fetch?projection=SUMMARY",
        service="cbioportal",
        json_body={"entrezGeneIds": ids, "sampleListId": f"{study}_all"},
        timeout=180,
    )
    cna = request_json(
        "POST",
        f"{CBIO}/molecular-profiles/{_profile(study, 'gistic')}/molecular-data/fetch?projection=SUMMARY",
        service="cbioportal",
        json_body={"entrezGeneIds": ids, "sampleListId": f"{study}_all"},
        timeout=180,
    )
    out: dict[str, dict] = {g: {"n_mut": 0, "frac_mut": 0.0, "n_samples_cna": 0,
                                "frac_amp": 0.0, "frac_homdel": 0.0} for g in genes}
    mut_samples: dict[int, set] = {}
    for m in muts or []:
        eid = m.get("entrezGeneId")
        if eid is not None:
            mut_samples.setdefault(eid, set()).add(m.get("sampleId"))
    cna_counts: dict[int, list[int]] = {}
    for r in cna or []:
        eid = r.get("entrezGeneId")
        v = r.get("value")
        if eid is None:
            continue
        c = cna_counts.setdefault(eid, [0, 0, 0])
        c[0] += 1
        if v == 2:
            c[1] += 1
        elif v == -2:
            c[2] += 1
    for eid, sym in back.items():
        rec = out.get(sym)
        if rec is None:
            continue
        n_mut = len(mut_samples.get(eid, set()))
        c = cna_counts.get(eid, [0, 0, 0])
        n_cna = c[0] or 1
        rec.update(
            {
                "n_mut": n_mut,
                "frac_mut": round(n_mut / n_cna, 4),
                "n_samples_cna": c[0],
                "frac_amp": round(c[1] / n_cna, 4),
                "frac_homdel": round(c[2] / n_cna, 4),
            }
        )
    return out


def _clinical(study: str) -> dict[str, dict[str, str]]:
    recs = request_json(
        "GET",
        f"{CBIO}/studies/{study}/clinical-data",
        service="cbioportal",
        params={"clinicalDataType": "PATIENT", "projection": "SUMMARY"},
        timeout=180,
    )
    out: dict[str, dict[str, str]] = {}
    for r in recs or []:
        pid = r.get("patientId")
        if pid:
            out.setdefault(pid, {})[r.get("clinicalAttributeId")] = r.get("value")
    return out


@tool(
    "query_cbioportal_expression",
    "database",
    "TCGA-COADREAD expression of a gene: tumour mRNA distribution, z-score versus matched normal, "
    "fraction of tumours with z>2 (over-expression), and the number of profiled samples.",
    gene="HGNC symbol",
    study="cBioPortal study id",
)
def query_cbioportal_expression(gene: str, study: str = STUDY) -> dict:
    raw, missing = _fetch_matrix(study, [gene], "rna_seq_v2_mrna")
    z, _ = _fetch_matrix(study, [gene], "rna_seq_v2_mrna_median_all_sample_ref_normal_Zscores")
    vals = [v[gene] for v in raw.values() if gene in v]
    zvals = [v[gene] for v in z.values() if gene in v]
    if not vals:
        return {"ok": False, "error": f"no expression data for {gene}", "missing": missing}
    z3 = sum(1 for x in zvals if x > 2)
    return {
        "ok": True,
        "source": f"cBioPortal {study} (RNA-seq v2 RSEM; z vs normal)",
        "gene": gene,
        "n_samples": len(vals),
        "mrna_median": round(stats.median(vals), 2),
        "mrna_mean": round(stats.mean(vals), 2),
        "mrna_iqr": [round(stats.percentile(vals, 0.25), 2), round(stats.percentile(vals, 0.75), 2)],
        "n_z": len(zvals),
        "mean_z_vs_normal": round(stats.mean(zvals), 3) if zvals else None,
        "frac_z_gt2": round(z3 / len(zvals), 3) if zvals else None,
        "n_overexpressed": z3,
    }


@tool(
    "query_cbioportal_alterations",
    "database",
    "Mutation and copy-number alteration frequency for a gene in TCGA-COADREAD "
    "(mutation count, % mutated samples, % amplified, % deep-deleted).",
    gene="HGNC symbol",
    study="cBioPortal study id",
)
def query_cbioportal_alterations(gene: str, study: str = STUDY) -> dict:
    ids, back, missing = exact_ids([gene])
    if not ids:
        return {"ok": False, "error": f"could not map {gene}"}
    eid = ids[0]
    muts = request_json(
        "POST",
        f"{CBIO}/molecular-profiles/{_profile(study, 'mutations')}/mutations/fetch?projection=SUMMARY",
        service="cbioportal",
        json_body={"entrezGeneIds": [eid], "sampleListId": f"{study}_all"},
        timeout=120,
    )
    cna = request_json(
        "POST",
        f"{CBIO}/molecular-profiles/{_profile(study, 'gistic')}/molecular-data/fetch?projection=SUMMARY",
        service="cbioportal",
        json_body={"entrezGeneIds": [eid], "sampleListId": f"{study}_all"},
        timeout=120,
    )
    cna_vals = [r.get("value") for r in (cna or [])]
    n_cna = len(cna_vals)
    amp = sum(1 for v in cna_vals if v == 2)
    homdel = sum(1 for v in cna_vals if v == -2)
    mut_samples = {m.get("sampleId") for m in (muts or [])}
    classes: dict[str, int] = {}
    for m in muts or []:
        cls = m.get("mutationType") or m.get("variantType") or "other"
        classes[cls] = classes.get(cls, 0) + 1
    return {
        "ok": True,
        "source": f"cBioPortal {study} (mutations + GISTIC CNA)",
        "gene": gene,
        "n_mutated_samples": len(mut_samples),
        "n_mutation_events": len(muts or []),
        "n_cna_samples": n_cna,
        "frac_amplified": round(amp / n_cna, 4) if n_cna else 0.0,
        "frac_deep_deleted": round(homdel / n_cna, 4) if n_cna else 0.0,
        "mutation_classes": dict(sorted(classes.items(), key=lambda kv: -kv[1])[:6]),
    }


def survival_from_matrix(gene: str, expr: dict[str, dict[str, float]], clin: dict[str, dict[str, str]],
                         endpoint: str = "OS") -> dict:
    """Kaplan–Meier + log-rank for one gene given an already-downloaded matrix."""
    endpoint = endpoint.upper()
    times, events, high = [], [], []
    for sample_id, genes in expr.items():
        if gene not in genes:
            continue
        pid = sample_id.rsplit("-", 1)[0] if sample_id.count("-") >= 3 else sample_id
        c = clin.get(pid) or clin.get(sample_id)
        if not c:
            continue
        t_raw = c.get(f"{endpoint}_MONTHS")
        s_raw = (c.get(f"{endpoint}_STATUS") or "").upper()
        if not t_raw or not s_raw:
            continue
        try:
            t = float(t_raw)
        except ValueError:
            continue
        if t <= 0:
            continue
        event = 1 if ("DECEASED" in s_raw or "RECURRED" in s_raw or "PROGRESSION" in s_raw
                      or s_raw.startswith("1:")) else 0
        times.append(t)
        events.append(event)
        high.append(genes[gene])
    if len(times) < 40:
        return {"ok": False, "error": f"insufficient survival data for {gene} ({len(times)})"}
    cut = stats.median(high)
    groups = [1 if v > cut else 0 for v in high]
    chi2, p = stats.logrank(times, events, groups)
    hr = stats.hazard_ratio(times, events, groups)
    km_hi = stats.kaplan_meier([t for t, g in zip(times, groups) if g == 1],
                               [e for e, g in zip(events, groups) if g == 1])
    km_lo = stats.kaplan_meier([t for t, g in zip(times, groups) if g == 0],
                               [e for e, g in zip(events, groups) if g == 0])

    def median_surv(curve):
        for t, s, _ in curve:
            if s <= 0.5:
                return round(t, 1)
        return None

    return {
        "ok": True,
        "gene": gene,
        "endpoint": endpoint,
        "n_patients": len(times),
        "split_value": round(cut, 2),
        "n_high": sum(groups),
        "n_low": len(groups) - sum(groups),
        "logrank_chi2": round(chi2, 3),
        "p_value": p,
        "hazard_ratio_high_vs_low": round(hr, 3),
        "median_survival_high": median_surv(km_hi),
        "median_survival_low": median_surv(km_lo),
        "events": sum(events),
        "km": {
            "high": [[round(t, 1), round(s, 4)] for t, s, _ in km_hi][:80],
            "low": [[round(t, 1), round(s, 4)] for t, s, _ in km_lo][:80],
        },
    }


@tool(
    "query_cbioportal_survival",
    "database",
    "Kaplan–Meier analysis for a gene in TCGA-COADREAD: median mRNA split, log-rank p-value, "
    "hazard ratio and per-group median survival. Endpoint selectable (OS/DFS/DSS/PFS).",
    gene="HGNC symbol",
    study="cBioPortal study id",
    endpoint="OS | DFS | DSS | PFS",
)
def query_cbioportal_survival(gene: str, study: str = STUDY, endpoint: str = "OS") -> dict:
    expr, _ = _fetch_matrix(study, [gene], "rna_seq_v2_mrna")
    clin = _clinical(study)
    res = survival_from_matrix(gene, expr, clin, endpoint)
    if res.get("ok"):
        res["source"] = f"cBioPortal {study} (clinical {endpoint.upper()}_MONTHS/{endpoint.upper()}_STATUS + mRNA)"
    return res

@tool(
    "query_cbioportal_coexpression",
    "database",
    "Co-expression of a query gene with a panel of candidates in TCGA-COADREAD: Pearson r, "
    "p-value, BH-FDR and the number of shared samples (single matrix download, cached).",
    anchor_gene="gene whose expression is the reference (e.g. DPEP1)",
    genes="candidate gene list",
    study="cBioPortal study id",
)
def query_cbioportal_coexpression(anchor_gene: str, genes: list[str], study: str = STUDY) -> dict:
    panel = list(dict.fromkeys([anchor_gene] + list(genes)))
    matrix, missing = _fetch_matrix(study, panel, "rna_seq_v2_mrna")
    samples = [s for s, g in matrix.items() if anchor_gene in g]
    if len(samples) < 20:
        return {"ok": False, "error": "insufficient co-expression samples"}
    x = [matrix[s][anchor_gene] for s in samples]
    out = {}
    pvals = {}
    for g in panel:
        if g == anchor_gene:
            continue
        y = [matrix[s].get(g) for s in samples]
        r, p, n = stats.pearson(x, y)
        out[g] = {"r": round(r, 4), "p": p, "n": n}
        pvals[g] = p
    adjusted = stats.bh_fdr([pvals[g] for g in out])
    for g, q in zip(out, adjusted):
        out[g]["fdr"] = q
    return {
        "ok": True,
        "source": f"cBioPortal {study} (RNA-seq v2; Pearson on log2 RSEM)",
        "anchor": anchor_gene,
        "n_samples": len(samples),
        "unresolved": missing,
        "correlations": out,
    }


@tool(
    "query_cbioportal_expression_panel",
    "database",
    "Expression profile of many genes in TCGA-COADREAD: mean z-score vs normal, fraction of "
    "tumours with z>2 and median mRNA per gene (used for panel-level filtering).",
    genes="candidate gene list",
    study="cBioPortal study id",
)
def query_cbioportal_expression_panel(genes: list[str], study: str = STUDY) -> dict:
    gene_set = list(dict.fromkeys(genes))
    raw, missing = _fetch_matrix(study, gene_set, "rna_seq_v2_mrna")
    z, _ = _fetch_matrix(study, gene_set, "rna_seq_v2_mrna_median_all_sample_ref_normal_Zscores")
    out = {}
    for g in gene_set:
        vals = [v[g] for v in raw.values() if g in v]
        zvals = [v[g] for v in z.values() if g in v]
        if not vals:
            continue
        out[g] = {
            "n": len(vals),
            "mrna_median": round(stats.median(vals), 2),
            "mean_z": round(stats.mean(zvals), 3) if zvals else None,
            "frac_z_gt2": round(sum(1 for x in zvals if x > 2) / len(zvals), 3) if zvals else None,
        }
    return {
        "ok": True,
        "source": f"cBioPortal {study} (RNA-seq v2)",
        "n_genes": len(out),
        "unresolved": missing,
        "expression": out,
    }


def _normal_cdf(x: float) -> float:
    return NormalDist().cdf(x)


def combined_tumor_expression_score(gene: str, study: str = STUDY) -> float | None:
    """Convenience for the multi-evidence scorer (0-1)."""
    res = query_cbioportal_expression(gene, study)
    if not res.get("ok"):
        return None
    z = res.get("mean_z_vs_normal") or 0.0
    frac = res.get("frac_z_gt2") or 0.0
    return max(0.0, min(1.0, 0.5 * (1 - _normal_cdf(-z)) + 0.5 * min(1.0, frac / 0.3)))
