"""Multi-step retrosynthesis planning scenario.

Stages
------
S1 target analysis      parse the molecule, compute descriptors and functional-group inventory
S2 disconnections       enumerate and score every one-step disconnection of the target
S3 search               depth-limited best-first search to commercially available building blocks
S4 route ranking        rank routes, report per-step templates and benchmark the planner on a
                        suite of drugs whose literature syntheses are known

The planner is classical (template + stock), so every route is inspectable; the failure cases are
reported rather than hidden.
"""

from __future__ import annotations

import time

from ..workflows.stages import RunContext, _call

BENCHMARK = [
    {"name": "aspirin", "smiles": "CC(=O)Oc1ccccc1C(=O)O", "literature_steps": 1},
    {"name": "paracetamol", "smiles": "CC(=O)Nc1ccc(O)cc1", "literature_steps": 1},
    {"name": "benzocaine", "smiles": "CCOC(=O)c1ccc(N)cc1", "literature_steps": 1},
    {"name": "lidocaine", "smiles": "CCN(CC)CC(=O)Nc1c(C)cccc1C", "literature_steps": 2},
    {"name": "phenacetin", "smiles": "CCOc1ccc(NC(C)=O)cc1", "literature_steps": 2},
    {"name": "benorilate", "smiles": "CC(=O)Nc1ccc(OC(=O)c2ccccc2OC(C)=O)cc1", "literature_steps": 3},
    {"name": "sulfanilamide", "smiles": "Nc1ccc(S(N)(=O)=O)cc1", "literature_steps": 2},
    {"name": "vanillin", "smiles": "COc1cc(C=O)ccc1O", "literature_steps": 2},
]


def _fmt_route(node: dict, depth: int = 0) -> list[str]:
    pad = "  " * depth
    if node.get("buyable"):
        return [f"{pad}- `{node['smiles']}` (stock)"]
    lines = [f"{pad}- `{node['smiles']}` ← **{node.get('template')}** ({node.get('note')})"]
    for ch in node.get("children", []):
        lines.extend(_fmt_route(ch, depth + 1))
    return lines


def stage_target(ctx: RunContext) -> dict:
    t0 = time.time()
    smiles = ctx.target
    props = _call("molecule_properties", smiles=smiles)
    if not props.get("ok"):
        return {"stage": "stage_1", "name": "Target analysis", "status": "failed",
                "findings": [props.get("error", "invalid target")], "artefacts": {}, "tool_calls": []}
    groups = {k: v for k, v in (props.get("functional_groups") or {}).items() if v}
    ctx.state["target_props"] = props
    ctx.save_json("stage1_target.json", props)
    return {
        "stage": "stage_1",
        "name": "Target analysis",
        "status": "ok",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Target {props['canonical']} ({props['formula']}, MW {props['mw']}, cLogP {props['clogp']}).",
            f"Reactive handles available for disconnection: {', '.join(groups) or 'none detected'}.",
            f"Heavy atoms {props['heavy_atoms']}, rings {props['rings']}.",
        ],
        "artefacts": {"target": "stage1_target.json"},
        "tool_calls": ["molecule_properties"],
    }


def stage_disconnections(ctx: RunContext) -> dict:
    t0 = time.time()
    smiles = ctx.state["target_props"]["canonical"]
    res = _call("one_step_disconnections", smiles=smiles)
    dis = res.get("disconnections", []) if res.get("ok") else []
    ctx.state["disconnections"] = dis
    ctx.save_json("stage2_disconnections.json", res)
    counts: dict[str, int] = {}
    for d in dis:
        counts[d["name"]] = counts.get(d["name"], 0) + 1
    return {
        "stage": "stage_2",
        "name": "One-step disconnection enumeration",
        "status": "ok" if dis else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"{len(dis)} one-step disconnections enumerated.",
            f"Template usage: {counts}.",
            f"{sum(1 for d in dis if d['n_buyable'] == len(d['precursors']))} disconnections are fully buyable in one step.",
        ],
        "artefacts": {"disconnections": "stage2_disconnections.json"},
        "tool_calls": ["one_step_disconnections"],
    }


def stage_search(ctx: RunContext) -> dict:
    t0 = time.time()
    smiles = ctx.state["target_props"]["canonical"]
    depth = int(ctx.params.get("max_depth", 6))
    nodes = int(ctx.params.get("max_nodes", 400))
    res = _call("search_route", smiles=smiles, max_depth=depth, max_nodes=nodes)
    ctx.state["route"] = res.get("route")
    ctx.state["search"] = res.get("search", {})
    ctx.save_json("stage3_route.json", res)
    route = res.get("route")
    return {
        "stage": "stage_3",
        "name": "Multi-step search",
        "status": "ok" if res.get("solved") else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Search {'solved' if res.get('solved') else 'did not solve'} the target within depth {depth}.",
            f"Nodes expanded: {res.get('search', {}).get('expanded')}; leaves: {len(res.get('leaves') or [])}.",
        ] + ([f"Route cost {route.get('cost')}"] if route else []),
        "artefacts": {"route": "stage3_route.json"},
        "tool_calls": ["search_route"],
    }


def stage_ranking(ctx: RunContext) -> dict:
    t0 = time.time()
    route = ctx.state.get("route")
    metrics = _call("route_metrics", route=route) if route else {"ok": False}
    # benchmark
    bench = []
    for item in BENCHMARK:
        r = _call("search_route", smiles=item["smiles"], max_depth=int(ctx.params.get("max_depth", 6)),
                  max_nodes=int(ctx.params.get("max_nodes", 400)))
        m = _call("route_metrics", route=r.get("route")) if r.get("solved") else {"ok": False}
        bench.append({
            "name": item["name"],
            "solved": bool(r.get("solved")),
            "steps": m.get("steps") if m.get("ok") else None,
            "literature_steps": item["literature_steps"],
            "confidence": m.get("confidence") if m.get("ok") else None,
        })
    solved = [b for b in bench if b["solved"]]
    ctx.state["benchmark"] = bench
    ctx.state["metrics"] = metrics
    ctx.save_csv("stage4_benchmark.csv", bench)
    ctx.save_json("stage4_metrics.json", metrics)

    lines = []
    if route:
        lines.extend(_fmt_route(route))
    return {
        "stage": "stage_4",
        "name": "Route ranking and benchmark",
        "status": "ok" if route else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Best route: {metrics.get('steps')} step(s), templates {metrics.get('unique_templates')}, "
            f"confidence {metrics.get('confidence')}.",
            f"Benchmark: solved {len(solved)}/{len(bench)} drugs; mean planned steps "
            f"{round(sum(b['steps'] for b in solved) / max(1, len(solved)), 2)} vs literature "
            f"{round(sum(b['literature_steps'] for b in solved) / max(1, len(solved)), 2)}.",
        ],
        "artefacts": {"benchmark": "stage4_benchmark.csv"},
        "tool_calls": ["route_metrics", "search_route"],
        "route_lines": lines,
    }


STAGES = {
    "stage_1": stage_target,
    "stage_2": stage_disconnections,
    "stage_3": stage_search,
    "stage_4": stage_ranking,
}


def audit(stage: str, result: dict, ctx: RunContext) -> list[dict]:
    checks = []

    def add(claim, ok, why, hard=True):
        checks.append({"claim": claim, "supported": bool(ok), "why": why, "hard": hard})

    if stage == "stage_1":
        p = ctx.state.get("target_props") or {}
        add("Target parsed", bool(p.get("canonical")), "invalid SMILES")
        add("Reactive handles found", any(v for v in (p.get("functional_groups") or {}).values()),
            "no known functional group -> no template applies", False)
        add("Target is not a stock compound", not p.get("buyable"),
            "the target is itself a building block; nothing to plan", False)
    elif stage == "stage_2":
        dis = ctx.state.get("disconnections") or []
        add("Disconnections enumerated", len(dis) >= 1, "no template matched the target")
        add("At least one disconnection is fully buyable",
            any(d["n_buyable"] == len(d["precursors"]) for d in dis), "one-step screen failed", False)
    elif stage == "stage_3":
        add("Route found", bool(ctx.state.get("route")), "search exhausted without reaching stock")
    elif stage == "stage_4":
        bench = ctx.state.get("benchmark") or []
        solved = [b for b in bench if b["solved"]]
        add("Benchmark executed", len(bench) >= 5, "benchmark too small")
        add("Benchmark success rate acceptable", len(solved) / max(1, len(bench)) >= 0.5,
            f"solved {len(solved)}/{len(bench)}", False)
        add("Every solved route terminates in stock",
            all(b["steps"] is not None for b in solved), "route without stock leaves")
    return checks


def render(ctx: RunContext, results: list[dict], ranking: list[dict], **kw) -> str:
    props = ctx.state.get("target_props") or {}
    metrics = ctx.state.get("metrics") or {}
    bench = ctx.state.get("benchmark") or []
    route = ctx.state.get("route")
    L = ["## Results", ""]
    L.append(f"Target: **{ctx.target}** → `{props.get('canonical')}` "
             f"({props.get('formula')}, MW {props.get('mw')}).")
    L.append("")
    if route:
        L.append("### Planned route")
        L.append("")
        L.extend(_fmt_route(route))
        L.append("")
        L.append(f"Steps: **{metrics.get('steps')}**, templates: {metrics.get('unique_templates')}, "
                 f"confidence: **{metrics.get('confidence')}**.")
        L.append("")
    else:
        L.append("> The planner did not find a route to stock within the depth budget; the failure is "
                 "reported as a result, not hidden.")
        L.append("")
    L.append("### Benchmark on drugs with known syntheses")
    L.append("")
    L.append("| drug | literature steps | planned steps | solved | confidence |")
    L.append("|---|---|---|---|---|")
    for b in bench:
        L.append(f"| {b['name']} | {b['literature_steps']} | {b['steps'] if b['solved'] else '—'} | "
                 f"{'yes' if b['solved'] else 'no'} | {b['confidence'] if b['solved'] else '—'} |")
    solved = [b for b in bench if b["solved"]]
    L.append("")
    L.append(f"Success rate **{len(solved)}/{len(bench)}**; mean planned steps "
             f"**{round(sum(b['steps'] for b in solved) / max(1, len(solved)), 2)}** "
             f"vs literature **{round(sum(b['literature_steps'] for b in solved) / max(1, len(solved)), 2)}**.")
    L.append("")
    return "\n".join(L)
