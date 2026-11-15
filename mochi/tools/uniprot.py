"""UniProt-backed tools: protein identity, sequence, topology, domains, GO."""

from __future__ import annotations

import re
from typing import Any

from .http import request_json
from .registry import tool

UNIPROT = "https://rest.uniprot.org/uniprotkb"

# Return-fields accepted by the REST API (`/configure/uniprotkb/result-fields`).
# Requesting only these keeps the payload ~8x smaller and the batch queries fast.
FIELDS = (
    "accession,gene_names,length,sequence,ft_transmem,ft_topo_dom,ft_lipid,ft_signal,"
    "ft_domain,cc_function,cc_subcellular_location,xref_pfam,xref_embl,organism_name"
)


def _pfam_names(entry: dict) -> list[str]:
    out = []
    for x in entry.get("uniProtKBCrossReferences", []):
        if x.get("database") != "Pfam":
            continue
        for p in x.get("properties", []):
            if p.get("key") in ("Entry Name", "EntryName"):
                out.append(p.get("value"))
    return [o for o in out if o]


def _feature_text(f: dict) -> str:
    desc = f.get("description", "")
    if not desc:
        desc = f.get("type", "")
    return desc


@tool(
    "query_uniprot",
    "database",
    "Fetch a UniProt entry: sequence, topology (TM / GPI-anchor / signal peptide), domains, "
    "subcellular location, function and GO annotations. Use it to test whether a protein can "
    "transduce a signal itself (transmembrane + intracellular domain) or is an ectoenzyme/GPI protein.",
    protein="HGNC symbol or UniProt accession",
)
def query_uniprot(protein: str) -> dict:
    protein = (protein or "").strip()
    entry = None
    if _looks_like_accession(protein):
        try:
            entry = request_json("GET", f"{UNIPROT}/{protein}.json", service="uniprot",
                                 params={"fields": FIELDS}, timeout=60)
        except Exception:  # noqa: BLE001
            entry = None
    if not entry:
        for reviewed in ("true", "false"):
            payload = request_json(
                "GET",
                f"{UNIPROT}/search",
                service="uniprot",
                params={
                    "query": f"gene_exact:{protein} AND organism_id:9606 AND reviewed:{reviewed}",
                    "format": "json",
                    "size": 5,
                    "fields": FIELDS,
                },
                timeout=60,
            )
            results = (payload or {}).get("results", []) if isinstance(payload, dict) else []
            if results:
                entry = results[0]
                break
    if not entry:
        return {"ok": False, "error": f"UniProt: no entry for {protein}"}
    e = entry

    features = e.get("features", [])
    tm = [f for f in features if f.get("type") == "Transmembrane"]
    sig = [f for f in features if f.get("type") == "Signal peptide"]
    lip = [f for f in features if f.get("type") == "Lipidation"]
    domains = [f for f in features if f.get("type") in ("Domain", "Region", "Motif")]
    topo = [f for f in features if f.get("type") == "Topological domain"]

    gpi = any("gpi" in _feature_text(f).lower() for f in lip)
    locations = []
    function_text = ""
    tissue = ""
    for c in e.get("comments", []):
        ctype = c.get("commentType")
        if ctype == "SUBCELLULAR LOCATION":
            locations += [l.get("location", {}).get("value", "") for l in c.get("subcellularLocations", [])]
        elif ctype == "FUNCTION":
            for t in c.get("texts", []):
                function_text += t.get("value", "") + " "
        elif ctype == "TISSUE SPECIFICITY":
            for t in c.get("texts", []):
                tissue += t.get("value", "") + " "

    pfam = _pfam_names(e)
    interpro = []
    for x in e.get("uniProtKBCrossReferences", []):
        db = x.get("database")
        props = {p.get("key"): p.get("value") for p in x.get("properties", [])}
        if db == "InterPro":
            interpro.append(f"{x.get('id')}:{props.get('Entry Name') or props.get('EntryName', '')}")

    go = {g.get("id"): [] for g in e.get("uniProtKBCrossReferences", []) if g.get("database") == "GO"}
    for g in e.get("uniProtKBCrossReferences", []):
        if g.get("database") == "GO":
            props = {p.get("key"): p.get("value") for p in g.get("properties", [])}
            term = props.get("GoTerm", "")
            if term:
                go.setdefault(g.get("id"), []).append(term)

    seq = e.get("sequence", {}).get("value", "")
    intracellular_length = sum(
        int(t.get("location", {}).get("end", {}).get("value", 0)) - int(t.get("location", {}).get("start", {}).get("value", 0))
        for t in topo
        if "cytoplasmic" in _feature_text(t).lower()
    )

    # ---- decide whether this protein can transduce signals on its own ----
    has_icd = intracellular_length > 20
    is_tm = len(tm) >= 1
    signaling_competent = bool(is_tm and has_icd)
    if gpi and not is_tm:
        architecture = "GPI-anchored ectoprotein (no transmembrane helix, no intracellular domain)"
    elif is_tm and has_icd:
        architecture = f"{len(tm)}-pass transmembrane protein with intracellular domain(s)"
    elif is_tm and not has_icd:
        architecture = "transmembrane protein without a substantial intracellular domain"
    else:
        architecture = "soluble / non-membrane protein"

    return {
        "ok": True,
        "source": "UniProt REST (uniprotkb/search)",
        "accession": e.get("primaryAccession"),
        "entry_name": e.get("uniProtkbId"),
        "gene": ";".join(g.get("geneName", {}).get("value", "") for g in e.get("genes", [])),
        "protein_name": (
            e.get("proteinDescription", {})
            .get("recommendedName", {})
            .get("fullName", {})
            .get("value", "")
        ),
        "organism": e.get("organism", {}).get("scientificName"),
        "length": e.get("sequence", {}).get("length"),
        "sequence": seq,
        "architecture": architecture,
        "topology": {
            "n_transmembrane": len(tm),
            "transmembrane_segments": [
                [f["location"]["start"]["value"], f["location"]["end"]["value"]] for f in tm
            ],
            "gpi_anchored": gpi,
            "signal_peptide": bool(sig),
            "intracellular_residues": intracellular_length,
            "topological_domains": [
                {
                    "description": _feature_text(f),
                    "start": f["location"]["start"]["value"],
                    "end": f["location"]["end"]["value"],
                }
                for f in topo
            ],
        },
        "signaling_competent_by_topology": signaling_competent,
        "functional_sites": [
            {
                "type": f.get("type"),
                "start": f["location"]["start"]["value"],
                "end": f["location"]["end"]["value"],
                "description": _feature_text(f),
            }
            for f in features
            if f.get("type") in ("Active site", "Binding site", "Site", "Metal binding")
        ],
        "domains": [
            {
                "type": f.get("type"),
                "description": _feature_text(f),
                "start": f["location"]["start"]["value"],
                "end": f["location"]["end"]["value"],
            }
            for f in domains
        ],
        "pfam": pfam,
        "interpro": interpro,
        "subcellular_location": sorted({l for l in locations if l}),
        "function": function_text.strip(),
        "tissue_specificity": tissue.strip(),
        "go_terms": [
            {"id": k, "terms": sorted(set(v))} for k, v in go.items() if v
        ],
        "embl_accessions": [
            x.get("id") for x in e.get("uniProtKBCrossReferences", []) if x.get("database") == "EMBL"
        ][:5],
    }


_ACCESSION_RE = re.compile(r"^[OPQ][0-9][A-Z0-9]{3}[0-9]$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$")


def _looks_like_accession(s: str) -> bool:
    return bool(_ACCESSION_RE.match((s or "").strip()))


@tool(
    "query_uniprot_batch",
    "database",
    "Batch-fetch topology/domain summaries for many proteins at once (used by the signaling "
    "potential scorer). Returns one compact record per gene.",
    genes="list of gene symbols",
)
def query_uniprot_batch(genes: list[str]) -> dict:
    genes = [g for g in dict.fromkeys(genes) if g][:200]
    out: dict[str, Any] = {}
    for i in range(0, len(genes), 40):
        chunk = genes[i : i + 40]
        q = " OR ".join(f"gene_exact:{g}" for g in chunk)
        payload = request_json(
            "GET",
            f"{UNIPROT}/search",
            service="uniprot",
            params={
                "query": f"({q}) AND organism_id:9606 AND reviewed:true",
                "format": "json",
                "size": 500,
                "fields": FIELDS,
            },
            timeout=90,
        )
        for e in (payload or {}).get("results", []) if isinstance(payload, dict) else []:
            gene = (e.get("genes") or [{}])[0].get("geneName", {}).get("value", "")
            if not gene or gene not in chunk:
                continue
            feats = e.get("features", [])
            tm = [f for f in feats if f.get("type") == "Transmembrane"]
            lip = [f for f in feats if f.get("type") == "Lipidation"]
            topo = [f for f in feats if f.get("type") == "Topological domain"]
            icd = sum(
                int(t["location"]["end"]["value"]) - int(t["location"]["start"]["value"])
                for t in topo
                if "cytoplasmic" in _feature_text(t).lower()
            )
            pfam = _pfam_names(e)
            function_text = " ".join(
                t.get("value", "")
                for c in e.get("comments", [])
                if c.get("commentType") == "FUNCTION"
                for t in c.get("texts", [])
            )
            locs = sorted(
                {
                    l.get("location", {}).get("value", "")
                    for c in e.get("comments", [])
                    if c.get("commentType") == "SUBCELLULAR LOCATION"
                    for l in c.get("subcellularLocations", [])
                }
                - {""}
            )
            out[gene] = {
                "accession": e.get("primaryAccession"),
                "length": e.get("sequence", {}).get("length"),
                "n_tm": len(tm),
                "gpi": any("gpi" in _feature_text(f).lower() for f in lip),
                "has_signal_peptide": any(f.get("type") == "Signal peptide" for f in feats),
                "intracellular_residues": icd,
                "pfam": pfam,
                "function": function_text[:600],
                "locations": locs,
            }
    return {"ok": True, "source": "UniProt REST (batch)", "n": len(out), "proteins": out}
