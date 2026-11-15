#!/usr/bin/env python
"""Run every MOCHI scenario end-to-end.

    python cases/run_all.py --engine mock      # local OpenAI-compatible mock (no key)
    python cases/run_all.py --engine offline   # deterministic engine
    python cases/run_all.py --engine openai    # real model (needs MOCHI_API_KEY)

The mock mode starts ``tests/mock_llm_server.py`` in-process, so the whole suite runs offline
while still exercising the HTTP model path (request formatting, JSON parsing, retries, logging).
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

SCENARIOS = [
    ("target_discovery", "DPEP1", "colorectal cancer"),
    ("enzyme_design", "P68175", "strictosidine synthase"),
    ("retrosynthesis", "CCN(CC)CC(=O)Nc1c(C)cccc1C", "lidocaine"),
    ("sdl_protocol", "str_activity_assay", "STR activity assay"),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["mock", "offline", "openai"], default="mock")
    ap.add_argument("--only", default="", help="comma separated scenario keys")
    args = ap.parse_args()

    server = None
    if args.engine == "mock":
        from mock_llm_server import serve

        server = serve(0)
        port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()
        import os

        os.environ["MOCHI_ENGINE"] = "openai"
        os.environ["MOCHI_BASE_URL"] = f"http://127.0.0.1:{port}/v1"
        os.environ["MOCHI_API_KEY"] = "mock-key"
        os.environ["MOCHI_MODEL"] = "deepseek-V4.1-pro"
        print(f"[run_all] mock OpenAI server on http://127.0.0.1:{port}/v1")

    # settings are read at import time, so configure the environment before importing
    from mochi import initialize
    from mochi.settings import SETTINGS

    SETTINGS.engine = "openai" if args.engine == "mock" else args.engine
    if args.engine == "mock":
        SETTINGS.base_url = f"http://127.0.0.1:{port}/v1"
        SETTINGS.api_key = "mock-key"
        SETTINGS.model = "deepseek-V4.1-pro"

    wanted = {s.strip() for s in args.only.split(",") if s.strip()}
    rows = []
    for scenario, target, label in SCENARIOS:
        if wanted and scenario not in wanted:
            continue
        print("\n" + "=" * 78)
        print(f"[run_all] {scenario} | {target} | {label}")
        agent = initialize(verbose=False)
        res = agent.run(target=target, scenario=scenario)
        rows.append({
            "scenario": scenario,
            "target": target,
            "status": [s["status"] for s in res.stage_results],
            "elapsed_s": round(res.elapsed_s, 1),
            "report": str(res.report_path),
            "top": (res.ranking[0]["gene"] if res.ranking else None),
        })
        print(f"[run_all] done in {res.elapsed_s:.1f}s -> {res.run_dir}")

    print("\n" + "=" * 78)
    print(json.dumps(rows, indent=1, ensure_ascii=False))
    if server:
        server.shutdown()
    return 0 if all(all(s == "ok" for s in r["status"]) for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
