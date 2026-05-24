"""OpenAI-compatible SSE streaming for HLF compilation and execution.

Exposes an async generator that yields SSE data: lines with HLF flow mapped
to OpenAI's streaming chat-completion chunk format.  Any OpenAI-compatible
chat UI can render the stream without modification.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any, AsyncGenerator


# ── SSE formatting ────────────────────────────────────────────────────────────


def _sse_chunk(event_id: str, delta_content: str, *, finish_reason: str | None = None) -> str:
    """Build one OpenAI-compatible SSE data line."""
    chunk = {
        "id": event_id,
        "object": "hlf.execution.chunk",
        "created": int(time.time()),
        "model": "hlf-vm",
        "choices": [
            {
                "index": 0,
                "delta": {"content": delta_content},
                "finish_reason": finish_reason,
            }
        ],
    }
    return f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"


_FINISH_LINE = "data: [DONE]\n\n"


# ── Step renderers ────────────────────────────────────────────────────────────


# Opcode → human-readable description for the stream
_OP_RENDER: dict[str, str] = {
    "NOP":         "⟐ no-op",
    "PUSH_CONST":  "⇧ PUSH constant",
    "STORE":       "↓ STORE to scope",
    "LOAD":        "↑ LOAD from scope",
    "ADD":         "+ ADD",
    "SUB":         "− SUB",
    "MUL":         "× MUL",
    "DIV":         "÷ DIV",
    "MOD":         "% MOD",
    "EQ":          "≟ EQ",
    "NEQ":         "≠ NEQ",
    "LT":          "< LT",
    "GT":          "> GT",
    "LTE":         "≤ LTE",
    "GTE":         "≥ GTE",
    "AND":         "∧ AND",
    "OR":          "∨ OR",
    "NOT":         "¬ NOT",
    "JMP":         "↪ JMP",
    "JMP_IF_FALSE":"↪? JMP_IF_FALSE",
    "CALL":        "↗ CALL",
    "RET":         "↩ RET",
    "DUP":         "⧅ DUP",
    "SWAP":        "⇄ SWAP",
    "POP":         "✕ POP",
    "HALT":        "⏹ HALT",
    "MEMORY_STORE":"⊡ MEMORY write",
    "MEMORY_RECALL":"⊡ MEMORY read",
    "EXPECT":      "Ж EXPECT check",
    "CONSTRAINT":  "Ж CONSTRAINT gate",
    "WITNESS":     "∇ WITNESS record",
    "SECRET":      "∇ SECRET vault",
    "CAPSULE":     "⬡ CAPSULE boundary",
    "ROUTE":       "↯ ROUTE dispatch",
    "DELEGATE":    "⇉ DELEGATE authority",
    "SWARM":       "✧ SWARM spawn",
    "INSTINCT":    "☿ INSTINCT trigger",
    "AUDIT":       "⛓ AUDIT record",
}


def _render_step(entry: dict[str, Any], stack_depth: int) -> str:
    """Render a single VM step as a stream line."""
    op = entry.get("op", "?")
    pc = entry.get("pc", 0)
    gas = entry.get("gas", 0)
    glyph = _OP_RENDER.get(op, f"⚙ {op}")
    detail = ""
    if "push" in entry:
        detail = f" [{entry['push']!r}]"
    elif "stored" in entry:
        detail = f" [{entry['stored']} = {entry.get('value', '?')!r}]"
    return f"{glyph}{detail}  │  pc={pc}  gas={gas}  stack={stack_depth}\n"


# ── Async stream generator ────────────────────────────────────────────────────


async def generate_hlf_stream(
    source: str,
    compiler: Any,
    runtime: Any,
    *,
    session_id: str | None = None,
    tier: str = "hearth",
    max_gas: int = 100,
) -> AsyncGenerator[str, None]:
    """OpenAI-compatible SSE stream of HLF compilation + execution.

    Yields ``data: {…}\\n\\n`` SSE frames that any OpenAI-compatible chat
    client can render as a real-time execution trace.
    """
    exec_id = f"hlf-exec-{uuid.uuid4().hex[:12]}"
    ts = int(time.time())

    # ── Phase 0: Greeting ─────────────────────────────────────────────────
    yield _sse_chunk(
        exec_id,
        f"Δ INTENT received  │  {len(source)} chars  │  tier={tier}  max_gas={max_gas}\n",
    )

    # ── Phase 1: Compilation ──────────────────────────────────────────────
    yield _sse_chunk(exec_id, "⚙ COMPILE: surface → parse tree …\n")
    # (The compiler is synchronous — we can't yield per-phase without
    #  refactoring it.  We report phases as milestones.)
    try:
        compiled = compiler.compile(source)
    except Exception as exc:
        yield _sse_chunk(exec_id, f"✕ COMPILE FAILED: {exc}\n", finish_reason="error")
        yield _FINISH_LINE
        return

    ast_nodes = len(compiled.get("ast", [])) if isinstance(compiled, dict) else 0
    hlb_data = compiled.get("bytecode", b"") if isinstance(compiled, dict) else b""
    byte_len = len(hlb_data)
    yield _sse_chunk(exec_id, f"⚙ COMPILE: AST ({ast_nodes} nodes) → bytecode ({byte_len} bytes)\n")
    yield _sse_chunk(exec_id, "⚙ COMPILE ✓\n")

    # ── Phase 2: Execution ────────────────────────────────────────────────
    if not hlb_data:
        yield _sse_chunk(exec_id, "✕ No bytecode produced — cannot execute.\n", finish_reason="error")
        yield _FINISH_LINE
        return

    # Wire the step callback with a thread-safe list + event pattern.
    import threading

    step_events: list[dict[str, Any]] = []
    step_lock = threading.Lock()
    step_done = threading.Event()

    def _on_step(entry: dict[str, Any]) -> None:
        with step_lock:
            step_events.append(entry)

    vm = runtime.create_vm(tier=tier, max_gas=max_gas) if hasattr(runtime, "create_vm") else None
    if vm is None:
        from hlf_mcp.hlf.runtime import HlfVM
        vm = HlfVM(tier=tier, max_gas=max_gas, session_id=session_id)
    vm._step_callback = _on_step

    yield _sse_chunk(exec_id, "☿ EXECUTE: VM booting …\n")

    # Run execution in a thread so we can stream steps as they happen.
    import concurrent.futures

    loop = asyncio.get_running_loop()
    result_future: concurrent.futures.Future[Any] = concurrent.futures.Future()

    def _run_vm() -> None:
        try:
            r = vm.execute(hlb_data)
            step_done.set()
            result_future.set_result(r)
        except Exception as exc:
            step_done.set()
            result_future.set_exception(exc)

    thread = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    thread.submit(_run_vm)

    # Drain step buffer, yielding SSE frames as steps become available.
    step_idx = 0
    step_count = 0
    while not step_done.is_set() or step_idx < len(step_events):
        with step_lock:
            new_steps = step_events[step_idx:]
            step_idx = len(step_events)
        for entry in new_steps:
            step_count += 1
            yield _sse_chunk(exec_id, _render_step(entry, len(vm.stack)))
        if step_done.is_set() and step_idx >= len(step_events):
            break
        await asyncio.sleep(0.001)  # yield to event loop

    # Collect result.
    try:
        result = await loop.run_in_executor(None, result_future.result, 30)
    except Exception as exc:
        yield _sse_chunk(exec_id, f"✕ EXECUTE CRASHED: {exc}\n", finish_reason="error")
        yield _FINISH_LINE
        return

    # ── Phase 3: Result ───────────────────────────────────────────────────
    code = result.code if hasattr(result, "code") else -1
    msg = result.message if hasattr(result, "message") else "?"
    gas = result.gas_used if hasattr(result, "gas_used") else 0
    stack_top = result.stack[-1] if hasattr(result, "stack") and result.stack else None

    status_glyph = "✓" if code == 0 else "✕"
    yield _sse_chunk(
        exec_id,
        f"{status_glyph} RESULT: code={code}  gas={gas}/{max_gas}  "
        f"steps={step_count}  stack_top={stack_top!r}\n"
        f"  {msg}\n",
    )

    yield _sse_chunk(exec_id, "", finish_reason="stop")
    yield _FINISH_LINE
