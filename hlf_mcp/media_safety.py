from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import asdict, dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Optional PIL support for rich EXIF stripping
# ---------------------------------------------------------------------------
try:
    from PIL import Image

    HAS_PIL = True
except ImportError:  # pragma: no cover – fallback path only
    HAS_PIL = False

# ---------------------------------------------------------------------------
# Magic-byte signatures (first bytes of well-known formats)
# ---------------------------------------------------------------------------
_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "gif": [b"GIF8"],
    "pdf": [b"%PDF"],
    "mp3": [b"\xff\xfb", b"\xff\xf3", b"\xff\xf2", b"ID3"],
    "wav": [b"RIFF"],
    "mp4": [],  # handled specially – ftyp box after 4-byte size
    "txt": [b""],  # special-cased: absence of binary control chars
}

# ISO base media file format "ftyp" detection: skip 4-byte size, read "ftyp"
_FTYP_OFFSET = 4
_FTYP_MAGIC = b"ftyp"

# ---------------------------------------------------------------------------
# EXIF tag constants (APP1 marker and well-known IFD tag ids)
# ---------------------------------------------------------------------------
_EXIF_APP1_MARKER = b"\xff\xe1"
_EXIF_IDENT = b"Exif\x00\x00"

# Well-known EXIF tags we *always* strip (decimal tag ids)
_EXIF_TAG_NAMES: dict[int, str] = {
    # TIFF / IFD0
    0x010F: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013B: "Artist",
    0x013E: "WhitePoint",
    0x013F: "PrimaryChromaticities",
    0x0211: "YCbCrCoefficients",
    0x0213: "YCbCrPositioning",
    0x0214: "ReferenceBlackWhite",
    0x8298: "Copyright",
    # SubIFD
    0x920A: "FocalLength",
    # GPS IFD
    0x8825: "GPSInfo",
    # EXIF IFD
    0x8769: "ExifIFD",
    # Thumbnail-related
    0x0201: "JPEGInterchangeFormat",
    0x0202: "JPEGInterchangeFormatLength",
    # DateTime sub-tags in EXIF IFD
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    # MakerNote
    0x927C: "MakerNote",
}

# ---------------------------------------------------------------------------
# Prompt injection pattern bank
# ---------------------------------------------------------------------------

# Each entry: (pattern_name, severity, compiled_regex)
_INJECTION_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = []


def _compile_patterns() -> list[tuple[str, str, re.Pattern[str]]]:
    """Build the injection-pattern bank (done once at module load)."""
    patterns: list[tuple[str, str, re.Pattern[str]]] = []

    # -- System prompt extraction -------------------------------------------
    system_patterns = [
        ("system_prompt_extraction_ignore", re.compile(
            r"ignore\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|messages?|prompts?|directives?)",
            re.IGNORECASE,
        )),
        ("system_prompt_extraction_you_are", re.compile(
            r"(you\s+are\s+now|from\s+now\s+on\s+you\s+are|your\s+new\s+role\s+is)",
            re.IGNORECASE,
        )),
        ("system_prompt_extraction_reveal", re.compile(
            r"(system\s*prompt|original\s+instructions?|base\s+instructions?)",
            re.IGNORECASE,
        )),
        ("system_prompt_extraction_codeblock", re.compile(
            r"```\s*(system|instructions?|rules?|prompt)",
            re.IGNORECASE,
        )),
        ("system_prompt_extraction_print", re.compile(
            r"(print|show|display|repeat|output|dump)\s+(your\s+)?(system\s+)?(prompt|instructions?|rules?|directives?)",
            re.IGNORECASE,
        )),
        ("system_prompt_extraction_translate", re.compile(
            r"(translate|encode|decode)\s+(your\s+)?(system\s+)?(prompt|instructions?)",
            re.IGNORECASE,
        )),
    ]
    for name, pat in system_patterns:
        patterns.append((name, "critical", pat))

    # -- Delimiter injection ------------------------------------------------
    delimiter_patterns = [
        ("delimiter_injection_triple_backtick", re.compile(r"```")),
        ("delimiter_injection_xml", re.compile(
            r"</?\s*(system|function|tool|instruction|directive|prompt|rule|policy)",
            re.IGNORECASE,
        )),
        ("delimiter_injection_section", re.compile(r"^={3,}$", re.MULTILINE)),
        ("delimiter_injection_markdown_header_injection", re.compile(
            r"^#{1,6}\s+(system|instructions?|rules?|prompt|tool)", re.MULTILINE | re.IGNORECASE,
        )),
    ]
    for name, pat in delimiter_patterns:
        patterns.append((name, "high", pat))

    # -- Role confusion / jailbreak -----------------------------------------
    role_patterns = [
        ("role_confusion_dan", re.compile(
            r"\bDAN\b|do\s+anything\s+now", re.IGNORECASE,
        )),
        ("role_confusion_jailbreak", re.compile(
            r"\bjailbreak\b", re.IGNORECASE,
        )),
        ("role_confusion_developer_mode", re.compile(
            r"developer\s*mode|dev\s*mode", re.IGNORECASE,
        )),
        ("role_confusion_persona_switch", re.compile(
            r"pretend\s+(you\s+are|to\s+be)|act\s+as\s+(if|a|an)",
            re.IGNORECASE,
        )),
        ("role_confusion_no_limits", re.compile(
            r"(no\s+limits?|without\s+restrictions?|unfiltered|uncensored)",
            re.IGNORECASE,
        )),
        ("role_confusion_bypass_ethics", re.compile(
            r"(bypass|override|disable|ignore)\s+(your\s+)?(ethics|safety|restrictions?|rules?|guidelines?)",
            re.IGNORECASE,
        )),
    ]
    for name, pat in role_patterns:
        patterns.append((name, "high", pat))

    # -- Tool call injection ------------------------------------------------
    tool_patterns = [
        ("tool_call_function_json", re.compile(
            r'\{\s*"\s*(name|function|tool)\s*"\s*:\s*"',
        )),
        ("tool_call_tool_use_xml", re.compile(
            r"<\s*(tool_use|function_call|tool_call|invoke)", re.IGNORECASE,
        )),
        ("tool_call_execute_command", re.compile(
            r"(execute|run|invoke)\s+(command|tool|function)\s*[\(\"]",
            re.IGNORECASE,
        )),
    ]
    for name, pat in tool_patterns:
        patterns.append((name, "medium", pat))

    # -- Hidden text / Unicode control chars --------------------------------
    hidden_patterns = [
        ("hidden_text_zero_width", re.compile(
            r"[\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064"
            r"\ufeff\ufff9\ufffa\ufffb\ufffc]",
        )),
        ("hidden_text_unicode_control", re.compile(
            r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f]",
        )),
        ("hidden_text_bidi_override", re.compile(
            r"[\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069]",
        )),
    ]
    for name, pat in hidden_patterns:
        patterns.append((name, "medium", pat))

    return patterns


_INJECTION_PATTERNS = _compile_patterns()

# Severity ordering for threshold comparison
_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2, "critical": 3}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class PromptInjectionHit:
    """A single detected prompt-injection pattern."""

    pattern_name: str
    severity: str  # low | medium | high | critical
    matched_text: str  # truncated to 80 characters
    offset: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MediaSafetyConfig:
    """Configuration knobs for the media-safety scanning pipeline."""

    max_file_size_bytes: int = 10 * 1024 * 1024  # 10 MB
    allowed_extensions: set[str] = field(default_factory=lambda: {
        ".jpg", ".jpeg", ".png", ".gif", ".pdf", ".mp3", ".wav", ".mp4", ".txt",
    })
    enable_exif_stripping: bool = True
    enable_injection_scanning: bool = True
    injection_severity_threshold: str = "medium"


@dataclass(slots=True)
class SanitizedMediaResult:
    """Complete result of running the media-safety scan pipeline."""

    original_sha256: str
    sanitized_sha256: str
    passed: bool
    stripped_exif_fields: list[str] = field(default_factory=list)
    injection_hits: list[PromptInjectionHit] = field(default_factory=list)
    file_type_verified: bool = False
    size_within_limits: bool = False
    sanitization_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "original_sha256": self.original_sha256,
            "sanitized_sha256": self.sanitized_sha256,
            "passed": self.passed,
            "stripped_exif_fields": list(self.stripped_exif_fields),
            "injection_hits": [hit.to_dict() for hit in self.injection_hits],
            "file_type_verified": self.file_type_verified,
            "size_within_limits": self.size_within_limits,
            "sanitization_notes": self.sanitization_notes,
        }
        return result

    def is_safe_for_dream_cycle(self) -> bool:
        """Convenience method: returns True only if ALL checks passed."""
        return self.passed


# ---------------------------------------------------------------------------
# MediaSafetyScanner
# ---------------------------------------------------------------------------


class MediaSafetyScanner:
    """Multimodal media safety pipeline: EXIF, injections, magic bytes, size."""

    # ------------------------------------------------------------------
    # EXIF Sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def strip_exif(image_bytes: bytes) -> tuple[bytes, list[str]]:
        """Strip all EXIF metadata from *image_bytes*.

        Returns ``(sanitized_bytes, stripped_field_names)``.

        Uses Pillow when available; falls back to raw APP1-marker scanning
        otherwise (which covers JPEG only).
        """
        stripped: list[str] = []

        if HAS_PIL:
            return MediaSafetyScanner._strip_exif_pil(image_bytes, stripped)

        return MediaSafetyScanner._strip_exif_raw(image_bytes, stripped)

    # -- PIL path -----------------------------------------------------------

    @staticmethod
    def _strip_exif_pil(image_bytes: bytes, stripped: list[str]) -> tuple[bytes, list[str]]:
        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            # Cannot parse image at all — return as-is
            return image_bytes, stripped

        exif_data = img.getexif()
        if not exif_data:
            # No EXIF to strip
            return image_bytes, stripped

        for tag_id in list(exif_data.keys()):
            name = _EXIF_TAG_NAMES.get(tag_id, f"EXIF-{tag_id}")
            if tag_id in _EXIF_TAG_NAMES and name not in stripped:
                stripped.append(name)

        # Build a clean image without EXIF
        # We use Image.new to copy pixel data without metadata
        try:
            clean = Image.new(img.mode, img.size)
            clean.putdata(list(img.getdata()))
        except Exception:
            # Fallback: just convert to RGB and save without EXIF
            clean = img.convert("RGB")

        buf = io.BytesIO()
        fmt = img.format or "PNG"
        clean.save(buf, format=fmt)
        return buf.getvalue(), stripped

    # -- Raw fallback path (JPEG APP1 marker scanning) ----------------------

    @staticmethod
    def _strip_exif_raw(image_bytes: bytes, stripped: list[str]) -> tuple[bytes, list[str]]:
        """Scan for JPEG APP1/Exif markers and remove them.

        Only works for JPEG files. For non-JPEG input returns bytes unchanged.
        """
        if len(image_bytes) < 4 or image_bytes[:2] != b"\xff\xd8":
            return image_bytes, stripped

        out = bytearray()
        pos = 2
        out.extend(image_bytes[:2])  # SOI marker

        while pos < len(image_bytes) - 1:
            if image_bytes[pos] != 0xFF:
                # Not a marker — just copy
                out.append(image_bytes[pos])
                pos += 1
                continue

            marker = image_bytes[pos + 1]

            # SOS marker (0xDA) — copy rest verbatim
            if marker == 0xDA:
                out.extend(image_bytes[pos:])
                break

            # APP1 marker (0xE1) — check for Exif
            if marker == 0xE1 and pos + 4 < len(image_bytes):
                seg_len = struct.unpack(">H", image_bytes[pos + 2:pos + 4])[0]
                if pos + 2 + seg_len <= len(image_bytes):
                    seg_data = image_bytes[pos + 4:pos + 2 + seg_len]
                    if seg_data[:6] == _EXIF_IDENT:
                        stripped.append("APP1_Exif")
                        pos += 2 + seg_len
                        continue

            # Handle segment-length-prefixed markers (APP0–APP15, DQT, DHT, etc.)
            if 0xE0 <= marker <= 0xEF or marker in (0xC0, 0xC2, 0xC4, 0xDB, 0xDD, 0xFE):
                if pos + 4 > len(image_bytes):
                    out.extend(image_bytes[pos:])
                    break
                seg_len = struct.unpack(">H", image_bytes[pos + 2:pos + 4])[0]
                if pos + 2 + seg_len > len(image_bytes):
                    out.extend(image_bytes[pos:])
                    break
                out.extend(image_bytes[pos:pos + 2 + seg_len])
                pos += 2 + seg_len
                continue

            # Standalone marker (DNL, RST, etc.) — copy 2 bytes
            out.extend(image_bytes[pos:pos + 2])
            pos += 2

        return bytes(out), stripped

    # ------------------------------------------------------------------
    # Prompt Injection Screening
    # ------------------------------------------------------------------

    @staticmethod
    def scan_for_injections(text: str) -> list[PromptInjectionHit]:
        """Scan *text* for known prompt-injection patterns.

        Returns a (possibly empty) list of :class:`PromptInjectionHit`.
        """
        if not text:
            return []

        # Ensure we're working with valid Unicode – replace surrogates / lone
        # surrogates that would break regex matching
        try:
            text.encode("utf-8")
        except UnicodeEncodeError:
            # Replace unencodable characters with the U+FFFD replacement character
            text = text.encode("utf-8", errors="replace").decode("utf-8")

        hits: list[PromptInjectionHit] = []
        seen_spans: set[tuple[int, int]] = set()

        for pattern_name, severity, pattern in _INJECTION_PATTERNS:
            for match in pattern.finditer(text):
                span = match.span()
                # Avoid duplicate overlapping hits from different patterns
                if span in seen_spans:
                    continue
                seen_spans.add(span)

                matched = match.group(0)
                truncated = matched[:80] + "…" if len(matched) > 80 else matched

                hits.append(
                    PromptInjectionHit(
                        pattern_name=pattern_name,
                        severity=severity,
                        matched_text=truncated,
                        offset=match.start(),
                    )
                )

        return hits

    # ------------------------------------------------------------------
    # File Safety Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _guess_type_from_bytes(data: bytes) -> str | None:
        """Return a media-type category inferred from magic bytes."""
        if len(data) == 0:
            return None

        for cat, sigs in _MAGIC_SIGNATURES.items():
            if cat == "mp4":
                # ftyp box check
                if len(data) >= 12:
                    if data[_FTYP_OFFSET:_FTYP_OFFSET + 4] == _FTYP_MAGIC:
                        return "mp4"
                continue
            if cat == "txt":
                continue  # handled separately
            for sig in sigs:
                if data[:len(sig)] == sig:
                    return cat

        # txt fallback: no null bytes and no excessive binary control chars
        if b"\x00" not in data[:4096]:
            control_count = sum(
                1 for b in data[:4096]
                if b < 0x09 or (0x0B <= b <= 0x0C) or (0x0E <= b <= 0x1F) or b == 0x7F
            )
            if control_count < len(data[:4096]) * 0.05:  # fewer than 5% control chars
                return "txt"

        return None

    @staticmethod
    def validate_file_type(data: bytes, claimed_type: str) -> bool:
        """Validate that *data* matches the claimed media type via magic bytes.

        *claimed_type* should be one of the values in ``ALLOWED_MEDIA_TYPES``
        or a well-known format name like ``"jpeg"``, ``"png"``, etc.
        """
        if not data:
            return False

        # Map ALLOWED_MEDIA_TYPES to magic-type categories
        type_map: dict[str, set[str]] = {
            "image": {"jpeg", "png", "gif"},
            "diagram_image": {"jpeg", "png", "gif"},
            "document_image": {"jpeg", "png", "gif", "pdf"},
            "audio_transcript": {"txt", "mp3", "wav"},
            "video_summary": {"txt", "mp4"},
            # Bare format names
            "jpeg": {"jpeg"},
            "jpg": {"jpeg"},
            "png": {"png"},
            "gif": {"gif"},
            "pdf": {"pdf"},
            "mp3": {"mp3"},
            "wav": {"wav"},
            "mp4": {"mp4"},
            "txt": {"txt"},
        }

        allowed = type_map.get(claimed_type.lower())
        if allowed is None:
            # Unknown claimed type — be permissive for forward compatibility
            return True

        inferred = MediaSafetyScanner._guess_type_from_bytes(data)
        if inferred is None:
            return False

        return inferred in allowed

    @staticmethod
    def check_file_size(data: bytes, max_size: int) -> bool:
        """Return ``True`` if *data* is within the *max_size* limit (bytes)."""
        return len(data) <= max_size

    # ------------------------------------------------------------------
    # Full scan pipeline
    # ------------------------------------------------------------------

    @staticmethod
    def scan_media(
        data: bytes,
        media_type: str,
        derived_text: str,
        config: MediaSafetyConfig | None = None,
    ) -> SanitizedMediaResult:
        """Run the complete safety pipeline on one media artifact.

        Parameters
        ----------
        data:
            Raw bytes of the media file.
        media_type:
            One of ``ALLOWED_MEDIA_TYPES``.
        derived_text:
            Text extracted from the media (may be empty string).
        config:
            Optional configuration; uses :class:`MediaSafetyConfig` defaults
            if not provided.

        Returns
        -------
        :class:`SanitizedMediaResult`
        """
        if config is None:
            config = MediaSafetyConfig()

        original_sha256 = hashlib.sha256(data).hexdigest()
        notes_parts: list[str] = []
        checks_passed: list[bool] = []

        # --- EXIF stripping -------------------------------------------------
        stripped_exif: list[str] = []
        sanitized_bytes = data

        if config.enable_exif_stripping:
            # Only strip for image-like types
            image_types = {"image", "diagram_image", "document_image"}
            if media_type in image_types:
                sanitized_bytes, stripped_exif = MediaSafetyScanner.strip_exif(data)
                if stripped_exif:
                    notes_parts.append(
                        f"EXIF stripped: {', '.join(sorted(stripped_exif))}"
                    )
        # EXIF stripping is advisory, not a hard failure
        # (it just feeds into sanitization_notes)

        sanitized_sha256 = hashlib.sha256(sanitized_bytes).hexdigest()

        # --- File type validation ------------------------------------------
        file_type_verified = MediaSafetyScanner.validate_file_type(data, media_type)
        checks_passed.append(file_type_verified)
        if not file_type_verified:
            notes_parts.append(
                f"File type validation FAILED: claimed={media_type}, "
                f"detected={MediaSafetyScanner._guess_type_from_bytes(data) or 'unknown'}"
            )

        # --- File size -----------------------------------------------------
        size_within_limits = MediaSafetyScanner.check_file_size(
            data, config.max_file_size_bytes
        )
        checks_passed.append(size_within_limits)
        if not size_within_limits:
            notes_parts.append(
                f"File size {len(data)} bytes exceeds limit "
                f"of {config.max_file_size_bytes} bytes"
            )

        # --- Injection scanning --------------------------------------------
        injection_hits: list[PromptInjectionHit] = []
        if config.enable_injection_scanning and derived_text:
            try:
                injection_hits = MediaSafetyScanner.scan_for_injections(derived_text)
            except Exception:
                # If scanning itself fails, treat as an injection concern
                injection_hits = [
                    PromptInjectionHit(
                        pattern_name="scanning_failure",
                        severity="high",
                        matched_text="[injection scanning raised an exception]",
                        offset=0,
                    )
                ]

        if injection_hits:
            threshold = _SEVERITY_ORDER.get(config.injection_severity_threshold, 1)
            severe_hits = [
                h for h in injection_hits
                if _SEVERITY_ORDER.get(h.severity, 0) >= threshold
            ]
            if severe_hits:
                checks_passed.append(False)
                notes_parts.append(
                    f"Injection hits ({len(severe_hits)} above "
                    f"threshold '{config.injection_severity_threshold}'): "
                    + ", ".join(
                        f"{h.pattern_name}({h.severity})" for h in severe_hits[:5]
                    )
                )
            elif injection_hits:
                # Hits exist but all below threshold — warn but don't fail
                checks_passed.append(True)
                notes_parts.append(
                    f"Injection hits ({len(injection_hits)} below "
                    f"threshold '{config.injection_severity_threshold}'): "
                    + ", ".join(
                        f"{h.pattern_name}({h.severity})" for h in injection_hits[:5]
                    )
                )
        else:
            checks_passed.append(True)  # No injection hits — this check passes

        # --- Determine overall pass/fail -----------------------------------
        passed = all(checks_passed)

        if not stripped_exif and not injection_hits and passed:
            notes_parts.append("All safety checks passed")

        return SanitizedMediaResult(
            original_sha256=original_sha256,
            sanitized_sha256=sanitized_sha256,
            passed=passed,
            stripped_exif_fields=stripped_exif,
            injection_hits=injection_hits,
            file_type_verified=file_type_verified,
            size_within_limits=size_within_limits,
            sanitization_notes="; ".join(notes_parts),
        )


# Re-export the io module reference for test patching
import io  # noqa: E402 – keep after class def for clean module-level visibility
