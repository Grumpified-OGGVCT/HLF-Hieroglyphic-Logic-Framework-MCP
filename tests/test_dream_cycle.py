from __future__ import annotations

import json
import uuid

import pytest

from hlf_mcp import server
from hlf_mcp.media_evidence import MediaEvidenceRecord


def _subject(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def test_dream_cycle_run_emits_advisory_report_and_structured_findings() -> None:
    subject_agent_id = _subject("dream-witness")
    server.REGISTERED_TOOLS["hlf_witness_record"](
        subject_agent_id=subject_agent_id,
        category="verification_failure",
        severity="warning",
        confidence=0.91,
        witness_id="dream-test",
        evidence_text="bounded dream input witness",
    )

    result = server.REGISTERED_TOOLS["hlf_dream_cycle_run"](max_artifacts=0, max_facts=10)

    assert result["status"] == "ok"
    assert result["advisory_only"] is True
    assert result["report"]["finding_count"] >= 1
    assert result["report"]["witness_record_id"]
    assert result["findings"]
    finding = result["findings"][0]
    assert finding["advisory_only"] is True
    assert finding["provenance"]["source"] == "server_context.run_dream_cycle"
    assert finding["evidence_refs"]
    listed = server.REGISTERED_TOOLS["hlf_dream_findings_list"](
        cycle_id=result["report"]["cycle_id"]
    )
    fetched = server.REGISTERED_TOOLS["hlf_dream_findings_get"](finding["finding_id"])
    assert listed["status"] == "ok"
    assert listed["count"] >= 1
    assert fetched["status"] == "ok"
    assert fetched["finding"]["finding_id"] == finding["finding_id"]


def test_dream_cycle_rejects_media_without_safety_and_provenance() -> None:
    result = server.REGISTERED_TOOLS["hlf_dream_cycle_run"](
        max_artifacts=0,
        max_facts=0,
        media_evidence=[
            {
                "media_type": "image",
                "sha256": "a" * 64,
                "extraction_mode": "ocr",
                "derived_text": "diagram says route through verifier",
            }
        ],
    )

    assert result["status"] == "error"
    assert result["error"] == "invalid_media_evidence"
    assert result["validation_errors"]


def test_media_evidence_requires_full_hex_sha256_digest() -> None:
    with pytest.raises(ValueError, match="64-character hexadecimal digest"):
        MediaEvidenceRecord(
            media_type="image",
            sha256="g" * 64,
            extraction_mode="ocr",
            safety_status="cleared",
            provenance={"source": "test-suite"},
            derived_text="diagram says route through verifier",
        )


def test_dream_resources_reflect_structured_media_aware_findings() -> None:
    result = server.REGISTERED_TOOLS["hlf_dream_cycle_run"](
        max_artifacts=0,
        max_facts=0,
        media_evidence=[
            {
                "media_type": "diagram_image",
                "sha256": "b" * 64,
                "extraction_mode": "vision_summary",
                "derived_text": "architecture diagram shows memory to verifier flow",
                "safety_status": "cleared",
                "sanitization_notes": "metadata stripped",
                "confidence": 0.84,
                "artifact_id": "media-arch-1",
                "provenance": {
                    "source": "test-suite",
                    "collector": "pytest",
                    "collected_at": "2026-03-20T00:00:00+00:00",
                    "artifact_path": "fixtures/arch.png",
                },
                "operator_summary": "Architecture diagram normalized for advisory review",
            }
        ],
    )

    assert result["status"] == "ok"
    media_finding = next(
        finding for finding in result["findings"] if finding["topic"] == "multimodal-evidence"
    )

    status_resource = json.loads(server.REGISTERED_RESOURCES["hlf://status/dream-cycle"]())
    list_resource = json.loads(server.REGISTERED_RESOURCES["hlf://dream/findings"]())
    detail_resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://dream/findings/{finding_id}"](
            media_finding["finding_id"]
        )
    )

    assert status_resource["status"] == "ok"
    assert status_resource["dream_cycle_status"]["total_cycles"] >= 1
    assert list_resource["status"] == "ok"
    assert list_resource["operator_summary"]
    assert list_resource["evidence_refs"]
    assert any(
        finding["finding_id"] == media_finding["finding_id"]
        for finding in list_resource["findings"]
    )
    assert detail_resource["status"] == "ok"
    assert detail_resource["operator_summary"]
    assert detail_resource["evidence_refs"]
    assert "evidence_lineage" in detail_resource
    assert isinstance(detail_resource["evidence_lineage"], list)
    assert detail_resource["finding"]["media_evidence_present"] is True
    assert detail_resource["finding"]["media_types"] == ["diagram_image"]
    assert detail_resource["finding"]["operator_summary"]
    assert isinstance(detail_resource["finding"].get("evidence_lineage"), list)


def test_shared_media_evidence_is_persisted_in_memory_surface() -> None:
    result = server.REGISTERED_TOOLS["hlf_dream_cycle_run"](
        max_artifacts=0,
        max_facts=0,
        media_evidence=[
            {
                "media_type": "audio_transcript",
                "sha256": "c" * 64,
                "extraction_mode": "speech_to_text",
                "derived_text": "operator note describes verification gaps",
                "safety_status": "cleared",
                "confidence": 0.88,
                "artifact_id": "media-audio-1",
                "provenance": {
                    "source": "test-suite",
                    "collector": "pytest",
                    "collected_at": "2026-03-20T00:05:00+00:00",
                    "artifact_path": "fixtures/audio.wav",
                },
            }
        ],
    )

    listing = server.REGISTERED_TOOLS["hlf_media_evidence_list"]()
    fetched = server.REGISTERED_TOOLS["hlf_media_evidence_get"]("media-audio-1")
    resource = json.loads(
        server.REGISTERED_RESOURCES["hlf://media/evidence/{artifact_id}"]("media-audio-1")
    )

    assert result["status"] == "ok"
    assert result["media_evidence"][0]["artifact_id"] == "media-audio-1"
    assert listing["status"] == "ok"
    assert any(item["artifact_id"] == "media-audio-1" for item in listing["media_evidence"])
    assert fetched["status"] == "ok"
    assert fetched["media_evidence"]["memory_ref"]["sha256"]
    assert resource["status"] == "ok"
    assert resource["operator_summary"]
    assert resource["evidence_refs"]
    assert "evidence_lineage" in resource
    assert isinstance(resource["evidence_lineage"], list)
    assert resource["media_evidence"]["media_type"] == "audio_transcript"
    assert resource["media_evidence"]["operator_summary"]
    assert isinstance(resource["media_evidence"].get("evidence_lineage"), list)


def test_dream_proposal_enforces_observe_propose_verify_promote_chain() -> None:
    result = server.REGISTERED_TOOLS["hlf_dream_cycle_run"](
        max_artifacts=0,
        max_facts=1,
        media_evidence=[
            {
                "media_type": "diagram_image",
                "sha256": "d" * 64,
                "extraction_mode": "vision_summary",
                "derived_text": "diagram shows a verifier gate between proposal and promotion",
                "safety_status": "cleared",
                "confidence": 0.83,
                "artifact_id": "media-diagram-2",
                "provenance": {
                    "source": "test-suite",
                    "collector": "pytest",
                    "collected_at": "2026-03-20T00:10:00+00:00",
                    "artifact_path": "fixtures/gate.png",
                },
            }
        ],
    )

    proposal = server.REGISTERED_TOOLS["hlf_dream_proposal_create"](
        finding_ids=[result["findings"][0]["finding_id"], result["findings"][-1]["finding_id"]],
        title="Bind dream evidence into bridge proposal",
        summary="Use advisory dream evidence to stage a bridge-lane proposal without bypassing verify.",
        lane="bridge",
        proposal_text="Create a bounded bridge implementation guarded by explicit verification artifacts.",
        verification_plan=[
            "run focused dream/proposal regression tests",
            "capture operator review outcome",
        ],
    )
    listed = server.REGISTERED_TOOLS["hlf_dream_proposals_list"](lane="bridge")
    detail = json.loads(
        server.REGISTERED_RESOURCES["hlf://dream/proposals/{proposal_id}"](
            proposal["proposal"]["proposal_id"]
        )
    )

    assert proposal["status"] == "ok"
    citation_chain = proposal["proposal"]["citation_chain"]
    assert citation_chain["observe"]["finding_ids"]
    assert "media-diagram-2" in citation_chain["observe"]["media_evidence_ids"]
    assert citation_chain["verify"]["required"] is True
    assert citation_chain["verify"]["status"] == "pending"
    assert citation_chain["promote"]["eligible"] is False
    assert "verify_stage_incomplete" in citation_chain["promote"]["blocked_by"]
    assert listed["status"] == "ok"
    assert any(
        item["proposal_id"] == proposal["proposal"]["proposal_id"] for item in listed["proposals"]
    )
    assert detail["status"] == "ok"
    assert detail["operator_summary"]
    assert detail["evidence_refs"]
    assert "evidence_lineage" in detail
    assert isinstance(detail["evidence_lineage"], list)
    assert detail["proposal"]["lane"] == "bridge"
    assert detail["proposal"]["operator_summary"]
    assert isinstance(detail["proposal"].get("evidence_lineage"), list)
