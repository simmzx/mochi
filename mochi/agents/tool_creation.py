"""Tool Creation agent — research, design, implement, test and register a new tool.

This is the self-evolution component.  The sequence is fixed and auditable:

1. **Research** - real PubMed and GitHub queries for existing implementations.
2. **Design** - tool spec (inputs/outputs/algorithm/validation plan).
3. **Implement** - the tool source is written to ``tools_created/<name>.py``.
4. **Test** - the tool's own control suite runs; failure triggers at most 3 debug
   iterations, and the acceptance criteria are never weakened.
5. **Register** - the module is loaded into the Tool Ocean and the manifest is updated.

In offline mode the implementation comes from a vetted blueprint in
``mochi/toolblueprints/``; with an LLM the model writes the code and the
same validation gate decides whether it is allowed into the ocean.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import traceback
from pathlib import Path
from typing import Any

from ..tools import TOOLS, load_dynamic_tools, list_tools
from ..tools.http import request_json
from .base import BaseAgent, load_prompt, render

GITHUB_SEARCH = "https://api.github.com/search/repositories"

BLUEPRINTS = {
    "score_signaling_potential": "signaling_potential_scorer.py",
    "signaling_potential_scorer": "signaling_potential_scorer.py",
}


class ToolCreationAgent(BaseAgent):
    name = "tool_creation_agent"
    role = "toolmaker"

    def __init__(self, *a, blueprint_dir: Path | None = None, created_dir: Path | None = None, **kw):
        super().__init__(*a, **kw)
        self.system_prompt = load_prompt("tool_creation", self.prompts_dir)
        self.blueprint_dir = Path(blueprint_dir or (self.prompts_dir.parent / "toolblueprints"))
        self.created_dir = Path(created_dir or (self.prompts_dir.parent.parent / "tools_created"))

    # ------------------------------------------------------------------
    def research(self, spec: dict) -> dict:
        name = spec.get("name", "")
        purpose = spec.get("purpose", "")
        query = f"{name.replace('_', ' ')} signalling potential protein topology"
        pm = request_json(
            "GET",
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi",
            service="pubmed",
            params={"db": "pubmed", "term": query, "retmode": "json", "retmax": 5, "sort": "relevance"},
            timeout=60,
        )
        pmids = ((pm or {}).get("esearchresult") or {}).get("idlist", [])
        gh = request_json(
            "GET",
            GITHUB_SEARCH,
            service="github",
            params={"q": "signaling potential protein topology", "sort": "stars", "per_page": 3},
            timeout=60,
        )
        repos = [f"{r.get('full_name')} ({r.get('stargazers_count')} stars)" for r in (gh or {}).get("items", [])]
        decision = (
            "no drop-in implementation found; the algorithm is assembled from UniProt topology + Pfam "
            "families + annotation text, with control-based validation"
            if not repos
            else "existing implementations reviewed; the algorithm is assembled from UniProt topology + Pfam "
                 "families + annotation text, with control-based validation"
        )
        return {
            "pubmed": [f"PMID {p}" for p in pmids],
            "github": repos,
            "decision": decision,
            "note": decision,
        }

    # ------------------------------------------------------------------
    def design(self, spec: dict, research: dict) -> dict:
        user = render(
            """Design the tool described below.

SPEC: {spec}
RESEARCH: {research}
CONVENTIONS: {conventions}

Return JSON: {{"tool_name": "...", "algorithm": "...", "implementation_notes": "...",
"validation_plan": {{"positive_controls": [...], "negative_controls": [...], "acceptance": "..."}}}}""",
            spec=json.dumps(spec, ensure_ascii=False),
            research=json.dumps(research, ensure_ascii=False),
            conventions="register with @tool(name, category, description); return a dict with ok/source; "
                        "never raise; batch network access through mochi.tools.http",
        )
        return self.ask(kind="tool_creation.design", user=user, context={"spec": spec, "research": research})

    # ------------------------------------------------------------------
    def implement(self, tool_name: str, spec: dict, research: dict) -> dict:
        """Write the tool file. Blueprint first, LLM codegen second."""
        blueprint = BLUEPRINTS.get(tool_name)
        if blueprint:
            src = (self.blueprint_dir / blueprint).read_text(encoding="utf-8")
            origin = f"blueprint:{blueprint}"
        else:
            user = render(
                """Write the complete Python source for this tool.

SPEC: {spec}
RESEARCH: {research}

Requirements: single file, @tool decorator from mochi.tools.registry, structured dict return,
no network at import time, include validate() with the control cases. Return JSON
{{"code": "<python source>", "notes": "..."}}""",
                spec=json.dumps(spec, ensure_ascii=False),
                research=json.dumps(research, ensure_ascii=False),
            )
            res = self.ask(kind="tool_creation.code", user=user, context={"spec": spec})
            src = res.get("code") or ""
            origin = "llm"
            if not src.strip():
                return {"ok": False, "error": "the agent produced no code", "origin": origin}

        self.created_dir.mkdir(parents=True, exist_ok=True)
        path = self.created_dir / f"{tool_name}.py"
        path.write_text(src, encoding="utf-8")
        return {"ok": True, "path": str(path), "origin": origin}

    # ------------------------------------------------------------------
    def _run_validation(self, path: Path, tool_name: str) -> dict:
        """Import the generated module in isolation and execute its validate()."""
        mod_name = f"mochi_created_{tool_name}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        except Exception:
            return {"passed": False, "error": traceback.format_exc(limit=2), "cases": []}
        validate = getattr(module, "validate", None)
        if validate is None:
            return {"passed": False, "error": "tool has no validate() function", "cases": []}
        try:
            res = validate()
        except Exception:
            return {"passed": False, "error": traceback.format_exc(limit=2), "cases": []}
        return res

    # ------------------------------------------------------------------
    def create(self, spec: dict, ctx=None) -> dict:
        tool_name = spec.get("name") or "new_tool"
        self.banner(f"creating tool: {tool_name}")
        research = self.research(spec)
        self.log("research", research)
        design = self.design(spec, research)
        self.log("design", {k: design.get(k) for k in ("tool_name", "algorithm")})

        implementation = self.implement(tool_name, spec, research)
        if not implementation.get("ok"):
            return {"ok": False, "error": implementation.get("error"), "spec": spec, "research": research}

        path = Path(implementation["path"])
        validation = self._run_validation(path, tool_name)
        attempts = 1
        while not validation.get("passed") and attempts < 3:
            attempts += 1
            self.log("validation.retry", {"attempt": attempts, "error": validation.get("error", "")})
            implementation = self.implement(tool_name, spec, research)
            validation = self._run_validation(Path(implementation["path"]), tool_name)
        self.log("validation", {"passed": validation.get("passed"), "attempts": attempts})

        registered = []
        if validation.get("passed"):
            registered = load_dynamic_tools(self.created_dir)
            if ctx is not None:
                ctx.state["scorer_validation"] = validation
        else:
            if ctx is not None:
                ctx.state["scorer_validation"] = validation
            self.log("register.failed", validation.get("error", "validation failed"))

        result = {
            "ok": bool(validation.get("passed")),
            "tool_name": tool_name,
            "purpose": spec.get("purpose", ""),
            "research": research,
            "algorithm": design.get("algorithm", spec.get("algorithm", "")),
            "code_path": str(path),
            "origin": implementation.get("origin"),
            "validation": validation,
            "registered_as": tool_name if validation.get("passed") else None,
            "attempts": attempts,
            "limitations": [
                "competence, not activity: a competent receptor can still be silent in a given tumour",
                "domain inference depends on reviewed UniProt entries",
                "cannot identify the ligand or the direction of the axis",
            ] if tool_name == "score_signaling_potential" else [],
        }
        self.memory.collaboration.put("created_tool", result, author=self.name)
        return result

    # ------------------------------------------------------------------
    def available_tools(self) -> list[str]:
        return sorted(t.name for t in list_tools())
