"""Protein-network tools: STRING functional partners + IntAct physical interactions."""

from __future__ import annotations

from .http import request_json
from .identifiers import exact_ids
from .registry import tool

STRING = "https://string-db.org/api/json"
INTACT = "https://www.ebi.ac.uk/intact/ws/interaction/findInteractions"


@tool(
    "query_string",
    "network",
    "STRING interaction partners of a protein with per-channel scores (experimental, database, "
    "text-mining, co-expression). The experimental score is the strongest association evidence.",
    protein="gene symbol or UniProt accession",
    limit="max partners",
    min_score="minimum combined score (0-1)",
)
def query_string(protein: str, limit: int = 50, min_score: float = 0.4) -> dict:
    partners_raw = request_json(
        "GET",
        f"{STRING}/interaction_partners",
        service="string",
        params={"identifiers": protein, "species": 9606, "limit": max(limit, 5), "caller_identity": "mochi"},
        timeout=60,
    )
    edges = request_json(
        "GET",
        f"{STRING}/network",
        service="string",
        params={"identifiers": protein, "species": 9606, "required_score": int(min_score * 1000),
                "caller_identity": "mochi"},
        timeout=60,
    )
    partners = []
    for p in partners_raw or []:
        score = float(p.get("score", 0))
        if score < min_score:
            continue
        partners.append(
            {
                "gene": p.get("preferredName_B") or p.get("preferredName_A"),
                "score": round(score, 3),
                "experimental": round(float(p.get("escore", 0)), 3),
                "database": round(float(p.get("dscore", 0)), 3),
                "textmining": round(float(p.get("tscore", 0)), 3),
                "coexpression": round(float(p.get("ascore", 0)), 3),
            }
        )
    partners.sort(key=lambda x: -x["score"])
    return {
        "ok": True,
        "source": "STRING v12 API",
        "query": protein,
        "n_partners": len(partners),
        "n_edges_reported": len(edges or []),
        "partners": partners[:limit],
        "mean_experimental": round(sum(p["experimental"] for p in partners) / len(partners), 3) if partners else 0,
    }


@tool(
    "query_intact",
    "network",
    "IntAct curated physical / binary protein interactions for a protein (MI-annotated, "
    "experiment-backed). Complements STRING for direct binding evidence.",
    protein="gene symbol or UniProt accession",
    page_size="max interactions",
)
def query_intact(protein: str, page_size: int = 100) -> dict:
    payload = request_json(
        "GET",
        f"{INTACT}/{protein}",
        service="intact",
        params={"page": 0, "pageSize": page_size},
        timeout=90,
    )
    content = (payload or {}).get("content", []) if isinstance(payload, dict) else []
    partners: dict[str, dict] = {}
    for it in content:
        a, b = it.get("moleculeA"), it.get("moleculeB")
        other = b if (a or "").upper() == protein.upper() else a
        if not other or other.upper() == protein.upper():
            continue
        partners.setdefault(
            other,
            {
                "gene": other,
                "n_interactions": 0,
                "methods": set(),
                "pubmed": set(),
            },
        )
        partners[other]["n_interactions"] += 1
        for m in (it.get("interactionType") or []) if isinstance(it.get("interactionType"), list) else []:
            partners[other]["methods"].add(str(m))
        for d in it.get("publicationPubmedIdentifier") or []:
            partners[other]["pubmed"].add(str(d))
    out = []
    for v in partners.values():
        n = v["n_interactions"]
        out.append(
            {
                "gene": v["gene"],
                "n_interactions": n,
                "methods": sorted(v["methods"])[:3],
                "pmids": sorted(v["pubmed"])[:3],
                "score": round(min(1.0, n / 5.0), 3),
            }
        )
    out.sort(key=lambda x: -x["n_interactions"])
    return {
        "ok": True,
        "source": "IntAct REST (EBI)",
        "query": protein,
        "n_partners": len(out),
        "partners": out[:page_size],
    }


@tool(
    "build_ppi_union",
    "network",
    "Union of STRING + IntAct partners, with a combined association score (max of STRING "
    "combined and IntAct interaction-count score). This is the PPI branch of candidate generation.",
    protein="gene symbol",
    limit="max partners",
)
def build_ppi_union(protein: str, limit: int = 60) -> dict:
    s = query_string(protein, limit=limit)
    i = query_intact(protein, page_size=limit)
    merged: dict[str, dict] = {}
    for p in s.get("partners", []) if s.get("ok") else []:
        merged[p["gene"]] = {
            "gene": p["gene"],
            "string": p["score"],
            "string_experimental": p["experimental"],
            "intact": 0.0,
            "n_intact": 0,
            "source": ["STRING"],
        }
    for p in i.get("partners", []) if i.get("ok") else []:
        rec = merged.setdefault(
            p["gene"],
            {"gene": p["gene"], "string": 0.0, "string_experimental": 0.0, "intact": 0.0,
             "n_intact": 0, "source": []},
        )
        rec["intact"] = p["score"]
        rec["n_intact"] = p["n_interactions"]
        if "IntAct" not in rec["source"]:
            rec["source"].append("IntAct")
    for rec in merged.values():
        rec["association"] = round(max(rec["string"], rec["intact"]), 3)
    partners = sorted(merged.values(), key=lambda r: -r["association"])[:limit]
    return {
        "ok": True,
        "source": "STRING v12 + IntAct (union)",
        "query": protein,
        "n_partners": len(partners),
        "partners": partners,
    }
