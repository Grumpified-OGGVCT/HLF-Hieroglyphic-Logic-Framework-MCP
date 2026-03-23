from __future__ import annotations

import string
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

ALLOWED_MEDIA_TYPES = {
    "audio_transcript",
    "diagram_image",
    "document_image",
    "image",
    "video_summary",
}


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


@dataclass(slots=True)
class MediaEvidenceRecord:
    media_type: str
    sha256: str
    extraction_mode: str
    safety_status: str
    provenance: dict[str, Any]
    derived_text: str = ""
    structured_extraction_ref: str = ""
    sanitization_notes: str = ""
    confidence: float = 1.0
    source_path: str = ""
    artifact_id: str = ""
    operator_summary: str = ""
    collected_at: str = ""
    trust_tier: str = "normalized"

    def __post_init__(self) -> None:
        self.media_type = str(self.media_type or "").strip()
        self.sha256 = str(self.sha256 or "").strip().lower()
        self.extraction_mode = str(self.extraction_mode or "").strip()
        self.safety_status = str(self.safety_status or "").strip()
        self.derived_text = str(self.derived_text or "")
        self.structured_extraction_ref = str(self.structured_extraction_ref or "")
        self.sanitization_notes = str(self.sanitization_notes or "")
        self.source_path = str(self.source_path or "")
        self.artifact_id = str(self.artifact_id or "") or f"media-{self.sha256[:12]}"
        self.operator_summary = str(self.operator_summary or "")
        self.collected_at = str(
            self.collected_at or self.provenance.get("collected_at") or _iso_now()
        )
        self.trust_tier = str(self.trust_tier or "normalized")
        self.confidence = float(self.confidence)
        if self.media_type not in ALLOWED_MEDIA_TYPES:
            raise ValueError(f"Unsupported media_type: {self.media_type}")
        if len(self.sha256) != 64 or any(ch not in string.hexdigits for ch in self.sha256):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        if not self.extraction_mode:
            raise ValueError("extraction_mode is required for media evidence")
        if not self.safety_status:
            raise ValueError("safety_status is required for media evidence")
        if not isinstance(self.provenance, dict) or not self.provenance:
            raise ValueError("provenance is required for media evidence")
        if not (self.derived_text or self.structured_extraction_ref):
            raise ValueError("media evidence requires derived_text or structured_extraction_ref")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def render_content(self) -> str:
        summary = self.operator_summary or f"{self.media_type} evidence normalized"
        return (
            f"artifact_id={self.artifact_id}\n"
            f"media_type={self.media_type}\n"
            f"confidence={self.confidence:.2f}\n"
            f"safety_status={self.safety_status}\n"
            f"summary={summary}\n"
            f"derived_text={self.derived_text}"
        )

    def to_evidence_ref(self) -> dict[str, Any]:
        return {
            "kind": "media_evidence",
            "artifact_id": self.artifact_id,
            "media_type": self.media_type,
            "sha256": self.sha256,
            "extraction_mode": self.extraction_mode,
            "safety_status": self.safety_status,
            "source": self.provenance.get("source") or self.provenance.get("collector"),
            "source_path": self.source_path or self.provenance.get("artifact_path"),
        }


def normalize_media_evidence(items: list[dict[str, Any]] | None) -> list[MediaEvidenceRecord]:
    normalized: list[MediaEvidenceRecord] = []
    for item in items or []:
        normalized.append(
            MediaEvidenceRecord(
                media_type=str(item.get("media_type", "")),
                sha256=str(item.get("sha256", "")),
                extraction_mode=str(item.get("extraction_mode", "")),
                safety_status=str(item.get("safety_status", "")),
                provenance=dict(item.get("provenance") or {}),
                derived_text=str(item.get("derived_text", "")),
                structured_extraction_ref=str(item.get("structured_extraction_ref", "")),
                sanitization_notes=str(item.get("sanitization_notes", "")),
                confidence=float(item.get("confidence", 1.0)),
                source_path=str(item.get("source_path", "")),
                artifact_id=str(item.get("artifact_id", "")),
                operator_summary=str(item.get("operator_summary", "")),
                collected_at=str(item.get("collected_at", "")),
                trust_tier=str(item.get("trust_tier", "normalized")),
            )
        )
    return normalized
