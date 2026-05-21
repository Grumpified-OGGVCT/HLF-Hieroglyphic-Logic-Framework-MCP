"""
HLF Gallery Evidence Renderer — Human-readable evidence summaries.

Provides EvidenceSummaryRenderer with static methods for rendering
evidence contracts, media evidence records, dream findings, mission
summaries, evidence lists, and execution traces using Rich formatting.

Usage:
    from hlf_mcp.gallery.evidence_renderer import EvidenceSummaryRenderer

    renderer = EvidenceSummaryRenderer()
    print(renderer.render_evidence_contract(contract))
"""

from __future__ import annotations

import sys
from typing import Any

# ── Windows console encoding fix ────────────────────────────────────────────────
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text
    from rich import box
    from rich.style import Style
    _RICH = True
except ImportError:
    _RICH = False
    Console = None  # type: ignore
    Panel = None  # type: ignore
    Table = None  # type: ignore
    Text = None  # type: ignore
    box = None  # type: ignore
    Style = None  # type: ignore

# These must always resolve — used in f-strings
if _RICH:
    from rich.text import Text as _Text
    _BOLD = "bold"
    _DIM = "dim"
    _CYAN = "cyan"
    _GREEN = "green"
    _YELLOW = "yellow"
    _RED = "red"
    _MAGENTA = "magenta"
    _WHITE = "white"
    _BLUE = "blue"


def _truncate_sha(sha: str, chars: int = 12) -> str:
    """Truncate a sha256 digest for display."""
    if len(sha) <= chars * 2 + 3:
        return sha
    return f"{sha[:chars]}...{sha[-chars:]}"


def _confidence_bar(confidence: float, width: int = 10) -> str:
    """Render a confidence bar with Rich markup."""
    filled = max(1, int(confidence * width))
    empty = width - filled
    if confidence >= 0.8:
        color = "green"
    elif confidence >= 0.5:
        color = "yellow"
    else:
        color = "red"
    if _RICH:
        return f"[{color}]{'█' * filled}{'░' * empty}[/{color}]"
    return f"{'#' * filled}{'-' * empty}"


def _freshness_status(contract: Any) -> tuple[str, str]:
    """Determine freshness status and color from an EvidenceContract."""
    if getattr(contract, "revoked", False):
        return ("REVOKED", "red")
    if getattr(contract, "tombstoned", False):
        return ("TOMBSTONED", "red")
    if getattr(contract, "is_stale", None) and contract.is_stale():
        return ("STALE", "yellow")
    return ("FRESH", "green")


def _trust_tier_color(tier: str) -> str:
    """Return a Rich color for a trust tier."""
    colors = {
        "verified": "green",
        "validated": "green",
        "trusted": "cyan",
        "normalized": "yellow",
        "untrusted": "red",
        "local": "dim",
    }
    return colors.get(tier, "white")


class EvidenceSummaryRenderer:
    """Static methods for rendering evidence summaries with Rich formatting."""

    @staticmethod
    def render_evidence_contract(contract: Any) -> str:
        """Render a human-readable summary of an EvidenceContract.

        Args:
            contract: An EvidenceContract instance (from hlf_mcp.hlf.memory_node).

        Returns:
            A Rich-formatted or plain-text summary string.
        """
        sha = getattr(contract, "sha256", "") or ""
        sha_display = _truncate_sha(sha) if sha else "(no sha256)"
        trust_tier = getattr(contract, "trust_tier", "unknown")
        provenance = getattr(contract, "provenance_grade", "unknown")
        source = getattr(contract, "source_authority_label", "unknown")
        source_file = getattr(contract, "source_file", "")
        collector = getattr(contract, "collector", "")
        collected_at = getattr(contract, "collected_at", "")
        fresh_until = getattr(contract, "fresh_until", None)
        supersedes = getattr(contract, "supersedes_sha256", "")
        confidence = getattr(contract, "confidence", 0.5)
        artifact_form = getattr(contract, "artifact_form", "unknown")
        memory_stratum = getattr(contract, "memory_stratum", "unknown")
        storage_tier = getattr(contract, "storage_tier", "unknown")
        workflow_run_url = getattr(contract, "workflow_run_url", "")

        freshness_label, freshness_color = _freshness_status(contract)
        tier_color = _trust_tier_color(trust_tier)

        if _RICH:
            lines: list[str] = []
            lines.append(f"[bold]SHA256:[/bold] [dim]{sha_display}[/dim]")
            lines.append(
                f"[bold]Trust Tier:[/bold] [{tier_color}]{trust_tier.upper()}[/{tier_color}]  "
                f"[bold]Provenance:[/bold] [cyan]{provenance}[/cyan]"
            )
            lines.append(
                f"[bold]Source:[/bold] [magenta]{source}[/magenta]  "
                f"[bold]Freshness:[/bold] [{freshness_color}]{freshness_label}[/{freshness_color}]"
            )
            lines.append(
                f"[bold]Confidence:[/bold] {_confidence_bar(confidence)} {confidence:.2f}"
            )
            lines.append(
                f"[bold]Artifact Form:[/bold] {artifact_form}  "
                f"[bold]Stratum:[/bold] {memory_stratum}  "
                f"[bold]Storage:[/bold] {storage_tier}"
            )
            if source_file:
                lines.append(f"[bold]Source File:[/bold] [dim]{source_file}[/dim]")
            if collector:
                lines.append(f"[bold]Collector:[/bold] {collector}")
            if collected_at:
                lines.append(f"[bold]Collected At:[/bold] [dim]{collected_at}[/dim]")
            if fresh_until:
                lines.append(f"[bold]Fresh Until:[/bold] [dim]{fresh_until}[/dim]")
            if supersedes:
                lines.append(
                    f"[bold]Supersedes:[/bold] [dim]{_truncate_sha(supersedes)}[/dim]"
                )
            if workflow_run_url:
                lines.append(f"[bold]Workflow:[/bold] [dim]{workflow_run_url}[/dim]")

            panel = Panel(
                "\n".join(lines),
                title=f"[bold cyan]Evidence Contract[/bold cyan]",
                border_style=tier_color,
            )
            return str(panel)

        # Plain text fallback
        lines = [
            f"SHA256: {sha_display}",
            f"Trust Tier: {trust_tier} | Provenance: {provenance}",
            f"Source: {source} | Freshness: {freshness_label}",
            f"Confidence: {confidence:.2f}",
            f"Artifact: {artifact_form} | Stratum: {memory_stratum} | Storage: {storage_tier}",
        ]
        if source_file:
            lines.append(f"Source File: {source_file}")
        if collector:
            lines.append(f"Collector: {collector}")
        if supersedes:
            lines.append(f"Supersedes: {_truncate_sha(supersedes)}")
        return "\n".join(lines)

    @staticmethod
    def render_media_evidence(record: Any) -> str:
        """Render a human-readable summary of a MediaEvidenceRecord.

        Args:
            record: A MediaEvidenceRecord instance (from hlf_mcp.media_evidence).

        Returns:
            A Rich-formatted or plain-text summary string.
        """
        media_type = getattr(record, "media_type", "unknown")
        sha = getattr(record, "sha256", "") or ""
        sha_display = _truncate_sha(sha) if sha else "(no digest)"
        extraction_mode = getattr(record, "extraction_mode", "unknown")
        safety_status = getattr(record, "safety_status", "unknown")
        derived_text = getattr(record, "derived_text", "")
        confidence = getattr(record, "confidence", 1.0)
        artifact_id = getattr(record, "artifact_id", "unknown")
        trust_tier = getattr(record, "trust_tier", "normalized")
        source_path = getattr(record, "source_path", "")
        operator_summary = getattr(record, "operator_summary", "")

        # Safety status color
        if safety_status in ("safe", "clean", "verified", "normalized"):
            safety_color = "green"
        elif safety_status in ("flagged", "warning", "needs_review"):
            safety_color = "yellow"
        else:
            safety_color = "red"

        # Preview derived text (first 200 chars)
        text_preview = derived_text[:200] if derived_text else "(no text)"
        if len(derived_text) > 200:
            text_preview += "..."

        if _RICH:
            lines: list[str] = []
            lines.append(f"[bold]Artifact ID:[/bold] [cyan]{artifact_id}[/cyan]")
            lines.append(f"[bold]SHA256:[/bold] [dim]{sha_display}[/dim]")
            lines.append(
                f"[bold]Type:[/bold] [magenta]{media_type}[/magenta]  "
                f"[bold]Extraction:[/bold] {extraction_mode}"
            )
            lines.append(
                f"[bold]Safety:[/bold] [{safety_color}]{safety_status.upper()}[/{safety_color}]  "
                f"[bold]Trust:[/bold] [{_trust_tier_color(trust_tier)}]{trust_tier.upper()}[/{_trust_tier_color(trust_tier)}]"
            )
            lines.append(
                f"[bold]Confidence:[/bold] {_confidence_bar(confidence)} {confidence:.2f}"
            )
            if source_path:
                lines.append(f"[bold]Source:[/bold] [dim]{source_path}[/dim]")
            if operator_summary:
                lines.append(f"[bold]Operator Summary:[/bold] {operator_summary}")
            lines.append(f"[bold]Derived Text Preview:[/bold]")
            lines.append(f"  [dim]{text_preview}[/dim]")

            panel = Panel(
                "\n".join(lines),
                title=f"[bold cyan]Media Evidence[/bold cyan]",
                border_style="magenta",
            )
            return str(panel)

        # Plain text fallback
        lines = [
            f"Artifact: {artifact_id} | SHA256: {sha_display}",
            f"Type: {media_type} | Extraction: {extraction_mode}",
            f"Safety: {safety_status} | Trust: {trust_tier} | Confidence: {confidence:.2f}",
        ]
        if operator_summary:
            lines.append(f"Summary: {operator_summary}")
        lines.append(f"Text Preview: {text_preview}")
        return "\n".join(lines)

    @staticmethod
    def render_dream_finding(finding: Any) -> str:
        """Render a human-readable summary of a DreamFinding.

        Args:
            finding: A DreamFinding instance (from hlf_mcp.dream_cycle).

        Returns:
            A Rich-formatted or plain-text summary string.
        """
        finding_id = getattr(finding, "finding_id", "unknown")
        title = getattr(finding, "title", "Untitled")
        summary = getattr(finding, "summary", "")
        confidence = getattr(finding, "confidence", 0.5)
        advisory_only = getattr(finding, "advisory_only", True)
        topic = getattr(finding, "topic", "unknown")
        witness_status = getattr(finding, "witness_status", "unknown")
        candidate_actions = getattr(finding, "candidate_actions", [])
        evidence_refs = getattr(finding, "evidence_refs", [])
        media_evidence_present = getattr(finding, "media_evidence_present", False)
        media_types = getattr(finding, "media_types", [])
        created_at = getattr(finding, "created_at", "")

        binding_text = "ADVISORY" if advisory_only else "[bold red]BINDING[/bold red]"
        if not _RICH:
            binding_text = "ADVISORY" if advisory_only else "BINDING"

        if _RICH:
            lines: list[str] = []
            lines.append(f"[bold]ID:[/bold] [dim]{finding_id}[/dim]")
            lines.append(f"[bold]Title:[/bold] {title}")
            lines.append(f"[bold]Topic:[/bold] [cyan]{topic}[/cyan]")
            lines.append(f"[bold]Status:[/bold] {binding_text}  [bold]Witness:[/bold] {witness_status}")
            lines.append(
                f"[bold]Confidence:[/bold] {_confidence_bar(confidence)} {confidence:.2f}"
            )
            if created_at:
                lines.append(f"[bold]Created:[/bold] [dim]{created_at}[/dim]")
            lines.append(f"[bold]Summary:[/bold] {summary}")
            lines.append(
                f"[bold]Evidence Refs:[/bold] {len(evidence_refs)} ref(s)"
            )
            if media_evidence_present and media_types:
                lines.append(
                    f"[bold]Media Types:[/bold] [magenta]{', '.join(media_types)}[/magenta]"
                )
            if candidate_actions:
                lines.append("[bold]Candidate Actions:[/bold]")
                for action in candidate_actions:
                    lines.append(f"  • {action}")

            status_color = "yellow" if advisory_only else "red"
            panel = Panel(
                "\n".join(lines),
                title=f"[bold cyan]Dream Finding[/bold cyan]",
                border_style=status_color,
            )
            return str(panel)

        # Plain text fallback
        lines = [
            f"ID: {finding_id}",
            f"Title: {title} | Topic: {topic}",
            f"Status: {binding_text} | Witness: {witness_status}",
            f"Confidence: {confidence:.2f}",
            f"Summary: {summary}",
            f"Evidence Refs: {len(evidence_refs)}",
        ]
        if candidate_actions:
            lines.append("Candidate Actions:")
            for action in candidate_actions:
                lines.append(f"  - {action}")
        return "\n".join(lines)

    @staticmethod
    def render_mission_summary(mission: dict[str, Any]) -> str:
        """Render a human-readable summary of a mission from InstinctLifecycle.

        Args:
            mission: A mission dictionary from InstinctLifecycle.list_missions().

        Returns:
            A Rich-formatted or plain-text summary string.
        """
        mission_id = mission.get("mission_id", "unknown")
        topic = mission.get("topic", "")
        current_phase = mission.get("current_phase", "unknown")
        sealed = mission.get("sealed", False)
        created_at = mission.get("created_at", "")
        realignment_count = mission.get("realignment_count", 0)
        plan_nodes = mission.get("plan_nodes", 0)
        execution_summary = mission.get("execution_summary", {})

        execution_nodes = execution_summary.get("total_nodes", "?") if execution_summary else "?"
        verification_status = execution_summary.get("verification", "pending") if execution_summary else "pending"

        phase_colors = {
            "specify": "dim",
            "plan": "yellow",
            "execute": "cyan",
            "verify": "magenta",
            "merge": "green",
        }

        if _RICH:
            phase_color = phase_colors.get(current_phase, "white")
            seal_text = "[green]SEALED[/green]" if sealed else "[dim]ACTIVE[/dim]"

            lines: list[str] = []
            lines.append(f"[bold]Mission:[/bold] [cyan]{mission_id}[/cyan]")
            lines.append(f"[bold]Topic:[/bold] {topic}" if topic else "[bold]Topic:[/bold] [dim](none)[/dim]")
            lines.append(
                f"[bold]Phase:[/bold] [{phase_color}]{current_phase.upper()}[/{phase_color}]  "
                f"{seal_text}"
            )
            lines.append(
                f"[bold]Nodes:[/bold] {plan_nodes} planned  |  "
                f"[bold]Executed:[/bold] {execution_nodes}"
            )
            lines.append(
                f"[bold]Verification:[/bold] {verification_status}  "
                f"[bold]Realignments:[/bold] {realignment_count}"
            )
            if created_at:
                lines.append(f"[bold]Created:[/bold] [dim]{created_at}[/dim]")

            return "\n".join(lines)

        # Plain text fallback
        seal_text = "SEALED" if sealed else "ACTIVE"
        lines = [
            f"Mission: {mission_id}",
            f"Topic: {topic or '(none)'}",
            f"Phase: {current_phase} | {seal_text}",
            f"Nodes: {plan_nodes} planned | {execution_nodes} executed",
            f"Verification: {verification_status} | Realignments: {realignment_count}",
        ]
        return "\n".join(lines)

    @staticmethod
    def render_evidence_list(contracts: list[Any]) -> str:
        """Render a table of evidence contract summaries.

        Args:
            contracts: A list of EvidenceContract instances.

        Returns:
            A Rich-formatted or plain-text table string.
        """
        if not contracts:
            if _RICH:
                return str(Panel("[dim]No evidence contracts to display.[/dim]", title="Evidence List"))
            return "No evidence contracts to display."

        if _RICH:
            table = Table(title="Evidence Contracts", box=box.SIMPLE, expand=True)
            table.add_column("SHA256", style="dim")
            table.add_column("Trust Tier")
            table.add_column("Confidence")
            table.add_column("Source")
            table.add_column("Freshness")
            table.add_column("Provenance")

            for c in contracts:
                sha = _truncate_sha(getattr(c, "sha256", "") or "?")
                tier = getattr(c, "trust_tier", "?")
                conf = getattr(c, "confidence", 0.0)
                source = getattr(c, "source_authority_label", "?")
                freshness_label, freshness_color = _freshness_status(c)
                provenance = getattr(c, "provenance_grade", "?")

                table.add_row(
                    sha,
                    f"[{_trust_tier_color(tier)}]{tier}[/{_trust_tier_color(tier)}]",
                    f"{_confidence_bar(conf, 5)} {conf:.2f}",
                    source,
                    f"[{freshness_color}]{freshness_label}[/{freshness_color}]",
                    provenance,
                )
            return str(table)

        # Plain text fallback
        header = f"{'SHA256':<28} {'Tier':<12} {'Conf':>6} {'Source':<12} {'Status':<12} {'Provenance':<14}"
        lines = [header, "-" * len(header)]
        for c in contracts:
            sha = _truncate_sha(getattr(c, "sha256", "") or "?", 8)
            tier = getattr(c, "trust_tier", "?")
            conf = getattr(c, "confidence", 0.0)
            source = getattr(c, "source_authority_label", "?")
            freshness_label, _ = _freshness_status(c)
            provenance = getattr(c, "provenance_grade", "?")
            lines.append(
                f"{sha:<28} {tier:<12} {conf:>6.2f} {source:<12} {freshness_label:<12} {provenance:<14}"
            )
        return "\n".join(lines)

    @staticmethod
    def render_execution_trace(trace: list[dict[str, Any]]) -> str:
        """Render a timeline-style execution trace with status indicators.

        Args:
            trace: A list of execution trace dicts (each with node_id, status, etc.).

        Returns:
            A Rich-formatted or plain-text timeline string.
        """
        if not trace:
            if _RICH:
                return str(Panel("[dim]No execution trace entries.[/dim]", title="Execution Trace"))
            return "No execution trace entries."

        status_icons = {
            "success": "✅",
            "completed": "✅",
            "passed": "✅",
            "failed": "❌",
            "error": "❌",
            "running": "🔄",
            "pending": "⏳",
            "skipped": "⏭️",
            "blocked": "🚫",
        }

        status_colors = {
            "success": "green",
            "completed": "green",
            "passed": "green",
            "failed": "red",
            "error": "red",
            "running": "yellow",
            "pending": "dim",
            "skipped": "dim",
            "blocked": "red",
        }

        if _RICH:
            lines: list[str] = []
            for i, step in enumerate(trace):
                node_id = step.get("node_id", f"step-{i}")
                status = step.get("status", "unknown")
                agent_id = step.get("agent_id", "?")
                message = step.get("message", step.get("error", ""))
                duration = step.get("duration", step.get("elapsed", 0))

                icon = status_icons.get(status, "❓")
                color = status_colors.get(status, "white")

                time_str = f" ({duration:.1f}s)" if duration else ""
                msg_suffix = f": {message}" if message else ""

                lines.append(
                    f"[{color}]{icon} [bold]{node_id}[/bold][/{color}]  "
                    f"[dim]{agent_id}[/dim]  "
                    f"[{color}]{status.upper()}[/{color}]{time_str}{msg_suffix}"
                )

            panel = Panel(
                "\n".join(lines),
                title=f"[bold cyan]Execution Trace[/bold cyan] ({len(trace)} steps)",
                border_style="cyan",
            )
            return str(panel)

        # Plain text fallback
        lines: list[str] = []
        for i, step in enumerate(trace):
            node_id = step.get("node_id", f"step-{i}")
            status = step.get("status", "unknown")
            agent_id = step.get("agent_id", "?")
            icon = status_icons.get(status, "?")
            lines.append(f"  {icon} {node_id} [{agent_id}] → {status.upper()}")
        return "\n".join(lines)
