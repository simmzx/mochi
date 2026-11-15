"""Functional annotation tools: QuickGO (Gene Ontology) and InterPro/Pfam domains."""

from __future__ import annotations

from .http import request_json
from .identifiers import resolve_gene_ids
from .registry import tool

QUICKGO = "https://www.ebi.ac.uk/QuickGO/services/annotation/search"
INTERPRO = "https://www.ebi.ac.uk/interpro/api"

SIGNALLING_GO_HINTS = {
    "GO:0007165": "signal transduction",
    "GO:0007166": "cell surface receptor signaling pathway",
    "GO:0038023": "signaling receptor activity",
    "GO:0004871": "signal transducer activity",
    "GO:0004888": "transmembrane signaling receptor activity",
    "GO:0004872": "signaling receptor activity (alt)",
    "GO:0007167": "enzyme linked receptor protein signaling pathway",
    "GO:0004930": "G protein-coupled receptor activity",
}


def _uniprot_for(gene: str) -> str | None:
    from .uniprot import query_uniprot

    res = query_uniprot(gene)
    return res.get("accession") if res.get("ok") else None


@tool(
    "query_quickgo",
    "annotation",
    "Gene Ontology annotations of a protein (QuickGO): molecular function / biological process / "
    "cellular component, evidence codes and a derived signalling-annotation score.",
    gene="gene symbol",
)
def query_quickgo(gene: str) -> dict:
    acc = _uniprot_for(gene)
    if not acc:
        return {"ok": False, "error": f"no UniProt accession for {gene}"}
    payload = request_json(
        "GET",
        QUICKGO,
        service="quickgo",
        params={"geneProductId": f"UniProtKB:{acc}", "limit": 100, "taxonId": 9606},
        timeout=60,
    )
    results = (payload or {}).get("results", []) if isinstance(payload, dict) else []
    by_aspect: dict[str, list[dict]] = {}
    for r in results:
        aspect = r.get("goAspect", "other")
        by_aspect.setdefault(aspect, []).append(
            {"id": r.get("goId"), "evidence": r.get("goEvidence"), "ref": r.get("reference")}
        )
    signalling = sorted({r.get("goId") for r in results if r.get("goId") in SIGNALLING_GO_HINTS})
    return {
        "ok": True,
        "source": "QuickGO annotation service (EBI)",
        "gene": gene,
        "uniprot": acc,
        "n_annotations": len(results),
        "by_aspect": {k: len(v) for k, v in by_aspect.items()},
        "signalling_terms": [{"id": g, "name": SIGNALLING_GO_HINTS[g]} for g in signalling],
        "signalling_go_score": round(min(1.0, len(signalling) / 4.0), 3),
        "examples": [
            {"go": r.get("goId"), "aspect": r.get("goAspect"), "evidence": r.get("goEvidence")}
            for r in results[:15]
        ],
    }


@tool(
    "query_interpro",
    "annotation",
    "InterPro/Pfam domain architecture of a protein, with a compact flag set for signalling "
    "domain families (kinase, 7TM/GPCR, LRR, Frizzled, death domain, phosphatase, ...).",
    gene="gene symbol or UniProt accession",
)
def query_interpro(gene: str) -> dict:
    acc = gene if _is_uniprot(gene) else _uniprot_for(gene)
    if not acc:
        return {"ok": False, "error": f"no UniProt accession for {gene}"}
    payload = request_json(
        "GET",
        f"{INTERPRO}/entry/pfam/protein/uniprot/{acc}/",
        service="interpro",
        timeout=60,
        allow_status=(200, 204),
    )
    results = (payload or {}).get("results", []) if isinstance(payload, dict) else []
    domains = []
    for r in results:
        meta = r.get("metadata", {})
        prot = (r.get("proteins") or [{}])[0]
        loc = prot.get("entry_protein_locations") or []
        frags = []
        for l in loc:
            for f in l.get("fragments", []):
                frags.append([f.get("start"), f.get("end")])
        domains.append(
            {
                "accession": meta.get("accession"),
                "name": meta.get("name"),
                "type": meta.get("type"),
                "description": (meta.get("description") or [{}])[0].get("text", "")[:300]
                if isinstance(meta.get("description"), list)
                else str(meta.get("description"))[:300],
                "locations": frags,
            }
        )
    blob = " ".join(f"{d['name']} {d['description']}" for d in domains).lower()
    flags = {
        "kinase": any(k in blob for k in ("kinase", "phosphotransferase")),
        "seven_tm_gpcr": any(k in blob for k in ("7tm", "rhodopsin", "gpcr", "g protein-coupled")),
        "frizzled": "frizzled" in blob,
        "ldl_receptor": any(k in blob for k in ("ldl", "low-density lipoprotein", "low density lipoprotein")),
        "lrr": any(k in blob for k in ("leucine-rich", "leucine rich", "lrr")),
        "death_domain": "death" in blob,
        "phosphatase": "phosphatase" in blob,
        "immunoglobulin": "immunoglobulin" in blob,
        "egf": "egf" in blob,
        "tnfr": "tumor necrosis factor receptor" in blob or "tnfr" in blob,
        "cytokine_receptor": any(k in blob for k in ("cytokine receptor", "hematopoietin", "fibronectin type iii")),
        "ion_channel": "channel" in blob,
        "gpi_anchor_enzyme": any(k in blob for k in ("metallopeptidase", "dipeptidase", "peptidase")),
    }
    signalling_families = [
        k for k in ("kinase", "seven_tm_gpcr", "frizzled", "ldl_receptor", "death_domain",
                    "phosphatase", "tnfr", "cytokine_receptor", "ion_channel")
        if flags[k]
    ]
    return {
        "ok": True,
        "source": "InterPro REST (EBI)",
        "gene": gene,
        "uniprot": acc,
        "n_domains": len(domains),
        "domains": domains[:20],
        "signalling_domain_flags": flags,
        "signalling_families": signalling_families,
        "signalling_domain_count": len(signalling_families),
    }


def _is_uniprot(s: str) -> bool:
    from .uniprot import _looks_like_accession

    return _looks_like_accession(s)


@tool(
    "query_domain_architecture_panel",
    "annotation",
    "Batch domain-architecture summary for a candidate panel: Pfam families + signalling-domain "
    "flags from UniProt cross-references (no per-gene REST call beyond the batch UniProt query).",
    genes="candidate gene symbols",
)
def query_domain_architecture_panel(genes: list[str]) -> dict:
    from .uniprot import query_uniprot_batch

    batch = query_uniprot_batch(genes)
    proteins = batch.get("proteins", {})
    out = {}
    for gene, rec in proteins.items():
        blob = " ".join(rec.get("pfam", []) + [rec.get("function", "")]).lower()
        flags = {
            "kinase": "kinase" in blob,
            "gpcr": "7tm" in blob or "rhodopsin" in blob,
            "frizzled": "frizzled" in blob,
            "ldl_receptor": "ldl" in blob,
            "lrr": "leucine" in blob,
            "ig_like": "immunoglobulin" in blob,
            "tnfr": "tumor necrosis factor receptor" in blob,
            "channel": "channel" in blob,
        }
        out[gene] = {
            "pfam": rec.get("pfam", []),
            "flags": flags,
            "n_signalling_domains": sum(1 for v in flags.values() if v),
        }
    return {
        "ok": True,
        "source": "UniProt Pfam cross-references (batch)",
        "n_genes": len(out),
        "architecture": out,
    }
