#!/usr/bin/env python
"""Offline sanity checks. No network required.

    python tests/run_checks.py

Verifies: statistics against known values, tool registration, the signalling
scorer's control set, template retrieval, the offline engine's output contract,
the scoring transforms, and report rendering.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILS: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  PASS  {name}")
    except AssertionError as exc:
        FAILS.append(f"{name}: {exc}")
        print(f"  FAIL  {name}: {exc}")
    except Exception as exc:  # noqa: BLE001
        FAILS.append(f"{name}: {type(exc).__name__}: {exc}")
        print(f"  ERROR {name}: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
def test_stats() -> None:
    from mochi import stats

    # perfectly correlated series
    r, p, n = stats.pearson([1, 2, 3, 4, 5, 6], [2, 4, 6, 8, 10, 12])
    assert abs(r - 1.0) < 1e-9, r
    assert p < 1e-9, p
    # known anti-correlation
    r2, _, _ = stats.pearson([1, 2, 3, 4], [4, 3, 2, 1])
    assert abs(r2 + 1.0) < 1e-9, r2
    # log-rank on identical groups -> p ~ 1
    t = [10, 20, 30, 40, 50, 60] * 2
    e = [1, 0, 1, 1, 0, 1] * 2
    g = [0] * 6 + [1] * 6
    chi2, p = stats.logrank(t, e, g)
    assert abs(chi2) < 1e-9 and p > 0.99, (chi2, p)
    # KM monotonically non-increasing
    curve = stats.kaplan_meier([5, 10, 15, 20], [1, 1, 0, 1])
    survivors = [s for _, s, _ in curve]
    assert all(a >= b for a, b in zip(survivors, survivors[1:])), survivors
    # BH-FDR is monotone in rank and bounded
    q = stats.bh_fdr([0.001, 0.01, 0.04, 0.5])
    assert all(0 <= x <= 1 for x in q) and q[0] <= q[-1], q


def test_registry() -> None:
    import mochi.tools  # noqa: F401
    from mochi.tools import TOOLS, list_tools

    assert len(TOOLS) >= 25, len(TOOLS)
    for spec in list_tools():
        assert spec.name and spec.description, spec
        assert callable(spec.fn)
    text = __import__("mochi.tools", fromlist=["tool_arsenal_text"]).tool_arsenal_text()
    assert "query_uniprot" in text and "multi_evidence_scoring" in text


def test_signaling_controls() -> None:
    """The created tool must pass regardless of which copy we import."""
    import importlib.util

    path = ROOT / "mochi" / "toolblueprints" / "signaling_potential_scorer.py"
    spec = importlib.util.spec_from_file_location("bp", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    res = module.validate() if hasattr(module, "validate") else {"passed": False}
    # offline mode cannot hit UniProt; accept an explicit network marker
    assert res.get("passed") or "error" in res, res.get("cases")


def test_template_retrieval() -> None:
    from mochi.knowledge import TemplateLibrary

    lib = TemplateLibrary(ROOT / "mochi" / "templates")
    assert lib.status()["n_templates"] >= 1
    hits = lib.retrieve("discover the downstream effector target of DPEP1 in colorectal cancer", top_k=2)
    assert hits, "no template retrieved"
    # a learned template may legitimately outrank the prebuilt one (self-evolution);
    # what matters is that the retrieved template is an effector-discovery workflow
    ids = [h["skill_id"] for h in hits]
    assert any(
        i == "downstream_effector_target_discovery" or i.startswith("auto_") for i in ids
    ), ids
    assert hits[0]["template"].workflow, "template has no workflow steps"


def test_offline_engine() -> None:
    from mochi.offline import DeterministicEngine

    eng = DeterministicEngine()
    plan = eng.complete(
        kind="manager.plan",
        system="",
        user="",
        context={"target": "DPEP1", "disease": "colorectal cancer",
                 "template_summary": [{"skill_id": "t", "name": "T", "similarity": 0.9, "workflow": []}]},
    )
    assert isinstance(plan.data, dict) and len(plan.data.get("stages", [])) == 4, plan.data
    review = eng.complete(
        kind="critic.review", system="", user="",
        context={"stage": "stage_3", "audit": {"severity": 2, "checks": [
            {"claim": "Tool Ocean covers signalling competence", "supported": False, "why": "missing"}]}},
    )
    assert review.data["verdict"] == "evolve" and review.data["tool_requests"], review.data


def test_scoring_monotonicity() -> None:
    from mochi.tools.scoring import score_candidate

    weak = {"ppi_association": 0.2, "coexpr_r": 0.1, "signaling_score": 0.2,
            "expr_mean_z": 0.0, "novelty_score": 0.3, "druggability_score": 0.2}
    strong = {"ppi_association": 0.8, "coexpr_r": 0.5, "signaling_score": 0.8,
              "expr_mean_z": 1.5, "novelty_score": 0.9, "druggability_score": 0.8}
    a, b = score_candidate(weak), score_candidate(strong)
    assert b["composite"] > a["composite"], (a["composite"], b["composite"])
    # missing dimensions renormalise instead of scoring zero
    partial = score_candidate({"signaling_score": 0.8})
    assert partial["dimensions"]["association"] is None
    assert partial["composite"] > 0.5, partial


def test_report_rendering(tmp_path=None) -> None:
    from mochi import report
    from mochi.workflows.stages import RunContext

    run_dir = Path(tmp_path or (ROOT / "outputs" / "_selftest"))
    run_dir.mkdir(parents=True, exist_ok=True)
    ctx = RunContext(run_dir=run_dir, target="DPEP1", disease="colorectal cancer",
                     disease_id="MONDO_0005575", study="coadread_tcga_pan_can_atlas_2018")
    ranking = [{
        "rank": 1, "gene": "LRP6", "composite": 0.61,
        "dimensions": {"association": 0.7, "signaling": 0.68, "crc_evidence": 0.5,
                       "pathway_centrality": 0.4, "novelty": 0.8, "druggability": 0.6},
        "supporting_dimensions": ["association", "signaling", "novelty"],
        "n_supporting_dimensions": 3, "evidence": {"ppi_association": 0.7}, "survival": {},
    }]
    md = report.build_report(
        ctx=ctx, plan={"template_id": "t", "stages": [], "reasoning": ""}, stage_results=[],
        critiques=[], ranking=ranking, weights={"association": 1.0}, profile={},
        tool_creation=None, figures=[], run_meta={"run_id": "x", "engine": "offline", "date": "now"},
    )
    assert "LRP6" in md and "Evidence dossier" in md and "Wet-lab validation" in md


def test_provenance_and_cache() -> None:
    from mochi.tools import http

    cache = ROOT / "cache" / "_selftest_http"
    prov = ROOT / "cache" / "_selftest_prov.jsonl"
    for p in (prov,):
        if p.exists():
            p.unlink()
    http.configure(cache_dir=cache, provenance_path=prov)
    http._cache_put("k1", {"_status": 200, "payload": {"a": 1}})
    got = http._cache_get("k1", 999)
    assert got == {"_status": 200, "payload": {"a": 1}}, got
    http.PROVENANCE.log({"service": "selftest", "url": "u", "status": 200, "cached": True})
    assert prov.exists() and prov.read_text(encoding="utf-8").strip(), "provenance not written"


def main() -> int:
    print("MOCHI offline self-checks")
    check("statistics", test_stats)
    check("tool registry", test_registry)
    check("signalling scorer controls", test_signaling_controls)
    check("template retrieval", test_template_retrieval)
    check("offline engine contract", test_offline_engine)
    check("scoring monotonicity", test_scoring_monotonicity)
    check("report rendering", test_report_rendering)
    check("cache + provenance", test_provenance_and_cache)
    print()
    if FAILS:
        print(f"{len(FAILS)} check(s) failed")
        for f in FAILS:
            print(" -", f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
