#!/usr/bin/env python
"""Case study: discover the downstream effector target of DPEP1 in colorectal cancer.

Usage
-----
    python cases/dpep1_crc_effector_target.py                 # offline engine, cached data
    python cases/dpep1_crc_effector_target.py --fresh         # ignore the HTTP cache
    python cases/dpep1_crc_effector_target.py --engine openai # use a real LLM (needs a key)
    python cases/dpep1_crc_effector_target.py --target CEACAM5 --disease "colorectal cancer"

The script is deliberately thin: all orchestration lives in ``mochi``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mochi import Mochi  # noqa: E402
from mochi.settings import SETTINGS  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="MOCHI target-discovery case study")
    ap.add_argument("--target", default="DPEP1", help="anchor gene symbol (default: DPEP1)")
    ap.add_argument("--disease", default="colorectal cancer")
    ap.add_argument("--disease-id", default=SETTINGS.disease_efo, help="EFO/MONDO id")
    ap.add_argument("--engine", choices=["auto", "offline", "openai"], default="auto")
    ap.add_argument("--fresh", action="store_true", help="clear the HTTP cache before running")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--params", default="", help="JSON dict of parameter overrides")
    ap.add_argument("--seed-genes", default="",
                    help="hypothesis genes to score in addition to data-driven candidates, e.g. LRP6,FZD1")
    ap.add_argument("--expect", default="", help="known answer(s) for a hindcast check, e.g. LRP6")
    ap.add_argument("--task", default="",
                    help="free-text research instruction sent to the manager (default: auto-generated from target/disease)")
    args = ap.parse_args()

    if args.fresh:
        cache = ROOT / "cache" / "http"
        if cache.exists():
            shutil.rmtree(cache, ignore_errors=True)
        print("[case] HTTP cache cleared")

    SETTINGS.engine = args.engine
    SETTINGS.validate()
    print(f"[case] engine: {SETTINGS.engine_banner()}")
    params = json.loads(args.params) if args.params else {}
    if args.seed_genes:
        params["seed_genes"] = [g.strip() for g in args.seed_genes.split(",") if g.strip()]
    if args.expect:
        params["expect_genes"] = [g.strip() for g in args.expect.split(",") if g.strip()]

    agent = Mochi(verbose=not args.quiet, params=params)
    result = agent.run(target=args.target, disease=args.disease, disease_id=args.disease_id,
                       task=args.task or None)

    print("\n" + "=" * 78)
    print("RESULT")
    print("=" * 78)
    print(json.dumps(result.to_dict(), indent=1, ensure_ascii=False)[:4000])
    print(f"\nreport : {result.report_path}")
    print(f"summary: {result.summary_path}")
    print(f"files  : {result.run_dir}")
    return 0 if result.ranking else 1


if __name__ == "__main__":
    raise SystemExit(main())
