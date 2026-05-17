"""Tests for the Msty Claw audit trail bridge."""

import json
import os
import tempfile
import uuid
from datetime import datetime, timezone

import pytest

from hlf_mcp.bridges.msty_claw.audit_bridge import (
    AuditEvent,
    CausalChain,
    MstyAuditBridge,
    RecourseResult,
)


# ── Helpers ─────────────────────────────────────────────────────────────────────


def _make_event(
    event_type: str = "tool_invoked",
    intent_id: str = "test-intent",
    actor: str = "main_agent",
    session_id: str = "sess-001",
    payload: dict | None = None,
    constraint_checks: list | None = None,
    ts: str | None = None,
) -> AuditEvent:
    return AuditEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=ts or datetime.now(timezone.utc).isoformat(),
        triggering_intent_id=intent_id,
        actor=actor,
        payload=payload or {"tool_name": "shell", "args": {"command": "echo test"}},
        session_id=session_id,
        constraint_checks=constraint_checks or [],
    )


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def bridge():
    """Fresh in-memory bridge per test."""
    return MstyAuditBridge(":memory:")


@pytest.fixture
def seeded_bridge(bridge):
    """Bridge with 5 pre-ingested events using today's date."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    events = [
        _make_event("session_started", intent_id="deploy", ts=f"{today}T14:00:00"),
        _make_event(
            "tool_invoked",
            intent_id="deploy",
            payload={"tool_name": "shell", "args": {"command": "git status"}, "duration_ms": 120},
            ts=f"{today}T14:00:05",
        ),
        _make_event(
            "tool_invoked",
            intent_id="deploy",
            payload={"tool_name": "file_write", "args": {"path": "/workspace/config.yaml"}, "duration_ms": 45},
            ts=f"{today}T14:00:10",
        ),
        _make_event(
            "memory_written",
            intent_id="deploy",
            payload={"pack_id": "dep-001", "key": "deploy_config", "value_hash": "abc123"},
            ts=f"{today}T14:00:15",
        ),
        _make_event(
            "approval_granted",
            intent_id="deploy",
            payload={
                "tool_name": "shell",
                "args_preview": "kubectl apply",
                "risk_level": "medium",
                "granted_by": "operator",
            },
            ts=f"{today}T14:00:20",
        ),
    ]
    for ev in events:
        bridge.ingest_event(ev)
    return bridge, events


# ── Tests ───────────────────────────────────────────────────────────────────────


class TestIngestAndStore:
    """Test event ingestion and basic storage."""

    def test_ingest_stores_event(self, bridge):
        """Ingested event is retrievable by query."""
        ev = _make_event()
        eid = bridge.ingest_event(ev)
        assert eid == ev.event_id
        results = bridge.query_events(event_type="tool_invoked")
        assert len(results) == 1
        assert results[0].event_id == ev.event_id
        assert results[0].payload["tool_name"] == "shell"

    def test_duplicate_rejection(self, bridge):
        """Ingesting the same event_id twice raises ValueError."""
        ev = _make_event()
        bridge.ingest_event(ev)
        with pytest.raises(ValueError, match="Duplicate"):
            bridge.ingest_event(ev)

    def test_empty_event_id_raises(self, bridge):
        """Empty event_id raises ValueError."""
        ev = _make_event()
        ev.event_id = ""
        with pytest.raises(ValueError, match="event_id"):
            bridge.ingest_event(ev)

    def test_invalid_event_type_raises(self, bridge):
        """Invalid event_type raises ValueError."""
        ev = _make_event(event_type="bad_type")
        with pytest.raises(ValueError, match="Invalid event_type"):
            bridge.ingest_event(ev)


class TestQueryFilters:
    """Test query_events with various filters."""

    def test_query_by_event_type(self, seeded_bridge):
        """Filter by event_type returns only matching events."""
        bridge, _ = seeded_bridge
        results = bridge.query_events(event_type="memory_written")
        assert len(results) == 1
        assert results[0].event_type == "memory_written"

    def test_query_by_time_range(self, seeded_bridge):
        """Time-range filter restricts results."""
        bridge, _ = seeded_bridge
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        results = bridge.query_events(
            time_range=(f"{today}T14:00:00", f"{today}T14:00:05")
        )
        assert len(results) == 2  # session_started + tool_invoked

    def test_query_by_actor(self, seeded_bridge):
        """Actor filter works."""
        bridge, _ = seeded_bridge
        results = bridge.query_events(actor="main_agent")
        assert len(results) == 5

    def test_query_by_tool_name(self, seeded_bridge):
        """Tool-name filter matches payload.tool_name."""
        bridge, _ = seeded_bridge
        results = bridge.query_events(tool_name="file_write")
        assert len(results) == 1
        assert results[0].payload["tool_name"] == "file_write"

    def test_query_empty_returns_empty_list(self, bridge):
        """Empty bridge returns [] for any query."""
        results = bridge.query_events(event_type="tool_invoked")
        assert results == []


class TestCausalChain:
    """Test causal chain tracing."""

    def test_trace_causal_chain(self, seeded_bridge):
        """Trace returns CausalChain with root and all related events."""
        bridge, events = seeded_bridge
        chain = bridge.trace_causal_chain(events[1].event_id)  # first tool_invoked
        assert isinstance(chain, CausalChain)
        assert chain.root_intent is not None
        assert chain.root_intent.event_type == "session_started"
        assert len(chain.chain) == 5  # all events share same intent_id
        assert "/workspace/config.yaml" in chain.affected_files
        assert "deploy_config" in chain.affected_memories

    def test_trace_nonexistent_event(self, bridge):
        """Tracing a nonexistent event_id raises ValueError."""
        with pytest.raises(ValueError, match="Event not found"):
            bridge.trace_causal_chain("nonexistent-id")


class TestRecourseQuery:
    """Test natural-language recourse queries."""

    def test_recourse_time_range_query(self, seeded_bridge):
        """'show events between 14:00-14:05' returns time-filtered results."""
        bridge, _ = seeded_bridge
        result = bridge.recourse_query("show events between 14:00-14:05")
        assert isinstance(result, RecourseResult)
        assert len(result.supporting_events) >= 1
        assert result.confidence > 0.5

    def test_recourse_why_query(self, seeded_bridge):
        """'why was file X' returns related file_write events."""
        bridge, _ = seeded_bridge
        result = bridge.recourse_query("why was file config.yaml deleted?")
        assert isinstance(result, RecourseResult)
        # Should find the file_write event
        assert any(
            "file_write" in e.event_type
            or "config.yaml" in json.dumps(e.payload)
            for e in result.supporting_events
        )

    def test_recourse_who_query(self, seeded_bridge):
        """'who approved' returns approval_granted events."""
        bridge, _ = seeded_bridge
        result = bridge.recourse_query("who approved the deploy?")
        assert isinstance(result, RecourseResult)
        assert any(
            e.event_type == "approval_granted" for e in result.supporting_events
        )

    def test_recourse_empty_bridge(self, bridge):
        """Recourse query on empty bridge returns low-confidence result."""
        result = bridge.recourse_query("show events between 14:00-14:05")
        assert isinstance(result, RecourseResult)
        assert result.confidence <= 0.5


class TestSessionSummary:
    """Test session summary generation."""

    def test_session_summary_counts(self, seeded_bridge):
        """Summary has correct counts for tool calls, memories, approvals."""
        bridge, _ = seeded_bridge
        summary = bridge.generate_session_summary("sess-001")
        assert summary["session_id"] == "sess-001"
        assert summary["event_count"] == 5
        assert summary["tool_counts"]["shell"] == 1
        assert summary["tool_counts"]["file_write"] == 1
        assert summary["memory_mutations"] == 1
        assert summary["approvals"]["granted"] == 1
        assert "/workspace/config.yaml" in summary["files_touched"]
        assert summary["duration"] is not None

    def test_session_summary_empty(self, bridge):
        """Empty session returns zeroed summary."""
        summary = bridge.generate_session_summary("nonexistent")
        assert summary["event_count"] == 0
        assert summary["tool_counts"] == {}
        assert summary["duration"] is None


class TestWeeklyEvidence:
    """Test weekly evidence export."""

    def test_weekly_evidence_valid_json(self, seeded_bridge):
        """Export returns valid JSON with expected top-level keys."""
        bridge, _ = seeded_bridge
        exported = bridge.export_weekly_evidence()
        data = json.loads(exported)
        assert data["version"] == "HLF-v3"
        assert "generated_at" in data
        assert "merkle_root" in data
        assert "merkle_chain_depth" in data
        assert data["event_count"] == 5
        assert len(data["events"]) == 5

    def test_weekly_evidence_empty_bridge(self, bridge):
        """Empty bridge exports valid JSON."""
        exported = bridge.export_weekly_evidence()
        data = json.loads(exported)
        assert data["event_count"] == 0
        assert data["events"] == []
        assert "merkle_root" in data


class TestArchive:
    """Test session archive to NDJSON."""

    def test_archive_ndjson(self, seeded_bridge):
        """Archive writes NDJSON with Merkle root footer."""
        bridge, _ = seeded_bridge
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "session.ndjson")
            root = bridge.archive_session("sess-001", out_path)
            assert isinstance(root, str)
            assert len(root) == 64  # SHA256 hex

            # Verify file content
            with open(out_path, encoding="utf-8") as fh:
                lines = fh.readlines()

            assert len(lines) == 6  # 5 events + 1 footer
            for i, line in enumerate(lines[:-1]):
                record = json.loads(line)
                assert "event_id" in record

            footer = json.loads(lines[-1])
            assert footer["__hlf_footer__"] is True
            assert footer["merkle_root"] == root
            assert footer["event_count"] == 5

    def test_archive_empty_session(self, bridge):
        """Archiving empty session returns valid Merkle root."""
        with tempfile.TemporaryDirectory() as tmp:
            out_path = os.path.join(tmp, "empty.ndjson")
            root = bridge.archive_session("nonexistent", out_path)
            assert isinstance(root, str)
            assert len(root) == 64

    def test_event_count_property(self, seeded_bridge):
        """Event count property returns correct total."""
        bridge, _ = seeded_bridge
        assert bridge.event_count == 5


class TestConstraintChecks:
    """Test that constraint_checks survive round-trip."""

    def test_constraint_checks_preserved(self, bridge):
        """Constraint checks are stored and retrieved intact."""
        checks = [
            {"rule": "rule_001", "passed": True, "detail": "allowed by default"},
            {"rule": "rule_002", "passed": False, "detail": "blocked pattern"},
        ]
        ev = _make_event(constraint_checks=checks)
        bridge.ingest_event(ev)
        results = bridge.query_events()
        assert len(results) == 1
        assert results[0].constraint_checks == checks
