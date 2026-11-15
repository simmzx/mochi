"""Pathway tools: KEGG membership + curated gene-set libraries (Reactome / GO / KEGG).

Reactome and GO memberships are obtained from the Enrichr gene-set libraries,
which are downloaded once and cached as ``cache/genesets/<library>.json``.
Working from cached libraries (instead of a per-gene REST call) makes pathway
co-annotation, pathway centrality and enrichment analysis deterministic and fast
even for hundreds of candidates.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from .. import stats
from .http import request_text, ROOT
from .identifiers import exact_ids
from .registry import tool

KEGG = "https://rest.kegg.jp"
ENRICHR = "https://maayanlab.cloud/Enrichr/geneSetLibrary?mode=text&libraryName="
GENESET_DIR = ROOT / "cache" / "genesets"

LIBRARIES = {
    "Reactome_2022": "Reactome pathways (curated reactions)",
    "KEGG_2021_Human": "KEGG human pathways",
    "GO_Biological_Process_2023": "GO biological processes",
}

_MEM: dict[str, dict[str, list[str]]] = {}


def load_library(name: str) -> dict[str, list[str]]:
    """Return {term: [genes]} for an Enrichr library (cached on disk + memory)."""
    if name in _MEM:
        return _MEM[name]
    GENESET_DIR.mkdir(parents=True, exist_ok=True)
    path = GENESET_DIR / f"{name}.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        _MEM[name] = data
        return data
    txt = request_text("GET", f"{ENRICHR}{name}", service="enrichr", timeout=180, ttl=60 * 60 * 24 * 30)
    lib: dict[str, list[str]] = {}
    for line in (txt or "").splitlines():
        parts = [p.strip() for p in line.split("\t") if p.strip()]
        if len(parts) < 3:
            continue
        term = parts[0]
        genes = [g.upper() for g in parts[2:] if g.upper().isalnum() or "-" in g]
        if genes:
            lib[term] = genes
    path.write_text(json.dumps(lib), encoding="utf-8")
    _MEM[name] = lib
    return lib


def gene_terms(genes: list[str], library: str) -> dict[str, list[str]]:
    lib = load_library(library)
    want = {g.upper() for g in genes}
    out: dict[str, list[str]] = {g.upper(): [] for g in genes}
    for term, members in lib.items():
        for m in members:
            if m in out:
                out[m].append(term)
    return out


# Gene-set analysis 101: very large terms ("Metabolism", "Disease", "Signal
# Transduction") are shared by thousands of genes and create spurious overlap.
# They are excluded from similarity/centrality because their information content
# is near zero - the same reason enrichment tools filter by set size.
GENERIC_TERMS = {
    "Metabolism", "Disease", "Infectious Disease", "Immune System", "Signal Transduction",
    "Gene Expression", "Metabolism Of Lipids", "Metabolism Of Proteins", "Metabolism Of Rna",
    "Biological Oxidations", "Developmental Biology", "Vesicle-Mediated Transport",
    "Cell Cycle", "Dna Repair", "Programmed Cell Death", "Cellular Responses To Stress",
    "Post-Translational Protein Modification", "Transport Of Small Molecules",
    "Disease Of Cellular Proliferation", "Adaptive Immune System", "Innate Immune System",
}
MAX_TERM_SIZE = 300
MIN_TERM_SIZE = 5


def _term_size_ok(term: str, members: list[str]) -> bool:
    base = term.rsplit(" R-HSA-", 1)[0].strip()
    if base in GENERIC_TERMS:
        return False
    return MIN_TERM_SIZE <= len(members) <= MAX_TERM_SIZE


@tool(
    "query_pathway_membership",
    "pathway",
    "Pathway/process membership for a gene list from a curated gene-set library "
    "(Reactome_2022, KEGG_2021_Human, GO_Biological_Process_2023); returns terms per gene and "
    "the most frequently shared terms.",
    genes="gene symbols",
    library="gene-set library name",
)
def query_pathway_membership(genes: list[str], library: str = "Reactome_2022") -> dict:
    per_gene = gene_terms(genes, library)
    counts: dict[str, int] = {}
    for terms in per_gene.values():
        for t in set(terms):
            counts[t] = counts.get(t, 0) + 1
    top = sorted(counts.items(), key=lambda kv: -kv[1])[:15]
    return {
        "ok": True,
        "source": f"Enrichr library {library}",
        "library": library,
        "n_genes": len(per_gene),
        "membership": {g: sorted(t)[:25] for g, t in per_gene.items()},
        "shared_terms": [{"term": t, "n_genes": n} for t, n in top],
    }


@tool(
    "query_kegg_pathways",
    "pathway",
    "KEGG pathway membership for a single gene (official KEGG REST link + list endpoints).",
    gene="gene symbol",
)
def query_kegg_pathways(gene: str) -> dict:
    ids, back, missing = exact_ids([gene])
    if not ids:
        return {"ok": False, "error": f"could not map {gene}"}
    eid = ids[0]
    txt = request_text("GET", f"{KEGG}/link/pathway/hsa:{eid}", service="kegg", timeout=60)
    pathway_ids = []
    for line in (txt or "").splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            pathway_ids.append(parts[1].replace("path:", "").strip())
    names: dict[str, str] = {}
    if pathway_ids:
        listing = request_text("GET", f"{KEGG}/list/{'+'.join(pathway_ids)}", service="kegg", timeout=60)
        for line in (listing or "").splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                names[parts[0].replace("path:", "")] = parts[1]
    return {
        "ok": True,
        "source": "KEGG REST",
        "gene": gene,
        "entrez": eid,
        "pathways": [{"id": pid, "name": names.get(pid, "")} for pid in pathway_ids],
    }


@tool(
    "pathway_coannotation",
    "pathway",
    "Shared-pathway analysis between an anchor gene and candidates (Reactome/KEGG/GO): "
    "number of shared terms, Jaccard similarity and the anchor's own terms.",
    anchor="anchor gene symbol",
    genes="candidate genes",
    library="gene-set library",
)
def pathway_coannotation(anchor: str, genes: list[str], library: str = "Reactome_2022") -> dict:
    panel = list(dict.fromkeys([anchor] + list(genes)))
    lib = load_library(library)
    per_gene = gene_terms(panel, library)
    # keep only informative terms (not generic, not tiny, not genome-wide)
    filtered = {g: {t for t in ts if _term_size_ok(t, lib.get(t, []))} for g, ts in per_gene.items()}
    universe = {g for members in lib.values() for g in members}
    n_universe = max(1, len(universe))
    anchor_terms = filtered.get(anchor.upper(), set())
    out = {}
    for g in genes:
        terms = filtered.get(g.upper(), set())
        shared = sorted(anchor_terms & terms)
        union = anchor_terms | terms
        # information content: sum of -log2 P(term) over the shared terms, so that
        # sharing a 30-gene pathway counts far more than sharing a 300-gene one.
        ic = sum(
            math.log2(n_universe / max(1, len(lib.get(t, [])))) for t in shared
        )
        out[g] = {
            "n_terms": len(terms),
            "n_shared": len(shared),
            "shared": shared[:12],
            "jaccard": round(len(shared) / len(union), 3) if union else 0.0,
            "information_content": round(ic, 2),
        }
    return {
        "ok": True,
        "source": f"Enrichr library {library} (generic/oversized terms excluded)",
        "anchor": anchor,
        "anchor_terms": sorted(anchor_terms)[:20],
        "n_anchor_terms": len(anchor_terms),
        "genes": out,
    }


@tool(
    "query_pathway_enrichment",
    "pathway",
    "Hypergeometric enrichment of a gene list against a gene-set library with BH-FDR. "
    "Used to characterise the candidate pool (e.g. is it a Wnt / receptor-tyrosine-kinase module?).",
    genes="gene list",
    library="gene-set library",
    top_n="number of enriched terms to return",
)
def query_pathway_enrichment(genes: list[str], library: str = "Reactome_2022", top_n: int = 15) -> dict:
    from math import comb, log

    lib = load_library(library)
    universe = {g for members in lib.values() for g in members}
    query = {g.upper() for g in genes} & universe
    if len(query) < 3:
        return {"ok": False, "error": "too few genes overlap the library"}
    n, k = len(universe), len(query)
    results = []
    for term, members in lib.items():
        members = set(members) & universe
        hit = query & members
        if len(hit) < 2:
            continue
        m = len(members)
        # hypergeometric upper tail
        p = 0.0
        for x in range(len(hit), min(m, k) + 1):
            try:
                p += comb(m, x) * comb(n - m, k - x) / comb(n, k)
            except (ValueError, ZeroDivisionError):
                continue
        results.append(
            {
                "term": term,
                "overlap": len(hit),
                "term_size": m,
                "genes": sorted(hit)[:25],
                "p_value": p,
                "odds": log((len(hit) + 0.5) / (k - len(hit) + 0.5)) - log((m + 0.5) / (n - m + 0.5)),
            }
        )
    if not results:
        return {"ok": False, "error": "no enriched term"}
    results.sort(key=lambda r: r["p_value"])
    adjusted = stats.bh_fdr([r["p_value"] for r in results[:top_n]])
    for r, q in zip(results[:top_n], adjusted):
        r["fdr"] = q
    return {
        "ok": True,
        "source": f"Enrichr library {library} (hypergeometric + BH)",
        "library": library,
        "n_query": k,
        "n_universe": n,
        "results": results[:top_n],
    }
