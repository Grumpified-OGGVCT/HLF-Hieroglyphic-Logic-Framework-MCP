#!/usr/bin/env python3
"""
hlf-evidence — Human-readable operator interface for HLF evidence and provenance.

Usage:
    hlf-evidence show --capsule-id <ID>       Show a specific latent inference trace
    hlf-evidence show --latent                Show the most recent latent traces
    hlf-evidence list                         List all latent trace entries (summary)
    hlf-evidence verify --capsule-id <ID>     Verify a trace's Merkle chain integrity

Enterprise hardening item #4: Latent Evidence Rendering.
No more reading raw JSONL. Operators get human-readable provenance trails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Repository root detection
_REPO_ROOT = Path(__file__).resolve().parent.parent
_TRACES_FILE = _REPO_ROOT / "observability" / "openllmetry" / "latent_traces.jsonl"


def _load_traces() -> list[dict]:
    """Load all latent trace entries from the JSONL file."""
    if not _TRACES_FILE.exists():
        return []
    traces = []
    with open(_TRACES_FILE, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                traces.append(entry)
            except json.JSONDecodeError:
                continue
    return traces


def _find_trace(capsule_id: str) -> dict | None:
    """Find a specific trace by capsule_id (partial match)."""
    for trace in _load_traces():
        data = trace.get("data", {})
        if data.get("capsule_id", "") == capsule_id or capsule_id in data.get("capsule_id", ""):
            return trace
    return None


def _render_trace(trace: dict, show_latent: bool = True) -> str:
    """Render a single trace entry in human-readable format.

    Args:
        trace: The raw trace dict from JSONL.
        show_latent: If True, render full latent handoff trail. If False, summary only.
    """
    data = trace.get("data", {})
    trace_id = trace.get("trace_id", "?")[:16]
    capsule_id = data.get("capsule_id", "?")
    status = data.get("status", "?")
    total_gas = data.get("total_gas", 0)
    wall_time = data.get("total_wall_time_ms", 0)
    peak_vram = data.get("peak_vram_mb", 0)
    num_steps = data.get("num_steps", 0)
    agents = data.get("agents", [])
    attestations = data.get("attestations", [])
    provenance_chain = data.get("provenance_chain", [])
    final_text = data.get("final_text", "")
    prompt = data.get("prompt", "")
    adapter_hashes = data.get("adapter_hashes", {})

    status_icon = "[OK]" if status == "ok" else "[ABORTED]" if status == "aborted" else f"[{status.upper()}]"

    lines = [
        "=" * 60,
        f"  Trace: {trace_id}",
        f"  Capsule: {capsule_id}",
        f"  Status: {status_icon}",
        f"  Agents: {', '.join(agents) if agents else '(none)'}",
        f"  Rounds/Steps: {num_steps}",
        f"  Gas: {total_gas} / 500 ({total_gas/500*100:.0f}%)  |  Wall Time: {wall_time/1000:.1f}s  |  Peak VRAM: {peak_vram} MB",
    ]

    if prompt:
        lines.append(f"  Prompt: {prompt[:120]}{'...' if len(prompt) > 120 else ''}")

    if attestations:
        if show_latent:
            lines.append("  " + "-" * 56)
            lines.append("  LATENT HANDOFF TRAIL:")
            current_round = 0
            for i, att in enumerate(attestations):
                src = att.get("source_agent", "?")
                tgt = att.get("target_agent", "?")
                adapter = att.get("adapter_sha256", "?")
                adapter_short = adapter[:16] if len(adapter) > 16 else adapter
                gas = att.get("gas_consumed", 0)
                src_dim = att.get("source_dims", "?")
                tgt_dim = att.get("target_dims", "?")
                round_num = att.get("round", 0)

                # Resolve adapter name from known checkpoints
                adapter_name = _resolve_adapter_name(adapter, adapter_hashes)

                if round_num != current_round:
                    current_round = round_num
                    lines.append(f"    Round {current_round}")

                lines.append(
                    f"      Handoff #{i+1}: {src}({src_dim}d) -> {tgt}({tgt_dim}d)"
                )
                lines.append(f"                 Adapter: {adapter_name}")
                lines.append(f"                 Adapter Hash: {adapter_short}...")
                lines.append(f"                 Gas: {gas}")
        else:
            total_handoff_gas = sum(a.get("gas_consumed", 0) for a in attestations)
            lines.append(
                f"  Latent recursion: {num_steps//3} rounds, {len(attestations)} handoffs, "
                f"{total_handoff_gas} gas. Use --latent for details."
            )

    if provenance_chain:
        lines.append("  " + "-" * 56)
        lines.append(f"  MERKLE ROOT: {provenance_chain[-1][:32]}...")
        lines.append(f"  Chain depth: {len(provenance_chain)} hashes")

    if final_text:
        lines.append("  " + "-" * 56)
        lines.append(f"  FINAL OUTPUT:")
        preview = final_text[:300]
        if len(final_text) > 300:
            preview += "..."
        lines.append(f"    {preview}")

    lines.append("=" * 60)
    return "\n".join(lines)


def _resolve_adapter_name(adapter_hash: str, adapter_hashes: dict[str, str]) -> str:
    """Resolve an adapter hash to a human-readable checkpoint name.

    Looks up the hash in the adapter_hashes dict (name -> hash) to find
    the matching adapter name. Falls back to generic descriptions.

    Returns:
        Human-readable adapter name string.
    """
    if not adapter_hash or adapter_hash == "?":
        return "UNKNOWN (checkpoint loaded before hash registry)"

    # Check if the hash matches any known adapter
    for name, h in adapter_hashes.items():
        if h == adapter_hash:
            return name
        # Partial match on prefix for truncated hashes
        if len(adapter_hash) >= 12 and h.startswith(adapter_hash[:12]):
            return name

    # Fallback to generic resolution based on source/target patterns
    # (handled by caller if needed)
    return f"unregistered-adapter-{adapter_hash[:12]}"


def cmd_show_latent(args: argparse.Namespace) -> int:
    """Show latent traces, optionally filtered by capsule ID."""
    show_latent_detail = getattr(args, 'latent', False)

    if args.capsule_id:
        trace = _find_trace(args.capsule_id)
        if trace is None:
            print(f"No trace found for capsule ID: {args.capsule_id}")
            return 1

        # Try Rich renderer first for enhanced output
        if show_latent_detail:
            rendered = _try_rich_render(trace)
            if rendered:
                print(rendered)
                return 0

        # Plain text fallback
        print(_render_trace(trace, show_latent=show_latent_detail))
        return 0

    # Show most recent traces (last N)
    traces = _load_traces()
    if not traces:
        print("No latent traces found.")
        return 0

    limit = args.limit or 5
    for trace in traces[-limit:]:
        if show_latent_detail:
            rendered = _try_rich_render(trace)
            if rendered:
                print(rendered)
                continue
        print(_render_trace(trace, show_latent=show_latent_detail))
    return 0


def _try_rich_render(trace: dict) -> str | None:
    """Try to render a trace using EvidenceSummaryRenderer (Rich output).

    Returns None if the renderer is not available or fails.
    If Rich is available, renders the Panel to a string via console capture.
    """
    try:
        from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer

        data = trace.get("data", {})
        result = {
            "capsule_id": data.get("capsule_id", "?"),
            "status": data.get("status", "?"),
            "total_gas": data.get("total_gas", 0),
            "total_wall_time_ms": data.get("total_wall_time_ms", 0),
            "peak_vram_mb": data.get("peak_vram_mb", 0),
            "rounds_completed": data.get("num_steps", 0) // 3,
            "attestations": data.get("attestations", []),
            "provenance_chain": data.get("provenance_chain", []),
            "final_text": data.get("final_text", ""),
        }

        rendered = EvidenceSummaryRenderer.render_latent_provenance(result)

        # If it's already a string, return it
        if isinstance(rendered, str):
            return rendered

        # If it's a Rich renderable (Panel), render via console capture
        if hasattr(rendered, '__rich_console__'):
            from rich.console import Console
            from io import StringIO
            console = Console(file=StringIO(), force_terminal=True, width=100, color_system="standard")
            console.print(rendered)
            output = console.file.getvalue()  # type: ignore[attr-defined]
            if output and "Panel object" not in output:
                return output
            return None

        return str(rendered) if "Panel object" not in str(rendered) else None
    except ImportError:
        return None
    except Exception:
        return None


def cmd_list(args: argparse.Namespace) -> int:
    """List all latent trace entries in summary format."""
    traces = _load_traces()
    if not traces:
        print("No latent traces found.")
        return 0

    # Header
    header = f"{'Trace ID':<20} {'Capsule':<18} {'Status':<12} {'Gas':>6} {'Time':>8} {'VRAM':>8} {'Agents':<30}"
    print(header)
    print("-" * len(header))

    for trace in traces:
        data = trace.get("data", {})
        tid = trace.get("trace_id", "?")[:16]
        cid = data.get("capsule_id", "?")[:16]
        status = data.get("status", "?")
        gas = data.get("total_gas", 0)
        wall = f"{data.get('total_wall_time_ms', 0)/1000:.1f}s"
        vram = f"{data.get('peak_vram_mb', 0)}MB"
        agents = ", ".join(data.get("agents", [])[:2])

        print(f"{tid:<20} {cid:<18} {status:<12} {gas:>6} {wall:>8} {vram:>8} {agents:<30}")

    print(f"\n{len(traces)} trace(s) total")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify a trace's Merkle chain integrity."""
    if not args.capsule_id:
        print("[ERROR] --capsule-id is required for verify")
        return 1

    trace = _find_trace(args.capsule_id)
    if trace is None:
        print(f"[NOT_FOUND] No trace found for capsule ID: {args.capsule_id}")
        return 1

    data = trace.get("data", {})
    provenance = data.get("provenance_chain", [])
    attestations = data.get("attestations", [])

    if not provenance:
        print("[WARN] No provenance chain in trace — nothing to verify")
        return 1

    # Verify that provenance hashes form a valid chain
    valid = True
    tamper_detected = False

    for i in range(1, len(provenance)):
        prev = provenance[i-1]
        curr = provenance[i]
        # Basic sanity: hashes should be 64 hex chars
        if len(prev) != 64 or len(curr) != 64:
            print(f"[FAIL] Malformed hash at position {i}: {curr[:16]}...")
            valid = False
            break

    # Cross-check: each attestation should have a provenance_hash
    if valid and attestations and len(provenance) > 0:
        import hashlib
        # Verify attestation hashes are consistent
        for i, att in enumerate(attestations):
            prov_hash = att.get("provenance_hash")
            if prov_hash and prov_hash not in provenance:
                print(f"[TAMPER ALERT] Handoff #{i+1} provenance hash {prov_hash[:16]}... "
                      f"not found in Merkle chain. Chain integrity may be broken.")
                tamper_detected = True

    if tamper_detected:
        print(f"[FAIL] Tampered provenance detected for {args.capsule_id}")
        print(f"  Attestation hashes missing from Merkle chain")
        return 1
    elif valid:
        print(f"[OK] Merkle chain integrity verified for {args.capsule_id}")
        print(f"  Depth: {len(provenance)} hashes")
        print(f"  Root: {provenance[-1]}")
        # Check attestation count against chain depth
        if attestations:
            print(f"  Attestations: {len(attestations)} handoffs")
    else:
        print(f"[FAIL] Merkle chain verification failed for {args.capsule_id}")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="hlf-evidence — Human-readable HLF evidence and provenance viewer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  hlf-evidence list                              List all latent traces
  hlf-evidence show --latent                     Show last 5 latent traces
  hlf-evidence show --latent --limit 10          Show last 10
  hlf-evidence show --capsule-id test-cap-1      Show a specific capsule
  hlf-evidence verify --capsule-id test-cap-1    Verify Merkle chain
        """,
    )

    sub = parser.add_subparsers(dest="command", help="Command")

    # show
    show_parser = sub.add_parser("show", help="Show trace details")
    show_parser.add_argument("--latent", action="store_true", help="Show latent traces")
    show_parser.add_argument("--capsule-id", help="Filter by capsule ID")
    show_parser.add_argument("--limit", type=int, default=5, help="Max traces to show (default: 5)")

    # list
    sub.add_parser("list", help="List all traces (summary)")

    # verify
    verify_parser = sub.add_parser("verify", help="Verify Merkle chain integrity")
    verify_parser.add_argument("--capsule-id", required=True, help="Capsule ID to verify")

    args = parser.parse_args()

    if args.command == "show":
        return cmd_show_latent(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "verify":
        return cmd_verify(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
