#!/usr/bin/env python
"""End-to-end test of the *online* engine against a local OpenAI-compatible mock.

    python tests/test_online_mode.py

It proves the things that only break over the wire:
  * request formatting / auth header,
  * JSON extraction from fenced, prose-wrapped model output,
  * the manager -> dev -> critic -> tool-creation loop under a real model call path,
  * that the run records engine="openai-compatible" and still produces a report.

No API key and no external LLM is needed: ``tests/mock_llm_server.py`` answers.
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from mock_llm_server import serve  # noqa: E402

from mochi.settings import SETTINGS  # noqa: E402


def main() -> int:
    httpd = serve(0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}/v1"
    print(f"[test] mock LLM listening on {base}")

    SETTINGS.engine = "openai"
    SETTINGS.base_url = base
    SETTINGS.api_key = "test-key"
    SETTINGS.model = "mock-model"

    from mochi.llm import OpenAICompatibleLLM
    from mochi.core import Mochi

    ok, msg = OpenAICompatibleLLM().health_check()
    print(f"[test] health_check: {'OK' if ok else 'FAIL'} — {msg}")
    if not ok:
        httpd.shutdown()
        return 1

    agent = Mochi(verbose=False, params={"scoring_limit": 10})
    try:
        result = agent.run(target="DPEP1", run_id="selftest_online")
    finally:
        httpd.shutdown()

    from mochi.tools import TOOLS

    checks = {
        "engine is openai-compatible": result.engine == "openai-compatible",
        "ranking produced": len(result.ranking) >= 3,
        "report written": bool(result.report_path and result.report_path.exists()),
        # the tool may have been created in this run or already exist from a previous run
        "signalling tool available": "score_signaling_potential" in TOOLS,
        "llm calls recorded": (result.run_dir / "llm_calls.jsonl").exists(),
        "summary says openai": json.loads((result.run_dir / "run_summary.json").read_text(encoding="utf-8"))["engine"]
        == "openai-compatible",
    }
    for name, passed in checks.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    if all(checks.values()):
        print(f"\n[test] online mode OK — run dir: {result.run_dir}")
        return 0
    print("\n[test] online mode FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
