"""
HLF Swarm Orchestrator — multi-agent coordination via HLF.

Coordinates a 3-agent stack (Planner → Executor → Verifier) using the
live HLF translation → compilation pipeline. Every phase invokes
language_to_hlf + compile — zero simulation.

When an HLFLLMBridge is provided, the planner and executor phases route
through governed Ollama LLM calls instead of the heuristic translator,
producing genuinely intelligent HLF rather than pattern-matched output.

Integrates swarm_observer for progress events, witness_governance for
trust scoring, and formal_verifier for inter-agent message validation.
3 well-informed agents outperforms 4-5 agent swarms of smaller skill sets.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
import re
from typing import Any, TYPE_CHECKING

from hlf_mcp.hlf import HLFCompiler, language_to_hlf, hlf_source_to_english
from hlf_mcp.hlf.compiler import CompileError
from hlf_mcp.hlf.formal_verifier import FormalVerifier
from hlf_mcp.hlf.swarm_observer import SwarmObserver
from hlf_mcp.hlf.swarm_consensus import SwarmLedger, VotePosition, QuorumType
from hlf_mcp.hlf.witness_governance import WitnessGovernance, WitnessObservation

if TYPE_CHECKING:
    from hlf_mcp.hlf.hlf_llm_bridge import HLFLLMBridge, LLMCallResult

logger = logging.getLogger(__name__)


@dataclass
class Agent:
    """An agent participant in the swarm."""

    agent_id: str
    role: str  # e.g., "planner", "executor", "verifier", "reviewer"
    capabilities: list[str] = field(default_factory=list)


@dataclass
class SwarmPhase:
    """A single phase in the swarm workflow."""

    phase_id: str
    agent_id: str
    role: str
    action: str  # description of what the agent did
    hlf_input: str = ""
    hlf_output: str = ""
    status: str = "pending"  # pending | running | complete | error
    metrics: dict[str, Any] = field(default_factory=dict)
    started_ns: int = 0
    finished_ns: int = 0


@dataclass
class SwarmResult:
    """Result of a swarm execution."""

    swarm_id: str
    task_id: str
    final_status: str
    phases: list[SwarmPhase]
    final_hlf: str
    final_nl: str
    total_tokens: int
    total_time_ms: float
    compile_success: bool
    scope_score: float
    thoroughness_score: float


class SwarmOrchestrator:
    """Coordinate a 3-agent swarm (Planner→Executor→Verifier) via live HLF pipeline.

    Supports two operational modes:
    - Heuristic (default): uses language_to_hlf for NL→HLF translation
    - LLM-backed: uses HLFLLMBridge → Ollama for genuinely intelligent HLF generation

    Every phase compiles and verifies. Zero simulation.
    witness_governance scores each phase's trustworthiness;
    formal_verifier validates inter-agent HLF messages.
    """

    def __init__(
        self,
        observer: SwarmObserver | None = None,
        governance: WitnessGovernance | None = None,
        verifier: FormalVerifier | None = None,
        llm_bridge: HLFLLMBridge | None = None,
        consensus: SwarmLedger | None = None,
    ) -> None:
        self.compiler = HLFCompiler(strict_align=True)
        self.governance = governance or WitnessGovernance()
        self.verifier = verifier or FormalVerifier()
        self.observer = observer or SwarmObserver()
        self.llm_bridge = llm_bridge
        self.consensus = consensus  # optional SwarmLedger for delegation/dissent/vote tracking

    # ── Has LLM bridge? ─────────────────────────────────────────────────────

    @property
    def has_llm(self) -> bool:
        """True if an LLM bridge is configured for intelligent generation."""
        return self.llm_bridge is not None

    # ── Live helpers — replace the donor's _expand_hlf / _enrich_hlf ──────────

    def _emit(
        self,
        swarm_id: str,
        phase_id: str,
        agent_id: str,
        role: str,
        event_type: str,
        message: str = "",
        payload: dict[str, Any] | None = None,
    ) -> None:
        """Emit a progress event via the observer."""
        self.observer.emit(
            swarm_id=swarm_id,
            phase_id=phase_id,
            agent_id=agent_id,
            role=role,
            event_type=event_type,
            message=message,
            payload=payload or {},
        )

    def _translate(self, prompt: str, role: str) -> str:
        """Invoke language_to_hlf → compile to produce verified HLF source."""
        try:
            source = language_to_hlf(prompt, language="en", version="3")
        except Exception as exc:
            raise RuntimeError(f"{role}: language_to_hlf failed: {exc}") from exc

        if not source or not source.strip():
            raise RuntimeError(f"{role}: language_to_hlf returned empty source")

        # Compile for validation proof
        ast_result = self.compiler.compile(source)
        if ast_result is None:
            raise RuntimeError(f"{role}: compilation returned None AST")
        if ast_result.get("status") not in (None, "ok"):
            raise RuntimeError(
                f"{role}: compile error: {ast_result.get('status', 'unknown')}"
            )
        return source

    async def _llm_translate(self, prompt: str, role: str, system: str = "") -> str:
        """Translate via LLM bridge (async, governed). Returns compiled HLF source."""
        if not self.llm_bridge:
            raise RuntimeError(f"{role}: no LLM bridge configured")

        result: LLMCallResult = await self.llm_bridge.send_with_fallback(
            prompt, role=role, system=system
        )

        hlf_source = result.hlf_output
        if not hlf_source or not hlf_source.strip():
            raise RuntimeError(f"{role}: LLM returned empty HLF")

        # Validate the LLM output compiles
        try:
            ast_result = self.compiler.compile(hlf_source)
            if ast_result is None:
                raise RuntimeError(f"{role}: LLM output compiled to None AST")
            if ast_result.get("status") not in (None, "ok"):
                raise RuntimeError(
                    f"{role}: LLM output compile error: {ast_result.get('status', 'unknown')}"
                )
        except CompileError as exc:
            # Try to fix common LLM mistakes: missing Ω, @TAG instead of [TAG], etc.
            fixed = self._fix_llm_hlf(hlf_source)
            if fixed != hlf_source:
                ast_result = self.compiler.compile(fixed)
                if ast_result is not None and ast_result.get("status") in (None, "ok"):
                    return fixed
            raise RuntimeError(f"{role}: LLM output failed compilation: {exc}") from exc

        return hlf_source

    @staticmethod
    def _fix_llm_hlf(hlf_source: str) -> str:
        """Apply common fixes to LLM-generated HLF that may have syntax issues."""
        fixed = hlf_source.strip()

        # Ensure [HLF-v3] header
        if not fixed.startswith("[HLF-v3]"):
            fixed = "[HLF-v3]\n" + fixed

        # Fix @TAG → [TAG] (common LLM mistake)
        fixed_lines = []
        for line in fixed.split("\n"):
            stripped = line.strip()
            # Skip comment lines and terminator
            if stripped.startswith("#") or stripped == "Ω":
                fixed_lines.append(line)
                continue
            # Fix @TAG → [TAG] in glyph statements (regex catch-all)
            if any(stripped.startswith(g) for g in ("⌘", "Δ", "Ж", "∇", "Σ", "⨝", "⌂", "⊎", "⩕")):
                line = re.sub(r"@([A-Z][A-Z0-9_]*)", r"[\1]", line)
            fixed_lines.append(line)

        fixed = "\n".join(fixed_lines)

        # Ensure Ω terminator exists
        if not fixed.rstrip().endswith("Ω"):
            fixed = fixed.rstrip() + "\nΩ"

        return fixed

    def _govern(
        self, agent_id: str, phase_id: str, compile_success: bool, metrics: dict[str, Any]
    ) -> dict[str, Any]:
        """Record a witness observation and return trust snapshot."""
        observation = WitnessObservation(
            witness_id="swarm_orchestrator",
            subject_agent_id=agent_id,
            category=f"swarm_phase:{phase_id}",
            severity="info" if compile_success else "warning",
            confidence=0.95,
            goal_id=phase_id,
            details=metrics,
        )
        snapshot = self.governance.record_observation(observation)
        return snapshot.to_dict()

    # ── Phase helpers (shared between sync and async paths) ──────────────────

    def _build_verification_phase(
        self,
        phase: SwarmPhase,
        hlf_executed: str,
        description: str,
        swarm_id: str,
    ) -> None:
        """Populate verification phase results (compile + formal verify + NL)."""
        ver_results: list[dict[str, Any]] = []
        compile_ast: dict[str, Any] = {}
        try:
            compile_result = self.compiler.compile(hlf_executed)
            compile_ok = compile_result is not None and compile_result.get("status") in (None, "ok")
            compile_ast = compile_result.get("ast", {}) if compile_result else {}
        except CompileError:
            compile_ok = False
            compile_result = {"status": "compile_error"}

        try:
            if compile_ast:
                report = self.verifier.verify_ast(compile_ast)
                ver_results = report.to_dict().get("results", [])
        except Exception:
            ver_results = []

        gas_estimate = int(compile_result.get("gas_estimate", 0)) if compile_result else 0
        lint_errors = len([r for r in ver_results if r.get("severity") == "error"])

        try:
            nl_summary = hlf_source_to_english(hlf_executed) if hlf_executed else description
        except Exception:
            nl_summary = f"HLF plan ({len(hlf_executed.split())} tokens, compile={'OK' if compile_ok else 'FAIL'})"

        phase.hlf_output = hlf_executed
        phase.finished_ns = time.perf_counter_ns()
        phase.status = "complete"
        phase.metrics = {
            "hlf_tokens": len(hlf_executed.split()),
            "compile_success": compile_ok,
            "lint_errors": lint_errors,
            "gas_estimate": gas_estimate,
            "verification_checks": len(ver_results),
            "time_ms": (phase.finished_ns - phase.started_ns) / 1_000_000,
            "nl_summary": nl_summary,
        }
        trust = self._govern(phase.agent_id, phase.phase_id, compile_ok, phase.metrics)
        phase.metrics["trust"] = trust
        self._emit(
            swarm_id, phase.phase_id, phase.agent_id, phase.role,
            "complete",
            f"Verifier: compile={'OK' if compile_ok else 'FAIL'}, {lint_errors} errors, "
            f"gas={gas_estimate}, {len(ver_results)} checks",
            phase.metrics,
        )

    def _aggregate_result(
        self,
        swarm_id: str,
        description: str,
        phases: list[SwarmPhase],
        hlf_executed: str,
        nl_summary: str,
        total_tokens: int,
        overall_start_ns: int,
    ) -> SwarmResult:
        """Build the final SwarmResult from collected phases."""
        total_time_ns = time.perf_counter_ns() - overall_start_ns
        compile_success_final = all(p.metrics.get("compile_success", False) for p in phases)
        scope_score = sum(
            p.metrics.get("compile_success", 0) for p in phases
        ) / max(len(phases), 1)
        thoroughness = (
            scope_score * 0.5
            + (1.0 if compile_success_final else 0.0) * 0.3
            + (min(total_tokens, 500) / 500) * 0.2
        )

        # ── Consensus tracking (when SwarmLedger is configured) ──────────────
        if self.consensus is not None:
            from hlf_mcp.hlf.swarm_consensus import VotePosition, QuorumType
            task_id = hashlib.sha256(description.encode()).hexdigest()[:16]
            # Record each phase as a delegation
            for phase in phases:
                self.consensus.delegate(
                    from_agent="orchestrator",
                    to_agent=phase.agent_id,
                    task=f"{phase.action}: {description[:120]}",
                    priority=1,
                )
            # Record swarm outcome as a vote
            prop = self.consensus.propose(
                title=f"Swarm result: {description[:80]}",
                description=f"Task {task_id}: {compile_success_final}",
                proposed_by="orchestrator",
                quorum=QuorumType.SIMPLE_MAJORITY,
            )
            position = VotePosition.APPROVE if compile_success_final else VotePosition.REJECT
            self.consensus.vote(
                prop.proposal_id,
                "orchestrator",
                position,
                reason=f"Compile {'OK' if compile_success_final else 'FAILED'}, "
                       f"{len(phases)} phases, {total_tokens} tokens",
            )
            self.consensus.resolve(prop.proposal_id)

        return SwarmResult(
            swarm_id=swarm_id,
            task_id=hashlib.sha256(description.encode()).hexdigest()[:16],
            final_status="ok" if compile_success_final else "compile_error",
            phases=phases,
            final_hlf=hlf_executed,
            final_nl=nl_summary,
            total_tokens=total_tokens,
            total_time_ms=total_time_ns / 1_000_000,
            compile_success=compile_success_final,
            scope_score=scope_score,
            thoroughness_score=thoroughness,
        )

    # ── 3-agent stack (primary per plan: 3 > 4-5) ──────────────────────────────

    def run(self, description: str, language: str = "english") -> SwarmResult:
        """Run the 3-agent swarm (heuristic): Planner → Executor → Verifier.

        Uses the heuristic language_to_hlf translator for speed.
        For LLM-backed intelligent generation, use run_with_llm().
        """
        swarm_id = hashlib.sha256(
            f"3stack:{description}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        phases: list[SwarmPhase] = []
        overall_start = time.perf_counter_ns()
        total_tokens = 0

        # ── Phase 1: Planner ───────────────────────────────────────────────────
        p1 = SwarmPhase(
            phase_id="plan",
            agent_id="planner",
            role="planner",
            action="Translate NLP goal to structured HLF plan",
        )
        p1.started_ns = time.perf_counter_ns()
        p1.status = "running"
        self._emit(swarm_id, "plan", "planner", "planner",
                   "started", "Planner translating task to HLF")

        try:
            hlf_plan = self._translate(description, "planner")
            compile_ok = True
        except RuntimeError as exc:
            hlf_plan = f"; Planner error: {exc}\nΩ"
            compile_ok = False

        p1.hlf_output = hlf_plan
        p1.finished_ns = time.perf_counter_ns()
        p1.status = "complete"
        p1.metrics = {
            "hlf_tokens": len(hlf_plan.split()),
            "compile_success": compile_ok,
            "time_ms": (p1.finished_ns - p1.started_ns) / 1_000_000,
        }
        total_tokens += p1.metrics["hlf_tokens"]
        trust = self._govern("planner", "plan", compile_ok, p1.metrics)
        p1.metrics["trust"] = trust
        self._emit(swarm_id, "plan", "planner", "planner",
                   "complete",
                   f"Planner: {len(hlf_plan.split())} tokens, compile={'OK' if compile_ok else 'FAIL'}",
                   p1.metrics)
        phases.append(p1)

        # ── Phase 2: Executor ──────────────────────────────────────────────────
        p2 = SwarmPhase(
            phase_id="execute",
            agent_id="executor",
            role="executor",
            action="Enrich HLF plan with execution parameters and constraints",
            hlf_input=hlf_plan,
        )
        p2.started_ns = time.perf_counter_ns()
        p2.status = "running"
        self._emit(swarm_id, "execute", "executor", "executor",
                   "started", "Executor enriching HLF with execution details")

        hlf_executed = hlf_plan
        compile_ok = False
        try:
            plan_ast = self.compiler.compile(hlf_plan)
            if plan_ast and plan_ast.get("ast"):
                enriched_lines = hlf_plan.rstrip().split("\n")
                omega_idx = None
                for i, line in enumerate(enriched_lines):
                    if line.strip() == "Ω":
                        omega_idx = i
                        break
                if omega_idx is not None:
                    # Generate real HLF enrichment via translator, not hardcoded strings
                    exec_task = f"execute the plan: {description}"
                    try:
                        exec_hlf = language_to_hlf(exec_task)
                        exec_lines = exec_hlf.strip().split("\n")
                        # Extract body lines (skip [HLF-v3] header, comment, and trailing Ω)
                        body = [l for l in exec_lines if l.strip() and l.strip() != "Ω"
                                and not l.strip().startswith("[HLF-v3]")
                                and not l.strip().startswith("#")]
                        enriched_lines = enriched_lines[:omega_idx] + body + enriched_lines[omega_idx:]
                    except Exception:
                        enriched_lines = enriched_lines[:omega_idx] + [
                            f'SET task_input = "{description[:60]}"',
                            'Ж [ASSERT] condition="output conforms to spec"',
                        ] + enriched_lines[omega_idx:]
                    hlf_executed = "\n".join(enriched_lines)
                    # Recompile to verify enriched HLF is valid
                    try:
                        self.compiler.compile(hlf_executed)
                        compile_ok = True
                    except CompileError:
                        compile_ok = False
                else:
                    compile_ok = True  # No Ω found, treat plan as-is
        except CompileError:
            compile_ok = False

        p2.hlf_output = hlf_executed
        p2.finished_ns = time.perf_counter_ns()
        p2.status = "complete"
        p2.metrics = {
            "hlf_tokens": len(hlf_executed.split()),
            "compile_success": compile_ok,
            "time_ms": (p2.finished_ns - p2.started_ns) / 1_000_000,
            "added_lines": hlf_executed.count("\n") - hlf_plan.count("\n"),
        }
        total_tokens += p2.metrics["hlf_tokens"]
        trust = self._govern("executor", "execute", compile_ok, p2.metrics)
        p2.metrics["trust"] = trust
        self._emit(swarm_id, "execute", "executor", "executor",
                   "complete",
                   f"Executor: {p2.metrics['added_lines']} lines added, compile={'OK' if compile_ok else 'FAIL'}",
                   p2.metrics)
        phases.append(p2)

        # ── Phase 3: Verifier ──────────────────────────────────────────────────
        p3 = SwarmPhase(
            phase_id="verify",
            agent_id="verifier",
            role="verifier",
            action="Validate HLF, verify specs, produce NL summary",
            hlf_input=hlf_executed,
        )
        p3.started_ns = time.perf_counter_ns()
        p3.status = "running"
        self._emit(swarm_id, "verify", "verifier", "verifier",
                   "started", "Verifier validating final HLF")
        self._build_verification_phase(p3, hlf_executed, description, swarm_id)
        phases.append(p3)
        total_tokens += p3.metrics.get("hlf_tokens", len(hlf_executed.split()))

        nl_summary = p3.metrics.get("nl_summary", p3.role)
        if not isinstance(nl_summary, str):
            try:
                nl_summary = hlf_source_to_english(hlf_executed) if hlf_executed else description
            except Exception:
                nl_summary = description

        return self._aggregate_result(
            swarm_id, description, phases, hlf_executed, nl_summary,
            total_tokens, overall_start,
        )

    # ── 3-agent LLM-backed (async) ────────────────────────────────────────────

    async def run_with_llm(self, description: str) -> SwarmResult:
        """Run the 3-agent swarm WITH LLM backing: Planner → Executor → Verifier.

        Planner and Executor route through governed Ollama LLM calls,
        producing genuinely intelligent HLF. Verifier runs formal verification.
        """
        if not self.llm_bridge:
            raise RuntimeError("run_with_llm() requires an HLFLLMBridge")

        swarm_id = hashlib.sha256(
            f"3stack-llm:{description}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        phases: list[SwarmPhase] = []
        overall_start = time.perf_counter_ns()
        total_tokens = 0

        # ── Phase 1: Planner (LLM-backed) ──────────────────────────────────────
        p1 = SwarmPhase(
            phase_id="plan",
            agent_id="planner",
            role="planner",
            action="LLM: Plan task → structured HLF-v3 with glyph syntax",
        )
        p1.started_ns = time.perf_counter_ns()
        p1.status = "running"
        self._emit(swarm_id, "plan", "planner", "planner",
                   "started", "Planner (LLM) translating task to HLF")

        plan_prompt = (
            f"Translate this task into an HLF-v3 plan:\n\n{description}\n\n"
            f"Use Unicode glyphs: ⌘ [GOAL], Δ for actions, Ж [CONSTRAINT], "
            f"∇ for parameters, Σ for summary. Use [TAG] square-bracket tags (NOT @TAG). "
            f"Always include header [HLF-v3] and terminator Ω."
        )

        try:
            hlf_plan = await self._llm_translate(plan_prompt, "planner")
            compile_ok = True
        except RuntimeError as exc:
            logger.warning("Planner LLM call failed: %s — falling back to heuristic", exc)
            try:
                hlf_plan = self._translate(description, "planner")
                compile_ok = True
            except RuntimeError:
                hlf_plan = f"; Planner error: {exc}\nΩ"
                compile_ok = False

        p1.hlf_output = hlf_plan
        p1.finished_ns = time.perf_counter_ns()
        p1.status = "complete"
        p1.metrics = {
            "hlf_tokens": len(hlf_plan.split()),
            "compile_success": compile_ok,
            "time_ms": (p1.finished_ns - p1.started_ns) / 1_000_000,
            "source": "llm",
        }
        total_tokens += p1.metrics["hlf_tokens"]
        trust = self._govern("planner", "plan", compile_ok, p1.metrics)
        p1.metrics["trust"] = trust
        self._emit(swarm_id, "plan", "planner", "planner",
                   "complete",
                   f"Planner (LLM): {len(hlf_plan.split())} tokens, compile={'OK' if compile_ok else 'FAIL'}",
                   p1.metrics)
        phases.append(p1)

        # ── Phase 2: Executor (LLM-backed) ─────────────────────────────────────
        p2 = SwarmPhase(
            phase_id="execute",
            agent_id="executor",
            role="executor",
            action="LLM: Enrich HLF with execution details, assertions, routing",
            hlf_input=hlf_plan,
        )
        p2.started_ns = time.perf_counter_ns()
        p2.status = "running"
        self._emit(swarm_id, "execute", "executor", "executor",
                   "started", "Executor (LLM) enriching HLF")

        exec_prompt = (
            f"Enrich this HLF plan with execution details:\n\n{hlf_plan}\n\n"
            f"Original task: {description}\n\n"
            f"Add: SET bindings for inputs, Ж [ASSERT] for correctness, "
            f"⌘ [ROUTE] for delegation, concrete ∇ parameter values. "
            f"Keep all existing structure. Use square-bracket [TAG] tags. "
            f"Terminate with Ω."
        )

        try:
            hlf_executed = await self._llm_translate(exec_prompt, "executor")
            compile_ok = True
        except RuntimeError as exc:
            logger.warning("Executor LLM call failed: %s — using plan as-is", exc)
            hlf_executed = hlf_plan
            compile_ok = False

        p2.hlf_output = hlf_executed
        p2.finished_ns = time.perf_counter_ns()
        p2.status = "complete"
        p2.metrics = {
            "hlf_tokens": len(hlf_executed.split()),
            "compile_success": compile_ok,
            "time_ms": (p2.finished_ns - p2.started_ns) / 1_000_000,
            "added_lines": hlf_executed.count("\n") - hlf_plan.count("\n"),
            "source": "llm",
        }
        total_tokens += p2.metrics["hlf_tokens"]
        trust = self._govern("executor", "execute", compile_ok, p2.metrics)
        p2.metrics["trust"] = trust
        self._emit(swarm_id, "execute", "executor", "executor",
                   "complete",
                   f"Executor (LLM): {p2.metrics['added_lines']} lines added, compile={'OK' if compile_ok else 'FAIL'}",
                   p2.metrics)
        phases.append(p2)

        # ── Phase 3: Verifier (formal — same as heuristic path) ────────────────
        p3 = SwarmPhase(
            phase_id="verify",
            agent_id="verifier",
            role="verifier",
            action="Validate HLF, verify specs, produce NL summary",
            hlf_input=hlf_executed,
        )
        p3.started_ns = time.perf_counter_ns()
        p3.status = "running"
        self._emit(swarm_id, "verify", "verifier", "verifier",
                   "started", "Verifier validating final HLF")
        self._build_verification_phase(p3, hlf_executed, description, swarm_id)
        phases.append(p3)
        total_tokens += p3.metrics.get("hlf_tokens", len(hlf_executed.split()))

        try:
            nl_summary = hlf_source_to_english(hlf_executed)
        except Exception:
            nl_summary = description

        return self._aggregate_result(
            swarm_id, description, phases, hlf_executed, nl_summary,
            total_tokens, overall_start,
        )

    # ── 5-agent swarm (secondary: more overhead, lower returns per plan) ────────

    def run_5_agent_swarm(self, description: str) -> SwarmResult:
        """Run 5-agent swarm (heuristic): Planner→Researcher→Executor→Reviewer→Verifier.

        For LLM-backed 5-agent, use run_5_with_llm().
        """
        swarm_id = hashlib.sha256(
            f"5swarm:{description}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        phases: list[SwarmPhase] = []
        overall_start = time.perf_counter_ns()
        current_hlf = ""
        total_tokens = 0

        roles_sequence = [
            ("planner", "plan", "Translate NLP goal to structured HLF plan"),
            ("researcher", "research", "Enrich HLF with contextual parameters and constraints"),
            ("executor", "execute", "Expand HLF with execution details and actions"),
            ("reviewer", "review", "Review HLF for completeness and correctness, refine if needed"),
            ("verifier", "verify", "Final compile, verify specs, produce NL summary"),
        ]

        for agent_id, phase_id, action in roles_sequence:
            phase = SwarmPhase(
                phase_id=phase_id,
                agent_id=agent_id,
                role=agent_id,
                action=action,
                hlf_input=current_hlf,
            )
            phase.started_ns = time.perf_counter_ns()
            phase.status = "running"
            self._emit(swarm_id, phase_id, agent_id, agent_id,
                       "started", f"{agent_id} starting: {action}")

            if agent_id == "planner":
                prompt = (
                    f"Plan this task in HLF with clear structure:\n{description}\n\n"
                    f"Use HLF-v3 glyph syntax: ⌘ [TAG] for commands, Δ for analysis, "
                    f"Ж for constraints, ∇ for parameters, Σ for summary. Use [TAG] style tags. "
                    f"Terminate with Ω."
                )
            elif agent_id == "researcher":
                context = description if not current_hlf else current_hlf
                prompt = (
                    f"Enrich the following HLF with research context, parameters, "
                    f"and domain-specific constraints.\n\n{context}\n\n"
                    f"Add ∇ parameters, Ж [CONSTRAINT] directives, ⌂ [SOURCE] references. "
                    f"Keep all existing structure. Use glyph syntax. Terminate with Ω."
                )
            elif agent_id == "executor":
                prompt = (
                    f"Execute this HLF plan by adding concrete actions, values, "
                    f"and routing.\n\n{current_hlf}\n\n"
                    f"Original task: {description}\n\n"
                    f"Add Ж [ASSERT] conditions, ⌘ [ROUTE] directives, ⌘ [DELEGATE] if needed, "
                    f"concrete ∇ parameter values. Terminate with Ω."
                )
            elif agent_id == "reviewer":
                prompt = (
                    f"Review and refine this HLF for correctness and completeness.\n\n"
                    f"{current_hlf}\n\n"
                    f"Original task: {description}\n\n"
                    f"Fix any issues, add Ж [ASSERT] for correctness, ensure all "
                    f"steps are actionable, verify Ж [CONSTRAINT] is respected. "
                    f"Output only the corrected HLF using glyph syntax. Terminate with Ω."
                )
            else:  # verifier
                self._build_verification_phase(phase, current_hlf, description, swarm_id)
                phases.append(phase)
                total_time_ns = time.perf_counter_ns() - overall_start
                try:
                    nl_summary = hlf_source_to_english(current_hlf) if current_hlf else description
                except Exception:
                    nl_summary = "HLF plan (verification complete)"
                return SwarmResult(
                    swarm_id=swarm_id,
                    task_id=hashlib.sha256(description.encode()).hexdigest()[:16],
                    final_status="ok" if phase.metrics.get("compile_success") else "compile_error",
                    phases=phases,
                    final_hlf=current_hlf,
                    final_nl=nl_summary,
                    total_tokens=total_tokens + len(current_hlf.split()),
                    total_time_ms=total_time_ns / 1_000_000,
                    compile_success=bool(phase.metrics.get("compile_success")),
                    scope_score=1.0 if phase.metrics.get("compile_success") else 0.0,
                    thoroughness_score=0.7 if phase.metrics.get("compile_success") else 0.3,
                )

            # Non-verifier phases: translate via live pipeline
            try:
                current_hlf = self._translate(prompt, agent_id)
                compile_ok = True
            except RuntimeError as exc:
                current_hlf = f"; {agent_id} error: {exc}\nΩ"
                compile_ok = False

            phase.hlf_output = current_hlf
            phase.finished_ns = time.perf_counter_ns()
            phase.status = "complete"
            phase.metrics = {
                "hlf_tokens": len(current_hlf.split()),
                "compile_success": compile_ok,
                "time_ms": (phase.finished_ns - phase.started_ns) / 1_000_000,
            }
            total_tokens += phase.metrics["hlf_tokens"]
            trust = self._govern(agent_id, phase_id, compile_ok, phase.metrics)
            phase.metrics["trust"] = trust
            self._emit(swarm_id, phase_id, agent_id, agent_id,
                       "complete",
                       f"{agent_id}: {len(current_hlf.split())} tokens, compile={'OK' if compile_ok else 'FAIL'}",
                       phase.metrics)
            phases.append(phase)

        # Fallback
        total_time_ns = time.perf_counter_ns() - overall_start
        return SwarmResult(
            swarm_id=swarm_id,
            task_id=hashlib.sha256(description.encode()).hexdigest()[:16],
            final_status="incomplete",
            phases=phases,
            final_hlf=current_hlf,
            final_nl="",
            total_tokens=total_tokens,
            total_time_ms=total_time_ns / 1_000_000,
            compile_success=False,
            scope_score=0.0,
            thoroughness_score=0.0,
        )

    # ── 5-agent LLM-backed (async) ────────────────────────────────────────────

    async def run_5_with_llm(self, description: str) -> SwarmResult:
        """Run 5-agent swarm WITH LLM backing: Planner→Researcher→Executor→Reviewer→Verifier.

        All non-verifier phases route through governed Ollama LLM calls.
        """
        if not self.llm_bridge:
            raise RuntimeError("run_5_with_llm() requires an HLFLLMBridge")

        swarm_id = hashlib.sha256(
            f"5swarm-llm:{description}:{time.time_ns()}".encode()
        ).hexdigest()[:16]

        phases: list[SwarmPhase] = []
        overall_start = time.perf_counter_ns()
        current_hlf = ""
        total_tokens = 0

        roles_prompts: list[tuple[str, str, str, str]] = [
            ("planner", "plan", "LLM: Plan task → structured HLF-v3",
             f"Translate this task into an HLF-v3 plan:\n\n{description}\n\n"
             f"Use glyphs: ⌘ [GOAL], Δ for actions, Ж [CONSTRAINT], "
             f"∇ parameters, Σ summary. Square-bracket [TAG] tags only. "
             f"Header [HLF-v3], terminator Ω."),
            ("researcher", "research", "LLM: Enrich with research context and params",
             f"Enrich this HLF with research context, domain params, "
             f"and constraints:\n\n{{current_hlf}}\n\n"
             f"Original: {description}\n\n"
             f"Add ∇ parameters, Ж [CONSTRAINT], ⌂ [SOURCE] references. "
             f"Keep existing structure. Square-bracket [TAG] tags. Terminate with Ω."),
            ("executor", "execute", "LLM: Add concrete actions, routing, assertions",
             f"Execute this HLF plan with concrete actions and routing:\n\n"
             f"{{current_hlf}}\n\n"
             f"Original: {description}\n\n"
             f"Add Ж [ASSERT], ⌘ [ROUTE], ⌘ [DELEGATE], concrete ∇ values. "
             f"Square-bracket [TAG] tags. Terminate with Ω."),
            ("reviewer", "review", "LLM: Review and refine for correctness",
             f"Review and refine this HLF for correctness:\n\n"
             f"{{current_hlf}}\n\n"
             f"Original: {description}\n\n"
             f"Fix issues, add Ж [ASSERT] for correctness, ensure actionable steps. "
             f"Square-bracket [TAG] tags. Terminate with Ω."),
        ]

        for agent_id, phase_id, action, prompt_template in roles_prompts:
            phase = SwarmPhase(
                phase_id=phase_id,
                agent_id=agent_id,
                role=agent_id,
                action=action,
                hlf_input=current_hlf,
            )
            phase.started_ns = time.perf_counter_ns()
            phase.status = "running"
            self._emit(swarm_id, phase_id, agent_id, agent_id,
                       "started", f"{agent_id} (LLM) starting: {action}")

            prompt = prompt_template.replace("{current_hlf}", current_hlf or description)

            try:
                current_hlf = await self._llm_translate(prompt, agent_id)
                compile_ok = True
            except RuntimeError as exc:
                logger.warning("%s LLM failed: %s — falling back", agent_id, exc)
                try:
                    current_hlf = self._translate(prompt, agent_id)
                    compile_ok = True
                except RuntimeError:
                    current_hlf = f"; {agent_id} error: {exc}\nΩ"
                    compile_ok = False

            phase.hlf_output = current_hlf
            phase.finished_ns = time.perf_counter_ns()
            phase.status = "complete"
            phase.metrics = {
                "hlf_tokens": len(current_hlf.split()),
                "compile_success": compile_ok,
                "time_ms": (phase.finished_ns - phase.started_ns) / 1_000_000,
                "source": "llm",
            }
            total_tokens += phase.metrics["hlf_tokens"]
            trust = self._govern(agent_id, phase_id, compile_ok, phase.metrics)
            phase.metrics["trust"] = trust
            self._emit(swarm_id, phase_id, agent_id, agent_id,
                       "complete",
                       f"{agent_id} (LLM): {len(current_hlf.split())} tokens, compile={'OK' if compile_ok else 'FAIL'}",
                       phase.metrics)
            phases.append(phase)

        # Verifier phase
        vphase = SwarmPhase(
            phase_id="verify",
            agent_id="verifier",
            role="verifier",
            action="Validate HLF, verify specs, produce NL summary",
            hlf_input=current_hlf,
        )
        vphase.started_ns = time.perf_counter_ns()
        vphase.status = "running"
        self._emit(swarm_id, "verify", "verifier", "verifier",
                   "started", "Verifier validating final HLF")
        self._build_verification_phase(vphase, current_hlf, description, swarm_id)
        phases.append(vphase)
        total_tokens += vphase.metrics.get("hlf_tokens", len(current_hlf.split()))

        try:
            nl_summary = hlf_source_to_english(current_hlf)
        except Exception:
            nl_summary = description

        return self._aggregate_result(
            swarm_id, description, phases, current_hlf, nl_summary,
            total_tokens, overall_start,
        )
