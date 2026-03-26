from __future__ import annotations

from hlf_mcp.hlf.daemon_manager import DaemonManager


def test_daemon_manager_records_governance_events_as_audit_entries() -> None:
    manager = DaemonManager()
    event = {
        "kind": "approval_transition",
        "action": "approval_bypass_attempt",
        "status": "blocked",
        "severity": "critical",
        "source": "test.approval",
        "subject_id": "agent-1",
        "goal_id": "approval",
        "timestamp": "2026-03-21T00:00:00Z",
        "event_ref": {"kind": "approval_transition", "event_id": "evt-1", "trace_id": "trace-1"},
        "details": {"reason_code": "approval_token_mismatch", "request_id": "req-1"},
    }

    observed = manager.observe_governance_event(event, audit_trace_id="trace-1")
    trail = manager.get_audit_trail()
    alerts = manager.get_alerts()
    scribe_entries = manager.get_scribe_entries()

    assert observed["status"] == "ok"
    assert observed["sentinel_alerts"][0]["pattern"] == "approval_bypass_attempt"
    assert observed["scribe_entries"][0]["source"] == "governance"
    assert trail[0]["category"] == "approval"
    assert alerts[0]["pattern"] == "approval_bypass_attempt"
    assert alerts[0]["severity"] == "critical"
    assert scribe_entries[0]["source"] == "sentinel"
    assert "approval bypass" in trail[0]["operator_summary"].lower()


def test_daemon_manager_snapshot_counts_alerts_and_subjects() -> None:
    manager = DaemonManager()
    manager.observe_governance_event(
        {
            "kind": "routing_decision",
            "action": "route_selected",
            "status": "warning",
            "severity": "warning",
            "source": "test.route",
            "subject_id": "agent-a",
            "goal_id": "route",
            "timestamp": "2026-03-21T00:00:00Z",
            "event_ref": {"kind": "routing_decision", "event_id": "evt-2", "trace_id": "trace-2"},
            "details": {"selected_lane": "deterministic_local"},
        },
        audit_trace_id="trace-2",
    )
    manager.observe_governance_event(
        {
            "kind": "witness_observation",
            "action": "record_witness_observation",
            "status": "warning",
            "severity": "warning",
            "source": "test.witness",
            "subject_id": "agent-b",
            "goal_id": "witness",
            "timestamp": "2026-03-21T00:00:01Z",
            "event_ref": {"kind": "witness_observation", "event_id": "evt-3", "trace_id": "trace-3"},
            "details": {"category": "memory_integrity"},
        },
        audit_trace_id="trace-3",
    )

    snapshot = manager.status_snapshot()
    alerts = manager.get_alerts()
    scribe_entries = manager.get_scribe_entries()
    daemon_events = manager.get_daemon_events(source="sentinel")

    assert snapshot["manager_status"] == "running"
    assert snapshot["entry_count"] == 2
    assert snapshot["alert_count"] == 2
    assert snapshot["category_counts"]["routing"] == 1
    assert snapshot["category_counts"]["witness"] == 1
    assert snapshot["anomaly_summary"]["pressured_subject_count"] == 2
    assert len(alerts) == 2
    assert snapshot["sentinel_summary"]["alert_count"] == 2
    assert snapshot["scribe_summary"]["entry_count"] >= 4
    assert snapshot["daemon_bus_summary"]["source_counts"]["sentinel"] >= 2
    assert len(scribe_entries) >= 4
    assert len(daemon_events) >= 2


def test_daemon_manager_restores_pointer_and_recall_observability() -> None:
    manager = DaemonManager(scribe_token_budget=64)

    pointer_event = manager.observe_governance_event(
        {
            "kind": "pointer_resolution",
            "action": "resolve_memory_pointer",
            "status": "blocked",
            "severity": "warning",
            "source": "test.pointer",
            "subject_id": "fact-1",
            "goal_id": "execution",
            "timestamp": "2026-03-21T00:00:00Z",
            "event_ref": {"kind": "pointer_resolution", "event_id": "evt-pointer", "trace_id": "trace-pointer"},
            "details": {
                "pointer": "&fact-1",
                "purpose": "execution",
                "trust_mode": "enforce",
                "admitted": False,
                "reason": "pointer is revoked",
                "governance_status": "revoked",
                "freshness_status": "fresh",
            },
        },
        audit_trace_id="trace-pointer",
    )
    recall_event = manager.observe_governance_event(
        {
            "kind": "memory_governance",
            "action": "recall_governed_evidence",
            "status": "ok",
            "severity": "info",
            "source": "test.recall",
            "subject_id": "fact-2",
            "goal_id": "repair pointer trust",
            "timestamp": "2026-03-21T00:00:01Z",
            "event_ref": {"kind": "memory_governance", "event_id": "evt-recall", "trace_id": "trace-recall"},
            "details": {
                "query": "repair pointer trust",
                "result_count": 1,
                "entry_kinds": ["hks_exemplar"],
                "weekly_sync_count": 0,
                "require_provenance": True,
            },
        },
        audit_trace_id="trace-recall",
    )

    alerts = manager.get_alerts(pattern="pointer_resolution_denied")
    pointer_scribe = manager.get_scribe_entries(source="sentinel", event_type="sentinel_pointer_resolution_denied")
    recall_scribe = manager.get_scribe_entries(source="governance", event_type="memory_governance")

    assert pointer_event["sentinel_alerts"][0]["pattern"] == "pointer_resolution_denied"
    assert alerts[0]["event_ref"]["event_id"] == "evt-pointer"
    assert recall_event["sentinel_alerts"] == []
    assert pointer_scribe[0]["related_event_ref"]["event_id"] == "evt-pointer"
    assert "Governed recall returned 1 result" in recall_scribe[0]["prose"]