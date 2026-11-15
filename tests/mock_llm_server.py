#!/usr/bin/env python
"""A tiny OpenAI-compatible mock server used to prove the *online* code path.

Why: the project must work in two modes.  Offline mode is exercised by
``tests/run_checks.py``; this mock lets ``tests/test_online_mode.py`` drive the
exact same agents through HTTP (request formatting, JSON extraction, retries,
transcript recording) without needing a real API key.

The mock answers the four agent contracts with schema-valid JSON, deliberately
wrapped in prose + a fenced block so that :func:`mochi.llm.extract_json`
is tested too.

    python tests/mock_llm_server.py --port 8765
    # then:  set MOCHI_BASE_URL=http://127.0.0.1:8765/v1
    #        set MOCHI_API_KEY=test-key
    #        python cases/dpep1_crc_effector_target.py --engine openai
"""

from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PLAN_STAGES = [
    ("Profile construction", "Build the anchor profile and derive the topological constraint."),
    ("Candidate generation", "Nominate candidates from PPI, co-expression, pathway co-annotation and literature."),
    ("Signalling competence", "Score candidates for intrinsic signal-transduction capability."),
    ("Multi-evidence scoring", "Rank candidates on six dimensions with calibrated weights."),
]

TOOL_REQUEST = {
    "name": "score_signaling_potential",
    "purpose": "Quantify whether a candidate protein can transduce a signal by itself.",
    "why_existing_tools_fail": "No tool converts topology + domains into a calibrated competence score.",
    "inputs": ["genes: list[str]"],
    "outputs": ["signaling_score"],
    "algorithm": "Weighted UniProt topology + Pfam family + annotation + localisation with hard caps.",
    "validation": {
        "positive_controls": ["LRP6", "FZD1", "EGFR"],
        "negative_controls": ["DPEP1", "ALB"],
        "acceptance": "positives >= 0.60, negatives <= 0.35",
    },
}


def _last_user_text(body: dict) -> str:
    msgs = body.get("messages") or []
    for m in reversed(msgs):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


def _answer(user: str, system: str) -> str:
    text = user + "\n" + system
    if "Plan the investigation" in text or "Plan the investigation" in text:
        steps = "\n".join(
            f"{i}. **{name}** — {goal}\n   tools: n/a" for i, (name, goal) in enumerate(PLAN_STAGES, 1)
        )
        return (
            "Thought: I will retrieve the template and plan four stages.\n\n```json\n"
            + json.dumps(
                {
                    "reasoning": "The anchor cannot transduce a signal, so candidates must be scored for "
                                 "signalling competence before any ranking is attempted.",
                    "target": "DPEP1",
                    "disease": "colorectal cancer",
                    "template_id": "downstream_effector_target_discovery",
                    "stages": [
                        {"id": f"stage_{i + 1}", "name": name, "goal": goal, "tools": [],
                         "deliverable": "table", "success_criteria": ["critic audit passes"]}
                        for i, (name, goal) in enumerate(PLAN_STAGES)
                    ],
                    "hypotheses": ["DPEP1 acts through a signalling-competent membrane partner."],
                    "risks": ["public PPI data are sparse for GPI-anchored proteins"],
                    "expected_failure_modes": ["no candidate passes the competence threshold"],
                },
                indent=1,
            )
            + "\n```\n"
        )
    if "Plan the analysis for one stage" in text:
        return "```json\n" + json.dumps(
            {"steps": ["run the stage program"], "tools": [], "params": {}, "expected_outputs": ["tables"]}
        ) + "\n```"
    if "Review this completed stage" in text:
        needs_tool = "Tool Ocean can test whether a candidate can transduce a signal" in text
        payload = {
            "stage": "stage_1",
            "verdict": "evolve" if needs_tool else "accept",
            "scores": {"tool_adequacy": 2 if needs_tool else 4, "evidence_sufficiency": 4,
                       "directionality": 4, "statistical_validity": 4, "biological_plausibility": 4},
            "gaps": ["missing signalling-competence tool"] if needs_tool else [],
            "evidence_checks": [],
            "tool_requests": [TOOL_REQUEST] if needs_tool else [],
            "weight_adjustments": None,
            "reasoning": "tool creation required" if needs_tool else "evidence is sufficient",
        }
        return "Analysis:\n\n```json\n" + json.dumps(payload) + "\n```"
    if "Calibrate the six evidence weights" in text:
        return json.dumps(
            {
                "weights": {"association": 0.24, "signaling": 0.22, "crc_evidence": 0.20,
                            "pathway_centrality": 0.10, "novelty": 0.10, "druggability": 0.14},
                "reasoning": "biological core first, druggability last",
            }
        )
    if "Write the final scientific conclusion" in text:
        return "The top candidate is prioritised on signalling competence and disease evidence; the decisive " \
               "test is a reciprocal co-immunoprecipitation followed by epistasis."
    if "Design the tool described below" in text:
        return json.dumps(
            {
                "tool_name": "score_signaling_potential",
                "algorithm": "topology + pfam family + annotation + localisation",
                "implementation_notes": "blueprint",
                "validation_plan": TOOL_REQUEST["validation"],
            }
        )
    return "ok"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # silence the default stderr logging
        pass

    def _send(self, code: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path.rstrip("/").endswith("/models"):
            return self._send(200, {"object": "list", "data": [{"id": "mock-model", "object": "model"}]})
        self._send(404, {"error": "not found"})

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw)
        except Exception:  # noqa: BLE001
            return self._send(400, {"error": "bad json"})
        auth = self.headers.get("Authorization") or ""
        if not auth.startswith("Bearer "):
            return self._send(401, {"error": {"message": "Missing Authorization header"}})
        user = _last_user_text(body)
        system = next((m.get("content") or "" for m in body.get("messages", []) if m.get("role") == "system"), "")
        content = _answer(user, system)
        self._send(
            200,
            {
                "id": "chatcmpl-mock",
                "object": "chat.completion",
                "model": body.get("model", "mock-model"),
                "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                             "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(user) // 4, "completion_tokens": len(content) // 4},
            },
        )


def serve(port: int = 0) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    return httpd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()
    httpd = serve(args.port)
    print(f"mock OpenAI-compatible server on http://127.0.0.1:{httpd.server_address[1]}/v1")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
