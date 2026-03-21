from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Any

from hlf_mcp.media_evidence import MediaEvidenceRecord


def _digest(*parts: str) -> str:
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


DreamMediaEvidence = MediaEvidenceRecord


@dataclass(slots=True)
class DreamFinding:
    finding_id: str
    created_at: str
    cycle_id: str
    title: str
    summary: str
    topic: str
    confidence: float
    evidence_refs: list[dict[str, Any]]
    source_artifact_ids: list[str]
    witness_status: str
    provenance: dict[str, Any]
    advisory_only: bool = True
    novelty_score: float | None = None
    quality_score: float | None = None
    candidate_actions: list[str] = field(default_factory=list)
    related_memory_keys: list[str] = field(default_factory=list)
    supersedes: str = ""
    media_evidence_present: bool = False
    media_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render_content(self) -> str:
        return (
            f"{self.title}\n"
            f"topic={self.topic}\n"
            f"confidence={self.confidence:.2f}\n"
            f"advisory_only={self.advisory_only}\n"
            f"summary={self.summary}"
        )


@dataclass(slots=True)
class DreamCycleReport:
    cycle_id: str
    started_at: str
    completed_at: str
    input_window: str
    artifact_count: int
    media_artifact_count: int
    finding_count: int
    high_confidence_count: int
    status: str
    witness_record_id: str
    artifact_ids: list[str] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_dream_findings(
    *,
    cycle_id: str,
    created_at: str,
    weekly_artifacts: list[dict[str, Any]],
    memory_facts: list[dict[str, Any]],
    media_evidence: list[MediaEvidenceRecord],
    witness_record_id: str,
) -> list[DreamFinding]:
    findings: list[DreamFinding] = []

    if weekly_artifacts:
        artifact_ids = [str(artifact.get("artifact_id", "")) for artifact in weekly_artifacts]
        statuses = sorted(
            {
                str(artifact.get("artifact_status") or "advisory")
                for artifact in weekly_artifacts
            }
        )
        sources = sorted({str(artifact.get("source") or "unknown") for artifact in weekly_artifacts})
        findings.append(
            DreamFinding(
                finding_id=f"dream-finding-{_digest(cycle_id, 'weekly')}",
                created_at=created_at,
                cycle_id=cycle_id,
                title="Weekly evidence synthesis",
                summary=(
                    f"Reviewed {len(weekly_artifacts)} governed weekly artifacts across "
                    f"{len(sources)} source lanes; current statuses={', '.join(statuses)}."
                ),
                topic="weekly-evidence",
                confidence=0.76,
                evidence_refs=[
                    {
                        "kind": "weekly_artifact",
                        "artifact_id": artifact_id,
                        "status": str(artifact.get("artifact_status") or "advisory"),
                        "source": str(artifact.get("source") or "unknown"),
                    }
                    for artifact, artifact_id in zip(weekly_artifacts, artifact_ids)
                ],
                source_artifact_ids=artifact_ids,
                witness_status="linked",
                provenance={
                    "source_type": "dream_cycle",
                    "source": "server_context.run_dream_cycle",
                    "collector": "hlf_mcp.dream_cycle",
                    "collected_at": created_at,
                    "witness_record_id": witness_record_id,
                },
                advisory_only=True,
                candidate_actions=[
                    "review outstanding weekly artifact decisions",
                    "verify any artifact marked for promotion before merge",
                ],
            )
        )

    if memory_facts:
        counts: dict[str, int] = {}
        related_memory_keys: list[str] = []
        for fact in memory_facts:
            entry_kind = str(fact.get("entry_kind") or "fact")
            counts[entry_kind] = counts.get(entry_kind, 0) + 1
            related_memory_keys.append(str(fact.get("sha256") or ""))
        ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        summary = ", ".join(f"{kind}={count}" for kind, count in ranked[:4])
        evidence_refs = [
            {
                "kind": str(fact.get("entry_kind") or "fact"),
                "fact_id": int(fact.get("id") or 0),
                "sha256": str(fact.get("sha256") or ""),
                "topic": str(fact.get("topic") or ""),
            }
            for fact in memory_facts[:5]
        ]
        findings.append(
            DreamFinding(
                finding_id=f"dream-finding-{_digest(cycle_id, 'memory')}",
                created_at=created_at,
                cycle_id=cycle_id,
                title="Memory pattern synthesis",
                summary=(
                    f"Bounded synthesis over governed memory found the strongest current "
                    f"pattern mix as {summary}."
                ),
                topic="memory-patterns",
                confidence=0.71,
                evidence_refs=evidence_refs,
                source_artifact_ids=[str(fact.get("sha256") or "") for fact in memory_facts[:5]],
                witness_status="linked",
                provenance={
                    "source_type": "dream_cycle",
                    "source": "server_context.run_dream_cycle",
                    "collector": "hlf_mcp.dream_cycle",
                    "collected_at": created_at,
                    "witness_record_id": witness_record_id,
                },
                advisory_only=True,
                related_memory_keys=[key for key in related_memory_keys if key],
                candidate_actions=[
                    "inspect the highest-frequency governed evidence kinds",
                    "use these findings as advisory inputs for bounded proposal work only",
                ],
            )
        )

    if media_evidence:
        media_types = sorted({item.media_type for item in media_evidence})
        confidence = round(
            sum(item.confidence for item in media_evidence) / len(media_evidence), 4
        )
        findings.append(
            DreamFinding(
                finding_id=f"dream-finding-{_digest(cycle_id, 'media')}",
                created_at=created_at,
                cycle_id=cycle_id,
                title="Multimodal evidence admitted",
                summary=(
                    f"Admitted {len(media_evidence)} normalized media evidence artifact(s) "
                    f"covering {', '.join(media_types)} without bypassing provenance or safety gates."
                ),
                topic="multimodal-evidence",
                confidence=confidence,
                evidence_refs=[item.to_evidence_ref() for item in media_evidence],
                source_artifact_ids=[item.artifact_id for item in media_evidence],
                witness_status="linked",
                provenance={
                    "source_type": "dream_cycle",
                    "source": "server_context.run_dream_cycle",
                    "collector": "hlf_mcp.dream_cycle",
                    "collected_at": created_at,
                    "witness_record_id": witness_record_id,
                },
                advisory_only=True,
                media_evidence_present=True,
                media_types=media_types,
                candidate_actions=[
                    "keep media-derived findings advisory until stronger host-function contracts land",
                ],
            )
        )

    return findings