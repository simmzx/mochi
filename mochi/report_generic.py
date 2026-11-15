"""Report builder for non-target-discovery scenarios.

A scenario supplies a ``render(ctx, results, ranking)`` markdown body with its own tables;
this module wraps it with the common scientific scaffolding (task, plan, stage log, audit,
figures, limitations, provenance) so every scenario produces the same report structure.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

TITLES = {
    "enzyme_design": "Structure- and prior-guided enzyme variant library design for {target}",
    "retrosynthesis": "Multi-step retrosynthetic route planning for {target}",
    "sdl_protocol": "Compiling wet-lab protocols into validated self-driving-laboratory instructions",
}


def _mpl(run_dir: Path):
    import os

    os.environ.setdefault("MPLCONFIGDIR", str(Path(run_dir) / ".mplconfig"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    return plt


# ---------------------------------------------------------------------------
# figures
# ---------------------------------------------------------------------------

def _fmt3(x: float) -> str:
    """Three decimals with half-up rounding, so figure labels match the tables."""
    from decimal import Decimal, ROUND_HALF_UP
    return str(Decimal(str(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

def _fig_enzyme(plt, ctx, out: Path) -> bool:
    sel = ctx.state.get("selection") or []
    if not sel:
        return False
    rows = sel[:15][::-1]
    labels = [r["mutation"] for r in rows]
    scores = [r["score_final"] for r in rows]
    colors = ["#C0504D" if (ctx.state.get("hindcast") or []) and
              any(c["mutation"] == r["mutation"] and c["experiment"] == "hit" for c in ctx.state["hindcast"])
              else "#4F81BD" for r in rows]
    fig, ax = plt.subplots(figsize=(6.4, max(3.2, 0.34 * len(rows) + 1.2)))
    ax.barh(range(len(rows)), scores, color=colors, height=0.7)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlabel("variant score (leverage × chemistry/prior × packing − conservation)")
    ax.set_title("Designed round-2 library (red = published hit)", fontsize=9)
    for i, s in enumerate(scores):
        ax.text(s + 0.005, i, _fmt3(s), va="center", fontsize=6.5)
    ax.set_xlim(0, max(scores) * 1.12)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def _fig_enzyme_scatter(plt, ctx, out: Path) -> bool:
    lib = ctx.state.get("library") or []
    if not lib:
        return False
    fig, ax = plt.subplots(figsize=(5.6, 3.8))
    xs = [r["dist_to_site"] for r in lib]
    ys = [r["score_final"] for r in lib]
    cs = [r["prior_outcome"] for r in lib]
    palette = {"hit": "#C0504D", "reduced": "#F79646", "dead": "#7F7F7F", "untested": "#9DC3E6"}
    for cat in ("untested", "reduced", "hit", "dead"):
        idx = [i for i, c in enumerate(cs) if c == cat]
        if idx:
            ax.scatter([xs[i] for i in idx], [ys[i] for i in idx], s=14, alpha=0.7,
                       c=palette.get(cat, "grey"), label=cat)
    ax.set_xlabel("min heavy-atom distance to the catalytic cluster (Å)")
    ax.set_ylabel("variant score")
    ax.set_title("Score landscape of the single-substitution space", fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def _fig_retro(plt, ctx, out: Path) -> bool:
    bench = ctx.state.get("benchmark") or []
    if not bench:
        return False
    labels = [b["name"] for b in bench]
    steps = [b.get("steps") or 0 for b in bench]
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    bars = ax.bar(range(len(labels)), steps, color=["#4F81BD" if s else "#C0504D" for s in steps])
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=7.5)
    ax.set_ylabel("shortest route length (steps)")
    ax.set_title("Retrosynthesis benchmark: planned route length per drug", fontsize=9)
    for b, s in zip(bars, steps):
        ax.text(b.get_x() + b.get_width() / 2, s + 0.05, str(s), ha="center", fontsize=7)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def _fig_sdl(plt, ctx, out: Path) -> bool:
    prog = ctx.state.get("program") or {}
    steps = prog.get("steps") or []
    if not steps:
        return False
    fig, ax = plt.subplots(figsize=(7.0, 3.4))
    t = 0.0
    for i, s in enumerate(steps):
        dur = float(s.get("duration_min") or 5)
        ax.barh(0, dur, left=t, height=0.5, color="#4F81BD" if i % 2 == 0 else "#9DC3E6",
                edgecolor="white")
        ax.text(t + dur / 2, 0.32, s.get("opcode", ""), rotation=45, fontsize=6, ha="center")
        t += dur
    ax.set_yticks([])
    ax.set_xlabel("execution time (min)")
    ax.set_title(f"SDL execution timeline ({len(steps)} opcodes, {t:.0f} min total)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=200)
    plt.close(fig)
    return True


def make_figures(ctx, scenario: str) -> list[str]:
    figs: list[str] = []
    try:
        plt = _mpl(ctx.run_dir)
    except Exception:  # noqa: BLE001
        return figs
    jobs = {
        "enzyme_design": [("fig1_library_scores.png", _fig_enzyme),
                          ("fig2_score_landscape.png", _fig_enzyme_scatter)],
        "retrosynthesis": [("fig1_route_lengths.png", _fig_retro)],
        "sdl_protocol": [("fig1_execution_timeline.png", _fig_sdl)],
    }.get(scenario, [])
    for name, fn in jobs:
        try:
            if fn(plt, ctx, Path(ctx.run_dir) / name):
                figs.append(name)
        except Exception:  # noqa: BLE001
            continue
    return figs


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------
def build_scenario_report(*, ctx, scenario: str, plan: dict, stage_results: list[dict],
                          critiques: list[dict], figures: list[str], run_meta: dict,
                          body: str, scenario_def) -> str:
    L: list[str] = []
    A = L.append
    title = TITLES.get(scenario, "Multi-agent {scenario} run").format(target=ctx.target)
    A(f"# {title}")
    A("")
    A(f"*Run*: `{run_meta['run_id']}` | *scenario*: `{scenario}` | *engine*: `{run_meta['engine']}` | "
      f"*template*: `{plan.get('template_id')}` | *date*: {run_meta['date']}")
    A("")
    A(f"**Instruction**: {run_meta.get('task', '')}")
    A("")

    # summary
    A("## 1. Summary")
    A("")
    last = {}
    for r in stage_results:
        last[r.get("stage")] = r
    for sid in sorted(last):
        for f in last[sid].get("findings", [])[:3]:
            A(f"- {f}")
    A("")

    # method
    A("## 2. Method")
    A("")
    A("| Agent | Role in this run |")
    A("|---|---|")
    A("| Manager | retrieved the scenario template, planned the four stages, calibrated the final ranking |")
    A("| Dev | executed each stage's computational pipeline and persisted artefacts |")
    A("| Critic | ran the deterministic stage audit and vetoed or accepted each stage |")
    A("| Tool Creation | created a new tool if the audit found a capability gap |")
    A("")
    A("### Plan")
    A("")
    for i, st in enumerate(plan.get("stages", []), 1):
        A(f"{i}. **{st.get('name')}** — {st.get('goal')}")
    A("")
    if plan.get("reasoning"):
        A(f"*Manager reasoning*: {plan['reasoning']}")
        A("")

    # stages
    A("## 3. Stage log")
    A("")
    A("| stage | status | attempts | seconds |")
    A("|---|---|---|---|")
    attempts: dict[str, int] = {}
    for r in stage_results:
        attempts[r.get("stage")] = max(attempts.get(r.get("stage"), 0), r.get("attempt", 1))
    for sid in sorted(last):
        r = last[sid]
        A(f"| {r.get('name', sid)} | {r.get('status')} | {attempts.get(sid, 1)} | {r.get('duration_s', 0)} |")
    A("")

    # scenario results
    A("## 4. Results")
    A("")
    A(body)
    A("")

    # audit
    if critiques:
        A("## 5. Critic audit")
        A("")
        A("| check | result |")
        A("|---|---|")
        for c in critiques[-1].get("evidence_checks", []):
            A(f"| {c['claim']} | {'PASS' if c['supported'] else 'FAIL: ' + c.get('why', '')} |")
        A("")

    # figures
    if figures:
        A("## 6. Figures")
        A("")
        for f in figures:
            A(f"![{f}]({f})")
            A("")

    # limitations
    A("## 7. Limitations")
    A("")
    for lim in (getattr(scenario_def, "limitations", None) or []):
        A(f"- {lim}")
    A("- All numbers are computed by deterministic stage programs; the language model only selects "
      "actions and writes prose, so the report is reproducible from the run directory.")
    A("")

    # provenance
    A("## 8. Provenance")
    A("")
    prov = run_meta.get("provenance_summary", {})
    A(f"- {run_meta.get('n_tool_calls', 0)} tool calls recorded in `provenance.jsonl` "
      f"({json.dumps(prov, ensure_ascii=False)}).")
    A("- `transcript.jsonl` (agent turns), `llm_calls.jsonl` (model calls), `run_summary.json` (machine summary).")
    A(f"- Re-run: `python cases/run_{scenario}.py`")
    A("")
    return "\n".join(L)
