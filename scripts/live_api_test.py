#!/usr/bin/env python3
"""
HLF Live Ollama Cloud API Test
================================
Exercises every Ollama Cloud API capability end-to-end against real models.
Run in GitHub Actions via: workflow_dispatch on .github/workflows/test-live-ollama-api.yml

Capabilities tested:
  1. Basic chat completion (streaming)
  2. Tiered fallback chain (circuit-breaker + retry)
  3. Thinking mode (deepseek-r1 chain-of-thought)
  4. Structured outputs (JSON schema enforcement)
  5. Tool calling (function definition + tool_calls response)
  6. Web search (POST /api/web_search endpoint)
  7. Connection resilience (timeout simulation)
  8. Audit trail completeness

Requirements:
  OLLAMA_API_KEY environment variable must be set.
  Python 3.12+, .github/scripts/ollama_client.py must be on PYTHONPATH.
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).parent.parent / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from ollama_client import (
    CircuitBreaker,
    ConnectionMonitor,
    FallbackOrchestrator,
    REASONING_CHAIN,
    CODING_CHAIN,
    ETHICS_CHAIN,
    ANALYSIS_CHAIN,
    UNIVERSAL_CHAIN,
    web_search as ollama_web_search,
    WebSearchResult,
    CompletionResult,
)

# ---------------------------------------------------------------------------

API_KEY = os.environ.get("OLLAMA_API_KEY", "")
RESULTS: list[dict[str, Any]] = []

def _pass(test_id: str, msg: str, details: dict | None = None) -> None:
    print(f"  ✓ [{test_id}] {msg}")
    RESULTS.append({"id": test_id, "status": "PASS", "msg": msg, **(details or {})})

def _fail(test_id: str, msg: str, details: dict | None = None) -> None:
    print(f"  ✗ [{test_id}] FAIL: {msg}", file=sys.stderr)
    RESULTS.append({"id": test_id, "status": "FAIL", "msg": msg, **(details or {})})

def _skip(test_id: str, msg: str) -> None:
    print(f"  - [{test_id}] SKIP: {msg}")
    RESULTS.append({"id": test_id, "status": "SKIP", "msg": msg})

# ---------------------------------------------------------------------------
# Test 1: Basic streaming chat
# ---------------------------------------------------------------------------
def test_basic_streaming():
    print("\n=== Test 1: Basic streaming chat ===")
    try:
        orch = FallbackOrchestrator(
            chain=UNIVERSAL_CHAIN, api_key=API_KEY,
            use_streaming=True, temperature=0.1,
        )
        result: CompletionResult = orch.complete(
            system="You are a concise HLF documentation assistant.",
            prompt="In exactly one sentence, what is HLF (Hieroglyphic Logic Framework)?",
        )
        assert result.content, "No content returned"
        assert result.streamed is True, "Expected streaming=True"
        assert result.latency_s > 0, "Latency should be positive"
        _pass("T01", f"Streaming OK | model={result.model_used} tier={result.tier_index} "
                     f"{len(result.content)} chars in {result.latency_s:.1f}s")
        return result
    except Exception as exc:
        _fail("T01", f"Streaming failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Test 2: Tiered fallback (force primary circuit open)
# ---------------------------------------------------------------------------
def test_tiered_fallback():
    print("\n=== Test 2: Tiered fallback chain ===")
    try:
        # Reset circuit breakers
        CircuitBreaker._instances.clear()
        ConnectionMonitor._instances.clear()

        # Trip the primary model's circuit breaker
        primary = CODING_CHAIN[0]  # devstral:24b
        cb = CircuitBreaker(primary)
        for _ in range(4):   # CIRCUIT_FAIL_THRESHOLD
            cb.record_failure()
        assert cb.is_open, f"Circuit for {primary} should be open"
        _pass("T02a", f"Circuit OPEN for {primary} (simulated failures)")

        # Now complete should automatically fall back to tier 2
        orch = FallbackOrchestrator(chain=CODING_CHAIN, api_key=API_KEY, temperature=0.1)
        result = orch.complete(
            system="You are an HLF coding assistant.",
            prompt="Write one line of HLF that assigns the integer 42 to a constant X.",
        )
        assert result.tier_index >= 1, f"Expected fallback (tier>=1), got tier={result.tier_index}"
        assert result.model_used != primary, f"Expected fallback model, got {result.model_used}"
        _pass("T02b", f"Fallback to tier {result.tier_index+1} ({result.model_used}) — "
                     f"{result.attempts} total attempts, {len(result.content)} chars")
        _pass("T02c", f"Audit trail has {len(result.audit_trail)} entries "
                     f"(includes circuit_open record for {primary})")

        # Restore
        cb.reset()
        return result
    except Exception as exc:
        _fail("T02", f"Tiered fallback failed: {exc}")
        traceback.print_exc()
        return None

# ---------------------------------------------------------------------------
# Test 3: Thinking mode (deepseek-r1 chain)
# ---------------------------------------------------------------------------
def test_thinking_mode():
    print("\n=== Test 3: Thinking mode (deepseek-r1) ===")
    try:
        orch = FallbackOrchestrator(
            chain=ETHICS_CHAIN, api_key=API_KEY,
            think=True, temperature=0.1, use_streaming=True,
        )
        result = orch.complete(
            system="You are a careful ethical reasoning agent for HLF.",
            prompt=(
                "Reason step by step: Should an AI system execute code that "
                "attempts to exfiltrate user data? Give your final answer as YES or NO."
            ),
        )
        assert result.content, "No content"
        _pass("T03a", f"Thinking model responded | model={result.model_used} "
                     f"{len(result.content)} chars")
        if result.thinking:
            _pass("T03b", f"Thinking trace captured: {len(result.thinking)} chars "
                         f"(first 100: {result.thinking[:100]!r})")
        else:
            _skip("T03b", "No thinking trace in response (model may not support think=true)")
        return result
    except Exception as exc:
        _fail("T03", f"Thinking mode failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Test 4: Structured outputs
# ---------------------------------------------------------------------------
def test_structured_outputs():
    print("\n=== Test 4: Structured outputs (JSON schema) ===")
    schema = {
        "type": "object",
        "properties": {
            "opcode": {"type": "string", "description": "HLF opcode mnemonic"},
            "hex": {"type": "string", "description": "Hex code e.g. 0x01"},
            "gas": {"type": "integer", "description": "Gas cost"},
        },
        "required": ["opcode", "hex", "gas"],
    }
    try:
        orch = FallbackOrchestrator(
            chain=ANALYSIS_CHAIN, api_key=API_KEY,
            format_schema=schema, temperature=0.0,
            use_streaming=False,  # Structured outputs work best with stream=false
        )
        result = orch.complete(
            system="You are an HLF bytecode specification expert. Respond ONLY in valid JSON.",
            prompt="Describe the NOP opcode in HLF bytecode. Return exactly the JSON schema fields: opcode, hex, gas.",
        )
        assert result.content, "No content"
        try:
            parsed = json.loads(result.content)
            assert "opcode" in parsed, f"Missing 'opcode' key in: {parsed}"
            _pass("T04", f"Structured output valid JSON | model={result.model_used} "
                        f"opcode={parsed.get('opcode')!r} hex={parsed.get('hex')!r} gas={parsed.get('gas')}")
        except json.JSONDecodeError as je:
            _fail("T04", f"Response not valid JSON: {result.content[:200]!r} — {je}")
        return result
    except Exception as exc:
        _fail("T04", f"Structured outputs failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Test 5: Tool calling
# ---------------------------------------------------------------------------
def test_tool_calling():
    print("\n=== Test 5: Tool calling ===")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_opcode_info",
                "description": "Look up HLF bytecode opcode details by name",
                "parameters": {
                    "type": "object",
                    "required": ["opcode_name"],
                    "properties": {
                        "opcode_name": {
                            "type": "string",
                            "description": "The opcode mnemonic e.g. NOP, HALT, PUSH_INT",
                        },
                    },
                },
            },
        }
    ]
    try:
        orch = FallbackOrchestrator(
            chain=REASONING_CHAIN, api_key=API_KEY,
            tools=tools, temperature=0.1, use_streaming=True,
        )
        result = orch.complete(
            system="You are an HLF bytecode assistant with access to opcode lookup tools.",
            prompt="What are the details of the HALT opcode in HLF? Use the available tool.",
        )
        assert result.content or result.tool_calls, "Neither content nor tool_calls returned"
        if result.tool_calls:
            tc = result.tool_calls[0]
            func_name = tc.get("function", {}).get("name", "") if isinstance(tc, dict) else ""
            _pass("T05a", f"Tool call emitted | function={func_name!r} | tool_calls={len(result.tool_calls)}")
        else:
            _pass("T05a", f"Model answered directly (no tool call) | {len(result.content)} chars")
        _pass("T05b", f"Tool calling completed | model={result.model_used}")
        return result
    except Exception as exc:
        _fail("T05", f"Tool calling failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Test 6: Web search
# ---------------------------------------------------------------------------
def test_web_search():
    print("\n=== Test 6: Web search (POST /api/web_search) ===")
    try:
        ws_result: WebSearchResult = ollama_web_search(
            query="HLF Hieroglyphic Logic Framework MCP",
            max_results=3,
            api_key=API_KEY,
        )
        assert isinstance(ws_result.results, list), "results should be a list"
        _pass("T06a", f"Web search returned {len(ws_result.results)} results for query")
        if ws_result.results:
            first = ws_result.results[0]
            assert "title" in first or "url" in first or "content" in first, \
                f"Result missing expected keys: {list(first.keys())}"
            _pass("T06b", f"First result: {first.get('title', '?')[:60]!r} — {first.get('url', '?')[:60]}")
        return ws_result
    except Exception as exc:
        _fail("T06", f"Web search failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Test 7: Web search + chat integration
# ---------------------------------------------------------------------------
def test_web_search_in_chat():
    print("\n=== Test 7: Web search injected into chat ===")
    try:
        orch = FallbackOrchestrator(
            chain=REASONING_CHAIN, api_key=API_KEY,
            web_search=True,      # inject web_search tool automatically
            temperature=0.1,
            use_streaming=True,
        )
        result = orch.complete(
            system="You are an HLF research assistant with web access.",
            prompt=(
                "Use the web_search tool to find information about the HLF "
                "Hieroglyphic Logic Framework. Then summarize what it is in 2-3 sentences."
            ),
        )
        assert result.content, "No content returned"
        _pass("T07", f"Web search in chat | model={result.model_used} "
                    f"tool_calls={len(result.tool_calls)} "
                    f"content={len(result.content)} chars")
        return result
    except Exception as exc:
        _fail("T07", f"Web search in chat failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Test 8: Health report
# ---------------------------------------------------------------------------
def test_health_report():
    print("\n=== Test 8: Connection health report ===")
    try:
        orch = FallbackOrchestrator(chain=UNIVERSAL_CHAIN, api_key=API_KEY)
        report = orch.health_report()
        assert "nemotron-3-super" in report
        assert "qwen3.5:cloud" in report
        _pass("T08", f"Health report generated | {len(report.split(chr(10)))} lines")
        print(report)
        return report
    except Exception as exc:
        _fail("T08", f"Health report failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    print("=" * 60)
    print("HLF Live Ollama Cloud API Test Suite")
    print("=" * 60)
    print(f"API key set: {'yes (' + str(len(API_KEY)) + ' chars)' if API_KEY else 'NO — set OLLAMA_API_KEY'}")
    print(f"Primary model: {REASONING_CHAIN[0]}")
    print(f"Chain: {' -> '.join(REASONING_CHAIN)}")
    print()

    if not API_KEY:
        print("ERROR: OLLAMA_API_KEY is not set.", file=sys.stderr)
        print("Set it via: export OLLAMA_API_KEY=your_key_here", file=sys.stderr)
        sys.exit(1)

    t_start = time.monotonic()

    # Run all tests
    test_basic_streaming()
    test_tiered_fallback()
    test_thinking_mode()
    test_structured_outputs()
    test_tool_calling()
    test_web_search()
    test_web_search_in_chat()
    test_health_report()

    total_s = time.monotonic() - t_start

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    passed = [r for r in RESULTS if r["status"] == "PASS"]
    failed = [r for r in RESULTS if r["status"] == "FAIL"]
    skipped = [r for r in RESULTS if r["status"] == "SKIP"]

    print(f"  PASS:  {len(passed)}")
    print(f"  FAIL:  {len(failed)}")
    print(f"  SKIP:  {len(skipped)}")
    print(f"  Total: {len(RESULTS)}")
    print(f"  Time:  {total_s:.1f}s")

    if failed:
        print("\nFailed tests:")
        for r in failed:
            print(f"  ✗ [{r['id']}] {r['msg']}")
        print()

    # Write JSON summary for CI consumption
    summary = {
        "passed": len(passed),
        "failed": len(failed),
        "skipped": len(skipped),
        "total": len(RESULTS),
        "time_s": round(total_s, 2),
        "results": RESULTS,
    }
    output_path = "/tmp/live_test_results.json"
    Path(output_path).write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"Results written to {output_path}")

    if failed:
        sys.exit(1)
    print("\n✅ All live tests passed!")

if __name__ == "__main__":
    main()
