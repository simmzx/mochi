"""Reasoning-template (skill) library, modelled on MOCHI's ``skills/`` system.

Each template is one YAML file describing a reusable multi-stage scientific
workflow: steps, required tools, expected agents, quality metrics and provenance.
Retrieval is TF-IDF over the template text (MOCHI also uses TF-IDF, not
embeddings), combined with historical success rate and recency:

    final = 0.5 * cosine_similarity + 0.3 * success_rate + 0.2 * recency

Templates can be ``prebuilt`` (written by a human, versioned in the repo) or
``auto_generated`` (summarised from a successful run by the manager, which is the
"self-evolution" half of MOCHI's design).
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from . import stats

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "for", "to", "in", "on", "with", "by", "from", "is",
    "are", "be", "as", "at", "that", "this", "it", "we", "our", "which", "using", "use", "how",
    "what", "can", "into", "than", "then", "their", "its", "not", "no", "do", "does", "has",
}


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]+", (text or "").lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


@dataclass
class Template:
    skill_id: str
    name: str
    domain: str
    description: str
    workflow: list[dict] = field(default_factory=list)
    tools_required: list[dict] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    applicable_queries: list[str] = field(default_factory=list)
    quality_metrics: dict = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)
    status: str = "active"
    version: str = "1.0.0"
    path: str = ""

    # ---- text used for retrieval ----------------------------------------
    def retrieval_text(self) -> str:
        parts = [self.name, self.description, " ".join(self.tags), " ".join(self.applicable_queries)]
        for step in self.workflow:
            parts.append(" ".join(str(step.get(k, "")) for k in ("step", "action", "description")))
        parts += [t.get("tool_id", "") for t in self.tools_required]
        return " ".join(parts)

    @property
    def success_rate(self) -> float:
        q = self.quality_metrics or {}
        s, f = q.get("success_count", 0), q.get("failure_count", 0)
        return s / (s + f) if (s + f) else 0.5

    def recency(self) -> float:
        ts = (self.quality_metrics or {}).get("last_used") or (self.provenance or {}).get("created_at")
        if not ts:
            return 0.5
        try:
            t = time.mktime(time.strptime(str(ts)[:19], "%Y-%m-%d %H:%M:%S"))
        except Exception:
            return 0.5
        return math.exp(-max(0.0, time.time() - t) / (90 * 86400))

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.__dict__ | {"path": ""}, sort_keys=False, allow_unicode=True)

    def prompt_block(self) -> str:
        lines = [f"### Template: {self.name}  (id={self.skill_id}, v{self.version}, domain={self.domain})"]
        lines.append(f"Description: {self.description}")
        for i, step in enumerate(self.workflow, 1):
            tools = ", ".join(step.get("tools_required", []) or [])
            lines.append(
                f"{i}. {step.get('action', step.get('step', ''))} — {step.get('description', '')}"
                + (f" [tools: {tools}]" if tools else "")
                + (f" [agent: {step.get('agent')}]" if step.get("agent") else "")
            )
        q = self.quality_metrics or {}
        lines.append(
            f"Quality: success={self.success_rate:.2f}, runs={q.get('success_count', 0) + q.get('failure_count', 0)}"
        )
        return "\n".join(lines)


class TemplateLibrary:
    """Loads, retrieves and stores reasoning templates."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.prebuilt_dir = self.root / "prebuilt"
        self.auto_dir = self.root / "auto_generated"
        self.auto_dir.mkdir(parents=True, exist_ok=True)
        self.templates: list[Template] = []
        self.reload()

    # ---- loading ---------------------------------------------------------
    def reload(self) -> None:
        self.templates = []
        for d in (self.prebuilt_dir, self.auto_dir):
            if not d.exists():
                continue
            for path in sorted(d.glob("*.yaml")):
                try:
                    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                except Exception:
                    continue
                self.templates.append(self._from_dict(data, str(path)))
        self.rebuild_index()

    def _from_dict(self, data: dict, path: str) -> Template:
        return Template(
            skill_id=data.get("skill_id") or Path(path).stem,
            name=data.get("name", ""),
            domain=data.get("domain", "general"),
            description=data.get("description", ""),
            workflow=data.get("workflow", []) or [],
            tools_required=data.get("tools_required", []) or [],
            tags=data.get("tags", []) or [],
            applicable_queries=data.get("applicable_queries", []) or [],
            quality_metrics=data.get("quality_metrics", {}) or {},
            provenance=data.get("provenance", {}) or {},
            status=data.get("status", "active"),
            version=data.get("version", "1.0.0"),
            path=path,
        )

    # ---- TF-IDF index ----------------------------------------------------
    def rebuild_index(self) -> None:
        docs = [t.retrieval_text() for t in self.templates]
        self._tokens = [tokenize(d) for d in docs]
        df: dict[str, int] = {}
        for toks in self._tokens:
            for w in set(toks):
                df[w] = df.get(w, 0) + 1
        n = max(1, len(docs))
        self._idf = {w: math.log((n + 1) / (c + 1)) + 1.0 for w, c in df.items()}
        self._vectors = [self._vectorize(t) for t in self._tokens]

    def _vectorize(self, tokens: list[str]) -> dict[str, float]:
        tf: dict[str, float] = {}
        for w in tokens:
            tf[w] = tf.get(w, 0.0) + 1.0
        vec = {w: (1 + math.log(c)) * self._idf.get(w, 1.0) for w, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {w: v / norm for w, v in vec.items()}

    def _cosine(self, a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(v * b.get(w, 0.0) for w, v in a.items())

    # ---- retrieval -------------------------------------------------------
    def retrieve(self, query: str, top_k: int = 3, min_score: float = 0.05) -> list[dict]:
        qv = self._vectorize(tokenize(query))
        scored = []
        for t, vec in zip(self.templates, self._vectors):
            if t.status not in ("active", "experimental"):
                continue
            sim = self._cosine(qv, vec)
            # tag / glob bonus, like MOCHI's stage-1 match
            text = (query or "").lower()
            if any(tag.lower() in text for tag in t.tags):
                sim = max(sim, 0.3)
            score = 0.5 * sim + 0.3 * t.success_rate + 0.2 * t.recency()
            if sim >= min_score or score >= 0.35:
                scored.append((score, sim, t))
        scored.sort(key=lambda x: -x[0])
        return [
            {
                "skill_id": t.skill_id,
                "name": t.name,
                "score": round(score, 4),
                "similarity": round(sim, 4),
                "success_rate": round(t.success_rate, 3),
                "template": t,
            }
            for score, sim, t in scored[:top_k]
        ]

    def get(self, skill_id: str) -> Template | None:
        return next((t for t in self.templates if t.skill_id == skill_id), None)

    # ---- feedback / evolution -------------------------------------------
    def record_outcome(self, skill_id: str, success: bool, score: float | None = None) -> None:
        t = self.get(skill_id)
        if t is None:
            return
        q = t.quality_metrics
        q["success_count" if success else "failure_count"] = q.get("success_count" if success else "failure_count", 0) + 1
        q["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
        if score is not None:
            prev = q.get("avg_critic_score", score)
            runs = q.get("success_count", 0) + q.get("failure_count", 0)
            q["avg_critic_score"] = round(prev + (score - prev) / max(1, runs), 3)
        if t.path:
            path = Path(t.path)
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            data["quality_metrics"] = q
            path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def save_template(self, template: Template, overwrite: bool = False,
                      dedup_threshold: float = 0.85) -> Path:
        """Persist a template, updating an existing near-duplicate instead of duplicating it.

        Mirrors MOCHI's dedup rule: if the new workflow is >0.85 similar to an
        existing template, merge the evidence (counts, tools, changelog) rather
        than creating a near-identical skill every run.
        """
        new_vec = self._vectorize(tokenize(template.retrieval_text()))
        best, best_sim = None, 0.0
        for t, vec in zip(self.templates, self._vectors):
            sim = self._cosine(new_vec, vec)
            if sim > best_sim:
                best, best_sim = t, sim
        if best is not None and best_sim >= dedup_threshold and not overwrite:
            q = best.quality_metrics or {}
            q["success_count"] = q.get("success_count", 0) + 1
            q["last_used"] = time.strftime("%Y-%m-%d %H:%M:%S")
            q["avg_completion_time_sec"] = template.quality_metrics.get("avg_completion_time_sec")
            best.quality_metrics = q
            tools = {t.get("tool_id") for t in best.tools_required if isinstance(t, dict)}
            for t in template.tools_required:
                if isinstance(t, dict) and t.get("tool_id") not in tools:
                    best.tools_required.append({**t, "optional": True})
            prov = best.provenance or {}
            prov.setdefault("changelog", []).append(
                {"version": best.version, "date": q["last_used"], "changes": "reused by a successful run"}
            )
            best.provenance = prov
            if best.path:
                data = yaml.safe_load(Path(best.path).read_text(encoding="utf-8")) or {}
                data["quality_metrics"] = q
                data["tools_required"] = best.tools_required
                data["provenance"] = prov
                Path(best.path).write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
            return Path(best.path)

        self.auto_dir.mkdir(parents=True, exist_ok=True)
        path = self.auto_dir / f"{template.skill_id}.yaml"
        if path.exists() and not overwrite:
            template.skill_id = f"{template.skill_id}_{int(time.time())}"
            path = self.auto_dir / f"{template.skill_id}.yaml"
        template.path = str(path)
        path.write_text(template.to_yaml(), encoding="utf-8")
        self.templates.append(template)
        self.rebuild_index()
        return path

    def status(self) -> dict:
        return {
            "n_templates": len(self.templates),
            "prebuilt": len([t for t in self.templates if "prebuilt" in (t.path or "")]),
            "auto_generated": len([t for t in self.templates if "auto_generated" in (t.path or "")]),
            "ids": [t.skill_id for t in self.templates],
        }
