"""Protocol-to-SDL compiler tools.

Turning a natural-language wet-lab protocol into machine-executable instructions requires four
distinct steps, each exposed here as a tool:

    parse_protocol   text  -> typed steps (verb + parameters + units)
    compile_sdl      steps -> SDL opcodes with normalised SI units and resources
    validate_sdl     program -> list of violations (capacity, temperature, units, ordering, hazard)
    simulate_sdl     program -> execution timeline and resource usage on a digital twin

The compiler is rule-based and deterministic on purpose: an auditable program is more valuable
than a fluent one, and every emitted opcode can be traced back to a sentence of the protocol.
"""

from __future__ import annotations

import re

from .registry import tool

# ---------------------------------------------------------------------------
# device / vessel model (digital twin)
# ---------------------------------------------------------------------------
DEVICES = {
    "liquid_handler": {"max_volume_ml": 1000, "min_volume_ml": 0.001},
    "heat_block": {"max_temp_c": 150, "min_temp_c": 4},
    "incubator": {"max_temp_c": 60, "min_temp_c": 4},
    "centrifuge": {"max_g": 20000},
    "plate_reader": {"max_temp_c": 45},
}
VESSELS = {
    "eppendorf": 2.0,
    "falcon15": 15.0,
    "falcon50": 50.0,
    "vial2ml": 2.0,
    "well96": 0.3,
    "flask250": 250.0,
}
FLAMMABLE = {"diethyl ether": 34.0, "hexane": 69.0, "ethanol": 78.0, "methanol": 65.0, "acetone": 56.0}

OPCODES = ("TRANSFER", "HEAT", "COOL", "STIR", "INCUBATE", "CENTRIFUGE", "FILTER", "WASH", "MEASURE", "WAIT")

VOLUME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(µL|uL|μL|mL|L)\b")
TEMP_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:°C|degC|C)\b")
TIME_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(s|sec|min|minutes?|h|hours?)\b")
SPEED_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(rpm|g|xg)\b")


def to_ml(value: float, unit: str) -> float:
    unit = unit.replace("μ", "µ")
    if unit in ("µL", "uL"):
        return value / 1000.0
    if unit == "L":
        return value * 1000.0
    return value


def to_minutes(value: float, unit: str) -> float:
    if unit in ("s", "sec"):
        return value / 60.0
    if unit in ("h", "hour", "hours"):
        return value * 60.0
    return value


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
def _verb_of(sentence: str) -> str | None:
    s = sentence.lower()
    if "centrifug" in s:
        return "centrifuge"
    if "incubat" in s:
        return "incubate"
    if "heat" in s or "warm" in s:
        return "heat"
    if "cool" in s or "chill" in s:
        return "cool"
    if "stir" in s or "shake" in s or "vortex" in s:
        return "stir"
    if "filter" in s:
        return "filter"
    if "wash" in s:
        return "wash"
    if "inject" in s or "measure" in s or "read" in s or "analy" in s:
        return "measure"
    if "add" in s or "pipette" in s or "transfer" in s or "mix" in s or "quench" in s:
        return "transfer"
    if "wait" in s or "stand" in s:
        return "wait"
    return None


VESSEL_RE = re.compile(r"(\d+(?:\.\d+)?)\s*mL\s*(vial|tube|flask|well|plate)", re.I)


def _strip_vessel_mentions(text: str) -> str:
    """Remove '2 mL vial' style container phrases so they are not read as reagent volumes."""
    return re.sub(r"\d+(?:\.\d+)?\s*mL\s*(?:vial|tube|flask|well|plate|eppendorf)", " ", text, flags=re.I)


def _vessel_of(text: str) -> str | None:
    m = VESSEL_RE.search(text)
    if not m:
        return None
    cap = float(m.group(1))
    kind = m.group(2).lower()
    if kind == "well":
        return "well96"
    if cap <= 2.5:
        return "vial2ml" if kind == "vial" else "eppendorf"
    if cap <= 15:
        return "falcon15"
    if cap <= 50:
        return "falcon50" if kind == "tube" else "flask250"
    return "flask250"


@tool(
    "parse_protocol",
    "laboratory",
    "Parse a natural-language wet-lab protocol into typed steps with volumes, temperatures, "
    "durations, speeds and reagents; unparsable sentences are returned explicitly.",
    protocol_text="protocol as a list of sentences (or one string)",
)
def parse_protocol(protocol_text) -> dict:
    if isinstance(protocol_text, str):
        sentences = re.split(r"(?<=[.!?])\s+|\n+", protocol_text)
    else:
        sentences = list(protocol_text)
    steps, unparsed = [], []
    for i, raw in enumerate([s.strip() for s in sentences if s and s.strip()], 1):
        verb = _verb_of(raw)
        if verb is None:
            unparsed.append(raw)
            continue
        clean = _strip_vessel_mentions(raw)
        vols = [(float(v), u) for v, u in VOLUME_RE.findall(clean)]
        temps = [float(t) for t in TEMP_RE.findall(clean)]
        times = [(float(v), u) for v, u in TIME_RE.findall(clean)]
        speeds = [(float(v), u) for v, u in SPEED_RE.findall(clean)]
        vessel = _vessel_of(raw)
        reagent = None
        m = re.search(r"(?:of|with)\s+([A-Za-z][A-Za-z0-9 \-]{2,30}?)(?:\s+to|\s+into|\s+and|,|\.|$)", clean)
        if m:
            reagent = m.group(1).strip()
        steps.append({
            "step": i,
            "verb": verb,
            "text": raw,
            "volumes": [{"value": v, "unit": u, "ml": round(to_ml(v, u), 4)} for v, u in vols],
            "temperatures_c": temps,
            "times": [{"value": v, "unit": u, "minutes": round(to_minutes(v, u), 3)} for v, u in times],
            "speeds": [{"value": v, "unit": u} for v, u in speeds],
            "vessel": vessel,
            "reagent": reagent,
        })
    return {
        "ok": True,
        "source": "rule-based protocol parser",
        "n_steps": len(steps),
        "steps": steps,
        "unparsed": unparsed,
        "coverage": round(len(steps) / max(1, len(steps) + len(unparsed)), 3),
    }


# ---------------------------------------------------------------------------
# compilation
# ---------------------------------------------------------------------------
OPCODE_OF = {
    "transfer": "TRANSFER", "heat": "HEAT", "cool": "COOL", "stir": "STIR",
    "incubate": "INCUBATE", "centrifuge": "CENTRIFUGE", "filter": "FILTER",
    "wash": "WASH", "measure": "MEASURE", "wait": "WAIT",
}


@tool(
    "compile_sdl",
    "laboratory",
    "Compile parsed protocol steps into an SDL program: typed opcodes with SI units, device "
    "assignment, vessel, and per-step duration.",
    parsed="output of parse_protocol",
    vessel="default vessel type if the protocol does not state one",
)
def compile_sdl(parsed: dict, vessel: str = "eppendorf") -> dict:
    if not parsed.get("ok"):
        return {"ok": False, "error": "unparsed protocol"}
    program, warnings = [], []
    current_vessel = vessel
    for step in parsed["steps"]:
        opcode = OPCODE_OF.get(step["verb"])
        if opcode is None:
            warnings.append(f"step {step['step']}: no opcode for verb {step['verb']}")
            continue
        # a vessel declared once at the start of a protocol stays in force until changed
        if step.get("vessel"):
            current_vessel = step["vessel"]
        device = {
            "TRANSFER": "liquid_handler", "HEAT": "heat_block", "COOL": "heat_block",
            "STIR": "heat_block", "INCUBATE": "incubator", "CENTRIFUGE": "centrifuge",
            "FILTER": "liquid_handler", "WASH": "liquid_handler", "MEASURE": "plate_reader",
            "WAIT": "liquid_handler",
        }[opcode]
        volume_ml = sum(v["ml"] for v in step["volumes"]) if step["volumes"] else None
        duration = step["times"][0]["minutes"] if step["times"] else None
        if duration is None:
            duration = {"TRANSFER": 2.0, "HEAT": 10.0, "COOL": 10.0, "STIR": 5.0, "INCUBATE": 30.0,
                        "CENTRIFUGE": 10.0, "FILTER": 5.0, "WASH": 3.0, "MEASURE": 2.0, "WAIT": 5.0}[opcode]
            warnings.append(f"step {step['step']}: no duration stated, defaulted to {duration} min")
        program.append({
            "index": len(program) + 1,
            "opcode": opcode,
            "device": device,
            "vessel": current_vessel,
            "volume_ml": volume_ml,
            "temperature_c": step["temperatures_c"][0] if step["temperatures_c"] else None,
            "speed": step["speeds"][0] if step["speeds"] else None,
            "duration_min": round(float(duration), 2),
            "source_text": step["text"],
            "reagent": step.get("reagent"),
        })
    return {
        "ok": True,
        "source": "SDL compiler",
        "n_opcodes": len(program),
        "steps": program,
        "warnings": warnings,
        "total_min": round(sum(s["duration_min"] for s in program), 2),
    }


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------
@tool(
    "validate_sdl",
    "laboratory",
    "Statically validate an SDL program: vessel capacity, device temperature limits, missing units, "
    "non-positive durations, flammable-solvent hazards and basic ordering constraints.",
    program="output of compile_sdl",
)
def validate_sdl(program: dict) -> dict:
    if not program.get("ok"):
        return {"ok": False, "error": "no program"}
    issues = []
    for s in program["steps"]:
        vessel = s.get("vessel") or "eppendorf"
        cap = VESSELS.get(vessel)
        if s["volume_ml"] is not None and cap is not None and s["volume_ml"] > cap:
            issues.append({"severity": "error", "code": "vessel_overflow", "step": s["index"],
                           "message": f"{s['volume_ml']} mL exceeds the {vessel} capacity ({cap} mL)"})
        if s["volume_ml"] is None and s["opcode"] in ("TRANSFER", "WASH", "MEASURE"):
            issues.append({"severity": "warning", "code": "missing_volume", "step": s["index"],
                           "message": "volume not stated for a liquid-handling opcode"})
        if s["temperature_c"] is not None:
            lim = DEVICES.get(s["device"], {})
            if lim.get("max_temp_c") is not None and s["temperature_c"] > lim["max_temp_c"]:
                issues.append({"severity": "error", "code": "temperature_limit", "step": s["index"],
                               "message": f"{s['temperature_c']} C exceeds {s['device']} limit "
                                          f"({lim['max_temp_c']} C)"})
            if s["temperature_c"] < 0:
                issues.append({"severity": "warning", "code": "sub_zero", "step": s["index"],
                               "message": f"{s['temperature_c']} C is below 0 C; check the cooling device"})
        if s["duration_min"] is not None and s["duration_min"] <= 0:
            issues.append({"severity": "error", "code": "non_positive_duration", "step": s["index"],
                           "message": "duration must be positive"})
    # hazard screening is protocol-level: a solvent introduced in one step can be heated later
    all_text = " ".join((s.get("source_text") or "") for s in program["steps"]).lower()
    max_temp = max([s["temperature_c"] for s in program["steps"]
                    if s.get("temperature_c") is not None], default=None)
    for solvent, flash in FLAMMABLE.items():
        if solvent in all_text and max_temp is not None and max_temp > flash:
            issues.append({"severity": "error", "code": "flammable_hazard", "step": 0,
                           "message": f"{solvent} present and the protocol reaches {max_temp} C, "
                                      f"above its flash point ({flash} C)"})
    ops = [s["opcode"] for s in program["steps"]]
    if "CENTRIFUGE" in ops and "TRANSFER" not in ops[: ops.index("CENTRIFUGE")]:
        issues.append({"severity": "warning", "code": "centrifuge_before_transfer", "step": 1,
                       "message": "centrifugation before any liquid transfer"})
    if program.get("total_min", 0) > 24 * 60:
        issues.append({"severity": "warning", "code": "long_run", "step": 0,
                       "message": "total protocol time exceeds 24 h"})
    errors = [i for i in issues if i["severity"] == "error"]
    return {
        "ok": True,
        "source": "SDL static validator",
        "n_issues": len(issues),
        "n_errors": len(errors),
        "issues": issues,
        "valid": len(errors) == 0,
    }


# ---------------------------------------------------------------------------
# simulation
# ---------------------------------------------------------------------------
@tool(
    "simulate_sdl",
    "laboratory",
    "Simulate an SDL program on the device model: per-step start/end times, device occupancy and "
    "consumable usage.",
    program="output of compile_sdl",
)
def simulate_sdl(program: dict) -> dict:
    if not program.get("ok"):
        return {"ok": False, "error": "no program"}
    t = 0.0
    timeline, device_time = [], {}
    liquid_ml = 0.0
    for s in program["steps"]:
        start = t
        t += float(s["duration_min"])
        timeline.append({"step": s["index"], "opcode": s["opcode"], "device": s["device"],
                         "start_min": round(start, 2), "end_min": round(t, 2),
                         "duration_min": s["duration_min"]})
        device_time[s["device"]] = round(device_time.get(s["device"], 0.0) + float(s["duration_min"]), 2)
        if s["opcode"] in ("TRANSFER", "WASH") and s["volume_ml"]:
            liquid_ml += s["volume_ml"]
    return {
        "ok": True,
        "source": "SDL digital twin",
        "total_min": round(t, 2),
        "n_steps": len(timeline),
        "timeline": timeline,
        "device_utilisation_min": device_time,
        "liquid_consumed_ml": round(liquid_ml, 3),
        "bottleneck_device": max(device_time, key=device_time.get) if device_time else None,
    }
