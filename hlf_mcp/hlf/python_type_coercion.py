"""
Python Type Coercion Contract: safe HLF→Python type mapping with overflow
protection, precision guarantees, and None handling.

Design Principles:
1. Every HLF type maps to a Python type with explicit safety classification.
2. Numeric coercions are bounded by configurable bit-width and precision limits.
3. None propagation is explicit — optional types declare nullability; strict mode
   rejects None for non-optional types.
4. Coercion is traceable: every transformation records its path through
   intermediate types so audits can reconstruct how a value was mapped.
5. Batch coercion stops on the first DANGEROUS result by default, preventing
   cascading corruption from a single bad value.

This module is the type-safety membrane between HLF's type system and Python's
dynamic typing. It answers the question: "Can this HLF value be faithfully
represented in Python without loss, overflow, or precision degradation?"
"""

from __future__ import annotations

import math
import struct
import sys
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CoercionSafety(Enum):
    """Safety classification for a type coercion."""
    SAFE = "safe"           # Lossless, no warnings
    WARNING = "warning"     # Potential precision loss or truncation
    DANGEROUS = "dangerous" # Overflow, data corruption, or unsafe cast


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class CoercionRule:
    """Defines how an HLF type maps to a Python type.

    Attributes:
        hlf_type: The HLF source type (e.g. 'INT', 'FLOAT', 'OPTIONAL[STR]').
        python_type: The target Python type (e.g. int, float, str).
        safety: Baseline safety classification for this coercion.
        overflow_check: Optional callable(value) -> bool that returns True if
            the value would overflow. None means no overflow check.
        precision_loss: Maximum allowed precision loss as a fraction (0.0-1.0).
            0.0 means lossless; 0.1 means up to 10% precision can be lost.
        description: Human-readable explanation of the coercion.
    """
    hlf_type: str
    python_type: type
    safety: CoercionSafety
    overflow_check: Callable[[Any], bool] | None = None
    precision_loss: float = 0.0
    description: str = ""


@dataclass(slots=True)
class CoercionResult:
    """Result of coercing a single value from an HLF type to Python.

    Attributes:
        value: The coerced Python value, or None if coercion failed.
        original_type: The HLF type that was requested.
        target_type: The Python type that was actually produced.
        safety: The worst safety classification encountered during coercion.
        warnings: Human-readable warnings accumulated during coercion.
        coercion_path: Ordered list of intermediate type names showing how
            the value was transformed step by step.
        success: True if coercion completed without DANGEROUS failures.
    """
    value: Any
    original_type: str
    target_type: str
    safety: CoercionSafety
    warnings: list[str] = field(default_factory=list)
    coercion_path: list[str] = field(default_factory=list)
    success: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": repr(self.value) if self.value is not None else None,
            "original_type": self.original_type,
            "target_type": self.target_type,
            "safety": self.safety.value,
            "warnings": list(self.warnings),
            "coercion_path": list(self.coercion_path),
            "success": self.success,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bit_width(value: int) -> int:
    """Return the number of bits required to represent an integer magnitude.

    Returns 0 for value==0, otherwise ceil(log2(abs(value) + 1)).
    """
    if value == 0:
        return 0
    return abs(value).bit_length()


def _precision_digits(value: float) -> int:
    """Return the number of significant decimal digits in a float.

    Strips trailing zeros from the mantissa and counts remaining digits.
    For values like 3.14159 this returns 6; for 1.0e10 this returns 1.
    """
    if not math.isfinite(value):
        return 0
    # Represent as string to count significant digits
    s = f"{value:.15g}"
    # Remove sign, decimal point, leading zeros
    s = s.lstrip("-")
    if "e" in s or "E" in s:
        mantissa, _exp = s.split("e") if "e" in s else s.split("E")
        s = mantissa
    s = s.replace(".", "")
    s = s.lstrip("0")
    return len(s)


def _is_within_int_range(value: int, max_bits: int) -> bool:
    """Check if an integer fits within the given bit width (signed)."""
    if max_bits <= 0:
        return False
    max_val = (1 << (max_bits - 1)) - 1
    min_val = -(1 << (max_bits - 1))
    return min_val <= value <= max_val


def _parse_hlf_optional(hlf_type: str) -> tuple[bool, str]:
    """Parse 'OPTIONAL[T]' into (is_optional, inner_type).

    Returns (False, hlf_type) if not an optional wrapper.
    """
    stripped = hlf_type.strip()
    if stripped.upper().startswith("OPTIONAL[") and stripped.endswith("]"):
        inner = stripped[len("OPTIONAL["):-1].strip()
        return True, inner
    return False, stripped


# ---------------------------------------------------------------------------
# TypeCoercionContract
# ---------------------------------------------------------------------------

class TypeCoercionContract:
    """Safe bidirectional bridge between HLF types and Python types.

    The contract enforces:
    - Integer overflow protection (bounded by max_int_bits)
    - Floating-point precision guarantees (bounded by max_float_precision)
    - Explicit None handling (strict_none mode rejects None for non-optional types)
    - Recursive coercion of container types (LIST, MAP)
    - Traceable coercion paths for auditability

    Usage::

        contract = TypeCoercionContract(max_int_bits=64, strict_none=True)
        result = contract.coerce(42, "INT")
        assert result.success and result.value == 42
    """

    def __init__(
        self,
        name: str = "type-coercion",
        max_int_bits: int = 64,
        max_float_precision: int = 15,
        strict_none: bool = True,
    ) -> None:
        """Initialize the coercion contract.

        Args:
            name: Identifier for this contract instance.
            max_int_bits: Maximum bit width for integers. Values exceeding
                2^max_int_bits - 1 will be flagged as DANGEROUS.
            max_float_precision: Maximum decimal digits allowed for floats.
                Exceeding this threshold produces a WARNING.
            strict_none: If True, passing None for a non-optional type
                is a DANGEROUS coercion failure.
        """
        self.name = name
        self.max_int_bits = max_int_bits
        self.max_float_precision = max_float_precision
        self.strict_none = strict_none

        # Built-in coercion rules
        self._rules: dict[str, CoercionRule] = {}

        self._init_default_rules()

    # ------------------------------------------------------------------
    # Rule registration
    # ------------------------------------------------------------------

    def register_rule(self, hlf_type: str, rule: CoercionRule) -> None:
        """Register a custom coercion rule for an HLF type.

        Overwrites any existing rule for the same HLF type.
        """
        self._rules[hlf_type.strip().upper()] = rule

    def _init_default_rules(self) -> None:
        """Populate the default HLF-to-Python coercion rules."""
        self._rules["INT"] = CoercionRule(
            hlf_type="INT",
            python_type=int,
            safety=CoercionSafety.SAFE,
            overflow_check=lambda v: not _is_within_int_range(int(v), self.max_int_bits),
            precision_loss=0.0,
            description=f"HLF integer → Python int, bounded at {self.max_int_bits} bits",
        )
        self._rules["FLOAT"] = CoercionRule(
            hlf_type="FLOAT",
            python_type=float,
            safety=CoercionSafety.WARNING,
            precision_loss=1e-15,
            description=f"HLF float → Python float, precision capped at {self.max_float_precision} digits",
        )
        self._rules["STR"] = CoercionRule(
            hlf_type="STR",
            python_type=str,
            safety=CoercionSafety.SAFE,
            description="HLF string → Python str",
        )
        self._rules["BOOL"] = CoercionRule(
            hlf_type="BOOL",
            python_type=bool,
            safety=CoercionSafety.SAFE,
            description="HLF boolean → Python bool",
        )
        self._rules["LIST"] = CoercionRule(
            hlf_type="LIST",
            python_type=list,
            safety=CoercionSafety.SAFE,
            description="HLF list → Python list (elements recursively coerced)",
        )
        self._rules["MAP"] = CoercionRule(
            hlf_type="MAP",
            python_type=dict,
            safety=CoercionSafety.SAFE,
            description="HLF map → Python dict (values recursively coerced)",
        )
        self._rules["BYTES"] = CoercionRule(
            hlf_type="BYTES",
            python_type=bytes,
            safety=CoercionSafety.SAFE,
            overflow_check=lambda v: len(v) > 100 * 1024 * 1024,  # 100MB cap
            description="HLF bytes → Python bytes, size-capped at 100MB",
        )
        self._rules["ANY"] = CoercionRule(
            hlf_type="ANY",
            python_type=object,
            safety=CoercionSafety.WARNING,
            description="HLF any → Python object (unchecked)",
        )

    # ------------------------------------------------------------------
    # Main coercion entry point
    # ------------------------------------------------------------------

    def coerce(self, value: Any, hlf_type: str) -> CoercionResult:
        """Coerce a value from an HLF type to its Python equivalent.

        Core type mapping:
        - INT → int (with bit-width overflow check)
        - FLOAT → float (with precision check)
        - STR → str (size warning >10MB)
        - BOOL → bool
        - LIST → list (recursive element coercion)
        - MAP → dict (recursive value coercion)
        - OPTIONAL[T] → T | None
        - BYTES → bytes (size-capped)
        - ANY → Any (WARNING safety)
        """
        hlf_type = hlf_type.strip().upper()
        warnings: list[str] = []
        path: list[str] = [hlf_type]
        safety = CoercionSafety.SAFE

        # Handle None and OPTIONAL
        is_optional, inner_type = _parse_hlf_optional(hlf_type)
        if value is None:
            if is_optional:
                return CoercionResult(
                    value=None,
                    original_type=hlf_type,
                    target_type="NoneType",
                    safety=CoercionSafety.SAFE,
                    warnings=[],
                    coercion_path=path + ["NoneType"],
                    success=True,
                )
            elif self.strict_none:
                return CoercionResult(
                    value=None,
                    original_type=hlf_type,
                    target_type="NoneType",
                    safety=CoercionSafety.DANGEROUS,
                    warnings=[f"None passed to non-optional type '{hlf_type}' in strict mode"],
                    coercion_path=path + ["NoneType"],
                    success=False,
                )
            else:
                warnings.append(f"None passed to non-optional type '{hlf_type}'")
                return CoercionResult(
                    value=None,
                    original_type=hlf_type,
                    target_type="NoneType",
                    safety=CoercionSafety.WARNING,
                    warnings=warnings,
                    coercion_path=path + ["NoneType"],
                    success=True,
                )

        # If optional, delegate to inner type
        if is_optional:
            inner_result = self.coerce(value, inner_type)
            inner_result.coercion_path = [hlf_type] + inner_result.coercion_path
            inner_result.original_type = hlf_type
            return inner_result

        rule = self._rules.get(hlf_type)
        if rule is None:
            return CoercionResult(
                value=value,
                original_type=hlf_type,
                target_type=type(value).__name__,
                safety=CoercionSafety.DANGEROUS,
                warnings=[f"No coercion rule registered for HLF type '{hlf_type}'"],
                coercion_path=path,
                success=False,
            )

        # Check overflow
        if rule.overflow_check is not None:
            try:
                if rule.overflow_check(value):
                    safety = CoercionSafety.DANGEROUS
                    warnings.append(
                        f"Overflow detected coercing {value!r} to HLF type '{hlf_type}'"
                    )
                    return CoercionResult(
                        value=None,
                        original_type=hlf_type,
                        target_type=rule.python_type.__name__,
                        safety=safety,
                        warnings=warnings,
                        coercion_path=path,
                        success=False,
                    )
            except Exception:
                pass

        # Perform actual coercion
        coerced: Any = None
        try:
            if hlf_type == "INT":
                coerced = int(value)
                bits = _bit_width(coerced)
                if bits > self.max_int_bits:
                    safety = self._worse_safety(safety, CoercionSafety.DANGEROUS)
                    warnings.append(
                        f"INT value requires {bits} bits, exceeding {self.max_int_bits}-bit cap"
                    )
                path.append("int")

            elif hlf_type == "FLOAT":
                coerced = float(value)
                digits = _precision_digits(coerced)
                if digits > self.max_float_precision:
                    safety = self._worse_safety(safety, CoercionSafety.WARNING)
                    warnings.append(
                        f"FLOAT value has {digits} significant digits, "
                        f"exceeding precision cap of {self.max_float_precision}"
                    )
                path.append("float")

            elif hlf_type == "STR":
                coerced = str(value)
                if len(coerced) > 10 * 1024 * 1024:  # 10 MB
                    safety = self._worse_safety(safety, CoercionSafety.WARNING)
                    warnings.append(
                        f"STR length {len(coerced)} exceeds 10MB soft cap"
                    )
                path.append("str")

            elif hlf_type == "BOOL":
                coerced = bool(value)
                path.append("bool")

            elif hlf_type == "LIST":
                if not isinstance(value, (list, tuple)):
                    raise TypeError(f"Expected list, got {type(value).__name__}")
                coerced = []
                for i, elem in enumerate(value):
                    # Recursive coercion on list elements — use ANY if element
                    # type is not known
                    sub = self.coerce(elem, "ANY")
                    if not sub.success:
                        warnings.append(f"LIST[{i}]: {sub.warnings[0] if sub.warnings else 'coercion failed'}")
                    coerced.append(sub.value)
                path.append("list")

            elif hlf_type == "MAP":
                if not isinstance(value, dict):
                    raise TypeError(f"Expected dict, got {type(value).__name__}")
                coerced = {}
                for k, v in value.items():
                    sub = self.coerce(v, "ANY")
                    if not sub.success:
                        warnings.append(f"MAP[{k!r}]: {sub.warnings[0] if sub.warnings else 'coercion failed'}")
                    coerced[k] = sub.value
                path.append("dict")

            elif hlf_type == "BYTES":
                if isinstance(value, str):
                    coerced = value.encode("utf-8")
                elif isinstance(value, bytearray):
                    coerced = bytes(value)
                elif isinstance(value, bytes):
                    coerced = value
                else:
                    coerced = bytes(value)
                if len(coerced) > 100 * 1024 * 1024:  # 100 MB cap
                    safety = self._worse_safety(safety, CoercionSafety.DANGEROUS)
                    warnings.append(f"BYTES size {len(coerced)} exceeds 100MB cap")
                path.append("bytes")

            elif hlf_type == "ANY":
                coerced = value
                safety = self._worse_safety(safety, CoercionSafety.WARNING)
                warnings.append("ANY type coercion — no validation performed")
                path.append(type(value).__name__)

            else:
                safety = self._worse_safety(safety, rule.safety)
                coerced = rule.python_type(value)
                path.append(rule.python_type.__name__)

        except (TypeError, ValueError, OverflowError) as exc:
            return CoercionResult(
                value=None,
                original_type=hlf_type,
                target_type=rule.python_type.__name__,
                safety=CoercionSafety.DANGEROUS,
                warnings=warnings + [f"Coercion failed: {exc}"],
                coercion_path=path,
                success=False,
            )

        # Merge rule's baseline safety
        safety = self._worse_safety(safety, rule.safety)

        return CoercionResult(
            value=coerced,
            original_type=hlf_type,
            target_type=rule.python_type.__name__,
            safety=safety,
            warnings=warnings,
            coercion_path=path,
            success=safety != CoercionSafety.DANGEROUS,
        )

    # ------------------------------------------------------------------
    # Batch coercion
    # ------------------------------------------------------------------

    def coerce_batch(
        self,
        values: list[tuple[Any, str]],
        *,
        stop_on_dangerous: bool = True,
    ) -> list[CoercionResult]:
        """Coerce multiple (value, hlf_type) pairs.

        Args:
            values: List of (value, hlf_type) tuples to coerce.
            stop_on_dangerous: If True, stops processing at the first
                DANGEROUS result and returns results up to that point.

        Returns:
            List of CoercionResult, one per input pair (may be truncated
            if stop_on_dangerous is True).
        """
        results: list[CoercionResult] = []
        for value, hlf_type in values:
            result = self.coerce(value, hlf_type)
            results.append(result)
            if stop_on_dangerous and result.safety == CoercionSafety.DANGEROUS:
                break
        return results

    # ------------------------------------------------------------------
    # Roundtrip validation
    # ------------------------------------------------------------------

    def validate_roundtrip(self, hlf_type: str, python_value: Any) -> bool:
        """Check if a Python value could survive a roundtrip back to HLF.

        Coerces the value using the registered HLF→Python rule, then
        attempts to reconstruct what the HLF representation would be.
        Returns True if no information would be lost.

        Args:
            hlf_type: The HLF source type.
            python_value: The Python value to test.

        Returns:
            True if roundtrip is lossless, False otherwise.
        """
        result = self.coerce(python_value, hlf_type)
        if not result.success:
            return False
        if result.safety == CoercionSafety.DANGEROUS:
            return False
        # Check precision loss for float
        if hlf_type.strip().upper() == "FLOAT":
            try:
                original = float(python_value)
                coerced = float(result.value) if result.value is not None else 0.0
                if original == 0.0:
                    return coerced == 0.0
                rel_error = abs(original - coerced) / abs(original)
                return rel_error <= 1e-12
            except (ValueError, ZeroDivisionError):
                return False
        if hlf_type.strip().upper() == "INT":
            try:
                return int(python_value) == int(result.value) if result.value is not None else False
            except (ValueError, TypeError):
                return False
        return True

    # ------------------------------------------------------------------
    # Coercion table generation
    # ------------------------------------------------------------------

    def generate_coercion_table(self) -> str:
        """Generate a Markdown table of all registered HLF→Python mappings.

        Returns:
            Markdown-formatted string with columns: HLF Type, Python Type,
            Safety, Precision Loss, Description.
        """
        lines: list[str] = [
            "| HLF Type | Python Type | Safety | Precision Loss | Description |",
            "|----------|-------------|--------|----------------|-------------|",
        ]
        for hlf_type, rule in sorted(self._rules.items()):
            loss_str = f"{rule.precision_loss:.1e}" if rule.precision_loss else "0"
            lines.append(
                f"| `{hlf_type}` | `{rule.python_type.__name__}` "
                f"| {rule.safety.value} | {loss_str} | {rule.description} |"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Overflow pre-check
    # ------------------------------------------------------------------

    def check_overflow(self, value: Any, hlf_type: str) -> CoercionSafety:
        """Pre-check if a value would overflow without actually coercing it.

        This is a lightweight check that only evaluates overflow conditions
        — it does not perform the full coercion.

        Args:
            value: The candidate value.
            hlf_type: The target HLF type.

        Returns:
            DANGEROUS if overflow is certain, WARNING if borderline,
            SAFE if no overflow risk.
        """
        hlf_type = hlf_type.strip().upper()
        _, inner_type = _parse_hlf_optional(hlf_type)
        if inner_type:
            hlf_type = inner_type

        rule = self._rules.get(hlf_type)
        if rule is None or rule.overflow_check is None:
            return CoercionSafety.SAFE

        try:
            if rule.overflow_check(value):
                return CoercionSafety.DANGEROUS
        except Exception:
            return CoercionSafety.WARNING

        # Additional checks for INT
        if hlf_type == "INT":
            try:
                bits = _bit_width(int(value))
                if bits >= self.max_int_bits:
                    return CoercionSafety.WARNING
                if bits >= self.max_int_bits - 2:
                    return CoercionSafety.WARNING
            except (ValueError, TypeError):
                return CoercionSafety.DANGEROUS

        return CoercionSafety.SAFE

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _worse_safety(a: CoercionSafety, b: CoercionSafety) -> CoercionSafety:
        """Return the worse of two safety classifications."""
        order = {CoercionSafety.SAFE: 0, CoercionSafety.WARNING: 1, CoercionSafety.DANGEROUS: 2}
        return a if order[a] >= order[b] else b


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def coerce_hlf_value(
    value: Any,
    hlf_type: str,
    *,
    max_int_bits: int = 64,
    strict_none: bool = True,
) -> CoercionResult:
    """Convenience function: coerce a single HLF-typed value to Python."""
    contract = TypeCoercionContract(
        max_int_bits=max_int_bits,
        strict_none=strict_none,
    )
    return contract.coerce(value, hlf_type)


__all__ = [
    "CoercionSafety",
    "CoercionRule",
    "CoercionResult",
    "TypeCoercionContract",
    "coerce_hlf_value",
]
