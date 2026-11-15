"""Protocol-to-SDL compilation scenario.

Stages
------
S1 ingestion    parse the natural-language protocol into typed steps and report coverage
S2 compilation  emit SDL opcodes with SI units, devices, vessels and durations
S3 validation   static safety/feasibility checks, then a bounded repair loop
S4 simulation   digital-twin timeline plus a benchmark over a protocol suite that contains
                deliberately corrupted protocols (the compiler must catch them)
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from ..workflows.stages import RunContext, _call

DATA = Path(__file__).resolve().parents[2] / "data"

REPAIRS = {
    "vessel_overflow": "split the aliquot into two transfers of half the volume",
    "temperature_limit": "cap the set-point to the device maximum",
    "missing_volume": "assume the protocol default of 100 uL",
    "non_positive_duration": "set the minimum practical duration of 1 min",
    "flammable_hazard": "cap the temperature below the solvent flash point",
}


def _corpus() -> list[dict]:
    path = DATA / "protocols.json"
    return json.loads(path.read_text(encoding="utf-8")).get("protocols", []) if path.exists() else []


def _find(name: str) -> dict | None:
    for p in _corpus():
        if p["name"] == name or p["title"].lower() == name.lower():
            return p
    return None


def stage_ingest(ctx: RunContext) -> dict:
    t0 = time.time()
    proto = _find(ctx.target) or _corpus()[0]
    parsed = _call("parse_protocol", protocol_text=proto["text"])
    ctx.state["protocol"] = proto
    ctx.state["parsed"] = parsed
    ctx.save_json("stage1_parsed.json", parsed)
    return {
        "stage": "stage_1",
        "name": "Protocol ingestion",
        "status": "ok" if parsed.get("n_steps") else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Protocol '{proto['title']}': {parsed.get('n_steps')} executable steps parsed "
            f"(coverage {parsed.get('coverage')}).",
            f"Unparsed sentences: {len(parsed.get('unparsed') or [])}.",
        ],
        "artefacts": {"parsed": "stage1_parsed.json"},
        "tool_calls": ["parse_protocol"],
    }


def stage_compile(ctx: RunContext) -> dict:
    t0 = time.time()
    program = _call("compile_sdl", parsed=ctx.state["parsed"])
    ctx.state["program"] = program
    ctx.save_json("stage2_program.json", program)
    ops = [s["opcode"] for s in program.get("steps", [])]
    return {
        "stage": "stage_2",
        "name": "SDL program synthesis",
        "status": "ok" if program.get("n_opcodes") else "failed",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"{program.get('n_opcodes')} opcodes emitted: {', '.join(ops)}.",
            f"Estimated duration {program.get('total_min')} min; {len(program.get('warnings') or [])} compiler warnings.",
        ],
        "artefacts": {"program": "stage2_program.json"},
        "tool_calls": ["compile_sdl"],
    }


def _apply_repairs(program: dict, issues: list[dict]) -> dict:
    """Deterministic repair pass: fix what can be fixed, leave the rest flagged."""
    steps = [dict(s) for s in program["steps"]]
    for issue in issues:
        if issue["severity"] != "error":
            continue
        code = issue["code"]
        idx = issue.get("step", 0)
        if not (1 <= idx <= len(steps)):
            continue
        s = steps[idx - 1]
        if code == "vessel_overflow":
            s["volume_ml"] = round((s["volume_ml"] or 0) / 2, 3)
            s["repaired"] = "split into two aliquots"
        elif code == "temperature_limit":
            s["temperature_c"] = min(s["temperature_c"] or 0, 150)
            s["repaired"] = "temperature capped to device limit"
        elif code == "flammable_hazard":
            s["temperature_c"] = 25
            s["repaired"] = "temperature set below flash point"
        elif code == "missing_volume":
            s["volume_ml"] = 0.1
            s["repaired"] = "default volume 100 uL"
        elif code == "non_positive_duration":
            s["duration_min"] = 1.0
            s["repaired"] = "minimum duration 1 min"
    repaired = dict(program)
    repaired["steps"] = steps
    repaired["total_min"] = round(sum(s["duration_min"] for s in steps), 2)
    return repaired


def stage_validate(ctx: RunContext) -> dict:
    t0 = time.time()
    program = ctx.state["program"]
    v1 = _call("validate_sdl", program=program)
    issues = v1.get("issues", [])
    rounds = 0
    repaired = program
    v2 = v1
    while (not v2.get("valid")) and rounds < int(ctx.params.get("max_repair_rounds", 2)):
        rounds += 1
        repaired = _apply_repairs(repaired, v2.get("issues", []))
        v2 = _call("validate_sdl", program=repaired)
    ctx.state["validation"] = v2
    ctx.state["repaired_program"] = repaired
    ctx.save_json("stage3_validation.json", {"initial": v1, "final": v2, "repair_rounds": rounds})
    codes = sorted({i["code"] for i in issues})
    return {
        "stage": "stage_3",
        "name": "Static validation and repair",
        "status": "ok",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"{v1.get('n_issues')} issues found ({v1.get('n_errors')} errors): {codes or 'none'}.",
            f"Repair loop: {rounds} round(s); final validity {v2.get('valid')}.",
            "Repairs: " + "; ".join(f"{k}: {v}" for k, v in REPAIRS.items() if k in codes) if codes else "no repair needed.",
        ],
        "artefacts": {"validation": "stage3_validation.json"},
        "tool_calls": ["validate_sdl"],
    }


def stage_simulate(ctx: RunContext) -> dict:
    t0 = time.time()
    program = ctx.state.get("repaired_program") or ctx.state["program"]
    sim = _call("simulate_sdl", program=program)
    ctx.state["simulation"] = sim
    ctx.save_json("stage4_simulation.json", sim)

    # benchmark over the whole corpus, including the corrupted protocols
    bench = []
    for p in _corpus():
        parsed = _call("parse_protocol", protocol_text=p["text"])
        prog = _call("compile_sdl", parsed=parsed) if parsed.get("ok") else {"ok": False}
        val = _call("validate_sdl", program=prog) if prog.get("ok") else {"ok": False}
        detected = sorted({i["code"] for i in (val.get("issues") or [])})
        expected = sorted(p.get("expected_errors") or [])
        bench.append({
            "name": p["name"],
            "steps": parsed.get("n_steps"),
            "opcodes": prog.get("n_opcodes"),
            "issues": detected,
            "expected": expected,
            "caught": all(e in detected for e in expected) if expected else None,
            "valid_after_compile": bool(val.get("valid")),
        })
    ctx.state["benchmark"] = bench
    ctx.save_csv("stage4_benchmark.csv", [{k: (v if not isinstance(v, list) else "|".join(v))
                                           for k, v in b.items()} for b in bench])
    corrupted = [b for b in bench if b["expected"]]
    caught = [b for b in corrupted if b["caught"]]
    clean = [b for b in bench if not b["expected"]]
    clean_ok = [b for b in clean if b["valid_after_compile"]]
    return {
        "stage": "stage_4",
        "name": "Execution simulation and benchmark",
        "status": "ok",
        "duration_s": round(time.time() - t0, 1),
        "findings": [
            f"Simulated timeline: {sim.get('total_min')} min over {sim.get('n_steps')} steps; "
            f"bottleneck device {sim.get('bottleneck_device')}.",
            f"Compiler benchmark: {len(clean_ok)}/{len(clean)} clean protocols validate, "
            f"{len(caught)}/{len(corrupted)} corrupted protocols caught.",
        ],
        "artefacts": {"simulation": "stage4_simulation.json", "benchmark": "stage4_benchmark.csv"},
        "tool_calls": ["simulate_sdl"],
    }


STAGES = {
    "stage_1": stage_ingest,
    "stage_2": stage_compile,
    "stage_3": stage_validate,
    "stage_4": stage_simulate,
}


def audit(stage: str, result: dict, ctx: RunContext) -> list[dict]:
    checks = []

    def add(claim, ok, why, hard=True):
        checks.append({"claim": claim, "supported": bool(ok), "why": why, "hard": hard})

    if stage == "stage_1":
        p = ctx.state.get("parsed") or {}
        add("Protocol parsed into steps", (p.get("n_steps") or 0) >= 3, "too few steps")
        add("Parsing coverage above 80%", (p.get("coverage") or 0) >= 0.8,
            f"coverage {p.get('coverage')}", False)
    elif stage == "stage_2":
        prog = ctx.state.get("program") or {}
        add("Every parsed step mapped to an opcode", prog.get("n_opcodes") == len((ctx.state.get("parsed") or {}).get("steps", [])),
            "opcode/step mismatch")
        add("Durations assigned", all(s.get("duration_min") for s in prog.get("steps", [])), "missing durations", False)
    elif stage == "stage_3":
        v = ctx.state.get("validation") or {}
        add("Validation executed", "valid" in v, "validator did not run")
        add("Program valid after repair", bool(v.get("valid")), "unrepaired errors remain", False)
    elif stage == "stage_4":
        bench = ctx.state.get("benchmark") or []
        corrupted = [b for b in bench if b["expected"]]
        caught = [b for b in corrupted if b["caught"]]
        clean = [b for b in bench if not b["expected"]]
        clean_ok = [b for b in clean if b["valid_after_compile"]]
        add("Benchmark executed", len(bench) >= 8, "corpus too small")
        add("Corrupted protocols detected", len(caught) == len(corrupted),
            f"caught {len(caught)}/{len(corrupted)}")
        add("Clean protocols accepted", len(clean_ok) == len(clean),
            f"{len(clean_ok)}/{len(clean)} clean protocols validate", False)
        add("Timeline simulated", bool(ctx.state.get("simulation", {}).get("total_min")), "no timeline", False)
    return checks


def render(ctx: RunContext, results: list[dict], ranking: list[dict], **kw) -> str:
    proto = ctx.state.get("protocol") or {}
    prog = ctx.state.get("repaired_program") or ctx.state.get("program") or {}
    sim = ctx.state.get("simulation") or {}
    val = ctx.state.get("validation") or {}
    bench = ctx.state.get("benchmark") or []
    L = ["## Results", ""]
    L.append(f"Protocol: **{proto.get('title')}** ({proto.get('name')}): {len(proto.get('text', []))} sentences.")
    L.append("")
    L.append("### Compiled SDL program")
    L.append("")
    L.append("| # | opcode | device | vessel | volume (mL) | T (°C) | duration (min) | source |")
    L.append("|---|---|---|---|---|---|---|---|")
    for s in prog.get("steps", []):
        L.append(f"| {s['index']} | `{s['opcode']}` | {s['device']} | {s['vessel']} | "
                 f"{s['volume_ml'] if s['volume_ml'] is not None else '—'} | "
                 f"{s['temperature_c'] if s['temperature_c'] is not None else '—'} | {s['duration_min']} | "
                 f"{(s.get('source_text') or '')[:60]} |")
    L.append("")
    L.append(f"Validation: **{'valid' if val.get('valid') else 'invalid'}**, "
             f"{val.get('n_issues', 0)} issues ({val.get('n_errors', 0)} errors).")
    L.append("")
    L.append("### Digital-twin execution")
    L.append("")
    L.append(f"Total time **{sim.get('total_min')} min**, {sim.get('n_steps')} steps, "
             f"bottleneck **{sim.get('bottleneck_device')}**, liquid consumed "
             f"{sim.get('liquid_consumed_ml')} mL.")
    L.append("")
    L.append("### Compiler benchmark (clean + deliberately corrupted protocols)")
    L.append("")
    L.append("| protocol | steps | opcodes | expected error | detected | caught |")
    L.append("|---|---|---|---|---|---|")
    for b in bench:
        L.append(f"| {b['name']} | {b['steps']} | {b['opcodes']} | {', '.join(b['expected']) or '—'} | "
                 f"{', '.join(b['issues']) or '—'} | "
                 f"{'yes' if b['caught'] else ('n/a' if b['caught'] is None else 'NO')} |")
    L.append("")
    return "\n".join(L)
