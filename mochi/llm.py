"""LLM transport layer.

The framework only needs one primitive: ``complete(kind, system, user, context,
schema) -> LLMResult``.  Two backends implement it:

* :class:`OpenAICompatibleLLM` — any OpenAI-style ``/chat/completions`` server
  (DeepSeek, OpenRouter, vLLM, Ollama, LM Studio, ...).  Used as soon as an API
  key is present.
* :class:`~mochi.offline.DeterministicEngine` — a rule-based reference
  engine that produces schema-valid agent decisions from the *real* tool
  outputs, so the whole multi-agent workflow can be executed and audited with
  no key at all.  It is deliberately transparent: every artefact it produces is
  tagged ``engine=offline``.

Keeping the transport this thin is what makes the agent code portable: the
manager / dev / critic / tool-creation classes never touch HTTP for the LLM.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

from .settings import SETTINGS


@dataclass
class LLMResult:
    text: str
    data: Any = None
    engine: str = "unknown"
    model: str = ""
    usage: dict = field(default_factory=dict)
    latency_s: float = 0.0

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.text


def extract_json(text: str) -> Any:
    """Best-effort JSON extraction from an LLM answer (handles fences/prose)."""
    if not text:
        return None
    fences = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S)
    candidates = fences + [text]
    for cand in candidates:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except Exception:
            pass
        start = min([i for i in (cand.find("{"), cand.find("[")) if i >= 0], default=-1)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(cand)):
            if cand[i] in "{[":
                depth += 1
            elif cand[i] in "}]":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(cand[start : i + 1])
                    except Exception:
                        break
    return None


class BaseLLM:
    name = "base"
    model = ""

    def complete(
        self,
        *,
        kind: str,
        system: str,
        user: str,
        context: dict | None = None,
        schema: dict | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:  # pragma: no cover - interface
        raise NotImplementedError


class OpenAICompatibleLLM(BaseLLM):
    """Thin, dependency-free client for OpenAI-compatible chat endpoints."""

    name = "openai-compatible"

    def __init__(
        self,
        model: str | None = None,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.model = model or SETTINGS.model
        self.base_url = (base_url or SETTINGS.base_url).rstrip("/")
        self.api_key = api_key or SETTINGS.api_key
        self.timeout = timeout or SETTINGS.request_timeout
        self._session = requests.Session()
        self.calls: list[dict] = []

    # -- public API --------------------------------------------------------
    def complete(
        self,
        *,
        kind: str,
        system: str,
        user: str,
        context: dict | None = None,
        schema: dict | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMResult:
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": SETTINGS.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or SETTINGS.max_tokens,
        }
        if schema is not None:
            payload["response_format"] = {"type": "json_object"}

        t0 = time.time()
        last_err = None
        for attempt in range(3):
            try:
                resp = self._session.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=self.timeout,
                )
                if resp.status_code >= 400:
                    raise RuntimeError(f"LLM HTTP {resp.status_code}: {resp.text[:400]}")
                body = resp.json()
                text = body["choices"][0]["message"]["content"] or ""
                usage = body.get("usage", {})
                data = extract_json(text) if schema is not None else None
                rec = {
                    "kind": kind,
                    "model": self.model,
                    "latency_s": round(time.time() - t0, 2),
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                }
                self.calls.append(rec)
                return LLMResult(
                    text=text,
                    data=data,
                    engine=self.name,
                    model=self.model,
                    usage=usage,
                    latency_s=round(time.time() - t0, 2),
                )
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                time.sleep(2 * (attempt + 1))
        raise RuntimeError(f"LLM call '{kind}' failed: {last_err}")

    # -- diagnostics -------------------------------------------------------
    def health_check(self) -> tuple[bool, str]:
        """One tiny round-trip so ``mochi doctor`` can prove the wiring."""
        t0 = time.time()
        try:
            resp = self._session.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
                    "max_tokens": 8,
                    "temperature": 0,
                },
                timeout=min(60, self.timeout),
            )
        except Exception as exc:  # noqa: BLE001
            return False, f"cannot reach {self.base_url}: {type(exc).__name__}: {exc}"
        dt = time.time() - t0
        if resp.status_code == 401 or resp.status_code == 403:
            return False, (f"HTTP {resp.status_code}: the API key was rejected. "
                           f"Check MOCHI_API_KEY / that it matches {self.base_url}.")
        if resp.status_code == 404:
            return False, (f"HTTP 404 at {self.base_url}/chat/completions — base_url is probably wrong "
                           f"(DeepSeek: https://api.deepseek.com/v1).")
        if resp.status_code >= 400:
            return False, f"HTTP {resp.status_code}: {resp.text[:300]}"
        try:
            body = resp.json()
            text = body["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            return False, f"unexpected response shape: {resp.text[:300]}"
        return True, f"ok in {dt:.1f}s | model={self.model} | reply={str(text).strip()[:40]!r}"


def get_llm(force_offline: bool = False) -> BaseLLM:
    """Return the best available backend for the current configuration."""
    if force_offline or SETTINGS.resolve_engine() == "offline":
        from .offline import DeterministicEngine

        return DeterministicEngine()
    return OpenAICompatibleLLM()


class AgentLLM:
    """Wrapper that records every agent decision into the run transcript."""

    def __init__(self, llm: BaseLLM, recorder: Callable[[dict], None] | None = None) -> None:
        self._llm = llm
        self._recorder = recorder
        self.calls: list[dict] = []

    @property
    def name(self) -> str:
        return self._llm.name

    @property
    def model(self) -> str:
        return self._llm.model

    def complete(self, **kwargs) -> LLMResult:
        res = self._llm.complete(**kwargs)
        user_msg = kwargs.get("user") or ""
        rec = {
            "kind": kwargs.get("kind"),
            "engine": res.engine,
            "model": res.model,
            "latency_s": res.latency_s,
            "usage": res.usage,
            # the exact instruction sent to the model (truncated) — use this to verify
            # that a user-supplied --task really reached the manager prompt
            "user_preview": user_msg[:4000],
            "output_preview": res.text[:600],
            "data_preview": json.dumps(res.data, ensure_ascii=False)[:1200] if res.data is not None else None,
        }
        self.calls.append(rec)
        if self._recorder:
            self._recorder(rec)
        return res
