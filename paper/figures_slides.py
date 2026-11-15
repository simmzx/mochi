"""Slide-sized versions of the three result panels (larger fonts, wide aspect)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from decimal import Decimal, ROUND_HALF_UP  # noqa: E402

import figures_v2 as F  # noqa: E402

OUT = Path(r"D:\deepseek\workshop\mochi\paper\figures")

INK = "#12232E"
GREY = "#5C6B78"
BLUE = "#3F6FA8"
RED = "#B85450"
ORANGE = "#E08A3C"
GREEN = "#7E9E4E"

plt.rcParams.update({"font.family": "DejaVu Sans", "savefig.dpi": 300})


def fmt3(x: float) -> str:
    return str(Decimal(str(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def panel_a(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.9))
    enz = F._load_enzyme()[::-1]
    labels = [r["mutation"] for r in enz]
    scores = [float(r["score_final"]) for r in enz]
    colors = [RED if m == "M276L" else BLUE for m in labels]
    ax.barh(range(len(enz)), scores, color=colors, height=0.7)
    ax.set_yticks(range(len(enz)))
    ax.set_yticklabels(labels, fontsize=8.5)
    ax.set_xlim(0, max(scores) * 1.26)
    ax.set_xlabel("variant score", fontsize=9)
    ax.set_title("Designed enzyme library \u2014 top 15 of 2,773", fontsize=10.5, loc="left",
                 fontweight="bold", color=INK, pad=10)
    for i, s in enumerate(scores):
        ax.text(s + 0.008, i, fmt3(s), va="center", fontsize=8, color=INK)
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#E8ECEF", lw=0.6)
    ax.set_axisbelow(True)
    ax.text(0.99, 0.02, "red = published hit (M276L)", transform=ax.transAxes, ha="right",
            fontsize=8, color=RED, style="italic")
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def panel_b(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    retro = F._load_retro()
    names = [r["name"] for r in retro]
    steps = [int(r["steps"]) for r in retro]
    ax.bar(range(len(retro)), steps, color=BLUE, width=0.62)
    ax.set_xticks(range(len(retro)))
    ax.set_xticklabels(names, rotation=38, ha="right", fontsize=8.5)
    ax.set_ylabel("planned steps", fontsize=9)
    ax.set_ylim(0, 3.5)
    ax.set_title("Retrosynthesis benchmark \u2014 8 of 8 solved", fontsize=10.5, loc="left",
                 fontweight="bold", color=INK, pad=10)
    ax.tick_params(axis="y", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E8ECEF", lw=0.6)
    ax.set_axisbelow(True)
    for i, s in enumerate(steps):
        ax.text(i, s + 0.07, str(s), ha="center", fontsize=8, color=INK)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def panel_c(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 3.5))
    sim = F._load_sdl()
    timeline = sim["timeline"]
    devices = []
    for t in timeline:
        if t["device"] not in devices:
            devices.append(t["device"])
    cmap = {"TRANSFER": BLUE, "INCUBATE": ORANGE, "CENTRIFUGE": RED, "MEASURE": GREEN}
    total = max(t["end_min"] for t in timeline)
    for t in timeline:
        y = devices.index(t["device"])
        ax.barh(y, t["duration_min"], left=t["start_min"], height=0.5,
                color=cmap.get(t["opcode"], BLUE), edgecolor="white", linewidth=0.8)
    runs: list[tuple[int, str, list[dict]]] = []
    by_key: dict[tuple[int, str], list[dict]] = {}
    for t in timeline:
        by_key.setdefault((devices.index(t["device"]), t["opcode"]), []).append(t)
    for (y, opcode), ts in by_key.items():
        ts.sort(key=lambda z: z["start_min"])
        cur = [ts[0]]
        for prev, nxt in zip(ts, ts[1:]):
            if nxt["start_min"] - prev["end_min"] < 6:
                cur.append(nxt)
            else:
                runs.append((y, opcode, cur))
                cur = [nxt]
        runs.append((y, opcode, cur))
    for y, opcode, ts in runs:
        x0 = min(t["start_min"] for t in ts)
        x1 = max(t["end_min"] for t in ts)
        dur = sum(t["duration_min"] for t in ts)
        if dur >= 12:
            ax.text((x0 + x1) / 2, y, f"{opcode.title()}  {dur:.0f} min", ha="center", va="center",
                    fontsize=8.5, color="white", fontweight="bold")
        else:
            label = opcode.title() + (f" \u00d7{len(ts)}" if len(ts) > 1 else "")
            ax.text((x0 + x1) / 2, y + 0.34, label, ha="center", va="bottom", fontsize=8, color=INK)
    ax.set_yticks(range(len(devices)))
    ax.set_yticklabels([d.replace("_", " ") for d in devices], fontsize=8.5)
    ax.set_xlabel("simulated time (min)", fontsize=9)
    ax.set_xlim(0, total * 1.06)
    ax.set_ylim(-0.6, len(devices) - 0.1)
    ax.set_title(f"Compiled SDL program on the digital twin \u2014 {total:.0f} min, 6 opcodes",
                 fontsize=10.5, loc="left", fontweight="bold", color=INK, pad=10)
    ax.tick_params(axis="x", labelsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color="#E8ECEF", lw=0.6)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(path, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    panel_a(OUT / "fig_panel_a.png")
    panel_b(OUT / "fig_panel_b.png")
    panel_c(OUT / "fig_panel_c.png")
    print("slide panels written")
