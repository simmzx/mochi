"""Publication-quality figures for the MOCHI report.

Produces three files in paper/figures/:

    fig_workflow.png   target-discovery workflow (manager / dev / critic / tool creation / tool ocean)
    fig_sankey.png     Tool Ocean composition: 46 tools grouped into 11 categories
    fig_panels.png     A: enzyme library, B: retrosynthesis benchmark, C: SDL execution timeline

All figures are drawn at 300 dpi and sized for a ~166 mm text block.
"""

from __future__ import annotations

import csv
import json
import math
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, PathPatch, Rectangle  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

INK = "#22303C"
GREY = "#6E7B8B"
BLUE = "#3F6FA8"
LBLUE = "#DCE6F2"
RED = "#B85450"
GREEN = "#7E9E4E"
LGREEN = "#E2EBD5"
PURPLE = "#7C659B"
ORANGE = "#E08A3C"
TEAL = "#3E8E9E"
SAND = "#FBF3E9"
PINK = "#F6E4E1"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 7.4,
    "axes.linewidth": 0.6,
    "savefig.dpi": 300,
})


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def box(ax, x, y, w, h, fc, ec="white", lw=1.0, r=0.012, z=2, alpha=1.0):
    p = FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0.004,rounding_size={r}",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=z, alpha=alpha)
    ax.add_patch(p)
    return p


def text(ax, x, y, s, size=7.4, color=INK, weight="normal", ha="center", va="center", z=5, style="normal"):
    ax.text(x, y, s, ha=ha, va=va, fontsize=size, color=color, fontweight=weight,
            zorder=z, fontstyle=style, linespacing=1.25)


def arrow(ax, p0, p1, color=INK, lw=1.0, rad=0.0, style="-|>", z=3, shrink=2):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=8, color=color,
                                 linewidth=lw, connectionstyle=f"arc3,rad={rad}",
                                 shrinkA=shrink, shrinkB=shrink, zorder=z))


def ribbon(ax, x0, y0a, y0b, x1, y1a, y1b, color, alpha=0.55, z=1):
    verts = [(x0, y0a), (x0 + (x1 - x0) * 0.5, y0a), (x1 - (x1 - x0) * 0.5, y1a), (x1, y1a),
             (x1, y1b), (x1 - (x1 - x0) * 0.5, y1b), (x0 + (x1 - x0) * 0.5, y0b), (x0, y0b), (x0, y0a)]
    codes = [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4,
             MPath.LINETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4, MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none", alpha=alpha, zorder=z))


# ---------------------------------------------------------------------------
# figure 1: workflow of the target-discovery case
# ---------------------------------------------------------------------------
TOOLS = [('database',
  '12',
  ['fetch_homologs',
   'query_cbioportal_alterations',
   'query_cbioportal_coexpression',
   'query_cbioportal_expression',
   'query_cbioportal_expression_panel',
   'query_cbioportal_survival',
   'query_opentargets_associations',
   'query_opentargets_known_drugs',
   'query_opentargets_target',
   'query_uniprot',
   'query_uniprot_batch',
   'resolve_gene_ids']),
 ('chemistry',
  '6',
  ['druggability_score',
   'is_buyable',
   'molecule_properties',
   'one_step_disconnections',
   'query_chembl_target',
   'query_dgidb']),
 ('literature',
  '5',
  ['citation_network_score',
   'fetch_pubmed_abstracts',
   'query_pubmed',
   'query_pubmed_cooccurrence',
   'query_pubmed_novelty']),
 ('pathway / annotation',
  '8',
  ['conservation_profile',
   'pathway_coannotation',
   'query_domain_architecture_panel',
   'query_interpro',
   'query_kegg_pathways',
   'query_pathway_enrichment',
   'query_pathway_membership',
   'query_quickgo']),
 ('network', '3', ['build_ppi_union', 'query_intact', 'query_string']),
 ('structure / sequence',
  '5',
  ['design_primers_from_cds',
   'design_quikchange_primers',
   'fetch_alphafold_model',
   'fetch_nucleotide_sequence',
   'pocket_geometry']),
 ('retrosynthesis', '2', ['route_metrics', 'search_route']),
 ('laboratory automation', '4', ['compile_sdl', 'parse_protocol', 'simulate_sdl', 'validate_sdl']),
 ('scoring', '1', ['multi_evidence_scoring'])]


DOMAINS = [
    ("omics & disease data", ["database"], "#3F6FA8"),
    ("chemistry & structure", ["chemistry", "structure / sequence"], "#E08A3C"),
    ("literature & networks", ["literature", "network"], "#7E9E4E"),
    ("pathways & annotation", ["pathway / annotation"], "#7C659B"),
    ("laboratory & scoring", ["laboratory automation", "retrosynthesis", "scoring"], "#3E8E9E"),
]


def sankey(path: Path) -> None:
    total = sum(int(n) for _, n, _ in TOOLS)
    counts = {name: int(n) for name, n, _ in TOOLS}
    fig, ax = plt.subplots(figsize=(6.6, 4.0))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    top, bottom = 0.905, 0.095
    span = top - bottom
    gap_cat, gap_dom = 0.006, 0.012
    n_cat = sum(len(c) for _, c, _ in DOMAINS)
    scale = (span - gap_cat * (n_cat - 1) - gap_dom * (len(DOMAINS) - 1)) / total

    # ---- column 1: the whole ocean
    x1a, x1b = 0.030, 0.082
    box(ax, x1a, bottom, x1b - x1a, span, "#33475B", ec="white", lw=0.8, r=0.004)
    ax.text((x1a + x1b) / 2, (top + bottom) / 2, f"{total} tools", ha="center", va="center",
            fontsize=7.4, color="white", fontweight="bold", rotation=90)
    ax.text(x1b + 0.012, top + 0.018, "Tool Ocean", ha="left", va="bottom", fontsize=6.8,
            color=INK, fontweight="bold")

    # ---- column 2: capability domains (height = its categories + internal gaps)
    x2a, x2b = 0.400, 0.452
    y = top
    dom_span = {}
    for name, cats, colour in DOMAINS:
        h = sum(counts[c] for c in cats) * scale + gap_cat * (len(cats) - 1)
        lo = y - h
        dom_span[name] = (lo, y)
        box(ax, x2a, lo, x2b - x2a, h, colour, ec="white", lw=0.7, r=0.003)
        ax.text(x2b + 0.010, (lo + y) / 2 + 0.012, name, ha="left", va="center", fontsize=5.6,
                color=INK, fontweight="bold")
        ax.text(x2b + 0.010, (lo + y) / 2 - 0.016, f"{sum(counts[c] for c in cats)} tools",
                ha="left", va="center", fontsize=5.0, color=GREY)
        ribbon(ax, x1b, lo, y, x2a, lo, y, colour, alpha=0.30)
        y = lo - gap_dom

    # ---- column 3: the eleven categories
    x3a, x3b = 0.760, 0.812
    for name, cats, colour in DOMAINS:
        dlo, dhi = dom_span[name]
        y = dhi
        for cat in cats:
            h = counts[cat] * scale
            lo = y - h
            box(ax, x3a, lo, x3b - x3a, h, colour, ec="white", lw=0.6, r=0.0025)
            ax.text(x3b + 0.010, (lo + y) / 2, f"{cat}  ({counts[cat]})", ha="left",
                    va="center", fontsize=5.3, color=INK)
            ribbon(ax, x2b, lo, y, x3a, lo, y, colour, alpha=0.26)
            y = lo - gap_cat

    ax.text((x2a + x2b) / 2, 0.945, "five capability domains", ha="center", va="center",
            fontsize=6.4, color=INK, fontweight="bold")
    ax.text(x3b, 0.945, "eleven categories", ha="right", va="center",
            fontsize=6.4, color=INK, fontweight="bold")
    ax.text(0.5, 0.030, "ribbon width = number of tools; colour = capability domain",
            ha="center", va="center", fontsize=5.0, color=GREY, style="italic")

    fig.subplots_adjust(0, 0, 1, 1)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------------------
# figure 4: three-panel results figure
# ---------------------------------------------------------------------------
def _load_enzyme() -> list[dict]:
    run = next((ROOT / "outputs").glob("*enzyme_design*/stage4_designed_library.csv"))
    with run.open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))[:15]
    return rows


def _load_retro() -> list[dict]:
    runs = sorted((ROOT / "outputs").glob("*retrosynthesis*/stage4_benchmark.csv"),
                  key=lambda q: q.stat().st_mtime)
    with runs[-1].open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load_sdl() -> dict:
    run = next((ROOT / "outputs").glob("*sdl_protocol*/stage4_simulation.json"))
    return json.loads(run.read_text(encoding="utf-8"))


def _fmt3(x: float) -> str:
    from decimal import Decimal, ROUND_HALF_UP
    return str(Decimal(str(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def panels(path: Path) -> None:
    fig = plt.figure(figsize=(7.0, 5.9))
    gs = fig.add_gridspec(2, 2, width_ratios=(1.0, 1.0), height_ratios=(1.05, 0.72),
                          wspace=0.30, hspace=0.62, left=0.105, right=0.985, top=0.94, bottom=0.095)

    # ---- A: designed library
    axA = fig.add_subplot(gs[0, 0])
    enz = _load_enzyme()[::-1]
    labels = [r["mutation"] for r in enz]
    scores = [float(r["score_final"]) for r in enz]
    colors = [RED if m == "M276L" else BLUE for m in labels]
    axA.barh(range(len(enz)), scores, color=colors, height=0.68)
    axA.set_yticks(range(len(enz)))
    axA.set_yticklabels(labels, fontsize=6.0)
    axA.set_xlim(0, max(scores) * 1.26)
    axA.set_xlabel("variant score", fontsize=6.4)
    axA.set_title("A  Designed enzyme library (top 15 of 2,773)", fontsize=7.4, loc="left", fontweight="bold")
    for i, s in enumerate(scores):
        axA.text(s + 0.008, i, _fmt3(s), va="center", fontsize=5.0, color=INK)
    axA.tick_params(axis="x", labelsize=5.8)
    axA.spines[["top", "right"]].set_visible(False)
    axA.grid(axis="x", color="#E8E8E8", lw=0.5)
    axA.set_axisbelow(True)
    axA.text(0.98, 0.02, "red = published hit (M276L)", transform=axA.transAxes, ha="right",
             fontsize=5.0, color=RED, style="italic")

    # ---- B: retrosynthesis benchmark
    axB = fig.add_subplot(gs[0, 1])
    retro = _load_retro()
    names = [r["name"] for r in retro]
    steps = [int(r["steps"]) if r["solved"] == "True" else 0 for r in retro]
    cols = [BLUE if s else "#D0D0D0" for s in steps]
    axB.bar(range(len(retro)), steps, color=cols, width=0.66)
    axB.set_xticks(range(len(retro)))
    axB.set_xticklabels(names, rotation=45, ha="right", fontsize=5.2)
    axB.set_ylabel("planned steps", fontsize=6.2)
    axB.set_ylim(0, 3.4)
    axB.set_title("B  Retrosynthesis benchmark (8/8 solved)", fontsize=7.4, loc="left", fontweight="bold")
    axB.tick_params(axis="y", labelsize=5.6)
    axB.spines[["top", "right"]].set_visible(False)
    axB.grid(axis="y", color="#E8E8E8", lw=0.5)
    axB.set_axisbelow(True)
    for i, st in enumerate(steps):
        if st == 0:
            axB.text(i, 0.10, "no route", ha="center", va="bottom", fontsize=4.4, color=GREY, rotation=90)
        else:
            axB.text(i, st + 0.07, str(st), ha="center", fontsize=5.0, color=INK)

    # ---- C: SDL timeline
    axC = fig.add_subplot(gs[1, :])
    sim = _load_sdl()
    timeline = sim["timeline"]
    devices = []
    for t in timeline:
        if t["device"] not in devices:
            devices.append(t["device"])
    cmap = {"TRANSFER": BLUE, "INCUBATE": ORANGE, "CENTRIFUGE": RED, "MEASURE": GREEN}
    total = max(t["end_min"] for t in timeline)
    for t in timeline:
        y = devices.index(t["device"])
        axC.barh(y, t["duration_min"], left=t["start_min"], height=0.46,
                 color=cmap.get(t["opcode"], BLUE), edgecolor="white", linewidth=0.7)

    # labels: inside the long steps, grouped above the short ones so nothing overlaps
    # split into runs of consecutive steps (a gap larger than 6 min starts a new group)
    runs: list[tuple[int, str, list[dict]]] = []
    by_key: dict[tuple[int, str], list[dict]] = {}
    for t in timeline:
        by_key.setdefault((devices.index(t["device"]), t["opcode"]), []).append(t)
    for (y, opcode), ts in by_key.items():
        ts.sort(key=lambda z: z["start_min"])
        current = [ts[0]]
        for prev, nxt in zip(ts, ts[1:]):
            if nxt["start_min"] - prev["end_min"] < 6:
                current.append(nxt)
            else:
                runs.append((y, opcode, current))
                current = [nxt]
        runs.append((y, opcode, current))

    for y, opcode, ts in runs:
        if sum(t["duration_min"] for t in ts) >= 8:
            t = max(ts, key=lambda z: z["duration_min"])
            axC.text(t["start_min"] + t["duration_min"] / 2, y,
                     f"{opcode.title()}  {t['duration_min']:.0f} min",
                     ha="center", va="center", fontsize=5.2, color="white", fontweight="bold")
        else:
            x0 = min(t["start_min"] for t in ts)
            x1 = max(t["end_min"] for t in ts)
            label = f"{opcode.title()}" + (f" \u00d7{len(ts)}" if len(ts) > 1 else "")
            axC.text((x0 + x1) / 2, y + 0.34, label, ha="center", va="bottom",
                     fontsize=4.8, color=INK)
    axC.set_yticks(range(len(devices)))
    axC.set_yticklabels([d.replace("_", " ") for d in devices], fontsize=5.8)
    axC.set_xlabel("simulated time (min)", fontsize=6.4)
    axC.set_xlim(0, total * 1.08)
    axC.set_ylim(-0.6, len(devices) - 0.15)
    axC.set_title(f"C  Compiled SDL program on the digital twin ({total:.0f} min, 6 opcodes)",
                  fontsize=7.4, loc="left", fontweight="bold")
    axC.tick_params(axis="x", labelsize=5.8)
    axC.spines[["top", "right"]].set_visible(False)
    axC.grid(axis="x", color="#E8E8E8", lw=0.5)
    axC.set_axisbelow(True)

    fig.savefig(path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    sankey(OUT / "fig_sankey.png")
    panels(OUT / "fig_panels.png")
    print("figures written to", OUT)
