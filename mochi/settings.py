"""Runtime settings for the MOCHI agent stack.

Everything is overridable through environment variables or ``.env`` so that the
same code runs (a) fully offline with the deterministic reference engine and
(b) against any OpenAI-compatible endpoint (DeepSeek, OpenRouter, vLLM, Ollama).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_dotenv() -> None:
    """Minimal .env loader (avoids a python-dotenv dependency)."""
    for candidate in (ROOT / ".env", Path.cwd() / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()


@dataclass
class Settings:
    # ---- LLM -------------------------------------------------------------
    engine: str = field(default_factory=lambda: os.getenv("MOCHI_ENGINE", "auto"))
    model: str = field(default_factory=lambda: os.getenv("MOCHI_MODEL", "deepseek-chat"))
    base_url: str = field(
        default_factory=lambda: os.getenv("MOCHI_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or "https://api.deepseek.com/v1"
    )
    api_key: str = field(
        default_factory=lambda: os.getenv("MOCHI_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or ""
    )
    temperature: float = field(default_factory=lambda: float(os.getenv("MOCHI_TEMPERATURE", "0.2")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("MOCHI_MAX_TOKENS", "4096")))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("MOCHI_TIMEOUT", "180")))

    # ---- run control -----------------------------------------------------
    max_steps: int = field(default_factory=lambda: int(os.getenv("MOCHI_MAX_STEPS", "40")))
    max_review_rounds: int = field(default_factory=lambda: int(os.getenv("MOCHI_MAX_REVIEW_ROUNDS", "3")))
    enable_tool_creation: bool = field(
        default_factory=lambda: os.getenv("MOCHI_TOOL_CREATION", "1") not in ("0", "false", "False")
    )
    use_templates: bool = field(
        default_factory=lambda: os.getenv("MOCHI_TEMPLATES", "1") not in ("0", "false", "False")
    )

    # ---- paths -----------------------------------------------------------
    root: Path = ROOT
    outputs_dir: Path = ROOT / "outputs"
    cache_dir: Path = ROOT / "cache" / "http"
    created_tools_dir: Path = ROOT / "tools_created"
    templates_dir: Path = ROOT / "mochi" / "templates"

    # ---- disease context -------------------------------------------------
    disease_name: str = "colorectal cancer"
    disease_efo: str = "MONDO_0005575"
    cbioportal_study: str = "coadread_tcga_pan_can_atlas_2018"

    def resolve_engine(self) -> str:
        if self.engine in ("auto", ""):
            return "openai" if self.api_key else "offline"
        return self.engine

    def engine_banner(self) -> str:
        """One line describing which engine will actually run."""
        resolved = self.resolve_engine()
        if resolved == "offline":
            reason = "no API key configured" if not self.api_key else "MOCHI_ENGINE=offline"
            if self.engine not in ("auto", ""):
                reason = f"MOCHI_ENGINE={self.engine}"
            return f"offline (deterministic reference engine; {reason})"
        return f"openai-compatible | model={self.model} | base_url={self.base_url} | key={mask_secret(self.api_key)}"

    def validate(self) -> None:
        """Fail early with an actionable message instead of on the first LLM call."""
        if self.resolve_engine() != "openai":
            return
        if not self.api_key:
            raise SystemExit(
                "\n[mochi] MOCHI_ENGINE=openai but no API key was found.\n"
                "  1) run:  mochi config --api-key sk-... --base-url https://api.deepseek.com/v1 --model deepseek-chat\n"
                "     (or put MOCHI_API_KEY=... in .env, or export it in the shell)\n"
                "  2) or run without a key: python cases/dpep1_crc_effector_target.py --engine offline\n"
            )
        if self.model.lower().startswith("deepseek") and "deepseek" not in self.base_url:
            print(f"[mochi] warning: model={self.model} but base_url={self.base_url} "
                  f"(expected https://api.deepseek.com/v1)")

    def as_dict(self) -> dict:
        d = dict(self.__dict__)
        d.pop("api_key", None)
        d["api_key_present"] = bool(self.api_key)
        d["engine_resolved"] = self.resolve_engine()
        d["engine_banner"] = self.engine_banner()
        for k, v in list(d.items()):
            if isinstance(v, Path):
                d[k] = str(v)
        return d


def mask_secret(value: str, keep: int = 4) -> str:
    if not value:
        return "(none)"
    if len(value) <= keep * 2:
        return value[:2] + "***"
    return f"{value[:keep]}...{value[-keep:]}"


ENV_KEYS = ("MOCHI_ENGINE", "MOCHI_MODEL", "MOCHI_BASE_URL", "MOCHI_API_KEY", "MOCHI_TEMPERATURE")


def save_env(updates: dict[str, str], path: Path | None = None) -> Path:
    """Persist configuration into ``.env`` without disturbing unrelated lines."""
    env_path = Path(path or (ROOT / ".env"))
    existing: list[str] = []
    if env_path.exists():
        existing = env_path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    out: list[str] = []
    for line in existing:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key in updates:
            out.append(f"{key}={updates[key]}")
            seen.add(key)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    header = [
        "# MOCHI local configuration (generated by `mochi config`).",
        "# Do not commit this file.",
        "",
    ]
    if not any(l.startswith("# MOCHI local configuration") for l in out):
        out = header + out
    env_path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
    # make the change visible to the current process as well
    for key, value in updates.items():
        os.environ[key] = value
    return env_path


SETTINGS = Settings()
