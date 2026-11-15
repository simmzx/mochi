"""Command line interface.

    mochi run --target DPEP1 --disease "colorectal cancer"
    mochi run --target CEACAM5 --engine offline --fresh
    mochi tools            # list the Tool Ocean
    mochi templates        # list the reasoning templates
    mochi selftest         # offline sanity checks (no network)
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .settings import ENV_KEYS, SETTINGS, mask_secret, save_env


def _cmd_run(args) -> int:
    from .core import Mochi

    if args.fresh:
        cache = SETTINGS.cache_dir
        if Path(cache).exists():
            shutil.rmtree(cache, ignore_errors=True)
            print("[cli] HTTP cache cleared")
    SETTINGS.engine = args.engine
    SETTINGS.validate()
    print(f"[cli] engine: {SETTINGS.engine_banner()}")
    params = json.loads(args.params) if args.params else {}
    if getattr(args, "seed_genes", None):
        params["seed_genes"] = [g.strip() for g in args.seed_genes.split(",") if g.strip()]
    if getattr(args, "expect", None):
        params["expect_genes"] = [g.strip() for g in args.expect.split(",") if g.strip()]
    agent = Mochi(verbose=not args.quiet, params=params)
    result = agent.run(target=args.target, disease=args.disease, disease_id=args.disease_id,
                       task=getattr(args, "task", "") or None)
    print(json.dumps(result.to_dict(), indent=1, ensure_ascii=False)[:5000])
    print(f"\nreport: {result.report_path}")
    return 0 if result.ranking else 1


def _cmd_config(args) -> int:
    """Write .env so the chosen engine becomes the default for every future run."""
    updates: dict[str, str] = {}
    if args.engine:
        updates["MOCHI_ENGINE"] = args.engine
    if args.api_key:
        updates["MOCHI_API_KEY"] = args.api_key
    if args.base_url:
        updates["MOCHI_BASE_URL"] = args.base_url
    if args.model:
        updates["MOCHI_MODEL"] = args.model
    if args.temperature is not None:
        updates["MOCHI_TEMPERATURE"] = str(args.temperature)
    if not updates:
        current = {k: (mask_secret(__import__("os").getenv(k, "")) if k == "MOCHI_API_KEY" else __import__("os").getenv(k, "(unset)"))
                   for k in ENV_KEYS}
        print("[cli] current configuration (from env/.env):")
        for k, v in current.items():
            print(f"  {k:18s} = {v}")
        print(f"[cli] effective engine: {SETTINGS.engine_banner()}")
        return 0
    path = save_env(updates)
    print(f"[cli] wrote {path}")
    for k, v in updates.items():
        print(f"  {k:18s} = {mask_secret(v) if k == 'MOCHI_API_KEY' else v}")
    print("[cli] verify with: mochi doctor")
    return 0


def _cmd_doctor(args) -> int:
    """Check the LLM wiring (and optionally the biomedical endpoints)."""
    from .llm import OpenAICompatibleLLM

    if args.engine:
        SETTINGS.engine = args.engine
    resolved = SETTINGS.resolve_engine()
    print(f"[doctor] engine: {SETTINGS.engine_banner()}")
    ok_all = True
    if resolved != "openai":
        print("[doctor] offline mode: no network LLM needed.")
        print("         to test a key later: mochi doctor --engine openai")
    else:
        client = OpenAICompatibleLLM()
        ok, msg = client.health_check()
        ok_all &= ok
        print(f"[doctor] LLM: {'OK' if ok else 'FAIL'} — {msg}")
        if not ok:
            print("         hint: DeepSeek  MOCHI_BASE_URL=https://api.deepseek.com/v1  MOCHI_MODEL=deepseek-chat")
            print("               OpenRouter MOCHI_BASE_URL=https://openrouter.ai/api/v1  MOCHI_MODEL=google/gemini-3")
    if not args.skip_network:
        import requests

        checks = {
            "uniprot": "https://rest.uniprot.org/uniprotkb/search?query=gene_exact:DPEP1&format=json&size=1",
            "opentargets": "https://api.platform.opentargets.org/api/v4/graphql",
            "cbioportal": "https://www.cbioportal.org/api/studies?projection=SUMMARY",
            "pubmed": "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/einfo.fcgi",
        }
        for name, url in checks.items():
            try:
                r = requests.get(url, timeout=20)
                good = r.status_code < 500
                ok_all &= good
                print(f"[doctor] {name:12s} {'OK' if good else 'FAIL'} (HTTP {r.status_code})")
            except Exception as exc:  # noqa: BLE001
                ok_all = False
                print(f"[doctor] {name:12s} FAIL ({type(exc).__name__})")
    print("\n[doctor] result:", "PASS" if ok_all else "FAIL")
    return 0 if ok_all else 1


def _cmd_tools(args) -> int:
    from .tools import list_tools

    rows = [t.as_dict() for t in list_tools()]
    if args.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return 0
    current = None
    for r in rows:
        if r["category"] != current:
            current = r["category"]
            print(f"\n## {current}")
        print(f"  {r['name']:32s} [{r['origin']}] {r['description'][:110]}")
    print(f"\n{len(rows)} tools")
    return 0


def _cmd_templates(args) -> int:
    from .knowledge import TemplateLibrary

    lib = TemplateLibrary(SETTINGS.templates_dir)
    print(json.dumps(lib.status(), indent=1))
    for t in lib.templates:
        print(f"\n- {t.skill_id} v{t.version} [{t.status}] {t.name}\n  {t.description[:200]}")
    return 0


def _cmd_selftest(args) -> int:
    import subprocess

    script = SETTINGS.root / "tests" / "run_checks.py"
    return subprocess.call([sys.executable, str(script)])


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mochi", description="Multi-agent target discovery")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("run", help="run a target-discovery workflow")
    r.add_argument("--target", required=True)
    r.add_argument("--disease", default=SETTINGS.disease_name)
    r.add_argument("--disease-id", default=SETTINGS.disease_efo)
    r.add_argument("--engine", choices=["auto", "offline", "openai"], default="auto")
    r.add_argument("--fresh", action="store_true")
    r.add_argument("--quiet", action="store_true")
    r.add_argument("--params", default="")
    r.add_argument("--seed-genes", default="", help="extra hypothesis genes to score, e.g. LRP6,FZD1")
    r.add_argument("--expect", default="", help="known answer(s) to check, e.g. LRP6")
    r.add_argument("--task", default="", help="free-text instruction sent to the manager")
    r.set_defaults(func=_cmd_run)

    c = sub.add_parser("config", help="write .env (engine / api key / base url / model)")
    c.add_argument("--engine", choices=["auto", "offline", "openai"])
    c.add_argument("--api-key")
    c.add_argument("--base-url")
    c.add_argument("--model")
    c.add_argument("--temperature", type=float)
    c.set_defaults(func=_cmd_config)

    d = sub.add_parser("doctor", help="check the LLM wiring and the biomedical endpoints")
    d.add_argument("--engine", choices=["auto", "offline", "openai"])
    d.add_argument("--skip-network", action="store_true")
    d.set_defaults(func=_cmd_doctor)

    t = sub.add_parser("tools", help="list the Tool Ocean")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=_cmd_tools)

    s = sub.add_parser("templates", help="list reasoning templates")
    s.set_defaults(func=_cmd_templates)

    st = sub.add_parser("selftest", help="offline sanity checks")
    st.set_defaults(func=_cmd_selftest)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
