"""Scenario registry.

The four agents (Manager / Dev / Critic / Tool Creation), the template library, the
Tool Ocean and the report machinery are scenario-agnostic.  A *scenario* supplies the
scientific content of the four stages:

    STAGES        {stage_id: callable(ctx) -> dict}
    AUDIT         optional callable(stage_id, result, ctx) -> list[check dict]
    TEMPLATE_ID   reasoning template used when the task matches
    DEFAULT_TASK  fallback instruction
    LABEL         human readable name

Adding a new AIDD task therefore means writing one module here - the control plane,
auditing, provenance and reporting stay untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ..workflows import stages as _target_discovery


@dataclass
class Scenario:
    key: str
    label: str
    template_id: str
    default_task: str
    stages: dict[str, Callable]
    stage_names: list[str] | None = None
    audit: Callable | None = None
    report: Callable | None = None


def _load() -> dict[str, Scenario]:
    from . import enzyme_design, retrosynthesis, sdl_protocol

    return {
        "target_discovery": Scenario(
            key="target_discovery",
            label="Effector-target discovery",
            template_id="downstream_effector_target_discovery",
            default_task=(
                "Discover the unreported downstream effector target of the anchor protein in the disease: "
                "identify the signal-transducing membrane protein through which it acts, ranked by "
                "multi-dimensional evidence and supported by a wet-lab validation plan."
            ),
            stages=_target_discovery.STAGE_PROGRAMS,
            audit=None,  # built-in audit in CriticAgent
            report=None,  # built-in report in mochi.report
        ),
        "enzyme_design": Scenario(
            key="enzyme_design",
            label="Enzyme activity engineering",
            template_id="enzyme_activity_engineering",
            default_task=(
                "Design a focused single-point mutant library for the enzyme, rank variants by predicted "
                "activity gain and stability risk, and validate the ranking against published round-2 "
                "experimental data."
            ),
            stages=enzyme_design.STAGES,
            stage_names=["Enzyme profile", "Candidate enumeration", "Ranking", "Library selection"],
            audit=enzyme_design.audit,
            report=enzyme_design.render,
        ),
        "retrosynthesis": Scenario(
            key="retrosynthesis",
            label="Multi-step retrosynthesis planning",
            template_id="multi_step_retrosynthesis",
            default_task=(
                "Plan a shortest, chemically plausible multi-step synthesis of the target molecule from "
                "commercially available building blocks and report the route with per-step confidence."
            ),
            stages=retrosynthesis.STAGES,
            stage_names=["Target analysis", "Disconnection enumeration", "Multi-step search", "Route ranking"],
            audit=retrosynthesis.audit,
            report=retrosynthesis.render,
        ),
        "sdl_protocol": Scenario(
            key="sdl_protocol",
            label="Protocol to SDL instruction compiler",
            template_id="protocol_to_sdl_compiler",
            default_task=(
                "Compile a natural-language wet-lab protocol into a validated, machine-executable "
                "self-driving-laboratory instruction program, catch unsafe or infeasible steps, and "
                "simulate the execution timeline."
            ),
            stages=sdl_protocol.STAGES,
            stage_names=["Protocol ingestion", "SDL compilation", "Validation and repair", "Simulation"],
            audit=sdl_protocol.audit,
            report=sdl_protocol.render,
        ),
    }


SCENARIOS: dict[str, Scenario] = {}


def _registry() -> dict[str, Scenario]:
    global SCENARIOS
    if not SCENARIOS:
        SCENARIOS = _load()
    return SCENARIOS


def get(key: str) -> Scenario:
    reg = _registry()
    if key not in reg:
        raise KeyError(f"unknown scenario '{key}'; available: {sorted(reg)}")
    return reg[key]


def list_scenarios() -> list[dict]:
    return [
        {"key": s.key, "label": s.label, "template": s.template_id, "stages": sorted(s.stages)}
        for s in _registry().values()
    ]
