#!/usr/bin/env python3
"""
HLF Weekly Model Drift Detection Script
========================================
Uses Ollama Cloud to probe HLF's core grammar/spec/runtime contracts weekly,
measuring whether the models' understanding of HLF semantics drifts over time.

This is NOT just a "call the LLM and hope" script — it uses structured outputs
(JSON schema enforcement) so results are machine-parseable and comparable week
over week. Drift score is computed by comparing expected vs actual classifications.

Ollama features used:
    • Structured outputs  — format: JSON schema on every probe call
    • Tiered fallback     — glm-5:cloud -> nemotron-3-super -> cogito-2.1:671b-cloud -> qwen3.5:cloud
  • Web search          — inject web_search tool to let model check for HLF
                          spec updates or known issues
  • Streaming           — default streaming with buffer protection
  • Circuit breaker     — automatic failover if any model is unavailable

Output: JSON written to stdout or --output file, consumed by the workflow.
{
  "driftScore":   0.0-1.0,  # 0 = perfect, 1 = full regression
  "status":       "OK|WARN|ALERT",
  "probes":       [...],    # detailed probe results
  "modelUsed":    "...",
  "tier":         0,        # which fallback tier was used
  "timestamp":    "ISO8601",
  "summary":      "..."
}
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).parent.parent / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from ollama_client import FallbackOrchestrator, REASONING_CHAIN
    _CLIENT_AVAILABLE = True
except ImportError:
    _CLIENT_AVAILABLE = False

# ---------------------------------------------------------------------------
# HLF semantic probe suite
# ---------------------------------------------------------------------------
# Each probe has:
#   prompt     — a question about HLF semantics/contracts
#   expected   — the correct answer (used to compute drift score)
#   weight     — how critical this contract is (higher = more drift impact)
#   category   — which part of HLF this tests

PROBES: list[dict[str, Any]] = [
    {
        "id": "P001",
        "category": "grammar",
        "weight": 2.0,
        "prompt": (
            "In the HLF (Hieroglyphic Logic Framework) language, the SET statement "
            "declares a variable. Is a SET-declared variable mutable or immutable? "
            "Answer with exactly one word: MUTABLE or IMMUTABLE."
        ),
        "expected": "IMMUTABLE",
    },
    {
        "id": "P002",
        "category": "bytecode",
        "weight": 2.0,
        "prompt": (
            "In HLF bytecode, what opcode mnemonic stores an immutable binding? "
            "Answer with exactly the opcode name: STORE or STORE_IMMUT."
        ),
        "expected": "STORE_IMMUT",
    },
    {
        "id": "P003",
        "category": "security",
        "weight": 3.0,
        "prompt": (
            "HLF's ALIGN Ledger is designed to detect security patterns before "
            "execution. Name ONE pattern it should detect: credential exposure, "
            "SSRF, shell injection, path traversal, or data exfiltration. "
            "Answer with exactly ONE of those five terms."
        ),
        "expected_set": [
            "credential exposure", "ssrf", "shell injection",
            "path traversal", "data exfiltration",
        ],
    },
    {
        "id": "P004",
        "category": "ethos",
        "weight": 1.5,
        "prompt": (
            "HLF's core ethos prioritizes one group above all others in its design. "
            "Who is the ultimate priority? Answer with exactly one word or phrase: "
            "PEOPLE, AI, or CORPORATIONS."
        ),
        "expected": "PEOPLE",
    },
    {
        "id": "P005",
        "category": "vm",
        "weight": 2.5,
        "prompt": (
            "HLF's bytecode VM uses a gas system. What happens when a program exceeds "
            "its gas budget? Answer: HALT, CONTINUE, or EXCEPTION."
        ),
        "expected": "EXCEPTION",
    },
    {
        "id": "P006",
        "category": "instinct",
        "weight": 1.5,
        "prompt": (
            "HLF's Instinct SDD lifecycle has a specific gate that uses CoVE "
            "(Chain of Verification) adversarial checking. Between which two phases "
            "does the CoVE gate operate? Answer: SPECIFY->PLAN, PLAN->EXECUTE, "
            "EXECUTE->VERIFY, or VERIFY->MERGE."
        ),
        "expected": "VERIFY->MERGE",
    },
    {
        "id": "P007",
        "category": "crypto",
        "weight": 2.0,
        "prompt": (
            "HLF's crypto stdlib uses real AES encryption (not simulated). "
            "What mode does it use? Answer: AES-256-GCM, AES-128-CBC, or XOR."
        ),
        "expected": "AES-256-GCM",
    },
]

# JSON schema for structured output — every probe must return this shape
PROBE_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The exact answer to the probe question",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence in the answer, 0.0-1.0",
        },
        "reasoning": {
            "type": "string",
            "description": "Brief reasoning (1-2 sentences)",
        },
    },
    "required": ["answer", "confidence", "reasoning"],
}

SYSTEM_PROMPT = """\
You are an expert on the HLF (Hieroglyphic Logic Framework) MCP server and language specification.
HLF is a formal AI orchestration language with a 5-pass LALR(1) compiler, bytecode VM with gas
metering, zero-trust security (ALIGN Ledger), and a people-first ethos.

Answer ALL questions based strictly on the HLF specification. Be precise and use the exact
terminology of the specification. Your answers will be used to detect specification drift.
Always respond in the JSON format requested, with an "answer", "confidence", and "reasoning" field.
"""


def _check_probe(probe: dict[str, Any], answer: str) -> bool:
    """Returns True if the model's answer matches the expected answer.
    Uses exact word matching (after normalisation) to avoid false positives
    from substring containment (e.g. 'SSRF_ATTACK' matching 'SSRF').
    """
    import re
    ans_norm = re.sub(r"[^A-Z0-9_>]", "", answer.strip().upper())
    expected = probe.get("expected", "")
    expected_set = probe.get("expected_set", [])

    if expected:
        exp_norm = re.sub(r"[^A-Z0-9_>]", "", expected.strip().upper())
        return ans_norm == exp_norm
    if expected_set:
        for e in expected_set:
            e_norm = re.sub(r"[^A-Z0-9_>]", "", e.strip().upper())
            if ans_norm == e_norm:
                return True
        return False
    return False


def run_drift_probes(api_key: str | None = None) -> dict[str, Any]:
    """
    Run all semantic probes against the primary Ollama model and compute drift score.
    Returns the full result dict to be written as JSON output.
    """
    if not _CLIENT_AVAILABLE:
        raise RuntimeError("ollama_client not available — check PYTHONPATH includes .github/scripts")

    resolved_key = api_key or os.environ.get("OLLAMA_API_KEY", "")
    timestamp = datetime.now(timezone.utc).isoformat()

    # Use REASONING_CHAIN: glm-5:cloud -> nemotron-3-super -> cogito-2.1:671b-cloud -> qwen3.5:cloud
    # Structured outputs + web search enabled
    orch = FallbackOrchestrator(
        chain=REASONING_CHAIN,
        temperature=0.0,          # zero temp for deterministic answers
        use_streaming=True,       # streaming with buffer protection
        format_schema=PROBE_RESPONSE_SCHEMA,  # enforce JSON schema on responses
        web_search=True,          # let model check for spec updates
        api_key=resolved_key,
        max_retries_per_tier=2,
    )

    probe_results: list[dict[str, Any]] = []
    total_weight = sum(p["weight"] for p in PROBES)
    drift_weight = 0.0
    model_used = "unknown"
    tier_used = 0

    for probe in PROBES:
        try:
            result = orch.complete(
                system=SYSTEM_PROMPT,
                prompt=probe["prompt"],
            )
            model_used = result.model_used
            tier_used = result.tier_index

            # Parse structured output
            try:
                parsed = json.loads(result.content)
                answer = parsed.get("answer", "")
                confidence = float(parsed.get("confidence", 0.0))
                reasoning = parsed.get("reasoning", "")
            except (json.JSONDecodeError, ValueError):
                # Model didn't honour the schema — treat as partial answer
                answer = result.content[:100].strip()
                confidence = 0.5
                reasoning = "(unstructured response)"

            correct = _check_probe(probe, answer)
            if not correct:
                drift_weight += probe["weight"]

            probe_results.append({
                "id": probe["id"],
                "category": probe["category"],
                "weight": probe["weight"],
                "expected": probe.get("expected") or probe.get("expected_set"),
                "answer": answer,
                "confidence": confidence,
                "reasoning": reasoning,
                "correct": correct,
                "model": model_used,
                "tier": tier_used,
                "thinking": result.thinking[:200] if result.thinking else "",
                "tool_calls": result.tool_calls,
                "latency_s": result.latency_s,
            })

        except Exception as exc:
            # Probe failed entirely — counts as maximum drift for its weight
            drift_weight += probe["weight"]
            probe_results.append({
                "id": probe["id"],
                "category": probe["category"],
                "weight": probe["weight"],
                "answer": "",
                "correct": False,
                "error": str(exc)[:300],
                "traceback": traceback.format_exc()[-500:],
            })

    drift_score = drift_weight / total_weight if total_weight > 0 else 0.0
    correct_count = sum(1 for p in probe_results if p.get("correct", False))

    if drift_score < 0.15:
        status = "OK"
    elif drift_score < 0.40:
        status = "WARN"
    else:
        status = "ALERT"

    summary = (
        f"{correct_count}/{len(PROBES)} probes correct | "
        f"drift={drift_score:.1%} | status={status} | "
        f"model={model_used} (tier {tier_used + 1})"
    )

    return {
        "driftScore":  round(drift_score, 4),
        "status":      status,
        "probes":      probe_results,
        "modelUsed":   model_used,
        "tier":        tier_used,
        "timestamp":   timestamp,
        "summary":     summary,
        "correct":     correct_count,
        "total":       len(PROBES),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="HLF Model Drift Detection")
    parser.add_argument("--output", default="-", help="Output file path (- = stdout)")
    parser.add_argument("--api-key", default=None, help="Override OLLAMA_API_KEY env var")
    args = parser.parse_args()

    try:
        result = run_drift_probes(api_key=args.api_key)
    except Exception as exc:
        result = {
            "driftScore": 1.0,
            "status": "ALERT",
            "probes": [],
            "modelUsed": "error",
            "tier": -1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": f"Fatal error: {exc}",
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }

    output = json.dumps(result, indent=2, ensure_ascii=False)

    if args.output == "-":
        print(output)
    else:
        Path(args.output).write_text(output, encoding="utf-8")
        print(
            f"[monitor_model_drift] Written to {args.output} "
            f"(status={result['status']} drift={result['driftScore']:.1%})",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
