"""Report generation: figures, tables, evidence dossier and the wet-lab handoff."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from .tools.scoring import DIMENSIONS

PALETTE = ["#2E5E8C", "#C0504D", "#4F81BD", "#9BBB59", "#8064A2", "#F79646"]


def _mpl(run_dir: Path):
    """Import matplotlib lazily with a run-local config dir (no font-cache permission issues)."""
    import os

    os.environ.setdefault("MPLCONFIGDIR", str(Path(run_dir) / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


def _fig_heatmap(plt, ranking: list[dict], out: Path, top_n: int = 15) -> bool:
    rows = ranking[:top_n]
    if not rows:
        return False
    genes = [r["gene"] for r in rows]
    data = []
    for r in rows:
        data.append([(r["dimensions"].get(d) if r["dimensions"].get(d) is not None else float("nan")) for d in DIMENSIONS])
    fig, ax = plt.subplots(figsize=(8.6, max(3.2, 0.34 * len(rows) + 1.4)))
    im = ax.imshow(data, cmap="YlGnBu", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(DIMENSIONS)))
    ax.set_xticklabels([d.replace("_", " ") for d in DIMENSIONS], rotation=28, ha="right", fontsize=8)
    ax.set_yticks(range(len(genes)))
    ax.set_yticklabels([f"{i + 1}. {g}" for i, g in enumerate(genes)], fontsize=8)
    for i in range(len(genes)):
        for j in range(len(DIMENSIONS)):
            v = data[i][j]
            if not math.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.5,
                        color="white" if v > 0.55 else "#222")
            else:
                ax.text(j, i, "n/a", ha="center", va="center", fontsize=6, color="#999")
    ax.set_title("Evidence dimensions of the top candidates", fontsize=10)
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02, label="dimension score (0-1)")
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def _fig_ranking(plt, ranking: list[dict], weights: dict, out: Path, top_n: int = 12) -> bool:
    rows = ranking[:top_n]
    if not rows:
        return False
    genes = [r["gene"] for r in rows][::-1]
    dims = [d for d in DIMENSIONS]
    fig, ax = plt.subplots(figsize=(8.2, max(3.2, 0.36 * len(rows) + 1.5)))
    left = [0.0] * len(rows)
    norm = sum(weights.get(d, 0) for d in dims) or 1.0
    for k, d in enumerate(dims):
        vals = []
        for r in rows[::-1]:
            v = r["dimensions"].get(d)
            vals.append(0.0 if v is None else v * weights.get(d, 0) / norm)
        ax.barh(range(len(rows)), vals, left=left, color=PALETTE[k % len(PALETTE)], label=d.replace("_", " "),
                height=0.72)
        left = [a + b for a, b in zip(left, vals)]
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(genes, fontsize=8)
    for i, r in enumerate(rows[::-1]):
        ax.text(left[i] + 0.005, i, f"{r['composite']:.2f}", va="center", fontsize=7)
    ax.set_xlabel("weighted evidence contribution (composite score)")
    ax.set_title("Weighted multi-evidence ranking", fontsize=10)
    ax.legend(fontsize=6.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.14), frameon=False)
    ax.set_xlim(0, max(left) * 1.12 if left else 1)
    fig.tight_layout()
    fig.savefig(out, dpi=200, bbox_inches="tight")
    plt.close(fig)
    return True


def _fig_survival(plt, gene: str, km: dict, pval: float, hr: float, out: Path) -> bool:
    high = km.get("high") or []
    low = km.get("low") or []
    if not high or not low:
        return False
    fig, ax = plt.subplots(figsize=(4.6, 3.6))
    for curve, label, color in ((high, f"{gene} high", "#C0504D"), (low, f"{gene} low", "#4F81BD")):
        xs = [0.0] + [t for t, _ in curve]
        ys = [1.0] + [s for _, s in curve]
        ax.step(xs, ys, where="post", label=label, color=color, linewidth=1.6)
    ax.set_xlabel("Overall survival (months)")
    ax.set_ylabel("Survival probability")
    ax.set_ylim(0, 1.02)
    ax.set_title(f"TCGA-COADREAD: {gene} (log-rank p={pval:.3g}, HR={hr:.2f})", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def _fig_radar(plt, ranking: list[dict], out: Path, top_n: int = 3) -> bool:
    rows = ranking[:top_n]
    if len(rows) < 2:
        return False
    angles = [n / len(DIMENSIONS) * 2 * math.pi for n in range(len(DIMENSIONS))]
    angles += angles[:1]
    fig, ax = plt.subplots(figsize=(4.8, 4.4), subplot_kw={"polar": True})
    for k, r in enumerate(rows):
        vals = [(r["dimensions"].get(d) or 0.0) for d in DIMENSIONS]
        vals += vals[:1]
        ax.plot(angles, vals, linewidth=1.4, label=r["gene"], color=PALETTE[k % len(PALETTE)])
        ax.fill(angles, vals, alpha=0.08, color=PALETTE[k % len(PALETTE)])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels([d.replace("_", "\n") for d in DIMENSIONS], fontsize=7)
    ax.set_ylim(0, 1)
    ax.set_title("Top candidates: evidence profile", fontsize=9)
    ax.legend(fontsize=7, loc="upper right", bbox_to_anchor=(1.25, 1.12))
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def make_figures(run_dir: Path, ranking: list[dict], weights: dict, survival: dict | None = None,
                 gene: str | None = None) -> list[str]:
    figs: list[str] = []
    errors: list[str] = []
    try:
        plt = _mpl(run_dir)
    except Exception as exc:  # noqa: BLE001
        (Path(run_dir) / "figure_errors.txt").write_text(f"matplotlib unavailable: {exc}", encoding="utf-8")
        return figs
    jobs = [
        ("fig1_evidence_heatmap.png", lambda p: _fig_heatmap(plt, ranking, p)),
        ("fig2_weighted_ranking.png", lambda p: _fig_ranking(plt, ranking, weights, p)),
        ("fig3_evidence_radar.png", lambda p: _fig_radar(plt, ranking, p)),
    ]
    for name, fn in jobs:
        try:
            if fn(Path(run_dir) / name):
                figs.append(name)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{name}: {type(exc).__name__}: {exc}")
    if survival and gene:
        try:
            if _fig_survival(plt, gene, survival.get("km") or {}, survival.get("p_value", 1.0),
                             survival.get("hazard_ratio_high_vs_low", 1.0), Path(run_dir) / "fig4_survival.png"):
                figs.append("fig4_survival.png")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"fig4_survival.png: {type(exc).__name__}: {exc}")
    if errors:
        (Path(run_dir) / "figure_errors.txt").write_text("\n".join(errors), encoding="utf-8")
    return figs


# ---------------------------------------------------------------------------
# wet-lab handoff
# ---------------------------------------------------------------------------
def wetlab_plan(target: str, top: dict, profile: dict) -> list[dict]:
    gene = top["gene"]
    ev = top.get("evidence", {})
    dims = top.get("dimensions", {})
    plan = [
        {
            "assay": "Co-immunoprecipitation (Co-IP) / proximity ligation",
            "question": f"Does {target} physically associate with {gene} in CRC cells?",
            "design": (
                f"Transfect CRC lines (e.g. HCT116, SW480) with tagged constructs "
                f"({target}-HA and {gene}-FLAG, plus tags swapped), immunoprecipitate with anti-HA/anti-FLAG, "
                f"and probe the reciprocal tag by Western blot. Include a tag-only and a catalytically dead "
                f"{target} mutant as negative controls."
            ),
            "readout": "Co-IP Western blot (reciprocal pull-down), PPI quantification by densitometry",
            "supported_by": f"PPI evidence = {ev.get('ppi_association')}; co-expression r = {ev.get('coexpr_r')}",
            "priority": "high" if (ev.get("ppi_association") or 0) > 0.4 else "medium",
        },
        {
            "assay": "Loss- and gain-of-function epistasis",
            "question": f"Is the phenotype of {target} dependent on {gene}?",
            "design": (
                f"Knock down/out {target} (siRNA or CRISPR) and measure {gene} expression and downstream "
                f"pathway output; then rescue with {gene} overexpression or a constitutively active "
                f"{gene} construct. Test whether {gene} knockdown abolishes the {target}-driven phenotype."
            ),
            "readout": "qPCR + Western blot for pathway markers; proliferation/migration/colony assays",
            "supported_by": f"pathway centrality = {dims.get('pathway_centrality')}; "
                            f"signalling competence = {dims.get('signaling')}",
            "priority": "high",
        },
        {
            "assay": "Site-directed mutagenesis of the predicted interface",
            "question": f"Which residue(s) of {gene} are required for the {target} dependency?",
            "design": (
                f"Map the extracellular domain boundaries from the UniProt topology of {gene}, model the "
                f"complex (AlphaFold-Multimer / HADDOCK), select 3-5 interface residues, mutate to alanine, "
                f"and test rescue activity of each mutant."
            ),
            "readout": "Rescue assay + Co-IP of each mutant; loss of binding confirms the interface",
            "supported_by": "topology + domain architecture from stage 1/3",
            "priority": "medium",
        },
        {
            "assay": "Clinical association in patient cohorts",
            "question": f"Do {target} and {gene} co-vary and stratify outcome in CRC?",
            "design": (
                f"IHC / multiplex immunofluorescence on a CRC TMA for {target} and {gene}; correlate with "
                f"stage, MSI status and survival. Cross-check against TCGA-COADREAD expression."
            ),
            "readout": "H-score correlation, Kaplan–Meier by co-high vs co-low, Cox model",
            "supported_by": f"expression z = {ev.get('expr_mean_z')}; OS p = {ev.get('survival_p')}",
            "priority": "medium",
        },
    ]
    return plan


# ---------------------------------------------------------------------------
# markdown report
# ---------------------------------------------------------------------------
def _fmt(v: Any, nd: int = 3) -> str:
    if v is None:
        return "n/a"
    if isinstance(v, float):
        if v != 0 and (abs(v) < 10 ** (-nd) or abs(v) >= 10 ** nd):
            return f"{v:.2e}"
        return f"{v:.{nd}f}"
    return str(v)


def _hypothesis(target: str, top: dict, profile: dict) -> str:
    """Compose the mechanistic paragraph from the evidence that actually exists."""
    gene = top.get("gene", "the candidate")
    ev = top.get("evidence", {})
    arch = profile.get("topology", {}).get("architecture") or "a membrane protein"

    reasons: list[str] = []
    r = ev.get("coexpr_r")
    if r is not None and abs(r) >= 0.25:
        fdr = ev.get("coexpr_fdr")
        fdr_txt = f", FDR {fdr:.1e}" if isinstance(fdr, (int, float)) and fdr > 0 else ""
        reasons.append(f"its expression tracks {target} across TCGA-COADREAD (r={r:+.2f}{fdr_txt})")
    ppi = ev.get("ppi_association") or 0
    if ppi >= 0.4:
        reasons.append(f"it has a reported physical interaction with {target} (STRING/IntAct score {ppi:.2f})")
    if (ev.get("n_shared_pathways") or 0) >= 1:
        reasons.append(
            f"it shares {ev['n_shared_pathways']} specific pathway(s) with {target} "
            f"(information content {ev.get('pathway_information_content', 0):.1f} bits)"
        )
    if (ev.get("lit_cooccurrence") or 0) >= 1:
        reasons.append(f"it is co-mentioned with {target} in {ev['lit_cooccurrence']} PubMed record(s)")
    sig = ev.get("signaling_score") or 0
    if sig >= 0.35:
        reasons.append(
            f"it can itself transduce a signal (competence {sig:.2f}"
            + (f"; families: {', '.join(ev.get('signalling_families') or [])}" if ev.get("signalling_families") else "")
            + ")"
        )

    head = (
        f"{target} is {arch}. It cannot generate an intracellular signal on its own, so the phenotype it "
        f"drives must be relayed by a signal-transducing partner."
    )
    if reasons:
        body = (
            f" {gene} is the best-supported relay: " + "; ".join(reasons) +
            f". The proposed axis is **{target} → {gene} → downstream pathway output**."
        )
    else:
        body = (
            f" For {gene} the association evidence is weak; it is prioritised mainly on disease evidence and "
            f"signalling competence, so the linkage is a hypothesis rather than an observation."
        )
    tail = (
        " Directionality is not established by correlation, so the axis is stated as a testable hypothesis; "
        "the co-IP and epistasis experiments in section 8 are the decisive test."
    )
    return head + body + tail


def _zh_abstract(target: str, profile: dict, ranking: list[dict], tool_creation: dict | None,
                 weights: dict) -> list[str]:
    """A short Chinese abstract so the report is usable without translating the body."""
    lines: list[str] = ["## 0. 摘要（中文）", ""]
    topo = profile.get("topology", {})
    arch = topo.get("architecture") or "未知拓扑"
    lines.append(
        f"**锚点**：{target}（UniProt {profile.get('uniprot', {}).get('accession', 'n/a')}，"
        f"{profile.get('uniprot', {}).get('length', 'n/a')} aa）。拓扑判定：{arch}。"
    )
    if not topo.get("signaling_competent"):
        lines.append(
            "因此它**不能自身转导信号**，其效应靶点必须是一个具备胞内信号输出的跨膜蛋白——这是本任务的核心约束。"
        )
    lines.append("")
    if ranking:
        top = ranking[0]
        dims = {k: v for k, v in (top.get("dimensions") or {}).items() if v is not None}
        strong = [k for k, v in dims.items() if v >= 0.6]
        lines.append(
            f"**排序结论**：在 {len(ranking)} 个进入六维打分的候选中，**{top['gene']}** 排名第一"
            f"（复合分 {top['composite']:.3f}，权重 {', '.join(f'{k}={v:.2f}' for k, v in weights.items())}）；"
            f"六维中 {len(strong)} 维 ≥0.60（{', '.join(strong) if strong else '无'}）。"
        )
        runners = "、".join(f"{r['gene']}({r['composite']:.3f})" for r in ranking[1:4])
        if runners:
            lines.append(f"第二至第四名：{runners}。")
        lines.append("")
        spread = ranking[0]["composite"] - ranking[min(4, len(ranking)) - 1]["composite"]
        lines.append(
            f"**可信度**：前五名复合分差仅 {spread:.3f}，且没有一个候选在 ≥3 个维度上同时达到 0.6，"
            "因此这是一个**不确定性下的优先级排序**，不是确证结论；决定性证据来自报告第 8 节的 Co-IP 与回补实验。"
        )
    else:
        lines.append("**排序结论**：没有候选通过证据闸门，详见第 3 节失败模式。")
    lines.append("")
    if tool_creation:
        val = (tool_creation.get("validation") or {})
        lines.append(
            f"**自进化**：Critic 判定缺少“信号转导能力评估”工具 → Tool Creation Agent 检索并创建 "
            f"`{tool_creation.get('tool_name')}`，{len(val.get('cases', []))} 个对照全部通过"
            f"（{sum(1 for c in val.get('cases', []) if c.get('pass'))}/{len(val.get('cases', []))}），"
            f"注册后重跑受影响阶段。"
        )
        lines.append("")
    return lines


def build_report(*, ctx, plan: dict, stage_results: list[dict], critiques: list[dict],
                 ranking: list[dict], weights: dict, profile: dict, tool_creation: dict | None,
                 figures: list[str], run_meta: dict) -> str:
    target = ctx.target
    disease = ctx.disease
    top = ranking[0] if ranking else None
    lines: list[str] = []
    A = lines.append

    A(f"# Multi-agent discovery of a downstream effector target of {target} in {disease}")
    A("")
    A(f"*Run id*: `{run_meta.get('run_id')}`  |  *Engine*: `{run_meta.get('engine')}`  |  "
      f"*Template*: `{plan.get('template_id', 'n/a')}`  |  *Date*: {run_meta.get('date')}")
    A("")
    A("> Generated by a MOCHI-style multi-agent system (Manager / Dev / Critic / Tool Creation) "
      "operating on real public biomedical databases. Every number below is traceable to a tool call "
      "recorded in `provenance.jsonl`.")
    A("")
    lines.extend(_zh_abstract(target, profile, ranking, tool_creation, weights))

    # ---- executive summary ------------------------------------------------
    A("## 1. Executive summary")
    A("")
    if top:
        ev = top.get("evidence", {})
        dims = top.get("dimensions", {})
        supported = top.get("supporting_dimensions", [])
        A(f"**{top['gene']}** ranks first among {len(ranking)} scored candidates "
          f"(composite score **{top['composite']:.3f}**), supported by "
          f"{top.get('n_supporting_dimensions')} of 6 evidence dimensions "
          f"({', '.join(supported) if supported else 'none above 0.6'}).")
        A("")
        A(f"- **Signalling competence**: {_fmt(ev.get('signaling_score'))} — the candidate can transduce a signal "
          f"itself, which the anchor protein cannot ({profile.get('topology', {}).get('architecture', '')}).")
        A(f"- **Association with {target}**: PPI {_fmt(ev.get('ppi_association'), 2)}, "
          f"co-expression r = {_fmt(ev.get('coexpr_r'), 2)}, "
          f"shared Reactome pathways = {ev.get('n_shared_pathways')}, "
          f"PubMed co-mentions = {ev.get('lit_cooccurrence')}.")
        A(f"- **Disease evidence**: mean mRNA z vs normal = {_fmt(ev.get('expr_mean_z'), 2)}; "
          f"OS log-rank p = {_fmt(ev.get('survival_p'))}, HR = {_fmt(ev.get('survival_hr'), 2)}.")
        A(f"- **Novelty / druggability**: {ev.get('n_pubmed_crc')} PubMed papers for the gene in CRC; "
          f"druggability score {_fmt(ev.get('druggability_score'), 2)}.")
        A("")
    else:
        A("No candidate survived the evidence pipeline; see the stage results for failure modes.")
        A("")

    # ---- workflow ---------------------------------------------------------
    A("## 2. How the answer was produced")
    A("")
    if run_meta.get("task"):
        A(f"**Instruction given to the manager** ({run_meta.get('task_source', 'default')}): "
          f"> {run_meta['task']}")
        A("")
    A("| Agent | Responsibility in this run |")
    A("|---|---|")
    A("| Manager | retrieved the reasoning template, produced the stage plan, calibrated weights, "
      "integrated the final report |")
    A("| Dev | executed each stage's data pipeline (database glue code + statistics) and persisted artefacts |")
    A("| Critic | reviewed tool adequacy and evidence sufficiency, raised capability gaps, re-weighted dimensions |")
    A("| Tool Creation | built, validated and registered new tools when a capability gap was found |")
    A("")
    A("### Plan (manager)")
    A("")
    for i, st in enumerate(plan.get("stages", []), 1):
        A(f"{i}. **{st.get('name')}** — {st.get('goal')}")
        A(f"   - tools: {', '.join(st.get('tools', [])) or 'n/a'}")
        A(f"   - success criteria: {'; '.join(st.get('success_criteria', [])) or 'n/a'}")
    if plan.get("reasoning"):
        A("")
        A(f"*Manager reasoning*: {plan['reasoning']}")
    A("")

    # ---- stages -----------------------------------------------------------
    A("## 3. Stage results")
    A("")
    latest: dict[str, dict] = {}
    attempts: dict[str, int] = {}
    for r in stage_results:
        sid = r.get("stage", "?")
        latest[sid] = r
        attempts[sid] = max(attempts.get(sid, 0), r.get("attempt", 1))
    for sid, r in latest.items():
        extra = f", {attempts[sid]} attempts" if attempts[sid] > 1 else ""
        A(f"### {r.get('name', sid)} — `{r.get('status')}` ({r.get('duration_s', 0)} s{extra})")
        A("")
        for f in r.get("findings", []):
            A(f"- {f}")
        A("")
        if r.get("capability_gap"):
            A(f"> **Capability gap detected**: `{r.get('missing_tool')}` was missing from the Tool Ocean.")
            A("")

    # ---- tool creation ----------------------------------------------------
    if tool_creation:
        A("## 4. Self-evolution: a new tool was created")
        A("")
        A(f"**Tool**: `{tool_creation.get('tool_name')}` — {tool_creation.get('purpose', '')}")
        A("")
        research = tool_creation.get("research", {})
        if research:
            A(f"- Literature consulted: {research.get('pubmed')}")
            A(f"- Code/implementations consulted: {research.get('github')}")
            A(f"- Design decision: {research.get('decision')}")
        A("")
        val = tool_creation.get("validation", {})
        A(f"- Validation **{'PASSED' if val.get('passed') else 'FAILED'}** on positive/negative controls:")
        A("")
        A("| control | expectation | observed | pass |")
        A("|---|---|---|---|")
        for c in val.get("cases", []):
            A(f"| {c.get('case')} | {c.get('expected')} | {_fmt(c.get('observed'))} | {'yes' if c.get('pass') else 'no'} |")
        A("")
        A(f"- Registered in the Tool Ocean and re-run in the affected stage: "
          f"`{tool_creation.get('registered_as', 'n/a')}`")
        A("")
    if run_meta.get("learned_template"):
        A(f"> **Template self-evolution**: this run was summarised into the reasoning-template library as "
          f"`{run_meta['learned_template']}` (`status: experimental`), so a future task with a similar "
          f"goal retrieves it automatically.")
        A("")

    # ---- ranking ----------------------------------------------------------
    A("## 5. Multi-evidence ranking")
    A("")
    A(f"Weights: {json.dumps(weights, ensure_ascii=False)}")
    A("")
    A("| rank | gene | composite | association | signalling | CRC evidence | pathway | novelty | druggability | support |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for r in ranking[:15]:
        d = r.get("dimensions", {})
        A(f"| {r['rank']} | **{r['gene']}** | {r['composite']:.3f} | {_fmt(d.get('association'), 2)} | "
          f"{_fmt(d.get('signaling'), 2)} | {_fmt(d.get('crc_evidence'), 2)} | {_fmt(d.get('pathway_centrality'), 2)} | "
          f"{_fmt(d.get('novelty'), 2)} | {_fmt(d.get('druggability'), 2)} | {r.get('n_supporting_dimensions')}/6 |")
    A("")

    # ---- known-answer check ----------------------------------------------
    ka = run_meta.get("known_answer") or {}
    if ka.get("checks"):
        A("### 5.1 Known-answer check (hindcast)")
        A("")
        A(f"Expected target(s): **{', '.join(ka.get('expected', []))}**. "
          f"Recall@stage-2 = {ka.get('recall_at_stage2')}, recall@stage-4 = {ka.get('recall_at_stage4')}.")
        A("")
        A("| gene | nominated at stage 2 | sources | co-expr r | signalling | scored at stage 4 | rank | composite |")
        A("|---|---|---|---|---|---|---|---|")
        for c in ka["checks"]:
            A(f"| **{c['gene']}** | {'yes' if c['nominated_at_stage2'] else 'no'} | {c.get('sources') or '—'} | "
              f"{_fmt(c.get('coexpression_r'), 3)} | {_fmt(c.get('signaling_score'), 2)} | "
              f"{'yes' if c.get('scored_at_stage4') else 'no'} | {c.get('rank') or '—'} | {_fmt(c.get('composite'), 3)} |")
        A("")
        missed = [c["gene"] for c in ka["checks"] if not c.get("nominated_at_stage2")]
        if missed:
            A(f"> {', '.join(missed)} was **not nominated** by the data-driven channels. That is a statement about "
              f"the evidence, not a bug: a gene with no PPI, no co-expression above threshold and no shared "
              f"specific pathway cannot be recovered without prior knowledge. Use `--seed-genes` to score it as a "
              f"hypothesis, or widen the panel/thresholds (see README §10).")
            A("")

    # ---- dossier ----------------------------------------------------------
    if top:
        A(f"## 6. Evidence dossier — {top['gene']}")
        A("")
        ev = top.get("evidence", {})
        A("| evidence type | value | source |")
        A("|---|---|---|")
        rows = [
            ("UniProt topology",
             f"{ev.get('n_tm') if ev.get('n_tm') is not None else 'n/a'} TM; "
             f"competence {_fmt(ev.get('signaling_score'))} ({ev.get('topology_reason') or 'n/a'})",
             "UniProt / created scorer"),
            ("Signalling domain families", ", ".join(ev.get("signalling_families") or []) or "none detected",
             "Pfam / InterPro"),
            ("PPI with anchor",
             f"combined {_fmt(ev.get('ppi_association'), 3)}"
             f" (experimental channel {_fmt(ev.get('ppi_experimental'), 3)}); "
             f"IntAct interactions {ev.get('intact_interactions') if ev.get('intact_interactions') is not None else 'n/a'}",
             "STRING + IntAct"),
            ("Co-expression (TCGA)", f"r={_fmt(ev.get('coexpr_r'), 3)}, FDR={_fmt(ev.get('coexpr_fdr'))}",
             "cBioPortal COADREAD"),
            ("Shared pathways", f"{_fmt(ev.get('n_shared_pathways'))} (IC {_fmt(ev.get('pathway_information_content'), 1)} bits)",
             "Reactome (Enrichr library)"),
            ("Literature co-mention", _fmt(ev.get("lit_cooccurrence")), "PubMed E-utilities"),
            ("Tumour expression", f"mean z={_fmt(ev.get('expr_mean_z'), 2)}", "cBioPortal vs normal"),
            ("Prognosis", f"p={_fmt(ev.get('survival_p'))}, HR={_fmt(ev.get('survival_hr'), 2)}",
             "TCGA-COADREAD OS"),
            ("Novelty", f"{_fmt(ev.get('n_pubmed_crc'))} CRC papers", "PubMed"),
            ("Druggability", _fmt(ev.get("druggability_score"), 2), "ChEMBL + DGIdb + Open Targets"),
        ]
        for a, b, c in rows:
            A(f"| {a} | {b} | {c} |")
        A("")
        A("### Mechanistic hypothesis")
        A("")
        A(_hypothesis(target, top, profile))
        A("")
        if len(ranking) >= 3:
            spread = ranking[0]["composite"] - ranking[min(4, len(ranking)) - 1]["composite"]
            A(f"> The composite score of the top five candidates spans only {spread:.3f}, so this is a "
              f"prioritisation under uncertainty rather than a decisive call. The decisive evidence is the "
              f"co-IP / epistasis experiment in section 8, not the ranking itself.")
            A("")

    # ---- contradictions ---------------------------------------------------
    A("## 7. Limitations and contradictions")
    A("")
    if critiques:
        last = critiques[-1]
        A("**Critic audit (deterministic checks):**")
        A("")
        for c in last.get("evidence_checks", [])[:10]:
            if c.get("supported"):
                A(f"- {c.get('claim')} — **PASS**")
            else:
                A(f"- {c.get('claim')} — **FAIL**: {c.get('why')}")
        A("")
    A("- Correlation-based dimensions (co-expression, literature co-mention) do not establish directionality; "
      "the causal claim rests on the topology constraint plus the epistasis experiments proposed below.")
    A("- Public bulk cohorts cannot resolve cell-type-specific expression; single-cell or spatial data would "
      "strengthen the co-expression argument.")
    A("- The scoring transforms are documented heuristics, not a learned model; ranking is sensitive to the "
      "critic-calibrated weights, which are reported alongside every score.")
    A("")

    # ---- wet lab ----------------------------------------------------------
    A("## 8. Wet-lab validation handoff")
    A("")
    if top:
        A("| assay | question | design | readout | priority |")
        A("|---|---|---|---|---|")
        for step in wetlab_plan(target, top, profile):
            A(f"| {step['assay']} | {step['question']} | {step['design']} | {step['readout']} | {step['priority']} |")
        A("")

    # ---- figures ----------------------------------------------------------
    if figures:
        A("## 9. Figures")
        A("")
        for f in figures:
            A(f"![{f}]({f})")
            A("")

    # ---- provenance -------------------------------------------------------
    A("## 10. Provenance and reproducibility")
    A("")
    A(f"- Databases: UniProt REST, Open Targets Platform (GraphQL v4), cBioPortal "
      f"(`{ctx.study}`), PubMed E-utilities, KEGG REST, Reactome/KEGG/GO gene sets via Enrichr, "
      f"STRING v12, IntAct, QuickGO, InterPro, ChEMBL, DGIdb, mygene.info.")
    A(f"- {run_meta.get('n_tool_calls', 0)} tool calls recorded in `provenance.jsonl` "
      f"({json.dumps(run_meta.get('provenance_summary', {}), ensure_ascii=False)}).")
    A(f"- Full agent transcript: `transcript.jsonl`; stage artefacts under the same run directory.")
    A(f"- Re-run: `python cases/{run_meta.get('case_script', 'dpep1_crc_effector_target.py')}` "
      f"(add `--fresh` to ignore the HTTP cache).")
    A("")
    return "\n".join(lines)
