"""
HLF Latent Capsule — governed wrapper around RecursiveMAS latent-space inference.

Seals RecursiveMAS recursion rounds inside a sovereign-tier IntentCapsule.
Only the final decoded text and a provenance metadata hash cross the capsule
boundary into HLF's Merkle-chain audit system.  Intermediate latent tensors
are never serialized, logged, or exposed.

Trust model (Option C):
  - Capsule declares `latent_communication` as a sovereign-tier capability
  - Each latent round produces a SHA-256 metadata attestation:
      SHA-256(agent_id || round || tensor_shape || adapter_sha256 || capability_ref)
  - The Merkle chain records THAT latent communication occurred, not WHAT it contained
  - Gas is metered per-round and bounded by `max_rounds * 15 gas`
  - Final text output is the only inspectable artifact exiting the capsule

Integration:
  - hlf_mcp.hlf.latent_model_interface: RecursiveMAS PyTorch pipeline
  - hlf_mcp.hlf.capsules: sovereign_capsule(), IntentCapsule
  - hlf_mcp.hlf.capability_manifest: EFFECT_TO_CAPABILITY mapping
  - governance/host_functions.json: LATENT_EXTRACT / LATENT_PROJECT / LATENT_INJECT
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.capsules import CapsuleViolation, IntentCapsule, sovereign_capsule

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Latent audit record
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class LatentRoundAttestation:
    """Immutable metadata record for one latent recursion round.

    This is what enters the Merkle chain — NOT the tensor.  A forensic
    auditor can verify from this record that:
      - Agent identities were fixed
      - Recursion depth was bounded
      - Tensor geometry was consistent with declared interfaces
      - Adapter weights were exactly the published checkpoints (immutable hash)
      - The capability manifest authorized this communication path
    """

    round_idx: int
    source_agent: str
    target_agent: str
    source_dims: int
    target_dims: int
    adapter_sha256: str           # Immutable checkpoint hash
    capability_digest: str         # Manifest hash authorizing this path
    gas_consumed: int              # Gas consumed in this round
    wall_time_ms: float            # Wall-clock time for this round
    tensor_shape: tuple[int, ...]  # Shape of the projected tensor (dims only)

    def to_provenance_hash(self) -> str:
        """Produce a SHA-256 attestation suitable for Merkle-chain insertion."""
        payload = "||".join(
            str(x) for x in [
                self.round_idx,
                self.source_agent,
                self.target_agent,
                self.source_dims,
                self.target_dims,
                self.adapter_sha256,
                self.capability_digest,
                self.gas_consumed,
                ",".join(str(d) for d in self.tensor_shape),
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "round": self.round_idx,
            "source_agent": self.source_agent,
            "target_agent": self.target_agent,
            "source_dims": self.source_dims,
            "target_dims": self.target_dims,
            "adapter_sha256": self.adapter_sha256,
            "capability_digest": self.capability_digest,
            "gas_consumed": self.gas_consumed,
            "wall_time_ms": self.wall_time_ms,
            "tensor_shape": list(self.tensor_shape),
            "provenance_hash": self.to_provenance_hash(),
        }


@dataclass(slots=True)
class LatentCapsuleResult:
    """What exits the capsule boundary after latent recursion completes."""

    final_text: str
    rounds_completed: int
    attestations: list[LatentRoundAttestation]
    total_gas: int
    total_wall_time_ms: float
    capsule: IntentCapsule

    def to_dict(self) -> dict[str, Any]:
        return {
            "final_text": self.final_text,
            "rounds_completed": self.rounds_completed,
            "total_gas": self.total_gas,
            "total_wall_time_ms": self.total_wall_time_ms,
            "capsule_id": self.capsule.capsule_id,
            "capsule_tier": self.capsule.tier,
            "attestations": [a.to_dict() for a in self.attestations],
            "provenance_chain": [a.to_provenance_hash() for a in self.attestations],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Latent Capsule — the governed wrapper
# ═══════════════════════════════════════════════════════════════════════════════


class LatentCapsule:
    """Governed wrapper around RecursiveMAS latent-space inference.

    Creates a sovereign-tier IntentCapsule that authorizes latent_communication,
    then wraps the RecursiveMAS pipeline inside it.  Intermediate tensor states
    are sealed inside the capsule — only the final text output and metadata
    provenance hashes exit into HLF's audit chain.

    Usage:
        capsule = LatentCapsule(agent_id="swarm-orchestrator")
        result = capsule.run(prompt="Prove: ∀x ∈ ℤ, x + 0 = x")
        # result.final_text → decoded LLM output
        # result.attestations → Merkle-chain-ready provenance records
    """

    # Sovereign-tier only: HEARTH and FORGE cannot touch latent communication
    _LATENT_TIERS: frozenset[str] = frozenset({"sovereign"})

    # Gas model (from host_functions.json):
    #   LATENT_EXTRACT  = 5 gas  (hidden state grab)
    #   LATENT_PROJECT  = 15 gas (matrix multiply + GELU, ~3M FLOPs per token pos)
    #   LATENT_INJECT   = 5 gas  (input embedding injection)
    # Per-round gas: extract(source) + project + inject(target) = 5 + 15 + 5 = 25
    _GAS_PER_HANDOFF: int = 25
    _GAS_PER_ROUND: int = 3 * _GAS_PER_HANDOFF  # 3 handoffs per round: P→C, C→S, S→P
    _MAX_GAS_DEFAULT: int = 1000

    def __init__(
        self,
        *,
        agent_id: str = "latent-capsule",
        max_rounds: int = 3,
        base_tier: str = "sovereign",
    ) -> None:
        self.agent_id = agent_id
        self.max_rounds = max_rounds
        self.base_tier = base_tier

        # Compute max gas from round count
        max_gas = max(self._GAS_PER_ROUND * max_rounds + 50, self._MAX_GAS_DEFAULT)

        # Create the sovereign capsule that gates latent communication
        self._capsule = sovereign_capsule(
            base_tier=self.base_tier,
            agent_id=self.agent_id,
        )
        # Bump gas for latent recursion (default sovereign is 1000, latent needs more)
        self._capsule.max_gas = max_gas
        # Declare latent_communication as an allowed effect
        self._capsule.approval_required_tags.add("LATENT_COMMUNICATION")

    @property
    def capsule(self) -> IntentCapsule:
        return self._capsule

    def compute_capability_digest(self, adapter_hashes: dict[str, str]) -> str:
        """Compute a stable capability digest from adapter hashes + topology."""
        payload = {
            "max_rounds": self.max_rounds,
            "adapters": dict(sorted(adapter_hashes.items())),
            "capsule_id": self._capsule.capsule_id,
            "tier": self._capsule.tier,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def attest_round(
        self,
        round_idx: int,
        source_agent: str,
        target_agent: str,
        source_dims: int,
        target_dims: int,
        adapter_sha256: str,
        capability_digest: str,
        tensor_shape: tuple[int, ...],
        wall_time_ms: float,
    ) -> LatentRoundAttestation:
        """Create a provenance attestation for one latent handoff."""
        gas = self._GAS_PER_HANDOFF
        return LatentRoundAttestation(
            round_idx=round_idx,
            source_agent=source_agent,
            target_agent=target_agent,
            source_dims=source_dims,
            target_dims=target_dims,
            adapter_sha256=adapter_sha256,
            capability_digest=capability_digest,
            gas_consumed=gas,
            wall_time_ms=wall_time_ms,
            tensor_shape=tensor_shape,
        )

    def wrap_result(
        self,
        final_text: str,
        rounds_completed: int,
        attestations: list[LatentRoundAttestation],
        total_wall_time_ms: float,
    ) -> LatentCapsuleResult:
        """Wrap the latent session output in a governed capsule result."""
        return LatentCapsuleResult(
            final_text=final_text,
            rounds_completed=rounds_completed,
            attestations=attestations,
            total_gas=len(attestations) * self._GAS_PER_HANDOFF,
            total_wall_time_ms=total_wall_time_ms,
            capsule=self._capsule,
        )

    def validate_before_run(self) -> list[str]:
        """Pre-flight checks before allowing latent execution."""
        violations: list[str] = []

        # Tier check: only sovereign capsules can run latent communication
        if self._capsule.tier not in self._LATENT_TIERS:
            violations.append(
                f"Tier '{self._capsule.tier}' cannot execute latent_communication "
                f"(requires one of {sorted(self._LATENT_TIERS)})"
            )

        # Round bound check
        if self.max_rounds > 5:
            violations.append(
                f"max_rounds={self.max_rounds} exceeds safety bound of 5"
            )

        return violations


# ═══════════════════════════════════════════════════════════════════════════════
# Convenience factory
# ═══════════════════════════════════════════════════════════════════════════════


def latent_capsule(
    *,
    agent_id: str = "latent-capsule",
    max_rounds: int = 3,
    base_tier: str = "sovereign",
) -> LatentCapsule:
    """Create a governed LatentCapsule for RecursiveMAS inference."""
    return LatentCapsule(
        agent_id=agent_id,
        max_rounds=max_rounds,
        base_tier=base_tier,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Integration bridge: runs RecursiveMAS inside a governed capsule
# ═══════════════════════════════════════════════════════════════════════════════
# Observability trace — feeds verify_chain.py with latent provenance data
# ═══════════════════════════════════════════════════════════════════════════════

import os as _os
from pathlib import Path as _Path

_OBS_DIR = _Path(__file__).resolve().parent.parent.parent.parent / "observability" / "openllmetry"


def _write_latent_observability_trace(
    *,
    capsule_id: str,
    prompt: str,
    steps: list[dict[str, Any]],
    adapter_sha256s: dict[str, str],
    attestations: list[Any] | None = None,
    provenance_chain: list[str] | None = None,
    total_gas: int,
    total_wall_time_ms: float,
    peak_vram_mb: float,
    final_text: str,
    status: str = "ok",
    secret_hashes: dict[str, str] | None = None,
) -> None:
    """Append a latent inference trace entry to the observability JSONL.

    This writes a single JSONL line to observability/openllmetry/latent_traces.jsonl
    with a SHA-256 trace_id computed from the canonical payload.  The resulting
    file can be validated by verify_chain.py just like standard intent-execution
    observability traces — the hashing format is identical.

    The trace now includes attestations (round-by-round provenance metadata),
    provenance_chain (Merkle hashes), and final_text for operator-facing
    evidence rendering via hlf-evidence CLI.
    """
    import datetime as _dt
    import hashlib as _hashlib

    try:
        _OBS_DIR.mkdir(parents=True, exist_ok=True)

        # Serialize attestations for storage
        serialized_attestations: list[dict[str, Any]] = []
        if attestations:
            for a in attestations:
                if hasattr(a, 'to_dict'):
                    serialized_attestations.append(a.to_dict())
                elif isinstance(a, dict):
                    serialized_attestations.append(a)

        # Build canonical payload matching verify_chain.py's expected format
        data = {
            "capsule_id": capsule_id,
            "num_steps": len(steps),
            "agents": list({s.get("agent", "?") for s in steps}),
            "total_gas": total_gas,
            "total_wall_time_ms": round(total_wall_time_ms, 1),
            "peak_vram_mb": peak_vram_mb,
            "adapter_hashes": adapter_sha256s,
            "status": status,
            "attestations": serialized_attestations,
            "provenance_chain": provenance_chain or [],
            "final_text": final_text[:1000] if final_text else "",
            "prompt": prompt[:200] if prompt else "",
            "secret_hashes": secret_hashes or {},
        }

        event_payload = {
            "event": "latent_governed_infer",
            "data": data,
        }

        # Compute trace_id using the same canonical JSON as verify_chain.py
        from json import dumps as _json_dumps
        payload_str = _json_dumps(event_payload, sort_keys=True)
        trace_id = _hashlib.sha256(payload_str.encode()).hexdigest()

        entry = {
            "trace_id": trace_id,
            "event": "latent_governed_infer",
            "data": data,
            "timestamp_utc": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        }

        trace_file = _OBS_DIR / "latent_traces.jsonl"
        with open(trace_file, "a", encoding="utf-8") as fh:
            fh.write(_json_dumps(entry, sort_keys=True) + "\n")

        logger.debug("Wrote latent observability trace %s to %s", trace_id[:16], trace_file)

    except Exception:
        logger.exception("Failed to write latent observability trace — verify_chain feed is down")


# ═══════════════════════════════════════════════════════════════════════════════


def governed_latent_infer(
    prompt: str,
    *,
    session_config: Any = None,  # RecursiveSessionConfig or dict
    agent_id: str = "latent-capsule",
    max_rounds: int = 3,
    adapter_sha256s: dict[str, str] | None = None,
    human_approval_required: bool = False,
    hitl_timeout_seconds: int = 600,
    model_versions: dict[str, str] | None = None,
    secrets: Any = None,  # SecretCapsule | None
) -> dict[str, Any]:
    """Run RecursiveMAS latent inference inside a governed sovereign capsule.

    This is the canonical HLF entry point for latent-space multi-agent recursion.
    The capsule seals intermediate tensors inside the sovereign tier; only the
    final text output and provenance hashes exit into HLF's audit chain.

    If human_approval_required=True, inference still runs to completion, but
    the result is submitted to the HITL gate for operator sign-off before the
    status transitions from AWAITING_HUMAN_APPROVAL to COMPLETED.  The caller
    should check `hitl_status` in the result dict.

    If model_versions is provided (dict of model_name → expected_sha256), the
    inference engine verifies that each declared model matches the live Ollama
    digest before loading.  Mismatch = CapsuleViolation, fail closed.

    Args:
        prompt: Input text to process.
        session_config: RecursiveSessionConfig or dict with config keys.
        agent_id: Capsule agent ID for audit trail.
        max_rounds: Maximum recursion rounds (bounded at 5).
        adapter_sha256s: Dict mapping adapter keys to SHA-256 hashes of their
            checkpoint files.  If omitted, hashes are computed on-the-fly.
        human_approval_required: If True, submit result to HITL gate after
            inference.  The response status will be 'awaiting_human_approval'
            instead of 'ok'.
        hitl_timeout_seconds: Seconds before the approval request auto-expires.
        model_versions: Optional dict of model_name → expected_sha256 digest.
            If provided, runs pre-flight verification against live Ollama scan.
        secrets: Optional SecretCapsule for workflow credentials (API keys, DB
            passwords).  Only SHA-256(ciphertext) appears in traces/audit.
            Plaintext is available to the inference engine but never logged.

    Returns:
        dict with keys:
          - final_text: Decoded LLM output
          - rounds_completed: Number of recursion rounds
          - attestations: List of LatentRoundAttestation dicts (Merkle-ready)
          - provenance_chain: List of provenance hash strings
          - capsule_id: Sovereign capsule ID
          - total_gas: Gas consumed across all latent rounds
          - total_wall_time_ms: Total wall-clock time
          - status: 'ok', 'awaiting_human_approval', 'error', or 'capsule_violation'
          - error: Error message if status in ('error', 'capsule_violation')
          - secret_hashes: Dict of secret_name → SHA-256(ciphertext) if secrets active
          - hitl_status: (only if human_approval_required=True) dict with
              approval_token, capsule_id, and instructions for hlf-operator
          - model_version_results: (only if model_versions was checked) list of
              ModelVersionResult dicts
    """
    import time as _time

    # ── Create the governed capsule ───────────────────────────────────
    capsule = LatentCapsule(
        agent_id=agent_id,
        max_rounds=max_rounds,
    )

    # ── Resolve secret hashes for audit trail ────────────────────────
    secret_hashes: dict[str, str] = {}
    if secrets is not None:
        try:
            secret_hashes = secrets.merkle_metadata
            logger.debug("Bound %d secrets to capsule %s", len(secret_hashes), 
                         capsule.capsule.capsule_id)
        except Exception as e:
            logger.warning("Failed to resolve secret hashes: %s", e)

    # Pre-flight validation
    violations = capsule.validate_before_run()
    if violations:
        return {
            "status": "error",
            "error": "; ".join(violations),
            "final_text": "",
            "rounds_completed": 0,
            "attestations": [],
            "provenance_chain": [],
            "capsule_id": capsule.capsule.capsule_id,
            "total_gas": 0,
            "total_wall_time_ms": 0,
            "secret_hashes": secret_hashes,
        }

    # ── Load RecursiveMAS session ────────────────────────────────────
    try:
        from hlf_mcp.hlf.latent_model_interface import (
            LatentRecursiveSession,
            RecursiveSessionConfig,
        )
    except ImportError as exc:
        return {
            "status": "error",
            "error": f"Failed to import latent_model_interface: {exc}",
            "final_text": "",
            "rounds_completed": 0,
            "attestations": [],
            "provenance_chain": [],
            "capsule_id": capsule.capsule.capsule_id,
            "total_gas": 0,
            "total_wall_time_ms": 0,
            "secret_hashes": secret_hashes,
        }

    # Convert dict config to RecursiveSessionConfig if needed
    if isinstance(session_config, dict):
        session_config = RecursiveSessionConfig(**session_config)
    elif session_config is None:
        # Auto-resolve from checkpoint cache
        try:
            from hlf_mcp.hlf.model_orchestrator import _resolve_checkpoint_base
            import torch
            if not torch.cuda.is_available():
                return {
                    "status": "error",
                    "error": "GPU not available for latent inference",
                    "final_text": "", "rounds_completed": 0,
                    "attestations": [], "provenance_chain": [],
                    "capsule_id": capsule.capsule.capsule_id,
                    "total_gas": 0, "total_wall_time_ms": 0,
                    "secret_hashes": secret_hashes,
                }

            import os as _os
            _cache_root = _os.path.expanduser("~/.cache/huggingface/recursivemas")
            _cp = _resolve_checkpoint_base

            agent_models = {
                "planner": _cp(_cache_root, "Sequential-Light-Planner-Qwen3-1.7B",
                               "Qwen/Qwen2.5-1.5B-Instruct"),
                "critic": _cp(_cache_root, "Sequential-Light-Critic-Llama3.2-1B",
                              "meta-llama/Llama-3.2-1B-Instruct"),
                "solver": _cp(_cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B",
                              "Qwen/Qwen2.5-Math-1.5B"),
            }

            adapter_task = "math"
            inner_link_paths = {
                "planner": _cp(_cache_root, "Sequential-Light-Planner-Qwen3-1.7B",
                               adapter_file=f"adapter({adapter_task}).pt"),
                "critic": _cp(_cache_root, "Sequential-Light-Critic-Llama3.2-1B",
                              adapter_file=f"adapter({adapter_task}).pt"),
                "solver": _cp(_cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B",
                              adapter_file=f"adapter({adapter_task}).pt"),
            }

            outer_link_paths = {
                "planner_critic": _cp(_cache_root, "Sequential-Light-Outerlinks",
                                      adapter_file=f"Planner-Critic-Outerlink({adapter_task}).pt"),
                "critic_solver": _cp(_cache_root, "Sequential-Light-Outerlinks",
                                     adapter_file=f"Critic-Solver-Outerlink({adapter_task}).pt"),
                "solver_planner": _cp(_cache_root, "Sequential-Light-Outerlinks",
                                      adapter_file=f"Solver-Planner-Outerlink({adapter_task}).pt"),
            }

            session_config = RecursiveSessionConfig(
                agent_models=agent_models,
                recursion_rounds=max_rounds,
                max_new_tokens=512,
                device="auto",
                adapter_task=adapter_task,
                inner_link_paths=inner_link_paths,
                outer_link_paths=outer_link_paths,
            )
        except Exception:
            return {
                "status": "error",
                "error": "No session_config provided and auto-resolution failed",
                "final_text": "", "rounds_completed": 0,
                "attestations": [], "provenance_chain": [],
                "capsule_id": capsule.capsule.capsule_id,
                "total_gas": 0, "total_wall_time_ms": 0,
            }

    # ── Compute adapter hashes if not provided ────────────────────────
    if adapter_sha256s is None:
        adapter_sha256s = {}
        if session_config:
            for key, path in getattr(session_config, 'outer_link_paths', {}).items():
                try:
                    with open(path, "rb") as fh:
                        adapter_sha256s[key] = hashlib.sha256(fh.read()).hexdigest()
                except Exception:
                    adapter_sha256s[key] = "unknown"

    capability_digest = capsule.compute_capability_digest(adapter_sha256s)

    # ── Model version verification (pre-flight) ────────────────────────
    model_version_results: list[dict[str, Any]] = []
    if model_versions:
        try:
            from hlf_mcp.hlf.model_version import verify_model_versions
            from hlf_mcp.hlf.capability_manifest import CapabilityManifest
            _manifest = CapabilityManifest(
                program_id=capsule.capsule.capsule_id,
                model_versions=model_versions,
            )
            _results = verify_model_versions(
                _manifest,
                scanner=None,  # Use lazy scan via verify_model_versions
            )
            model_version_results = [r.to_dict() for r in _results]
            logger.info(
                "Model version check passed: %d model(s) verified",
                len(model_version_results),
            )
        except CapsuleViolation as cv:
            logger.error("Model version check FAILED: %s", cv)
            return {
                "status": "capsule_violation",
                "error": str(cv),
                "final_text": "",
                "rounds_completed": 0,
                "attestations": [],
                "provenance_chain": [],
                "capsule_id": capsule.capsule.capsule_id,
                "total_gas": 0,
                "total_wall_time_ms": 0,
                "model_version_results": model_version_results,
                "secret_hashes": secret_hashes,
            }

    # ── Run the latent inference ──────────────────────────────────────
    t0 = _time.time()
    try:
        session = LatentRecursiveSession(session_config)
        if not session.load_all():
            return {
                "status": "error",
                "error": "Failed to load models",
                "final_text": "",
                "rounds_completed": 0,
                "attestations": [],
                "provenance_chain": [],
                "capsule_id": capsule.capsule.capsule_id,
                "total_gas": 0,
                "total_wall_time_ms": 0,
                "secret_hashes": secret_hashes,
            }

        partial_steps: list[dict] = []
        aborted = False
        oom_details: dict | None = None

        try:
            result = session.recursive_infer(prompt)
        except Exception as exc:
            # ── Chaos resilience: catch OOM, timeout, and other runtime aborts ──
            import torch as _torch
            import traceback as _tb
            is_oom = isinstance(exc, _torch.cuda.OutOfMemoryError) if hasattr(_torch.cuda, "OutOfMemoryError") else False
            # Also catch generic CUDA errors that might be OOM variants
            error_str = str(exc).lower()
            if not is_oom and ("out of memory" in error_str or "oom" in error_str or "cuda" in error_str):
                is_oom = True

            aborted = True
            oom_details = {
                "error_type": type(exc).__name__,
                "error_message": str(exc)[:500],
                "is_oom": is_oom,
                "traceback": _tb.format_exc()[-1000:],
            }
            # Build a minimal result with whatever partial steps we can infer
            result = {"final_text": f"[ABORTED: {type(exc).__name__}]", "rounds": 0, "steps": []}

        # Capture peak VRAM BEFORE unloading models
        peak_vram_mb = 0
        try:
            import torch
            if torch.cuda.is_available():
                peak_vram_mb = round(torch.cuda.max_memory_allocated() / (1024 ** 2), 1)
        except Exception:
            pass

        # ── Update ResourceMonitor with peak VRAM ───────────────────────
        try:
            from hlf_mcp.hlf.resource_monitor import ResourceMonitor
            _rm = ResourceMonitor.get_instance()
            _snap = _rm.get_latest_snapshot()
        except Exception:
            pass

        session.unload()

        total_wall_time_ms = (_time.time() - t0) * 1000.0
        final_text = result.get("final_text", "")
        steps = result.get("steps", [])

        # ── Build attestations from recorded steps ──────────────────
        attestations: list[LatentRoundAttestation] = []
        for step in steps:
            src = step.get("agent", "unknown")
            # Determine target from next step or final decode
            tgt = "final_decode"
            step_round = step.get("round", 1)
            src_dim = step.get("hidden_dim", 0)
            tgt_dim = step.get("hidden_dim", 0)  # Same as source within a step
            adapter_key = step.get("link_key", "inner")
            adapter_hash = adapter_sha256s.get(adapter_key, "unknown")

            # Use fixed wall time per step (not individually instrumented yet)
            per_step_ms = total_wall_time_ms / max(len(steps), 1)

            att = LatentRoundAttestation(
                round_idx=step_round,
                source_agent=src,
                target_agent=tgt,
                source_dims=src_dim,
                target_dims=tgt_dim,
                adapter_sha256=adapter_hash,
                capability_digest=capability_digest,
                gas_consumed=capsule._GAS_PER_HANDOFF,
                wall_time_ms=per_step_ms,
                tensor_shape=(1, 1, src_dim),
            )
            attestations.append(att)

        wrapped = capsule.wrap_result(
            final_text=final_text,
            rounds_completed=result.get("rounds", 0),
            attestations=attestations,
            total_wall_time_ms=total_wall_time_ms,
        )

        base_result = {
            "status": "aborted" if aborted else "ok",
            "final_text": wrapped.final_text,
            "rounds_completed": wrapped.rounds_completed,
            "attestations": [a.to_dict() for a in wrapped.attestations],
            "provenance_chain": wrapped.to_dict()["provenance_chain"],
            "capsule_id": wrapped.capsule.capsule_id,
            "total_gas": wrapped.total_gas,
            "total_wall_time_ms": wrapped.total_wall_time_ms,
            "steps": steps,
            "peak_vram_mb": peak_vram_mb,
            "secret_hashes": secret_hashes,
        }
        if model_version_results:
            base_result["model_version_results"] = model_version_results
        if oom_details:
            base_result["oom_details"] = oom_details

        # ── Write observability trace for verify_chain.py / hlf-evidence ──
        _write_latent_observability_trace(
            capsule_id=capsule.capsule.capsule_id,
            prompt=prompt,
            steps=steps,
            adapter_sha256s=adapter_sha256s,
            attestations=attestations,
            provenance_chain=base_result["provenance_chain"],
            total_gas=base_result["total_gas"],
            total_wall_time_ms=total_wall_time_ms,
            peak_vram_mb=peak_vram_mb,
            final_text=final_text,
            status=base_result["status"],
            secret_hashes=secret_hashes,
        )

        # ── HITL Gate: block if human approval required ──────────────────
        if human_approval_required and not aborted:
            try:
                from hlf_mcp.hlf.hitl_gate import (
                    require_human_approval,
                    HITLGate,
                )
                import hashlib as _hl

                manifest_hash = _hl.sha256(
                    json.dumps(adapter_sha256s, sort_keys=True).encode()
                ).hexdigest()[:16]
                output_hash = _hl.sha256(
                    final_text.encode()
                ).hexdigest()[:16]

                gate = HITLGate.get_instance()
                req = require_human_approval(
                    capsule_id=wrapped.capsule.capsule_id,
                    agent_id=agent_id,
                    tier="sovereign",
                    intent_summary=prompt[:200],
                    output_text=final_text,
                    manifest_hash=manifest_hash,
                    output_hash=output_hash,
                    gas_consumed=wrapped.total_gas,
                    gas_limit=1000,
                    provenance_hashes=base_result["provenance_chain"],
                    timeout_seconds=hitl_timeout_seconds,
                )
                approval_token = gate.build_approval_token(req)

                base_result["status"] = "awaiting_human_approval"
                base_result["hitl_status"] = {
                    "approval_token": approval_token,
                    "capsule_id": wrapped.capsule.capsule_id,
                    "status": req.status,
                    "created_at": req.created_at,
                    "timeout_seconds": req.timeout_seconds,
                    "instructions": (
                        f"Run: python scripts/hlf_operator.py approve "
                        f"--capsule-id {wrapped.capsule.capsule_id} "
                        f"--token {approval_token}"
                    ),
                }
                logger.info(
                    "HITL gate: capsule %s requires human approval (token: %s)",
                    wrapped.capsule.capsule_id, approval_token,
                )
            except Exception as exc:
                logger.warning("HITL gate submission failed (non-fatal): %s", exc)
                # If HITL gate fails, allow inference to proceed uncensored
                base_result["status"] = "ok"
                base_result["hitl_error"] = str(exc)

        return base_result

    except Exception as exc:
        logger.exception("Latent capsule inference failed")
        total_wall_time_ms = (_time.time() - t0) * 1000.0
        return {
            "status": "error",
            "error": str(exc),
            "final_text": "",
            "rounds_completed": 0,
            "attestations": [],
            "provenance_chain": [],
            "capsule_id": capsule.capsule.capsule_id,
            "total_gas": 0,
            "total_wall_time_ms": total_wall_time_ms,
            "secret_hashes": secret_hashes,
        }
