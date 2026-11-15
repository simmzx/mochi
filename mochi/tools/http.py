"""HTTP layer shared by every tool in the Tool Ocean.

Two responsibilities that every MOCHI-style tool needs:

1. **Polite, cached, retrying access** to public biomedical web services.
   Results are cached on disk (``cache/http``) with a per-endpoint TTL so a
   re-run of the workflow is fast and reproducible, and so that flaky public
   APIs cannot destroy a long multi-agent run.
2. **Provenance**: every network call is recorded (url, params, status,
   latency, sha256 of payload) in ``provenance.jsonl`` of the current run.
   The final report can therefore cite exactly which records were used.
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

USER_AGENT = (
    "mochi-agent/1.0 (academic research; contact: local user) "
    "python-requests"
)

_LOCK = threading.Lock()
_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})


class HTTPError(RuntimeError):
    """Raised when a remote service keeps failing after retries."""


@dataclass
class Provenance:
    """Run-scoped provenance recorder."""

    path: Path | None = None
    records: list[dict] = field(default_factory=list)
    _fh: Any = None

    def attach(self, path: Path) -> "Provenance":
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a", encoding="utf-8")
        return self

    def log(self, record: Mapping) -> None:
        rec = dict(record)
        rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S"))
        self.records.append(rec)
        if self._fh is not None:
            with _LOCK:
                self._fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                self._fh.flush()

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def summary(self) -> dict:
        by_service: dict[str, int] = {}
        for r in self.records:
            by_service[r.get("service", "unknown")] = by_service.get(r.get("service", "unknown"), 0) + 1
        return {
            "n_calls": len(self.records),
            "by_service": by_service,
            "cache_hits": sum(1 for r in self.records if r.get("cached")),
        }


PROVENANCE = Provenance()


def configure(cache_dir: str | os.PathLike | None = None, provenance_path: str | os.PathLike | None = None) -> None:
    """Point the HTTP layer at a run directory (called by the orchestrator)."""
    global CACHE_DIR
    if cache_dir is not None:
        CACHE_DIR = Path(cache_dir)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if provenance_path is not None:
        PROVENANCE.attach(Path(provenance_path))


ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "cache" / "http"

DEFAULT_TTL = 60 * 60 * 24 * 7  # one week


def _cache_key(method: str, url: str, params: Mapping | None, data: Any) -> str:
    raw = json.dumps(
        {"m": method, "u": url, "p": dict(params or {}), "d": data}, sort_keys=True, default=str
    )
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _cache_get(key: str, ttl: int) -> Any | None:
    p = CACHE_DIR / f"{key}.json"
    if not p.exists():
        return None
    try:
        if ttl and time.time() - p.stat().st_mtime > ttl:
            return None
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _cache_put(key: str, payload: Any) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = CACHE_DIR / f"{key}.tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, CACHE_DIR / f"{key}.json")
    except Exception:
        pass


def request_json(
    method: str,
    url: str,
    *,
    service: str = "unknown",
    params: Mapping | None = None,
    json_body: Any = None,
    data: Any = None,
    headers: Mapping | None = None,
    timeout: int = 60,
    retries: int = 3,
    ttl: int | None = DEFAULT_TTL,
    allow_status: tuple[int, ...] = (200,),
    use_cache: bool = True,
) -> Any:
    """Perform a cached JSON request with retries and provenance logging."""
    key = _cache_key(method, url, params, json_body if json_body is not None else data)
    if use_cache and ttl:
        hit = _cache_get(key, ttl)
        if hit is not None:
            PROVENANCE.log(
                {
                    "service": service,
                    "method": method,
                    "url": url,
                    "params": dict(params or {}),
                    "status": hit.get("_status"),
                    "cached": True,
                    "sha256": hit.get("_sha256"),
                    "bytes": hit.get("_bytes"),
                }
            )
            return hit["payload"]

    last_err: Exception | None = None
    for attempt in range(retries):
        t0 = time.time()
        try:
            resp = _SESSION.request(
                method,
                url,
                params=params,
                json=json_body,
                data=data,
                headers=dict(headers or {}),
                timeout=timeout,
            )
            dt = time.time() - t0
            if resp.status_code not in allow_status:
                raise HTTPError(f"{service} HTTP {resp.status_code}: {resp.text[:300]}")
            payload = resp.json() if resp.content else None
            raw = resp.content or b""
            rec = {
                "_status": resp.status_code,
                "_sha256": hashlib.sha256(raw).hexdigest()[:16],
                "_bytes": len(raw),
                "payload": payload,
            }
            if use_cache and ttl:
                _cache_put(key, rec)
            PROVENANCE.log(
                {
                    "service": service,
                    "method": method,
                    "url": url,
                    "params": dict(params or {}),
                    "status": resp.status_code,
                    "cached": False,
                    "latency_s": round(dt, 2),
                    "sha256": rec["_sha256"],
                    "bytes": rec["_bytes"],
                }
            )
            return payload
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise HTTPError(f"{service} failed after {retries} attempts: {last_err}")


def request_text(
    method: str,
    url: str,
    *,
    service: str = "unknown",
    params: Mapping | None = None,
    data: Any = None,
    headers: Mapping | None = None,
    timeout: int = 60,
    retries: int = 3,
    ttl: int | None = DEFAULT_TTL,
    allow_status: tuple[int, ...] = (200,),
) -> str:
    """Same as :func:`request_json` but for plain-text endpoints (KEGG, Enrichr)."""
    key = _cache_key(method + ":text", url, params, data)
    if ttl:
        hit = _cache_get(key, ttl)
        if hit is not None:
            PROVENANCE.log({"service": service, "url": url, "status": hit.get("_status"), "cached": True})
            return hit["payload"]
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = _SESSION.request(
                method, url, params=params, data=data, headers=dict(headers or {}), timeout=timeout
            )
            if resp.status_code not in allow_status:
                raise HTTPError(f"{service} HTTP {resp.status_code}: {resp.text[:300]}")
            txt = resp.text
            if ttl:
                _cache_put(key, {"_status": resp.status_code, "payload": txt})
            PROVENANCE.log(
                {"service": service, "url": url, "status": resp.status_code, "cached": False, "bytes": len(txt)}
            )
            return txt
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.5 * (attempt + 1))
    raise HTTPError(f"{service} failed after {retries} attempts: {last_err}")


def build_url(base: str, **params: Any) -> str:
    """Small helper for readable f-string free URLs."""
    clean = {k: v for k, v in params.items() if v is not None}
    return f"{base}?{urlencode(clean)}" if clean else base
