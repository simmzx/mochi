"""Identifier resolution (mygene.info) — gene symbol <-> Entrez <-> Ensembl."""

from __future__ import annotations

from .http import request_json
from .registry import tool

MYGENE = "https://mygene.info/v3"

_MEM: dict[str, dict] = {}


@tool(
    "resolve_gene_ids",
    "database",
    "Map HGNC symbols to Entrez / Ensembl identifiers in batch (mygene.info). "
    "Every cross-database tool needs this.",
    genes="list of gene symbols",
)
def resolve_gene_ids(genes: list[str]) -> dict:
    genes = [g.strip().upper() for g in dict.fromkeys(genes) if g and g.strip()]
    todo = [g for g in genes if g not in _MEM]
    for i in range(0, len(todo), 80):
        chunk = todo[i : i + 80]
        payload = request_json(
            "POST",
            f"{MYGENE}/query",
            service="mygene",
            data={"q": ",".join(chunk), "scopes": "symbol", "species": "human",
                  "fields": "symbol,entrezgene,ensembl.gene,name,alias", "size": 5},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=60,
        )
        for hit in (payload or []):
            sym = (hit.get("symbol") or "").upper()
            if not sym:
                continue
            ens = hit.get("ensembl")
            if isinstance(ens, list):
                ens = ens[0].get("gene") if ens and isinstance(ens[0], dict) else None
            elif isinstance(ens, dict):
                ens = ens.get("gene")
            _MEM[sym] = {
                "symbol": sym,
                "entrez": hit.get("entrezgene"),
                "ensembl": ens,
                "name": hit.get("name"),
            }
    resolved = {g: _MEM.get(g) for g in genes}
    missing = [g for g, v in resolved.items() if not v]
    return {
        "ok": True,
        "source": "mygene.info v3",
        "resolved": {g: v for g, v in resolved.items() if v},
        "unresolved": missing,
        "n": len([v for v in resolved.values() if v]),
    }


def exact_ids(genes: list[str], *, return_lists: bool = True) -> tuple[list[int], dict[int, str], list[str]]:
    """Helper for other tools: -> (entrez_ids, entrez->symbol, missing)."""
    res = resolve_gene_ids(genes)
    resolved = res.get("resolved", {}) if res.get("ok") else {}
    ids: list[int] = []
    back: dict[int, str] = {}
    missing = list(genes)
    for g in genes:
        v = resolved.get(g.strip().upper())
        if v and v.get("entrez"):
            eid = int(v["entrez"])
            if eid not in back:
                ids.append(eid)
                back[eid] = v.get("symbol", g)
            if g in missing:
                missing.remove(g)
    return ids, back, missing
