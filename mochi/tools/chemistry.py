"""Chemistry / druggability tools (ChEMBL, DGIdb)."""

from __future__ import annotations

from .http import request_json
from .registry import tool

CHEMBL = "https://www.ebi.ac.uk/chembl/api/data"
DGIDB = "https://dgidb.org/api/graphql"


@tool(
    "query_chembl_target",
    "chemistry",
    "ChEMBL target lookup and ligand statistics for a gene: target id, number of bioactivities, "
    "number of distinct compounds and the best clinical phase — a direct druggability signal.",
    gene="gene symbol",
)
def query_chembl_target(gene: str) -> dict:
    payload = request_json(
        "GET",
        f"{CHEMBL}/target/search",
        service="chembl",
        params={"q": gene, "format": "json", "limit": 5},
        timeout=60,
    )
    targets = (payload or {}).get("targets", []) if isinstance(payload, dict) else []
    human = [t for t in targets if t.get("organism") == "Homo sapiens"]
    if not human:
        return {"ok": True, "source": "ChEMBL REST", "gene": gene, "n_targets": 0,
                "n_compounds": 0, "n_bioactivities": 0, "max_phase": 0, "drugs": []}
    tgt = human[0]
    tid = tgt.get("target_chembl_id")
    acts = request_json(
        "GET",
        f"{CHEMBL}/activity",
        service="chembl",
        params={"target_chembl_id": tid, "format": "json", "limit": 1},
        timeout=60,
    )
    n_act = ((acts or {}).get("page_meta") or {}).get("total_count", 0) if isinstance(acts, dict) else 0
    mechs = request_json(
        "GET",
        f"{CHEMBL}/mechanism",
        service="chembl",
        params={"target_chembl_id": tid, "format": "json", "limit": 20},
        timeout=60,
    )
    mech_rows = (mechs or {}).get("mechanisms", []) if isinstance(mechs, dict) else []
    drugs = sorted({m.get("molecule_chembl_id") for m in mech_rows if m.get("molecule_chembl_id")})
    return {
        "ok": True,
        "source": "ChEMBL REST API",
        "gene": gene,
        "target_chembl_id": tid,
        "target_name": tgt.get("pref_name"),
        "n_bioactivities": n_act,
        "n_compounds": ((acts or {}).get("page_meta") or {}).get("total_count", 0)
        if isinstance(acts, dict)
        else 0,
        "n_mechanisms": len(mech_rows),
        "n_drugs": len(drugs),
        "drug_ids": drugs[:10],
    }


@tool(
    "query_dgidb",
    "chemistry",
    "DGIdb drug–gene interactions (approved / investigational drugs, interaction types).",
    gene="gene symbol",
)
def query_dgidb(gene: str) -> dict:
    q = """
    query($g:String!){
      genes(names:[$g]){
        nodes{ name interactions{ drug{ name conceptId } interactionTypes{ type } } }
      }
    }"""
    payload = request_json(
        "POST",
        DGIDB,
        service="dgidb",
        json_body={"query": q, "variables": {"g": gene}},
        timeout=60,
    )
    try:
        nodes = payload["data"]["genes"]["nodes"]
        interactions = nodes[0]["interactions"] if nodes else []
    except Exception:
        interactions = []
    drugs = {}
    for it in interactions:
        d = (it.get("drug") or {}).get("name")
        if not d:
            continue
        types = [t.get("type") for t in it.get("interactionTypes", []) if t.get("type")]
        drugs.setdefault(d, set()).update(types)
    return {
        "ok": True,
        "source": "DGIdb GraphQL API",
        "gene": gene,
        "n_drugs": len(drugs),
        "drugs": [{"name": k, "types": sorted(v)} for k, v in list(drugs.items())[:25]],
    }


@tool(
    "druggability_score",
    "chemistry",
    "Composite druggability score (0-1) from ChEMBL ligand volume, DGIdb interactions and "
    "Open Targets tractability buckets.",
    gene="gene symbol",
)
def druggability_score(gene: str) -> dict:
    from .opentargets import query_opentargets_known_drugs, query_opentargets_target

    chembl = query_chembl_target(gene)
    dgidb = query_dgidb(gene)
    ot_drugs = query_opentargets_known_drugs(gene)
    ot_target = query_opentargets_target(gene)

    tractability = ot_target.get("tractability", []) if ot_target.get("ok") else []
    buckets = sorted({t["label"] for t in tractability if t.get("value")})
    n_act = chembl.get("n_bioactivities", 0)
    n_drugs = (dgidb.get("n_drugs", 0) or 0) + (ot_drugs.get("n_drugs", 0) or 0)
    structural = any("structur" in b.lower() or "ligand" in b.lower() for b in buckets)

    score = (
        0.4 * min(1.0, n_act / 200.0)
        + 0.35 * min(1.0, n_drugs / 5.0)
        + 0.25 * (1.0 if structural or buckets else 0.0)
    )
    return {
        "ok": True,
        "source": "ChEMBL + DGIdb + Open Targets (composite)",
        "gene": gene,
        "score": round(score, 3),
        "n_bioactivities": n_act,
        "n_drugs": n_drugs,
        "chembl_target": chembl.get("target_chembl_id"),
        "tractability_buckets": buckets,
    }
