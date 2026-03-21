from __future__ import annotations

import pytest

from hlf_mcp.media_evidence import MediaEvidenceRecord


def test_media_evidence_record_requires_full_sha256_hex_digest() -> None:
    with pytest.raises(ValueError, match="sha256 must be a 64-character hexadecimal digest"):
        MediaEvidenceRecord(
            media_type="image",
            sha256="abc123",
            extraction_mode="ocr",
            safety_status="reviewed",
            provenance={"source": "unit-test"},
            derived_text="normalized text",
        )


def test_media_evidence_record_rejects_non_hex_sha256_digest() -> None:
    with pytest.raises(ValueError, match="sha256 must be a 64-character hexadecimal digest"):
        MediaEvidenceRecord(
            media_type="image",
            sha256="g" * 64,
            extraction_mode="ocr",
            safety_status="reviewed",
            provenance={"source": "unit-test"},
            derived_text="normalized text",
        )


def test_media_evidence_record_accepts_normalized_uppercase_sha256_input() -> None:
    record = MediaEvidenceRecord(
        media_type="image",
        sha256="A" * 64,
        extraction_mode="ocr",
        safety_status="reviewed",
        provenance={"source": "unit-test"},
        derived_text="normalized text",
    )

    assert record.sha256 == "a" * 64
