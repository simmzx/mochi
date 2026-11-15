"""Open Targets Platform tools (GraphQL v4)."""

from __future__ import annotations

from .http import request_json
from .registry import tool

OT_GQL = "https://api.platform.opentargets.org/api/v4/graphql"

_SEARCH_Q = """
query($q:String!){
  search(queryString:$q, entityNames:["target"], page:{index:0,size:5}){
    hits{ id name entity }
  }
}"""


def _gql(query: str, variables: dict | None = None) -> dict:
    payload = request_json(
        "POST",
        OT_GQL,
        service="opentargets",
        json_body={"query": query, "variables": variables or {}},
        timeout=60,
        allow_status=(200, 400),  # a schema error must not abort the whole stage
    )
    if isinstance(payload, dict) and payload.get("errors"):
        return {"ok": False, "error": payload["errors"], "data": payload.get("data")}
    return {"ok": True, "data": (payload or {}).get("data", {})}


def resolve_ensembl(gene: str) -> str | None:
    """Symbol -> Ensembl gene id using the Open Targets search endpoint."""
    gene = (gene or "").strip()
    if gene.upper().startswith("ENSG"):
        return gene
    res = _gql(_SEARCH_Q, {"q": gene})
    hits = (((res.get("data") or {}).get("search") or {}).get("hits")) or []
    for h in hits:
        if (h.get("name") or "").upper() == gene.upper() and str(h.get("id", "")).startswith("ENSG"):
            return h["id"]
    for h in hits:
        if str(h.get("id", "")).startswith("ENSG"):
            return h["id"]
    return None


@tool(
    "query_opentargets_target",
    "database",
    "Open Targets target profile: Ensembl id, biotype, function descriptions, pathway membership, "
    "subcellular localisation, tractability buckets and safety liabilities.",
    gene="HGNC gene symbol",
)
def query_opentargets_target(gene: str) -> dict:
    ens = resolve_ensembl(gene)
    if not ens:
        return {"ok": False, "error": f"OpenTargets: could not resolve {gene}"}
    q = """
    query($id:String!){
      target(ensemblId:$id){
        id approvedSymbol biotype
        functionDescriptions
        subcellularLocations { location source }
        pathways { pathwayId pathway topLevelTerm }
        tractability { label modality value }
        safetyLiabilities { event datasource }
      }
    }"""
    res = _gql(q, {"id": ens})
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error")}
    t = (res.get("data") or {}).get("target")
    if not t:
        return {"ok": False, "error": f"OpenTargets: no target for {gene}"}
    return {
        "ok": True,
        "source": "Open Targets Platform GraphQL v4",
        "id": t.get("id"),
        "symbol": t.get("approvedSymbol"),
        "biotype": t.get("biotype"),
        "function": (t.get("functionDescriptions") or [""])[0][:1200],
        "subcellular_locations": t.get("subcellularLocations") or [],
        "pathways": [
            {"id": p.get("pathwayId"), "name": p.get("pathway")} for p in (t.get("pathways") or [])[:40]
        ],
        "tractability": [
            {"label": x.get("label"), "modality": x.get("modality"), "value": x.get("value")}
            for x in (t.get("tractability") or [])
        ],
        "safety": [s.get("event") for s in (t.get("safetyLiabilities") or [])][:10],
    }


@tool(
    "query_opentargets_associations",
    "database",
    "Open Targets gene–disease associations: overall association profile, the score for a disease of "
    "interest (default MONDO_0005575 = colorectal cancer) and the top associated diseases.",
    gene="HGNC gene symbol",
    disease_efo="EFO/MONDO id of the disease",
    top_n="how many top diseases to return",
)
def query_opentargets_associations(gene: str, disease_efo: str = "MONDO_0005575", top_n: int = 10) -> dict:
    ens = resolve_ensembl(gene)
    if not ens:
        return {"ok": False, "error": f"OpenTargets: could not resolve {gene}"}
    q = """
    query($id:String!, $n:Int!){
      target(ensemblId:$id){
        id approvedSymbol
        associatedDiseases(page:{index:0,size:$n}){
          count
          rows { disease { id name } score datatypeScores { id score } }
        }
      }
    }"""
    res = _gql(q, {"id": ens, "n": top_n})
    if not res.get("ok"):
        return {"ok": False, "error": res.get("error")}
    t = (res.get("data") or {}).get("target") or {}
    rows = ((t.get("associatedDiseases") or {}).get("rows")) or []
    disease_score = None
    disease_name = None
    for r in rows:
        d = r.get("disease") or {}
        if d.get("id") == disease_efo:
            disease_score = r.get("score")
            disease_name = d.get("name")
            break
    if disease_score is None:
        q2 = """
        query($id:String!, $efo:String!){
          target(ensemblId:$id){
            associatedDiseases(Bs:[$efo]){ rows { disease { id name } score } }
          }
        }"""
        res2 = _gql(q2, {"id": ens, "efo": disease_efo})
        for r in (((res2.get("data") or {}).get("target") or {}).get("associatedDiseases") or {}).get("rows", []):
            disease_score = r.get("score")
            disease_name = (r.get("disease") or {}).get("name")
    return {
        "ok": True,
        "source": "Open Targets Platform GraphQL v4",
        "gene": gene,
        "ensembl_id": t.get("id") or ens,
        "n_associated_diseases": (t.get("associatedDiseases") or {}).get("count"),
        "disease_efo": disease_efo,
        "disease_name": disease_name,
        "disease_score": disease_score,
        "top_diseases": [
            {"id": (r.get("disease") or {}).get("id"), "name": (r.get("disease") or {}).get("name"), "score": r.get("score")}
            for r in rows
        ],
    }


@tool(
    "query_opentargets_known_drugs",
    "database",
    "Known drugs / clinical candidates for a target from Open Targets (druggability proxy).",
    gene="HGNC gene symbol",
)
def query_opentargets_known_drugs(gene: str) -> dict:
    ens = resolve_ensembl(gene)
    if not ens:
        return {"ok": True, "source": "Open Targets Platform GraphQL v4", "gene": gene, "n_drugs": 0, "drugs": []}
    q = """
    query($id:String!){
      target(ensemblId:$id){
        approvedSymbol
        drugAndClinicalCandidates {
          count
          rows { maxClinicalStage drug { id name } diseases { disease { name } } }
        }
      }
    }"""
    res = _gql(q, {"id": ens})
    t = (res.get("data") or {}).get("target") or {}
    kd = t.get("drugAndClinicalCandidates") or {}
    if not res.get("ok") or not kd:
        return {"ok": True, "source": "Open Targets Platform GraphQL v4", "gene": gene, "n_drugs": 0, "drugs": []}
    return {
        "ok": True,
        "source": "Open Targets Platform GraphQL v4",
        "gene": gene,
        "n_drugs": kd.get("count", 0),
        "drugs": [
            {
                "drug_id": (r.get("drug") or {}).get("id"),
                "drug_name": (r.get("drug") or {}).get("name"),
                "phase": r.get("maxClinicalStage"),
                "disease": ((r.get("diseases") or [{}])[0].get("disease") or {}).get("name"),
            }
            for r in (kd.get("rows") or [])
        ],
    }
