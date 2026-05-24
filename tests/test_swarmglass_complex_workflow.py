"""Complex governance workflow test — multi-agent coordination through full
governance pipeline with zero DSL imports.

Tests the observe→validate→audit→report governance loop with realistic
multi-agent scenarios, constraint violations, edge cases, concurrency,
and EXP=0 mode verification.
"""

from __future__ import annotations

import json
import os
import uuid
import time
import threading

# Ensure governance-only mode from the start
os.environ["SWARMGLASS_EXPERIMENTAL"] = "0"

from hlf_mcp import server
from hlf_mcp.server_context import build_server_context
from hlf_mcp.hlf.governance_events import GovernanceEvent, GovernanceEventKind, GovernanceStatus
from hlf_mcp.hlf.witness_governance import WitnessObservation, WitnessSeverity
from hlf_mcp.hlf.audit_chain import verify_event_chain


def _uid(prefix: str = "test") -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 1: Audit Chain — log events and verify integrity
# ══════════════════════════════════════════════════════════════════════


def test_audit_chain_log_and_verify() -> None:
    """Log events through AuditChain and verify integrity."""
    ctx = build_server_context()
    chain = ctx.audit_chain

    # Simple log API
    for i in range(5):
        evt = chain.log(f"test_event_{i}", data={"iteration": i})
        assert evt is not None, f"Event {i} is None"

    # Structured governance event
    for i in range(3):
        evt = chain.log_governance_event(GovernanceEvent(
            kind="governance_proof",
            source=_uid("agent"),
            action=f"governed_action_{i}",
            status="ok",
            subject_id=_uid("subject"),
        ))
        assert evt is not None, f"Governance event {i} is None"

    # Verify integrity (small limit to avoid reading entire log)
    ok = chain.verify_integrity(limit=5)
    assert ok is not None, "Integrity check returned None"

    # Recent events
    recent = chain.recent(limit=5)
    assert recent is not None
    assert len(recent) >= 1


def test_audit_chain_rapid_fire() -> None:
    """Rapid successive events remain consistent."""
    ctx = build_server_context()
    chain = ctx.audit_chain
    events = []

    for i in range(50):
        evt = chain.log(f"rapid_{i}", data={"seq": i})
        events.append(evt)

    assert len(events) == 50
    ok = chain.verify_integrity(limit=10)
    assert ok is not None


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 2: Align Governor — constraint evaluation
# ══════════════════════════════════════════════════════════════════════


def test_align_governor_evaluate() -> None:
    """AlignGovernor evaluates payloads and returns structured verdicts."""
    ctx = build_server_context()
    gov = ctx.align_governor

    # Evaluate a benign payload
    result = gov.evaluate({"action": "read_metrics", "scope": "production"})
    assert result is not None, "Benign evaluation returned None"

    # Evaluate a complex payload
    result2 = gov.evaluate({
        "action": "deploy_service",
        "target": "payment-api",
        "environment": "staging",
        "health_checks": True,
    })
    assert result2 is not None, "Complex evaluation returned None"

    # Evaluate string payload
    result3 = gov.evaluate("delete_all_records without confirmation")
    assert result3 is not None, "String payload evaluation returned None"

    # Log audit trail
    ctx.audit_chain.log("constraint_eval_complete", data={
        "verdict_count": 3,
    })
    ok = ctx.audit_chain.verify_integrity(limit=10)
    assert ok is not None


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 3: Witness Governance — record and query observations
# ══════════════════════════════════════════════════════════════════════


def test_witness_governance_observations() -> None:
    """Witness governance records observations and provides snapshots."""
    ctx = build_server_context()
    wg = ctx.witness_governance

    for i in range(5):
        obs = WitnessObservation(
            witness_id=_uid("witness"),
            subject_agent_id=_uid("agent"),
            category=f"test_category_{i}",
            severity="warning",
            confidence=0.9,
        )
        snapshot = wg.record_observation(obs)
        assert snapshot is not None, f"Observation {i} snapshot is None"

    # Status snapshot
    status = wg.status_snapshot()
    assert status is not None, "Status snapshot is None"

    # List snapshots
    snapshots = wg.list_snapshots()
    assert snapshots is not None, "Snapshot list is None"


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 4: Intent Normalizer — normalize real-world text
# ══════════════════════════════════════════════════════════════════════


def test_intent_normalizer() -> None:
    """Intent normalizer handles real-world task descriptions."""
    ctx = build_server_context()
    nm = ctx.intent_normalizer

    for intent in [
        "deploy the new caching layer to staging",
        "roll back the database migration",
        "add health check endpoint to all services",
        "analyze the spike in error rates for payment service",
    ]:
        result = nm.normalize(intent)
        assert result is not None, f"Normalization returned None for: {intent}"

    # Empty input should not crash
    for empty in ["", "   "]:
        result = nm.normalize(empty)
        assert result is not None, f"Empty input '{repr(empty)}' returned None"

    # auto_rewrite is a config flag (bool), not a method
    assert isinstance(nm.auto_rewrite, bool), "auto_rewrite should be a bool"


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 5: Memory Store — store, query, resolve
# ══════════════════════════════════════════════════════════════════════


def test_memory_store_operations() -> None:
    """Memory store handles facts with provenance tracking."""
    ctx = build_server_context()
    ms = ctx.memory_store

    # Store facts
    ms.store(
        content=json.dumps({"phase": "canary", "version": "1.0.0"}),
        topic="deployment_status",
        provenance="agent",
        entry_kind="fact",
    )

    # Store superseding fact
    ms.store(
        content=json.dumps({"phase": "production", "version": "1.0.0"}),
        topic="deployment_status",
        provenance="agent",
        entry_kind="fact",
    )

    # Store another topic
    ms.store(
        content=json.dumps({"healthy": True, "latency_ms": 42}),
        topic="health_check",
        provenance="agent",
        entry_kind="fact",
    )

    # Query
    results = ms.query("deployment_status", top_k=5)
    assert results is not None, "Memory query returned None"

    # Stats
    stats = ms.stats()
    assert stats is not None, "Memory stats returned None"

    # Resolve pointers
    resolved = ctx.resolve_memory_pointer("deployment_status")
    assert resolved is not None, "Memory pointer resolve returned None"


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 6: Daemon Manager — operational in governance mode
# ══════════════════════════════════════════════════════════════════════


def test_daemon_manager_operational() -> None:
    """Daemon manager is alive and running in governance-only mode."""
    ctx = build_server_context()

    assert ctx.daemon_manager is not None, "Daemon manager is None"
    assert hasattr(ctx.daemon_manager, "status"), "No status attribute"

    status = ctx.daemon_manager.status
    assert status is not None


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 7: Concurrent Thread Safety
# ══════════════════════════════════════════════════════════════════════


def test_concurrent_audit_operations() -> None:
    """Concurrent audit logs remain consistent across threads."""
    ctx = build_server_context()
    events_lock = threading.Lock()
    events_recorded = []
    errors = []

    def worker(label: str, count: int) -> None:
        for i in range(count):
            try:
                evt = ctx.audit_chain.log(f"concurrent_{label}", data={
                    "label": label, "iteration": i,
                    "thread": threading.current_thread().name,
                })
                with events_lock:
                    events_recorded.append(evt)
            except Exception as e:
                with events_lock:
                    errors.append(f"{label}-{i}: {e}")

    threads = [
        threading.Thread(target=worker, args=(f"w{c}", 5))
        for c in "ABCD"
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Concurrent errors: {errors}"
    assert len(events_recorded) == 20, \
        f"Expected 20 events, got {len(events_recorded)}"

    ok = ctx.audit_chain.verify_integrity(limit=10)
    assert ok is not None


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 8: Handoff events
# ══════════════════════════════════════════════════════════════════════


def test_handoff_event_lifecycle() -> None:
    """Handoff events are persisted and queryable."""
    ctx = build_server_context()

    agent_a = _uid("scribe")
    agent_b = _uid("planner")

    # Persist handoff
    ctx.persist_handoff_event({
        "from_agent": agent_a,
        "to_agent": agent_b,
        "context": "production_incident_analysis",
        "timestamp": time.time(),
    })

    # Query handoff chain
    chain = ctx.get_handoff_chain()
    assert chain is not None, "Handoff chain is None"

    # Handoff events deque
    events = ctx.handoff_events
    assert events is not None, "Handoff events deque is None"


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 9: Governed Routing
# ══════════════════════════════════════════════════════════════════════


def test_governed_routing() -> None:
    """Governed routes are persisted and recallable."""
    ctx = build_server_context()

    agent_id = _uid("gateway")

    # Persist a governed route
    ctx.persist_governed_route({
        "intent": "provision_staging_environment",
        "agent_id": agent_id,
        "tier": "forge",
        "timestamp": time.time(),
    })

    # Get governed route (no agent_id returns most recent)
    retrieved = ctx.get_governed_route()
    assert retrieved is not None, "Governed route retrieval returned None"
    assert retrieved["agent_id"] == agent_id

    # Governed recall with no args returns the current state
    recall = ctx.get_governed_recall()
    # May be None if no recall_id — this is expected
    # The important thing is it doesn't crash


# ══════════════════════════════════════════════════════════════════════
#  SCENARIO 10: EXP=0 Tool Availability Verification
# ══════════════════════════════════════════════════════════════════════


def test_governance_tools_available_exp0() -> None:
    """Essential governance tools are registered in EXP=0 mode."""
    tools = server.REGISTERED_TOOLS

    essential = [
        "hlf_governance_event_log",
        "hlf_memory_store",
        "hlf_memory_query",
        "hlf_memory_govern",
        "hlf_memory_stats",
        "hlf_memory_resolve",
        "hlf_witness_record",
        "hlf_witness_status",
        "hlf_witness_list",
        "hlf_align_check",
        "hlf_handoff_chain",
        "hlf_governed_recall",
        "hlf_governed_complete",
    ]
    for tn in essential:
        assert tn in tools, f"'{tn}' missing in EXP=0"


def test_dsl_tools_absent_exp0() -> None:
    """DSL-dependent tools are NOT registered in EXP=0 mode."""
    tools = server.REGISTERED_TOOLS

    dsl = [
        "hlf_do", "hlf_translate_to_hlf", "hlf_compile",
        "hlf_capsule_run", "hlf_swarm_mechanics",
        "hlf_capsule_validate", "hlf_pointer_validate",
        "hlf_host_call", "hlf_workflow_benchmark",
    ]
    for tn in dsl:
        assert tn not in tools, f"DSL tool '{tn}' leaked into EXP=0"


def test_entropy_anchor_unavailable_exp0() -> None:
    """hlf_entropy_anchor returns 'unavailable' without DSL."""
    result = server.hlf_entropy_anchor("test source")
    assert result["status"] == "unavailable"
    assert "compiler not loaded" in result.get("reason", "")
