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
    • Closed-book probes  — web search disabled so the baseline reflects model
                            understanding rather than live retrieval behavior
    • Deterministic calls — non-streaming requests for stricter JSON stability
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
import re
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
Do not use external search, tool calls, or retrieval behavior for these probes; they are a
closed-book baseline on the model's own understanding.
Always respond in the JSON format requested, with an "answer", "confidence", and "reasoning" field.
"""

OUTCOME_CORRECT = "correct"
OUTCOME_SEMANTIC_WRONG = "semantic_wrong_answer"
OUTCOME_PROTOCOL_FAILURE = "protocol_shape_failure"
OUTCOME_TOOL_CALL_FAILURE = "tool_call_behavior_failure"


def _extract_json_candidate(text: str) -> tuple[str | None, str | None]:
    stripped = text.strip()
    if not stripped:
        return None, "empty_response"

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip(), "fenced_json"

    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped, "raw_json"

    start = stripped.find("{")
    if start == -1:
        return None, "missing_json_object"

    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(stripped)):
        char = stripped[idx]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return stripped[start : idx + 1].strip(), "embedded_json"

    return None, "unterminated_json_object"


def _normalize_probe_response(raw_content: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    candidate, source = _extract_json_candidate(raw_content)
    metadata: dict[str, Any] = {
        "normalization": source,
        "raw_excerpt": raw_content.strip()[:200],
    }
    if candidate is None:
        metadata["error"] = source or "missing_json_object"
        return None, metadata

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        metadata["error"] = f"json_decode_error:{exc.msg}"
        return None, metadata

    if not isinstance(parsed, dict):
        metadata["error"] = "json_not_object"
        return None, metadata

    answer = parsed.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        metadata["error"] = "missing_answer"
        return None, metadata

    confidence_raw = parsed.get("confidence", 0.0)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.0
        metadata["confidence_normalized_from"] = str(confidence_raw)[:60]
    confidence = max(0.0, min(1.0, confidence))

    reasoning = parsed.get("reasoning", "")
    if reasoning is None:
        reasoning = ""
    elif not isinstance(reasoning, str):
        reasoning = str(reasoning)
        metadata["reasoning_normalized"] = True

    return {
        "answer": answer.strip(),
        "confidence": confidence,
        "reasoning": reasoning.strip(),
    }, metadata


def _empty_outcome_counts() -> dict[str, int]:
    return {
        OUTCOME_CORRECT: 0,
        OUTCOME_SEMANTIC_WRONG: 0,
        OUTCOME_PROTOCOL_FAILURE: 0,
        OUTCOME_TOOL_CALL_FAILURE: 0,
    }


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

    # Weekly drift probes are intentionally closed-book: schema enforcement stays on,
    # but search and tool-use are disabled and streaming is turned off.
    orch = FallbackOrchestrator(
        chain=REASONING_CHAIN,
        temperature=0.0,          # zero temp for deterministic answers
        use_streaming=False,
        format_schema=PROBE_RESPONSE_SCHEMA,  # enforce JSON schema on responses
        web_search=False,
        api_key=resolved_key,
        max_retries_per_tier=2,
    )

    probe_results: list[dict[str, Any]] = []
    total_weight = sum(p["weight"] for p in PROBES)
    drift_weight = 0.0
    model_used = "unknown"
    tier_used = 0
    outcome_counts = _empty_outcome_counts()

    for probe in PROBES:
        try:
            result = orch.complete(
                system=SYSTEM_PROMPT,
                prompt=probe["prompt"],
            )
            model_used = result.model_used
            tier_used = result.tier_index

            if result.tool_calls:
                drift_weight += probe["weight"]
                outcome_counts[OUTCOME_TOOL_CALL_FAILURE] += 1
                probe_results.append({
                    "id": probe["id"],
                    "category": probe["category"],
                    "weight": probe["weight"],
                    "expected": probe.get("expected") or probe.get("expected_set"),
                    "answer": "",
                    "confidence": 0.0,
                    "reasoning": "",
                    "correct": False,
                    "outcomeClass": OUTCOME_TOOL_CALL_FAILURE,
                    "failureDetail": "unexpected_tool_call",
                    "model": model_used,
                    "tier": tier_used,
                    "thinking": result.thinking[:200] if result.thinking else "",
                    "tool_calls": result.tool_calls,
                    "latency_s": result.latency_s,
                })
                continue

            parsed, normalization = _normalize_probe_response(result.content)
            if parsed is None:
                drift_weight += probe["weight"]
                outcome_counts[OUTCOME_PROTOCOL_FAILURE] += 1
                probe_results.append({
                    "id": probe["id"],
                    "category": probe["category"],
                    "weight": probe["weight"],
                    "expected": probe.get("expected") or probe.get("expected_set"),
                    "answer": result.content[:100].strip(),
                    "confidence": 0.0,
                    "reasoning": "",
                    "correct": False,
                    "outcomeClass": OUTCOME_PROTOCOL_FAILURE,
                    "failureDetail": normalization.get("error", "protocol_shape_failure"),
                    "normalization": normalization,
                    "model": model_used,
                    "tier": tier_used,
                    "thinking": result.thinking[:200] if result.thinking else "",
                    "tool_calls": result.tool_calls,
                    "latency_s": result.latency_s,
                })
                continue

            answer = parsed["answer"]
            confidence = parsed["confidence"]
            reasoning = parsed["reasoning"]
            correct = _check_probe(probe, answer)
            outcome_class = OUTCOME_CORRECT if correct else OUTCOME_SEMANTIC_WRONG
            outcome_counts[outcome_class] += 1
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
                "outcomeClass": outcome_class,
                "normalization": normalization,
                "model": model_used,
                "tier": tier_used,
                "thinking": result.thinking[:200] if result.thinking else "",
                "tool_calls": result.tool_calls,
                "latency_s": result.latency_s,
            })

        except Exception as exc:
            # Probe failed entirely — counts as maximum drift for its weight
            drift_weight += probe["weight"]
            outcome_counts[OUTCOME_PROTOCOL_FAILURE] += 1
            probe_results.append({
                "id": probe["id"],
                "category": probe["category"],
                "weight": probe["weight"],
                "answer": "",
                "correct": False,
                "outcomeClass": OUTCOME_PROTOCOL_FAILURE,
                "failureDetail": "runtime_exception",
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
        "chainUsed":   list(REASONING_CHAIN),
        "timestamp":   timestamp,
        "summary":     summary,
        "correct":     correct_count,
        "total":       len(PROBES),
        "outcomeCounts": outcome_counts,
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
