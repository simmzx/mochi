"""Tool Ocean package.

Importing this package registers every predefined tool in :data:`mochi.tools.registry.TOOLS`.
Dynamically created tools live in ``tools_created/`` and are loaded by
:func:`mochi.tools.registry.load_dynamic_tools`.
"""

from __future__ import annotations

from . import (  # noqa: F401  (import side effect: tool registration)
    cbioportal,
    chemistry,
    functional_annotation,
    identifiers,
    literature,
    networks,
    opentargets,
    pathways,
    protein_structure,
    retrosynthesis,
    scoring,
    sdl,
    uniprot,
)
from .registry import (  # noqa: F401
    DYNAMIC_TOOLS,
    TOOLS,
    ToolSpec,
    call_tool,
    dump_manifest,
    list_tools,
    load_dynamic_tools,
    tool,
    tool_arsenal_text,
)

__all__ = [
    "TOOLS",
    "DYNAMIC_TOOLS",
    "ToolSpec",
    "call_tool",
    "list_tools",
    "tool_arsenal_text",
    "load_dynamic_tools",
    "dump_manifest",
    "tool",
]
