"""Generate the architecture figure and the MOCHI logo used in the report and slides."""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Wedge  # noqa: E402

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(exist_ok=True)

INK = "#2F3E4E"
BLUE = "#4F81BD"
RED = "#C0504D"
GREEN = "#9BBB59"
PURPLE = "#8064A2"
ORANGE = "#F79646"
SAND = "#FDF6EC"


def _box(ax, x, y, w, h, text, color, fontsize=9, text_color="white", lw=1.2):
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
                         facecolor=color, edgecolor="white", linewidth=lw, zorder=2)
    ax.add_patch(box)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color=text_color,
            fontsize=fontsize, fontweight="bold", zorder=3)


def _arrow(ax, p1, p2, color=INK, style="-|>", lw=1.4, rad=0.0):
    ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle=style, mutation_scale=11,
                                 color=color, linewidth=lw,
                                 connectionstyle=f"arc3,rad={rad}", zorder=1))


def architecture(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(11.2, 6.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # task layer
    _box(ax, 0.02, 0.80, 0.17, 0.13,
         "Task\n(target discovery · enzyme design\n· retrosynthesis · SDL)", INK, 7.4)
    # manager
    _box(ax, 0.25, 0.82, 0.20, 0.11, "Manager\nplan · delegate · calibrate", BLUE, 8.2)
    # template library
    _box(ax, 0.50, 0.82, 0.20, 0.11, "Template library\nTF-IDF retrieval", PURPLE, 8.2)
    # dev critic toolmaker
    _box(ax, 0.25, 0.56, 0.18, 0.11, "Dev agent\nstage programs", GREEN, 8.2)
    _box(ax, 0.47, 0.56, 0.18, 0.11, "Critic agent\ndeterministic audit", RED, 8.2)
    _box(ax, 0.69, 0.56, 0.18, 0.11, "Tool creation\ngap → new tool", ORANGE, 8.2)
    # tool ocean
    _box(ax, 0.06, 0.28, 0.86, 0.13,
         "Tool Ocean  ·  46 tools  ·  UniProt · Open Targets · cBioPortal · PubMed · KEGG · Reactome · "
         "STRING · IntAct · AlphaFold\nRDKit · ChEMBL · DGIdb · GitHub · dynamic tools",
         "#2F3E4E", 7.6)
    # outputs
    _box(ax, 0.06, 0.05, 0.86, 0.13,
         "Outputs  ·  ranked targets + evidence dossier  ·  variant library + primers  ·  synthesis route  ·  "
         "validated SDL program\nfull provenance (every HTTP call)  ·  agent transcript  ·  reproducible run directory",
         "#6E7B8B", 7.6)

    # arrows
    _arrow(ax, (0.19, 0.865), (0.25, 0.875))
    _arrow(ax, (0.45, 0.875), (0.50, 0.875), style="<|-|>")
    _arrow(ax, (0.35, 0.82), (0.33, 0.67))
    _arrow(ax, (0.43, 0.615), (0.47, 0.615), style="<|-|>")
    _arrow(ax, (0.65, 0.615), (0.69, 0.615), style="<|-|>")
    _arrow(ax, (0.69, 0.62), (0.38, 0.80), style="-|>", color=ORANGE, rad=-0.25)
    _arrow(ax, (0.34, 0.56), (0.34, 0.41), style="<|-|>")
    _arrow(ax, (0.56, 0.56), (0.56, 0.41), style="<|-|>")
    _arrow(ax, (0.20, 0.28), (0.20, 0.18), style="-|>")
    _arrow(ax, (0.78, 0.28), (0.78, 0.18), style="-|>")

    ax.text(0.70, 0.735, "capability gap", color=ORANGE, fontsize=7.6, style="italic")
    ax.text(0.005, 0.965, "MOCHI", fontsize=15, fontweight="bold", color=INK)
    ax.text(0.115, 0.968, "self-evolving multi-agent orchestrator for AI drug discovery",
            fontsize=8.4, color="#6E7B8B")
    fig.tight_layout()
    fig.savefig(path, dpi=220, facecolor="white")
    plt.close(fig)


def logo(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(4.2, 4.2))
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.45, 1.15)
    ax.axis("off")
    # mochi body
    ax.add_patch(Circle((0, 0), 0.95, facecolor="#FFF7F0", edgecolor="#F2C9A0", linewidth=3, zorder=2))
    ax.add_patch(Wedge((0, 0), 0.95, 200, 340, width=0.0, facecolor="#FDEFE3", edgecolor="none", zorder=1))
    # four agent dots
    cols = [BLUE, GREEN, RED, ORANGE]
    for i, c in enumerate(cols):
        ang = math.radians(45 + 90 * i)
        ax.add_patch(Circle((0.42 * math.cos(ang), 0.42 * math.sin(ang)), 0.145,
                            facecolor=c, edgecolor="white", linewidth=2.2, zorder=3))
    # little sparkle for self-evolution
    ax.plot([0.0, 0.0], [-0.16, 0.16], color="#C9A227", linewidth=3.0, solid_capstyle="round", zorder=4)
    ax.plot([-0.16, 0.16], [0.0, 0.0], color="#C9A227", linewidth=3.0, solid_capstyle="round", zorder=4)
    ax.text(0, -1.18, "MOCHI", ha="center", va="center", fontsize=24, fontweight="bold", color=INK)
    fig.tight_layout()
    fig.savefig(path, dpi=220, transparent=True)
    plt.close(fig)


if __name__ == "__main__":
    architecture(OUT / "fig_architecture.png")
    logo(OUT / "fig_logo.png")
    print("written to", OUT)

