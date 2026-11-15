"""Cross-check every number in the LaTeX tables against the run artefacts."""

from __future__ import annotations

import csv
import re
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(r"D:\deepseek\workshop\mochi")
TEX = ROOT / "paper" / "latex" / "chapters"
OUT = ROOT / "outputs"


def r2(x: str) -> str:
    return str(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def r3(x: str) -> str:
    return str(Decimal(str(x)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def table_rows(tex: str, caption_fragment: str) -> list[list[str]]:
    i = tex.find(caption_fragment)
    if i < 0:
        return []
    j = tex.find("\\end{table}", i)
    block = tex[i:j]
    rows = []
    for line in block.splitlines():
        line = line.strip()
        if "&" in line and line.endswith(r"\\"):
            rows.append([c.strip() for c in line[:-2].split("&")])
    return rows[1:]  # drop header


ch4 = (TEX / "Chapter4.tex").read_text(encoding="utf-8")
ch3 = (TEX / "Chapter3.tex").read_text(encoding="utf-8")

problems = []

# ---- Table 6: target ranking
rank_csv = next(OUT.glob("2026*target_discovery*/stage4_ranking.csv"))
with rank_csv.open(encoding="utf-8") as fh:
    rank = {r["gene"]: r for r in csv.DictReader(fh)}
rows = table_rows(ch4, "Six-dimensional ranking" if False else "Six-dimension ranking")
if not rows:
    rows = table_rows(ch4, "Six-dimension ranking")
for row in rows:
    if len(row) < 10:
        continue
    gene = row[1]
    src = rank.get(gene)
    if not src:
        problems.append(f"Table 6: {gene} not in ranking csv")
        continue
    exp = [r3(src["composite"]), r2(src["dim_association"]), r2(src["dim_signaling"]),
           r2(src["dim_crc_evidence"]), r2(src["dim_pathway_centrality"]),
           r2(src["dim_novelty"]) if src["dim_novelty"] else "-", r2(src["dim_druggability"])]
    got = [row[2], row[3], row[4], row[5], row[6], row[7], row[8]]
    if got[:1] != exp[:1] or any(g != e for g, e in zip(got[1:], exp[1:])):
        problems.append(f"Table 6 {gene}: report={got} data={exp}")

# ---- Table 8: designed library
lib_csv = next(OUT.glob("*enzyme*/stage4_designed_library.csv"))
with lib_csv.open(encoding="utf-8") as fh:
    lib = {r["mutation"]: r for r in csv.DictReader(fh)}
rows = table_rows(ch4, "Top of the designed round-2 library")
for row in rows:
    if len(row) < 9:
        continue
    mut = row[1]
    src = lib.get(mut)
    if not src:
        problems.append(f"Table 8: {mut} not in library csv")
        continue
    exp = [r2(src["dist_to_site"]), r2(src["leverage"]), r2(src["chemistry"]),
           r2(src["packing"]), r3(src["score_final"])]
    got = [row[2], row[3], row[4], row[6], row[7]]
    if any(g != e for g, e in zip(got, exp)):
        problems.append(f"Table 8 {mut}: report={got} data={exp}")

# ---- Table 9: retrosynthesis
retro_csv = next(OUT.glob("*retrosynthesis*/stage4_benchmark.csv"))
with retro_csv.open(encoding="utf-8") as fh:
    retro = {r["name"]: r for r in csv.DictReader(fh)}
rows = table_rows(ch4, "Retrosynthesis benchmark")
for row in rows:
    if len(row) < 5:
        continue
    name = row[0].lower()
    src = retro.get(name)
    if not src:
        problems.append(f"Table 9: {name} not in benchmark csv")
        continue
    steps = src["steps"] if src["solved"] == "True" else "-"
    conf = r2(src["confidence"]) if src["confidence"] else "-"
    if row[2] != steps or row[4] != conf or (row[3] == "yes") != (src["solved"] == "True"):
        problems.append(f"Table 9 {name}: report={row[1:]} data=steps {steps} conf {conf}")

# ---- Table 10: SDL
sdl_csv = next(OUT.glob("*sdl_protocol*/stage4_benchmark.csv"))
with sdl_csv.open(encoding="utf-8") as fh:
    sdl = {r["name"]: r for r in csv.DictReader(fh)}
rows = table_rows(ch4, "Protocol compiler benchmark")
for row in rows:
    if len(row) < 6:
        continue
    name = row[0].lower().replace(" ", "_").replace("-", "_")
    src = sdl.get(name)
    if not src:
        continue
    if row[3] != (src["expected"] or "-") or row[4] != (src["issues"] or "-"):
        problems.append(f"Table 10 {name}: report={row[3:5]} data={src['expected']},{src['issues']}")

print("checked tables 6, 8, 9, 10")
print("problems:", len(problems))
for p in problems:
    print("  -", p)
