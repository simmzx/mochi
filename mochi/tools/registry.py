"""Tool Ocean: the registry every agent reads from.

A tool is a plain Python function registered with :func:`tool`.  Registration
captures the metadata the manager and critic prompts need (name, category,
one-line capability, inputs) so that "what can the swarm already do?" is always
answerable without importing the implementation.

New tools created at runtime by the Tool Creation Agent are loaded from
``tools_created/*.py`` through :func:`load_dynamic_tools`, which keeps the
self-evolution loop honest: a generated tool must be importable, callable and
pass its own validation suite before it joins the ocean.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

TOOLS: dict[str, "ToolSpec"] = {}
DYNAMIC_TOOLS: dict[str, "ToolSpec"] = {}


@dataclass
class ToolSpec:
    name: str
    fn: Callable
    category: str
    description: str
    inputs: list[str] = field(default_factory=list)
    origin: str = "predefined"  # predefined | created
    meta: dict = field(default_factory=dict)

    def to_prompt(self) -> str:
        args = ", ".join(self.inputs)
        return f"- {self.name}({args}) [{self.category}] — {self.description}"

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "inputs": self.inputs,
            "origin": self.origin,
            "meta": self.meta,
        }


def tool(name: str, category: str, description: str, *, origin: str = "predefined", **meta: Any):
    """Register a function in the Tool Ocean."""

    def deco(fn: Callable) -> Callable:
        sig = inspect.signature(fn)
        inputs = [p for p in sig.parameters if p not in ("self",)]
        spec = ToolSpec(
            name=name,
            fn=fn,
            category=category,
            description=description,
            inputs=inputs,
            origin=origin,
            meta=meta,
        )
        TOOLS[name] = spec
        fn.__tool_name__ = name  # type: ignore[attr-defined]
        return fn

    return deco


def call_tool(name: str, **kwargs) -> Any:
    """Invoke a tool by name, returning a structured error instead of raising."""
    spec = TOOLS.get(name)
    if spec is None:
        return {"ok": False, "error": f"unknown tool '{name}'", "available": sorted(TOOLS)}
    try:
        return spec.fn(**kwargs)
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "tool": name,
            "traceback": traceback.format_exc(limit=3),
        }


def list_tools(category: str | None = None, origin: str | None = None) -> list[ToolSpec]:
    out = list(TOOLS.values())
    if category:
        out = [t for t in out if t.category == category]
    if origin:
        out = [t for t in out if t.origin == origin]
    return sorted(out, key=lambda t: (t.category, t.name))


def tool_arsenal_text(categories: list[str] | None = None) -> str:
    """Compact rendering of the ocean for prompts (mirrors MOCHI's TOOL ARSENAL)."""
    specs = list_tools()
    if categories:
        specs = [s for s in specs if s.category in categories]
    lines, current = [], None
    for s in specs:
        if s.category != current:
            current = s.category
            lines.append(f"\n## {current}")
        lines.append(s.to_prompt())
    return "\n".join(lines).strip()


def manifest_path(root: Path) -> Path:
    p = root / "docs" / "tool_manifest.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def dump_manifest(root: Path) -> Path:
    p = manifest_path(root)
    p.write_text(
        json.dumps([t.as_dict() for t in list_tools()], indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return p


def load_dynamic_tools(directory: Path) -> list[str]:
    """Import every ``*.py`` in ``directory`` and register the tools it declares."""
    directory = Path(directory)
    if not directory.exists():
        return []
    added: list[str] = []
    for py in sorted(directory.glob("*.py")):
        if py.name.startswith("_"):
            continue
        mod_name = f"mochi_created_{py.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            continue
        for obj in vars(module).values():
            name = getattr(obj, "__tool_name__", None)
            # only functions *defined in this file* are new tools; imported helpers
            # (e.g. query_uniprot_batch) must keep their predefined origin
            if name and name in TOOLS and getattr(obj, "__module__", "") == module.__name__:
                TOOLS[name].origin = "created"
                TOOLS[name].meta.setdefault("file", str(py))
                DYNAMIC_TOOLS[name] = TOOLS[name]
                added.append(name)
    return added
