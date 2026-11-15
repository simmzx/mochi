"""Base agent: prompt rendering, LLM calls, transcript + memory plumbing."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import yaml

from ..knowledge import Template
from ..memory import MemoryManager


def load_prompt(name: str, prompts_dir: Path) -> str:
    path = Path(prompts_dir) / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return (data.get("system_prompt") or "").strip()


def render(text: str, **slots: Any) -> str:
    """Tiny ``{slot}`` renderer (no jinja dependency)."""

    def repl(match: re.Match) -> str:
        key = match.group(1)
        if key not in slots:
            return match.group(0)
        value = slots[key]
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, indent=1)[:12000]
        return str(value)

    return re.sub(r"\{([a-z_][a-z0-9_]*)\}", repl, text)


class BaseAgent:
    name = "base"
    role = "base"

    def __init__(
        self,
        llm,
        memory: MemoryManager,
        prompts_dir: Path,
        run_dir: Path,
        verbose: bool = True,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.prompts_dir = Path(prompts_dir)
        self.run_dir = Path(run_dir)
        self.verbose = verbose
        self.system_prompt = ""
        self.turns: list[dict] = []
        self._t0 = time.time()

    # ---- logging ---------------------------------------------------------
    def log(self, kind: str, content: Any, meta: dict | None = None) -> None:
        rec = self.memory.session.add(self.name, kind, content, meta)
        self.turns.append(rec)
        if self.verbose:
            head = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False)
            print(f"  [{self.name}] {kind}: {head[:220]}")

    def banner(self, text: str) -> None:
        if self.verbose:
            print(f"\n{'=' * 78}\n[{self.name.upper()}] {text}\n{'=' * 78}")

    # ---- LLM -------------------------------------------------------------
    def ask(
        self,
        *,
        kind: str,
        user: str,
        context: dict | None = None,
        schema: dict | None = None,
        system_extra: str = "",
        temperature: float | None = None,
    ) -> dict:
        """Call the LLM and return a dict (falling back to raw text)."""
        system = self.system_prompt + ("\n\n" + system_extra if system_extra else "")
        res = self.llm.complete(
            kind=kind,
            system=system,
            user=user,
            context=context or {},
            schema=schema,
            temperature=temperature,
        )
        if isinstance(res.data, dict):
            return res.data
        if res.data is not None:
            return {"_raw": res.data}
        return {"_text": res.text, "_engine": res.engine}

    # ---- prompt helpers --------------------------------------------------
    def template_block(self, templates: list[dict]) -> str:
        if not templates:
            return "(no template retrieved — reason from first principles)"
        parts = []
        for i, t in enumerate(templates, 1):
            tpl: Template = t["template"]
            parts.append(f"[{i}] similarity={t['similarity']:.2f} score={t['score']:.2f}\n{tpl.prompt_block()}")
        return "\n\n".join(parts)
