"""Three-tier memory, mirroring MOCHI.

Tier 1 - KnowledgeMemory  : reasoning templates (see :mod:`mochi.knowledge`).
Tier 2 - CollaborationMemory : the shared blackboard the manager / dev / critic
          write to while a run is in progress (artefacts, decisions, critiques).
Tier 3 - SessionMemory    : append-only transcript of every agent turn, persisted
          as JSONL so a run can be replayed and audited.

``AutoMemory`` is the lightweight performance tracker MOCHI uses to remember how
long each agent takes and whether it succeeded.
"""

from __future__ import annotations

import json
import time
from collections import deque
from pathlib import Path
from typing import Any


class SessionMemory:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else None
        self.turns: list[dict] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, role: str, kind: str, content: Any, meta: dict | None = None) -> dict:
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "role": role,
            "kind": kind,
            "content": content if isinstance(content, (str, int, float, bool, list, dict, type(None))) else str(content),
            "meta": meta or {},
        }
        self.turns.append(rec)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec

    def context(self, n: int = 8) -> list[dict]:
        return self.turns[-n:]


class CollaborationMemory:
    """Shared blackboard: key/value facts any agent can read or write."""

    def __init__(self) -> None:
        self.facts: dict[str, Any] = {}
        self.notes: list[dict] = []

    def put(self, key: str, value: Any, author: str = "manager") -> None:
        self.facts[key] = value
        self.notes.append({"ts": time.strftime("%H:%M:%S"), "author": author, "key": key})

    def get(self, key: str, default: Any = None) -> Any:
        return self.facts.get(key, default)

    def add_note(self, author: str, text: str) -> None:
        self.notes.append({"ts": time.strftime("%H:%M:%S"), "author": author, "note": text})

    def summary(self, max_chars: int = 4000) -> str:
        keys = ", ".join(sorted(self.facts))
        notes = "\n".join(f"- [{n['author']}] {n.get('note', n.get('key', ''))}" for n in self.notes[-12:])
        return f"Blackboard keys: {keys}\nRecent notes:\n{notes}"[:max_chars]


class AutoMemory:
    def __init__(self, maxlen: int = 100) -> None:
        self.history: deque[dict] = deque(maxlen=maxlen)

    def record(self, agent: str, task: str, success: bool, duration: float, detail: str = "") -> None:
        self.history.append(
            {
                "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
                "agent": agent,
                "task": task[:200],
                "success": success,
                "duration_s": round(duration, 2),
                "detail": detail[:300],
            }
        )

    def stats(self) -> dict:
        by_agent: dict[str, dict] = {}
        for h in self.history:
            s = by_agent.setdefault(h["agent"], {"n": 0, "ok": 0, "time": 0.0})
            s["n"] += 1
            s["ok"] += int(h["success"])
            s["time"] += h["duration_s"]
        return {
            "n_tasks": len(self.history),
            "by_agent": {
                k: {"n": v["n"], "success_rate": round(v["ok"] / v["n"], 2), "avg_s": round(v["time"] / v["n"], 1)}
                for k, v in by_agent.items()
            },
        }


class MemoryManager:
    def __init__(self, knowledge, session_path: Path | None = None) -> None:
        self.knowledge = knowledge
        self.session = SessionMemory(session_path)
        self.collaboration = CollaborationMemory()
        self.auto = AutoMemory()

    def summary(self) -> dict:
        return {
            "templates": self.knowledge.status() if self.knowledge else {},
            "session_turns": len(self.session.turns),
            "blackboard_keys": sorted(self.collaboration.facts),
            "performance": self.auto.stats(),
        }
