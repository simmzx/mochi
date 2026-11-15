"""PubMed / literature tools (NCBI E-utilities)."""

from __future__ import annotations

import re
import time

from .. import stats
from .http import request_json, request_text
from .registry import tool

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _esearch(term: str, retmax: int = 20, sort: str = "relevance") -> tuple[int, list[str]]:
    payload = request_json(
        "GET",
        f"{EUTILS}/esearch.fcgi",
        service="pubmed",
        params={"db": "pubmed", "term": term, "retmode": "json", "retmax": retmax, "sort": sort},
        timeout=60,
        ttl=60 * 60 * 24 * 3,
    )
    res = (payload or {}).get("esearchresult", {})
    return int(res.get("count", 0)), list(res.get("idlist", []))


def _esummary(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    payload = request_json(
        "GET",
        f"{EUTILS}/esummary.fcgi",
        service="pubmed",
        params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
        timeout=60,
        ttl=60 * 60 * 24 * 3,
    )
    result = (payload or {}).get("result", {})
    out = []
    for pid in pmids:
        rec = result.get(pid)
        if not rec:
            continue
        authors = [a.get("name") for a in rec.get("authors", [])][:3]
        out.append(
            {
                "pmid": pid,
                "title": rec.get("title", "").strip(),
                "journal": rec.get("source", ""),
                "year": (rec.get("pubdate", "") or "")[:4],
                "authors": authors,
                "doi": next((x.get("value") for x in rec.get("articleids", []) if x.get("idtype") == "doi"), None),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pid}/",
            }
        )
    return out


@tool(
    "query_pubmed",
    "literature",
    "PubMed search: returns the total hit count, the publication trend and the top records "
    "(title, journal, year, PMID, DOI). Use it for evidence retrieval and novelty assessment.",
    query="PubMed query string",
    retmax="how many records to return",
)
def query_pubmed(query: str, retmax: int = 10) -> dict:
    count, ids = _esearch(query, retmax=retmax)
    records = _esummary(ids)
    years: dict[str, int] = {}
    for r in records:
        years[r["year"]] = years.get(r["year"], 0) + 1
    return {
        "ok": True,
        "source": "NCBI PubMed E-utilities",
        "query": query,
        "count": count,
        "retrieved": len(records),
        "records": records,
        "recent_years": dict(sorted(years.items(), reverse=True)[:5]),
    }


@tool(
    "query_pubmed_cooccurrence",
    "literature",
    "Literature co-mention analysis: for each gene, how many PubMed records co-mention it with "
    "the anchor gene (and, optionally, the disease). Returns counts + example PMIDs.",
    anchor="anchor gene symbol (e.g. DPEP1)",
    genes="candidate gene list",
    disease="optional disease term added to the query",
)
def query_pubmed_cooccurrence(anchor: str, genes: list[str], disease: str = "") -> dict:
    out = {}
    extra = f" AND {disease}" if disease else ""
    for g in genes:
        term = f'("{anchor}"[Title/Abstract]) AND ("{g}"[Title/Abstract]){extra}'
        count, ids = _esearch(term, retmax=5)
        out[g] = {"cooccurrence": count, "pmids": ids}
        time.sleep(0.35)  # be polite to NCBI (3 req/s without API key)
    return {
        "ok": True,
        "source": "NCBI PubMed E-utilities (co-mention)",
        "anchor": anchor,
        "disease": disease,
        "cooccurrence": out,
    }


@tool(
    "query_pubmed_novelty",
    "literature",
    "Novelty assessment for a candidate target: PubMed volume for gene+CRC, gene+therapy and "
    "gene+drug queries, plus a saturation score (0 = heavily studied, 1 = unexplored).",
    gene="HGNC symbol",
    disease="disease context (default: colorectal cancer)",
)
def query_pubmed_novelty(gene: str, disease: str = "colorectal cancer") -> dict:
    q_crc = f'"{gene}"[Title/Abstract] AND ("{disease}"[Title/Abstract] OR CRC[Title/Abstract] OR colon cancer[Title/Abstract])'
    q_all = f'"{gene}"[Title/Abstract]'
    q_drug = f'"{gene}"[Title/Abstract] AND (inhibitor[Title/Abstract] OR antibody[Title/Abstract] OR "small molecule"[Title/Abstract] OR drug[Title/Abstract])'
    n_crc, _ = _esearch(q_crc, retmax=1)
    n_all, _ = _esearch(q_all, retmax=1)
    n_drug, _ = _esearch(q_drug, retmax=1)
    # Novelty must account for the *overall* study saturation of a gene, not only
    # its CRC literature: a gene with 0 CRC papers but 800 general papers is not a
    # discovery. Saturating transform -> 1.0 for unexplored genes, -> 0 for
    # heavily studied ones.
    novelty = 1.0 / (1.0 + n_crc / 30.0 + n_all / 400.0)
    drugged = n_drug > 0
    return {
        "ok": True,
        "source": "NCBI PubMed E-utilities (novelty)",
        "gene": gene,
        "n_gene_disease": n_crc,
        "n_gene_total": n_all,
        "n_gene_drug": n_drug,
        "novelty_score": round(novelty, 3),
        "drug_literature_present": drugged,
        "queries": {"crc": q_crc, "all": q_all, "drug": q_drug},
    }


@tool(
    "fetch_pubmed_abstracts",
    "literature",
    "Fetch abstracts for the top PubMed hits of a query (used by the critic to check whether an "
    "association is mechanistic or only correlative).",
    query="PubMed query",
    retmax="number of abstracts",
)
def fetch_pubmed_abstracts(query: str, retmax: int = 5) -> dict:
    count, ids = _esearch(query, retmax=retmax)
    out = []
    for pid in ids:
        xml = request_text(
            "GET",
            f"{EUTILS}/efetch.fcgi",
            service="pubmed",
            params={"db": "pubmed", "id": pid, "retmode": "text", "rettype": "abstract"},
            timeout=60,
            ttl=60 * 60 * 24 * 3,
        )
        text = re.sub(r"\s+", " ", xml or "").strip()
        out.append({"pmid": pid, "abstract": text[:1800]})
    return {"ok": True, "source": "NCBI PubMed E-utilities (efetch)", "query": query, "count": count, "abstracts": out}


@tool(
    "citation_network_score",
    "literature",
    "Composite literature score for a gene: co-mention with the anchor, disease specificity "
    "(gene+disease / gene total) and novelty — the three signals the critic asks for.",
    anchor="anchor gene",
    genes="candidate genes",
    disease="disease term",
)
def citation_network_score(anchor: str, genes: list[str], disease: str = "colorectal cancer") -> dict:
    co = query_pubmed_cooccurrence(anchor, genes, disease="")
    out = {}
    for g in genes:
        n_all, _ = _esearch(f'"{g}"[Title/Abstract]', retmax=1)
        n_dis, _ = _esearch(f'"{g}"[Title/Abstract] AND "{disease}"[Title/Abstract]', retmax=1)
        c = co["cooccurrence"].get(g, {}).get("cooccurrence", 0)
        specificity = (n_dis / n_all) if n_all else 0.0
        out[g] = {
            "cooccurrence_with_anchor": c,
            "n_total": n_all,
            "n_disease": n_dis,
            "disease_specificity": round(specificity, 3),
            "novelty": round(max(0.0, 1.0 - n_dis / 300.0), 3),
            "score": round(min(1.0, 0.5 * (c > 0) + 0.5 * min(1.0, c / 10.0)), 3),
        }
        time.sleep(0.35)
    vals = [v["cooccurrence_with_anchor"] for v in out.values()]
    return {
        "ok": True,
        "source": "NCBI PubMed E-utilities (citation network)",
        "anchor": anchor,
        "disease": disease,
        "median_cooccurrence": stats.median(vals) if vals else 0,
        "genes": out,
    }
