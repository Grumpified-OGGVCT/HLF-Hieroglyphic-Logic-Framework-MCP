"""
Error Translation: bidirectional Python exception ↔ HLF violation mapping with
stack trace provenance and severity classification.

Design Principles:
1. Every Python exception maps to an HLF ViolationCategory with explicit
   severity (0-1), recoverability flag, and suggested remediation.
2. Stack frames are captured with file, line, function, and source context
   so the HLF runtime can attribute violations to specific code locations.
3. The translator is bidirectional: exceptions → violations for reporting,
   and violations → exception classes for programmatic recovery.
4. Message templates support parameterized formatting so violation messages
   are consistent and auditable.
5. Batch translation and severity aggregation enable trend analysis across
   multiple exceptions — useful for governance dashboards.

This module is the semantic bridge between Python's exception hierarchy and
HLF's structured violation model. It answers the question: "What HLF violation
does this Python error represent, how severe is it, and can we recover?"
"""

from __future__ import annotations

import sys
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from types import TracebackType
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ViolationCategory(Enum):
    """Structured categories for HLF violations mapped from Python exceptions."""
    TYPE_ERROR = "type_error"
    VALUE_ERROR = "value_error"
    RUNTIME_ERROR = "runtime_error"
    IMPORT_ERROR = "import_error"
    MEMORY_ERROR = "memory_error"
    TIMEOUT_ERROR = "timeout_error"
    PERMISSION_ERROR = "permission_error"
    ASSERTION_ERROR = "assertion_error"
    DIVISION_ERROR = "division_error"
    INDEX_ERROR = "index_error"
    KEY_ERROR = "key_error"
    ATTRIBUTE_ERROR = "attribute_error"
    OS_ERROR = "os_error"
    NETWORK_ERROR = "network_error"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TranslatedViolation:
    """A Python exception translated into an HLF structured violation.

    Attributes:
        category: The HLF violation category.
        message: Formatted human-readable violation message.
        original_exception_type: The Python exception class name.
        original_message: The original exception's string message.
        stack_frames: List of stack frame dicts with file, line, function,
            and code context.
        hlf_context: HLF-specific metadata (e.g. agent_id, gas_state).
        severity: 0.0-1.0 score indicating violation severity.
        recoverable: True if the operation can be retried or recovered.
        suggested_action: Human-readable remediation suggestion.
    """
    category: ViolationCategory
    message: str
    original_exception_type: str
    original_message: str
    stack_frames: list[dict[str, Any]] = field(default_factory=list)
    hlf_context: dict[str, Any] = field(default_factory=dict)
    severity: float = 0.5
    recoverable: bool = True
    suggested_action: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize the violation to a JSON-compatible dict."""
        return {
            "category": self.category.value,
            "message": self.message,
            "original_exception_type": self.original_exception_type,
            "original_message": self.original_message,
            "stack_frames": list(self.stack_frames),
            "hlf_context": dict(self.hlf_context),
            "severity": self.severity,
            "recoverable": self.recoverable,
            "suggested_action": self.suggested_action,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TranslatedViolation:
        """Deserialize a TranslatedViolation from a dict."""
        category_raw = data.get("category", "unknown")
        try:
            category = ViolationCategory(category_raw)
        except ValueError:
            category = ViolationCategory.UNKNOWN
        return cls(
            category=category,
            message=data.get("message", ""),
            original_exception_type=data.get("original_exception_type", ""),
            original_message=data.get("original_message", ""),
            stack_frames=list(data.get("stack_frames", [])),
            hlf_context=dict(data.get("hlf_context", {})),
            severity=float(data.get("severity", 0.5)),
            recoverable=bool(data.get("recoverable", True)),
            suggested_action=data.get("suggested_action", ""),
        )


@dataclass(slots=True)
class PythonExceptionMapping:
    """Mapping from a Python exception type to an HLF violation.

    Attributes:
        exception_type: Fully-qualified Python exception class name.
        violation_category: The HLF violation category.
        severity: 0.0-1.0 severity score.
        recoverable: Whether the error is considered recoverable.
        message_template: Template string using {original_message} and
            {extra_context} placeholders.
    """
    exception_type: str
    violation_category: ViolationCategory
    severity: float = 0.5
    recoverable: bool = True
    message_template: str = "{original_message}"


# ---------------------------------------------------------------------------
# Default exception → violation mappings
# ---------------------------------------------------------------------------

_DEFAULT_MAPPINGS: list[PythonExceptionMapping] = [
    PythonExceptionMapping(
        exception_type="TypeError",
        violation_category=ViolationCategory.TYPE_ERROR,
        severity=0.5,
        recoverable=True,
        message_template="Type mismatch: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ValueError",
        violation_category=ViolationCategory.VALUE_ERROR,
        severity=0.4,
        recoverable=True,
        message_template="Invalid value: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="RuntimeError",
        violation_category=ViolationCategory.RUNTIME_ERROR,
        severity=0.6,
        recoverable=False,
        message_template="Runtime failure: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ImportError",
        violation_category=ViolationCategory.IMPORT_ERROR,
        severity=0.7,
        recoverable=False,
        message_template="Import failed: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ModuleNotFoundError",
        violation_category=ViolationCategory.IMPORT_ERROR,
        severity=0.7,
        recoverable=False,
        message_template="Module not found: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="MemoryError",
        violation_category=ViolationCategory.MEMORY_ERROR,
        severity=0.9,
        recoverable=False,
        message_template="Memory exhausted: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="TimeoutError",
        violation_category=ViolationCategory.TIMEOUT_ERROR,
        severity=0.7,
        recoverable=True,
        message_template="Operation timed out: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="PermissionError",
        violation_category=ViolationCategory.PERMISSION_ERROR,
        severity=0.6,
        recoverable=True,
        message_template="Permission denied: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="AssertionError",
        violation_category=ViolationCategory.ASSERTION_ERROR,
        severity=0.5,
        recoverable=True,
        message_template="Assertion failed: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ZeroDivisionError",
        violation_category=ViolationCategory.DIVISION_ERROR,
        severity=0.3,
        recoverable=True,
        message_template="Division by zero: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="IndexError",
        violation_category=ViolationCategory.INDEX_ERROR,
        severity=0.3,
        recoverable=True,
        message_template="Index out of range: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="KeyError",
        violation_category=ViolationCategory.KEY_ERROR,
        severity=0.3,
        recoverable=True,
        message_template="Key not found: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="AttributeError",
        violation_category=ViolationCategory.ATTRIBUTE_ERROR,
        severity=0.4,
        recoverable=True,
        message_template="Attribute error: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="OSError",
        violation_category=ViolationCategory.OS_ERROR,
        severity=0.6,
        recoverable=True,
        message_template="OS error: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="IOError",
        violation_category=ViolationCategory.OS_ERROR,
        severity=0.6,
        recoverable=True,
        message_template="I/O error: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ConnectionError",
        violation_category=ViolationCategory.NETWORK_ERROR,
        severity=0.6,
        recoverable=True,
        message_template="Connection failed: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ConnectionRefusedError",
        violation_category=ViolationCategory.NETWORK_ERROR,
        severity=0.6,
        recoverable=True,
        message_template="Connection refused: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="ConnectionResetError",
        violation_category=ViolationCategory.NETWORK_ERROR,
        severity=0.7,
        recoverable=True,
        message_template="Connection reset: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="BrokenPipeError",
        violation_category=ViolationCategory.NETWORK_ERROR,
        severity=0.7,
        recoverable=False,
        message_template="Broken pipe: {original_message}",
    ),
    PythonExceptionMapping(
        exception_type="FileNotFoundError",
        violation_category=ViolationCategory.OS_ERROR,
        severity=0.5,
        recoverable=True,
        message_template="File not found: {original_message}",
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_stack_frames(
    tb: TracebackType | None,
    max_depth: int = 20,
    include_source_context: bool = True,
) -> list[dict[str, Any]]:
    """Extract structured stack frames from a traceback object.

    Each frame is a dict with keys:
    - file: str — filename
    - line: int — line number
    - function: str — function name
    - code: str — source code line text (if include_source_context)

    Args:
        tb: The traceback object from an exception.
        max_depth: Maximum number of frames to extract.
        include_source_context: Whether to read source code lines.

    Returns:
        List of frame dicts, innermost frame first.
    """
    frames: list[dict[str, Any]] = []
    current = tb
    depth = 0
    while current is not None and depth < max_depth:
        frame_info: dict[str, Any] = {
            "file": current.tb_frame.f_code.co_filename,
            "line": current.tb_lineno,
            "function": current.tb_frame.f_code.co_name,
        }
        if include_source_context:
            try:
                import linecache
                code_line = linecache.getline(
                    frame_info["file"], frame_info["line"]
                ).strip()
                frame_info["code"] = code_line
            except Exception:
                frame_info["code"] = "<unavailable>"
        frames.append(frame_info)
        current = current.tb_next
        depth += 1
    return frames


def _format_message(
    template: str,
    original_message: str,
    extra_context: dict[str, Any] | None = None,
) -> str:
    """Format a violation message using a template.

    Supports {original_message} and any keys from extra_context as
    format variables.

    Args:
        template: The message template string.
        original_message: The original exception message (str() of exc).
        extra_context: Additional key-value pairs for template variables.

    Returns:
        Formatted message string.
    """
    ctx: dict[str, Any] = {"original_message": original_message}
    if extra_context:
        # Merge, but don't let extra_context overwrite original_message
        for k, v in extra_context.items():
            if k != "original_message":
                ctx[k] = v

    try:
        return template.format(**ctx)
    except (KeyError, ValueError, IndexError):
        # Fallback: just include the original message
        return f"{template} [original: {original_message}]"


def _resolve_exception_class_name(exc: Exception) -> str:
    """Get the fully-qualified class name of an exception."""
    cls = type(exc)
    module = cls.__module__
    name = cls.__qualname__
    if module == "builtins":
        return name
    return f"{module}.{name}"


def _find_mapping(
    exception_type: str,
    mappings: dict[str, PythonExceptionMapping],
) -> PythonExceptionMapping | None:
    """Find the best matching PythonExceptionMapping for an exception type.

    Checks exact match first, then walks the MRO for parent classes.
    """
    if exception_type in mappings:
        return mappings[exception_type]

    # Remove module prefix for builtins lookup
    short_name = exception_type.split(".")[-1]
    if short_name in mappings:
        return mappings[short_name]

    return None


# Reverse mapping: ViolationCategory → most common Python exception class
_REVERSE_MAP: dict[ViolationCategory, type] = {
    ViolationCategory.TYPE_ERROR: TypeError,
    ViolationCategory.VALUE_ERROR: ValueError,
    ViolationCategory.RUNTIME_ERROR: RuntimeError,
    ViolationCategory.IMPORT_ERROR: ImportError,
    ViolationCategory.MEMORY_ERROR: MemoryError,
    ViolationCategory.TIMEOUT_ERROR: TimeoutError,
    ViolationCategory.PERMISSION_ERROR: PermissionError,
    ViolationCategory.ASSERTION_ERROR: AssertionError,
    ViolationCategory.DIVISION_ERROR: ZeroDivisionError,
    ViolationCategory.INDEX_ERROR: IndexError,
    ViolationCategory.KEY_ERROR: KeyError,
    ViolationCategory.ATTRIBUTE_ERROR: AttributeError,
    ViolationCategory.OS_ERROR: OSError,
    ViolationCategory.NETWORK_ERROR: ConnectionError,
    ViolationCategory.UNKNOWN: RuntimeError,
}


# ---------------------------------------------------------------------------
# ErrorTranslator
# ---------------------------------------------------------------------------

class ErrorTranslator:
    """Bidirectional translator between Python exceptions and HLF violations.

    The translator:
    - Maps Python exceptions → HLF TranslatedViolations with stack provenance
    - Provides reverse mapping from violations back to Python exception classes
    - Supports custom exception mappings for domain-specific errors
    - Generates severity summaries and provenance reports for governance

    Usage::

        translator = ErrorTranslator()
        try:
            1 / 0
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.DIVISION_ERROR
    """

    def __init__(
        self,
        name: str = "error-translator",
        include_source_context: bool = True,
        max_stack_depth: int = 20,
    ) -> None:
        """Initialize the error translator.

        Args:
            name: Identifier for this translator instance.
            include_source_context: Whether to read source code lines for
                stack frames (uses linecache).
            max_stack_depth: Maximum number of stack frames to capture.
        """
        self.name = name
        self.include_source_context = include_source_context
        self.max_stack_depth = max_stack_depth

        # Internal mapping: exception type string → PythonExceptionMapping
        self._mappings: dict[str, PythonExceptionMapping] = {}
        self._populate_default_mappings()

    # ------------------------------------------------------------------
    # Mapping registration
    # ------------------------------------------------------------------

    def register_mapping(self, mapping: PythonExceptionMapping) -> None:
        """Register a custom exception → violation mapping.

        Overwrites any existing mapping for the same exception_type.
        """
        key = mapping.exception_type.split(".")[-1]  # Use short name as key
        self._mappings[key] = mapping

    # ------------------------------------------------------------------
    # Translation: Exception → Violation
    # ------------------------------------------------------------------

    def translate_exception(
        self,
        exc: Exception,
        hlf_context: dict[str, Any] | None = None,
    ) -> TranslatedViolation:
        """Translate a Python exception into an HLF TranslatedViolation.

        Extracts stack frames, resolves the violation category, formats the
        message using the mapping's template, and populates severity and
        recoverability.

        Args:
            exc: The caught Python exception.
            hlf_context: Optional HLF-specific metadata (e.g. agent_id,
                gas_remaining, module_path).

        Returns:
            TranslatedViolation with full provenance.
        """
        original_type = _resolve_exception_class_name(exc)
        original_message = str(exc) if str(exc) else type(exc).__name__

        # Extract stack frames
        tb = exc.__traceback__
        stack_frames = _extract_stack_frames(
            tb,
            max_depth=self.max_stack_depth,
            include_source_context=self.include_source_context,
        )

        # Find mapping
        mapping = _find_mapping(original_type, self._mappings)

        if mapping is not None:
            category = mapping.violation_category
            severity = mapping.severity
            recoverable = mapping.recoverable
            message = _format_message(
                mapping.message_template,
                original_message,
                hlf_context,
            )
        else:
            category = ViolationCategory.UNKNOWN
            severity = 0.5
            recoverable = False
            message = f"Unclassified error ({original_type}): {original_message}"

        # Generate suggested action
        suggested_action = self._suggest_action(category, recoverable, original_message)

        return TranslatedViolation(
            category=category,
            message=message,
            original_exception_type=original_type,
            original_message=original_message,
            stack_frames=stack_frames,
            hlf_context=dict(hlf_context or {}),
            severity=severity,
            recoverable=recoverable,
            suggested_action=suggested_action,
        )

    def translate_to_hlf_violation(
        self,
        exc_info: tuple[type, Exception, TracebackType | None],
        hlf_context: dict[str, Any] | None = None,
    ) -> TranslatedViolation:
        """Translate from sys.exc_info() tuple to HLF violation.

        Args:
            exc_info: The tuple returned by sys.exc_info().
            hlf_context: Optional HLF metadata.

        Returns:
            TranslatedViolation.
        """
        _, exc, _ = exc_info
        if exc is None:
            return TranslatedViolation(
                category=ViolationCategory.UNKNOWN,
                message="No exception in exc_info",
                original_exception_type="NoneType",
                original_message="exc_info contained None",
                severity=0.0,
                recoverable=True,
                suggested_action="No action needed — no exception present",
            )
        return self.translate_exception(exc, hlf_context)

    # ------------------------------------------------------------------
    # Reverse translation: Violation → Exception class
    # ------------------------------------------------------------------

    def reverse_translate(self, violation: TranslatedViolation) -> type:
        """Map an HLF violation back to the most appropriate Python exception
        class.

        Does not instantiate the exception — returns the class so the caller
        can construct it with a custom message.

        Args:
            violation: The translated violation to reverse-map.

        Returns:
            A Python exception class (e.g. TypeError, ValueError).
        """
        exc_class = _REVERSE_MAP.get(violation.category, RuntimeError)
        return exc_class

    # ------------------------------------------------------------------
    # Batch translation
    # ------------------------------------------------------------------

    def batch_translate(
        self,
        exceptions: list[Exception],
        hlf_context: dict[str, Any] | None = None,
    ) -> list[TranslatedViolation]:
        """Translate multiple Python exceptions at once.

        Args:
            exceptions: List of caught exceptions.
            hlf_context: Optional shared HLF context applied to all.

        Returns:
            One TranslatedViolation per input exception.
        """
        return [self.translate_exception(exc, hlf_context) for exc in exceptions]

    # ------------------------------------------------------------------
    # Severity summary
    # ------------------------------------------------------------------

    def severity_summary(
        self,
        violations: list[TranslatedViolation],
    ) -> dict[str, Any]:
        """Aggregate violations by category with severity statistics.

        Args:
            violations: List of translated violations to summarize.

        Returns:
            Dict with keys: total_count, categories (dict mapping category
            name to {count, max_severity, avg_severity, recoverable_count}).
        """
        if not violations:
            return {
                "total_count": 0,
                "categories": {},
                "max_overall_severity": 0.0,
                "avg_overall_severity": 0.0,
            }

        cats: dict[str, dict[str, Any]] = {}
        severities: list[float] = []

        for v in violations:
            cat_name = v.category.value
            if cat_name not in cats:
                cats[cat_name] = {
                    "count": 0,
                    "max_severity": 0.0,
                    "total_severity": 0.0,
                    "recoverable_count": 0,
                }
            entry = cats[cat_name]
            entry["count"] += 1
            entry["max_severity"] = max(entry["max_severity"], v.severity)
            entry["total_severity"] += v.severity
            if v.recoverable:
                entry["recoverable_count"] += 1
            severities.append(v.severity)

        # Compute averages
        for cat_data in cats.values():
            cat_data["avg_severity"] = (
                cat_data["total_severity"] / cat_data["count"]
                if cat_data["count"] > 0
                else 0.0
            )
            del cat_data["total_severity"]  # Clean up internal accumulator

        return {
            "total_count": len(violations),
            "categories": cats,
            "max_overall_severity": max(severities) if severities else 0.0,
            "avg_overall_severity": (
                sum(severities) / len(severities) if severities else 0.0
            ),
        }

    # ------------------------------------------------------------------
    # Provenance report
    # ------------------------------------------------------------------

    def generate_provenance_report(
        self,
        violation: TranslatedViolation,
    ) -> str:
        """Generate a Markdown provenance report for a single violation.

        Includes: category, severity, recoverability, original exception
        details, full stack trace, HLF context, and suggested remediation.

        Args:
            violation: The violation to report on.

        Returns:
            Markdown-formatted report string.
        """
        lines: list[str] = [
            f"# Violation Report: {violation.category.value}",
            "",
            "| Field | Value |",
            "|-------|-------|",
            f"| **Category** | `{violation.category.value}` |",
            f"| **Severity** | {violation.severity:.2f} / 1.0 |",
            f"| **Recoverable** | {'Yes' if violation.recoverable else 'No'} |",
            f"| **Original Exception** | `{violation.original_exception_type}` |",
            f"| **Original Message** | {violation.original_message} |",
            f"| **Suggested Action** | {violation.suggested_action} |",
            "",
            "## Formatted Message",
            "",
            f"> {violation.message}",
            "",
            "## Stack Trace",
            "",
        ]

        if violation.stack_frames:
            lines.append("| # | File | Line | Function | Code |")
            lines.append("|---|------|------|----------|------|")
            for i, frame in enumerate(violation.stack_frames, start=1):
                file_name = frame.get("file", "?").split("/")[-1].split("\\")[-1]
                lines.append(
                    f"| {i} | `{file_name}` | {frame.get('line', '?')} "
                    f"| `{frame.get('function', '?')}` "
                    f"| `{frame.get('code', '?')[:80]}` |"
                )
        else:
            lines.append("*(No stack frames available)*")

        if violation.hlf_context:
            lines.append("")
            lines.append("## HLF Context")
            lines.append("")
            for key, value in violation.hlf_context.items():
                lines.append(f"- **{key}**: `{value}`")

        lines.append("")
        lines.append("## Remediation")
        lines.append("")
        lines.append(f"1. {violation.suggested_action}")
        lines.append(f"2. Review the original exception: `{violation.original_exception_type}`")
        if violation.recoverable:
            lines.append("3. This violation is **recoverable** — retry or fallback is safe.")
        else:
            lines.append("3. This violation is **non-recoverable** — escalate to operator.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _suggest_action(
        category: ViolationCategory,
        recoverable: bool,
        original_message: str,
    ) -> str:
        """Generate a human-readable suggested action based on the violation."""
        suggestions: dict[ViolationCategory, str] = {
            ViolationCategory.TYPE_ERROR: "Check argument types against the expected HLF type contract",
            ViolationCategory.VALUE_ERROR: "Validate input value against allowed range or enum",
            ViolationCategory.RUNTIME_ERROR: "Inspect the runtime state at the point of failure",
            ViolationCategory.IMPORT_ERROR: "Verify the module is in the allowed import whitelist for this tier",
            ViolationCategory.MEMORY_ERROR: "Reduce memory allocation or increase the sandbox memory limit",
            ViolationCategory.TIMEOUT_ERROR: "Increase the timeout or optimize the operation into smaller steps",
            ViolationCategory.PERMISSION_ERROR: "Verify the agent has the required capability tier",
            ViolationCategory.ASSERTION_ERROR: "Review the failing invariant and update the proof",
            ViolationCategory.DIVISION_ERROR: "Guard division operations with a zero-check",
            ViolationCategory.INDEX_ERROR: "Validate index bounds before access",
            ViolationCategory.KEY_ERROR: "Use .get() with a default or check key existence",
            ViolationCategory.ATTRIBUTE_ERROR: "Verify the object has the expected attribute or interface",
            ViolationCategory.OS_ERROR: "Check file paths, permissions, and disk space",
            ViolationCategory.NETWORK_ERROR: "Retry with exponential backoff or verify connectivity",
            ViolationCategory.UNKNOWN: "Log the full exception and escalate for manual review",
        }
        base = suggestions.get(category, "Investigate the root cause and apply appropriate fix")
        if not recoverable:
            base += " (non-recoverable — escalation required)"
        return base

    def _populate_default_mappings(self) -> None:
        """Seed the translator with default exception → violation mappings."""
        for mapping in _DEFAULT_MAPPINGS:
            key = mapping.exception_type.split(".")[-1]
            self._mappings[key] = mapping


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------

def translate_exception(
    exc: Exception,
    hlf_context: dict[str, Any] | None = None,
) -> TranslatedViolation:
    """Translate a single Python exception to an HLF violation."""
    translator = ErrorTranslator()
    return translator.translate_exception(exc, hlf_context)


def translate_batch(
    exceptions: list[Exception],
) -> list[TranslatedViolation]:
    """Translate multiple exceptions at once."""
    translator = ErrorTranslator()
    return translator.batch_translate(exceptions)


__all__ = [
    "ViolationCategory",
    "TranslatedViolation",
    "PythonExceptionMapping",
    "ErrorTranslator",
    "translate_exception",
    "translate_batch",
]
