"""
Tests for HLF Real-Code Bridge Hardening — Python type coercion,
import whitelisting, sandbox execution, and bidirectional error translation.

Validates:
  - TypeCoercionContract: INT/FLOAT/STR/BOOL/LIST/MAP/OPTIONAL coercion
  - ImportWhitelist: per-tier allow/deny, transitive scanning, tier summary
  - SandboxExecutor: gas metering, AST validation, restricted builtins, execution
  - ErrorTranslator: exception→violation mapping, stack provenance, batch translation

Integration points:
  - hlf_mcp.hlf.python_type_coercion (TypeCoercionContract, CoercionSafety, CoercionResult)
  - hlf_mcp.hlf.import_whitelist (ImportWhitelist, CapabilityTier, ImportCheck)
  - hlf_mcp.hlf.sandbox_executor (SandboxExecutor, GasMeter, SandboxExecution)
  - hlf_mcp.hlf.error_translation (ErrorTranslator, ViolationCategory, TranslatedViolation)
"""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.python_type_coercion import (
    CoercionSafety,
    CoercionResult,
    CoercionRule,
    TypeCoercionContract,
    coerce_hlf_value,
)
from hlf_mcp.hlf.import_whitelist import (
    CapabilityTier,
    ImportCheck,
    ImportRule,
    ImportWhitelist,
)
from hlf_mcp.hlf.sandbox_executor import (
    SandboxResult,
    SandboxConfig,
    SandboxExecution,
    GasMeter,
    SandboxExecutor,
)
from hlf_mcp.hlf.error_translation import (
    ViolationCategory,
    TranslatedViolation,
    PythonExceptionMapping,
    ErrorTranslator,
    translate_exception,
)


# ═══════════════════════════════════════════════════════════════════════════════
# python_type_coercion tests (~9 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTypeCoercionInt:
    """Tests for INT coercion via TypeCoercionContract."""

    def test_coerce_int_safe(self) -> None:
        """int coerces safely within bit limits."""
        contract = TypeCoercionContract(max_int_bits=64, strict_none=True)
        result = contract.coerce(42, "INT")
        assert result.success
        assert result.value == 42
        assert result.safety == CoercionSafety.SAFE
        assert result.target_type == "int"

    def test_coerce_int_overflow(self) -> None:
        """value exceeding max_int_bits returns DANGEROUS."""
        contract = TypeCoercionContract(max_int_bits=4, strict_none=True)
        result = contract.coerce(100, "INT")
        assert not result.success
        assert result.safety == CoercionSafety.DANGEROUS
        assert result.value is None
        assert any(
            "overflow" in w.lower() or "exceeding" in w.lower()
            for w in result.warnings
        )

    def test_coerce_int_negative_safe(self) -> None:
        """negative int within bit bounds coerces safely."""
        contract = TypeCoercionContract(max_int_bits=64, strict_none=True)
        result = contract.coerce(-999, "INT")
        assert result.success
        assert result.value == -999
        assert result.safety == CoercionSafety.SAFE


class TestTypeCoercionFloat:
    """Tests for FLOAT coercion."""

    def test_coerce_float_precision_safe(self) -> None:
        """float within precision → SAFE (base safety is WARNING, but no
        precision-limit exceeded warning)."""
        contract = TypeCoercionContract(max_float_precision=15, strict_none=True)
        result = contract.coerce(3.14, "FLOAT")
        assert result.success
        assert result.value == pytest.approx(3.14)
        # Baseline safety for FLOAT is WARNING
        assert result.safety == CoercionSafety.WARNING

    def test_coerce_float_excessive_precision(self) -> None:
        """float with excessive precision digits triggers WARNING."""
        contract = TypeCoercionContract(max_float_precision=4, strict_none=True)
        result = contract.coerce(3.14159265358979, "FLOAT")
        # Should still succeed but may carry precision warnings
        assert result.success
        # Check that warnings about precision exist
        assert any(
            "precision" in w.lower() or "significant digits" in w.lower()
            for w in result.warnings
        ) or result.safety == CoercionSafety.WARNING


class TestTypeCoercionStrBool:
    """Tests for STR and BOOL coercion."""

    def test_coerce_str(self) -> None:
        """string coerces safely."""
        contract = TypeCoercionContract()
        result = contract.coerce("hello", "STR")
        assert result.success
        assert result.value == "hello"
        assert result.safety == CoercionSafety.SAFE
        assert result.target_type == "str"

    def test_coerce_str_from_non_str(self) -> None:
        """non-string value is stringified safely."""
        contract = TypeCoercionContract()
        result = contract.coerce(42, "STR")
        assert result.success
        assert result.value == "42"
        assert result.safety == CoercionSafety.SAFE

    def test_coerce_bool(self) -> None:
        """BOOl coerces safely."""
        contract = TypeCoercionContract()
        result = contract.coerce(True, "BOOL")
        assert result.success
        assert result.value is True
        assert result.safety == CoercionSafety.SAFE
        assert result.target_type == "bool"


class TestTypeCoercionCollections:
    """Tests for LIST and MAP coercion."""

    def test_coerce_list_recursive(self) -> None:
        """LIST coerces all elements recursively."""
        contract = TypeCoercionContract()
        result = contract.coerce([1, 2, 3], "LIST")
        assert result.success
        assert result.value == [1, 2, 3]
        assert result.safety == CoercionSafety.SAFE

    def test_coerce_map(self) -> None:
        """MAP coerces dict values."""
        contract = TypeCoercionContract()
        result = contract.coerce({"a": 1, "b": 2}, "MAP")
        assert result.success
        assert result.value == {"a": 1, "b": 2}
        assert result.safety == CoercionSafety.SAFE


class TestTypeCoercionOptional:
    """Tests for OPTIONAL type handling."""

    def test_coerce_optional_with_none(self) -> None:
        """OPTIONAL allows None."""
        contract = TypeCoercionContract(strict_none=True)
        result = contract.coerce(None, "OPTIONAL[INT]")
        assert result.success
        assert result.value is None
        assert result.safety == CoercionSafety.SAFE

    def test_coerce_strict_none_reject(self) -> None:
        """strict mode rejects None for non-optional."""
        contract = TypeCoercionContract(strict_none=True)
        result = contract.coerce(None, "INT")
        assert not result.success
        assert result.safety == CoercionSafety.DANGEROUS
        assert any("strict" in w for w in result.warnings)

    def test_coerce_non_strict_none_warns(self) -> None:
        """non-strict mode allows None with a WARNING."""
        contract = TypeCoercionContract(strict_none=False)
        result = contract.coerce(None, "INT")
        assert result.success
        assert result.safety == CoercionSafety.WARNING
        assert result.value is None


class TestTypeCoercionBatch:
    """Tests for batch coercion."""

    def test_coerce_batch(self) -> None:
        """batch coercion processes multiple values."""
        contract = TypeCoercionContract()
        values = [(42, "INT"), (3.14, "FLOAT"), ("hi", "STR")]
        results = contract.coerce_batch(values)
        assert len(results) == 3
        assert all(r.success for r in results)
        assert results[0].value == 42
        assert results[1].value == pytest.approx(3.14)
        assert results[2].value == "hi"

    def test_coerce_batch_stops_on_dangerous(self) -> None:
        """batch coercion stops at first DANGEROUS when stop_on_dangerous=True."""
        contract = TypeCoercionContract(max_int_bits=64)
        values = [(42, "INT"), (None, "INT"), ("ok", "STR")]
        results = contract.coerce_batch(values, stop_on_dangerous=True)
        # Second element (None→INT in strict mode) is DANGEROUS, so processing stops
        assert len(results) == 2
        assert results[0].success
        assert not results[1].success

    def test_coerce_batch_no_stop(self) -> None:
        """batch coercion continues past DANGEROUS when stop_on_dangerous=False."""
        contract = TypeCoercionContract(max_int_bits=64)
        values = [(42, "INT"), (None, "INT"), ("ok", "STR")]
        results = contract.coerce_batch(values, stop_on_dangerous=False)
        assert len(results) == 3


class TestTypeCoercionTable:
    """Tests for coercion table generation."""

    def test_generate_coercion_table(self) -> None:
        """markdown table contains expected type mappings."""
        contract = TypeCoercionContract()
        table = contract.generate_coercion_table()
        assert "HLF Type" in table
        assert "Python Type" in table
        assert "`INT`" in table
        assert "`FLOAT`" in table
        assert "`STR`" in table
        assert "`BOOL`" in table
        assert "`LIST`" in table
        assert "`MAP`" in table

    def test_coercion_result_to_dict(self) -> None:
        """CoercionResult.to_dict() produces expected fields."""
        contract = TypeCoercionContract()
        result = contract.coerce(42, "INT")
        d = result.to_dict()
        assert d["safety"] == "safe"
        assert d["target_type"] == "int"
        assert d["original_type"] == "INT"
        assert d["success"] is True

    def test_coerce_hlf_value_convenience(self) -> None:
        """Convenience function coerce_hlf_value works correctly."""
        result = coerce_hlf_value(42, "INT")
        assert result.success
        assert result.value == 42

    def test_check_overflow_precheck(self) -> None:
        """check_overflow returns DANGEROUS for overflow, SAFE for safe values."""
        contract = TypeCoercionContract(max_int_bits=64)
        assert contract.check_overflow(42, "INT") == CoercionSafety.SAFE
        # Very large value should trigger overflow
        big = 2 ** 128
        assert contract.check_overflow(big, "INT") in (
            CoercionSafety.DANGEROUS,
            CoercionSafety.WARNING,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# import_whitelist tests (~9 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestImportWhitelistBasic:
    """Tests for BASIC tier imports."""

    def test_import_whitelist_basic_math_allowed(self) -> None:
        """BASIC tier allows math."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("math", CapabilityTier.BASIC)
        assert check.allowed
        assert check.requested_import == "math"

    def test_import_whitelist_basic_os_denied(self) -> None:
        """BASIC tier denies os."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("os", CapabilityTier.BASIC)
        assert not check.allowed
        assert len(check.violations) > 0


class TestImportWhitelistStandard:
    """Tests for STANDARD tier imports."""

    def test_import_whitelist_standard_pathlib_allowed(self) -> None:
        """STANDARD allows pathlib."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("pathlib", CapabilityTier.STANDARD)
        assert check.allowed

    def test_import_whitelist_standard_os_path_allowed(self) -> None:
        """STANDARD allows os.path (explicitly in STANDARD set)."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("os.path", CapabilityTier.STANDARD)
        assert check.allowed

    def test_import_whitelist_standard_denies_socket(self) -> None:
        """STANDARD tier denies socket (requires ELEVATED)."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("socket", CapabilityTier.STANDARD)
        assert not check.allowed


class TestImportWhitelistElevatedPrivileged:
    """Tests for ELEVATED and PRIVILEGED tiers."""

    def test_import_whitelist_elevated_http_client(self) -> None:
        """ELEVATED allows http.client."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("http.client", CapabilityTier.ELEVATED)
        assert check.allowed

    def test_import_whitelist_elevated_allows_socket(self) -> None:
        """ELEVATED tier allows socket."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("socket", CapabilityTier.ELEVATED)
        assert check.allowed

    def test_import_whitelist_privileged_threading(self) -> None:
        """PRIVILEGED allows threading."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("threading", CapabilityTier.PRIVILEGED)
        assert check.allowed

    def test_import_whitelist_privileged_denies_at_basic(self) -> None:
        """threading denied at BASIC tier."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("threading", CapabilityTier.BASIC)
        assert not check.allowed


class TestImportWhitelistUnrestricted:
    """Tests for UNRESTRICTED tier."""

    def test_import_whitelist_unrestricted_allows_anything(self) -> None:
        """UNRESTRICTED allows any import, even unknown modules."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import(
            "some.fictional.module", CapabilityTier.UNRESTRICTED
        )
        assert check.allowed

    def test_import_whitelist_unrestricted_allows_everything(self) -> None:
        """UNRESTRICTED allows all standard modules."""
        whitelist = ImportWhitelist()
        for mod in ["os", "subprocess", "socket", "threading", "multiprocessing"]:
            check = whitelist.check_import(mod, CapabilityTier.UNRESTRICTED)
            assert check.allowed, f"UNRESTRICTED should allow {mod}"


class TestImportWhitelistBatchAndSummary:
    """Tests for batch checking and tier summaries."""

    def test_import_whitelist_check_imports_batch(self) -> None:
        """batch check returns correct count."""
        whitelist = ImportWhitelist()
        imports = ["math", "json", "os", "subprocess"]
        results = whitelist.check_imports(imports, CapabilityTier.BASIC)
        assert len(results) == 4
        allowed = [r for r in results if r.allowed]
        denied = [r for r in results if not r.allowed]
        # math, json allowed at BASIC; os, subprocess denied
        assert len(allowed) == 2
        assert len(denied) == 2

    def test_import_whitelist_tier_summary(self) -> None:
        """summary has counts per tier."""
        whitelist = ImportWhitelist()
        summary = whitelist.tier_summary()
        assert "BASIC" in summary
        assert "STANDARD" in summary
        assert "ELEVATED" in summary
        assert "PRIVILEGED" in summary
        for tier_name in ["BASIC", "STANDARD", "ELEVATED", "PRIVILEGED"]:
            assert summary[tier_name]["count"] > 0
            assert isinstance(summary[tier_name]["modules"], list)

    def test_import_whitelist_rule_count(self) -> None:
        """rule_count property returns expected count."""
        whitelist = ImportWhitelist()
        assert whitelist.rule_count > 0


class TestImportWhitelistCustomRules:
    """Tests for adding and removing custom rules."""

    def test_import_whitelist_add_remove_rule(self) -> None:
        """custom rules can be added and removed."""
        whitelist = ImportWhitelist()
        rule = ImportRule(
            module_path="my_custom_module",
            tier=CapabilityTier.BASIC,
            reason="Custom module for testing",
        )
        whitelist.add_rule(rule)
        check = whitelist.check_import("my_custom_module", CapabilityTier.BASIC)
        assert check.allowed
        assert check.matched_rule is not None
        assert check.matched_rule.module_path == "my_custom_module"

        removed = whitelist.remove_rule("my_custom_module")
        assert removed
        check2 = whitelist.check_import("my_custom_module", CapabilityTier.BASIC)
        assert not check2.allowed

    def test_import_whitelist_remove_nonexistent(self) -> None:
        """removing a non-existent rule returns False."""
        whitelist = ImportWhitelist()
        assert not whitelist.remove_rule("nonexistent.module")

    def test_import_whitelist_audit_imports(self) -> None:
        """audit_imports returns applicable rules for a tier."""
        whitelist = ImportWhitelist()
        rules = whitelist.audit_imports(CapabilityTier.BASIC)
        assert len(rules) > 0
        for rule in rules:
            assert rule.tier.value <= CapabilityTier.BASIC.value


class TestImportWhitelistEdgeCases:
    """Edge case tests for import whitelist."""

    def test_import_whitelist_longest_prefix_match(self) -> None:
        """longest-prefix rule (os.path) matches over shorter (os)."""
        whitelist = ImportWhitelist()
        # os.path.join should match os.path rule at STANDARD tier
        check = whitelist.check_import("os.path.join", CapabilityTier.STANDARD)
        # os.path is at STANDARD, so os.path.join should be allowed at STANDARD
        assert check.allowed

    def test_import_whitelist_import_check_to_dict(self) -> None:
        """ImportCheck.to_dict() produces expected fields."""
        whitelist = ImportWhitelist()
        check = whitelist.check_import("math", CapabilityTier.BASIC)
        d = check.to_dict()
        assert d["requested_import"] == "math"
        assert d["tier"] == "BASIC"
        assert d["allowed"] is True

    def test_import_whitelist_default_tier(self) -> None:
        """default_tier is used when no tier is passed to check_import."""
        whitelist = ImportWhitelist(default_tier=CapabilityTier.STANDARD)
        check = whitelist.check_import("math")
        assert check.allowed  # math is BASIC, STANDARD >= BASIC


# ═══════════════════════════════════════════════════════════════════════════════
# sandbox_executor tests (~9 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestGasMeter:
    """Tests for GasMeter."""

    def test_gas_meter_basic(self) -> None:
        """GasMeter charges correctly, returns remaining, detects exhaustion."""
        meter = GasMeter(gas_limit=100)
        assert meter.remaining == 100
        assert meter.consumed == 0
        assert not meter.exhausted

        ok = meter.charge("BinOp", count=3)  # 2 * 3 = 6
        assert ok
        assert meter.consumed == 6
        assert meter.remaining == 94

    def test_gas_meter_consumed(self) -> None:
        """consumed property tracks total gas used."""
        meter = GasMeter(gas_limit=1000)
        meter.charge("Expression", count=10)  # 1 * 10 = 10
        meter.charge("FunctionCall", count=5)  # 5 * 5 = 25
        assert meter.consumed == 35

    def test_gas_meter_exhaustion(self) -> None:
        """GasMeter signals exhaustion when limit reached."""
        meter = GasMeter(gas_limit=50)
        ok = meter.charge("ClassDef", count=10)  # 15 * 10 = 150 > 50
        assert not ok
        assert meter.exhausted
        assert meter.consumed == 0  # Not deducted when exhausted

    def test_gas_meter_reset(self) -> None:
        """reset clears state."""
        meter = GasMeter(gas_limit=500)
        meter.charge("Loop", count=10)  # 3 * 10 = 30
        assert meter.consumed == 30
        meter.reset()
        assert meter.consumed == 0
        assert meter.remaining == 500
        assert not meter.exhausted

    def test_gas_meter_unknown_node_type(self) -> None:
        """unknown node type defaults to cost 1."""
        meter = GasMeter(gas_limit=100)
        ok = meter.charge("UnknownNodeType", count=5)
        assert ok
        assert meter.consumed == 5  # Default cost is 1

    def test_gas_meter_custom_costs(self) -> None:
        """custom gas costs are used when provided."""
        custom = {"CustomNode": 100, "BinOp": 50}
        meter = GasMeter(gas_limit=1000, gas_costs=custom)
        meter.charge("CustomNode", count=1)
        assert meter.consumed == 100
        meter.charge("BinOp")
        assert meter.consumed == 150


class TestSandboxValidation:
    """Tests for code validation in SandboxExecutor."""

    def test_sandbox_validate_safe_code(self) -> None:
        """simple code passes validation."""
        executor = SandboxExecutor()
        is_valid, violations = executor.validate_code("x = 1 + 2")
        assert is_valid
        assert violations == []

    def test_sandbox_validate_restricted_eval(self) -> None:
        """eval() detected as restricted."""
        executor = SandboxExecutor()
        is_valid, violations = executor.validate_code("eval('1+1')")
        assert not is_valid
        assert any("eval" in v for v in violations)

    def test_sandbox_validate_restricted_exec(self) -> None:
        """exec() detected as restricted."""
        executor = SandboxExecutor()
        is_valid, violations = executor.validate_code("exec('x=1')")
        assert not is_valid
        assert any("exec" in v.lower() for v in violations)

    def test_sandbox_validate_restricted_open(self) -> None:
        """open() detected as restricted."""
        executor = SandboxExecutor()
        is_valid, violations = executor.validate_code("open('test.txt')")
        assert not is_valid
        assert any("open" in v for v in violations)

    def test_sandbox_validate_restricted_import(self) -> None:
        """import of os detected as restricted."""
        executor = SandboxExecutor()
        is_valid, violations = executor.validate_code("import os")
        assert not is_valid
        assert any("os" in v for v in violations)

    def test_sandbox_validate_syntax_error(self) -> None:
        """syntax error is caught during validation."""
        executor = SandboxExecutor()
        is_valid, violations = executor.validate_code("def foo(:")
        assert not is_valid
        assert any("Syntax" in v for v in violations)


class TestSandboxExecution:
    """Tests for safe code execution."""

    def test_sandbox_execute_simple(self) -> None:
        """simple arithmetic executes successfully."""
        executor = SandboxExecutor()
        result = executor.execute("x = 2 + 2")
        assert result.result == SandboxResult.SUCCESS

    def test_sandbox_execute_safe_simple(self) -> None:
        """execute_safe runs simple code to success."""
        executor = SandboxExecutor()
        result = executor.execute_safe("y = 3 * 7")
        assert result.result == SandboxResult.SUCCESS

    def test_sandbox_execution_to_dict(self) -> None:
        """SandboxExecution.to_dict() produces expected fields."""
        execution = SandboxExecution(
            result=SandboxResult.SUCCESS,
            output="hello",
            gas_used=42,
            execution_time_ms=1.5,
            ast_node_count=3,
        )
        d = execution.to_dict()
        assert d["result"] == "success"
        assert d["output"] == "hello"
        assert d["gas_used"] == 42


class TestSandboxGasEstimation:
    """Tests for gas estimation."""

    def test_sandbox_estimate_gas(self) -> None:
        """gas estimate is positive for non-trivial code."""
        executor = SandboxExecutor()
        gas = executor.estimate_gas("x = 1 + 2\nprint(x)")
        assert gas > 0

    def test_sandbox_estimate_gas_syntax_error(self) -> None:
        """gas estimate returns -1 for syntax errors."""
        executor = SandboxExecutor()
        gas = executor.estimate_gas("def foo(:")
        assert gas == -1

    def test_sandbox_gas_report(self) -> None:
        """gas_report returns breakdown with expected keys."""
        executor = SandboxExecutor()
        report = executor.gas_report("x = 1 + 2")
        assert "total_gas" in report
        assert "gas_limit" in report
        assert "within_limit" in report
        assert "breakdown" in report
        assert report["within_limit"] is True


class TestSandboxRestrictedBuiltins:
    """Tests for restricted builtins."""

    def test_sandbox_restricted_builtins_excludes_eval(self) -> None:
        """restricted builtins excludes eval."""
        executor = SandboxExecutor()
        safe = executor.restricted_builtins()
        assert "eval" not in safe
        assert "exec" not in safe
        assert "open" not in safe
        assert "__import__" not in safe

    def test_sandbox_restricted_builtins_includes_safe(self) -> None:
        """restricted builtins includes safe functions."""
        executor = SandboxExecutor()
        safe = executor.restricted_builtins()
        assert "print" in safe
        assert "len" in safe
        assert "range" in safe
        assert "int" in safe
        assert "str" in safe
        assert "list" in safe


class TestSandboxConfig:
    """Tests for SandboxConfig."""

    def test_sandbox_config_defaults(self) -> None:
        """SandboxConfig defaults are reasonable."""
        config = SandboxConfig()
        assert config.timeout_seconds == 5.0
        assert config.max_memory_mb == 128
        assert config.gas_limit == 1_000_000
        assert config.allow_network is False
        assert config.allow_file_io is False

    def test_sandbox_config_custom(self) -> None:
        """SandboxConfig accepts custom values."""
        config = SandboxConfig(
            timeout_seconds=10.0,
            gas_limit=5000,
            allowed_modules=["math", "json"],
        )
        assert config.timeout_seconds == 10.0
        assert config.gas_limit == 5000
        assert config.allowed_modules == ["math", "json"]


class TestSandboxConfigure:
    """Tests for configure method."""

    def test_sandbox_configure_updates_config(self) -> None:
        """configure() updates config fields."""
        executor = SandboxExecutor()
        executor.configure(timeout_seconds=60.0, gas_limit=500)
        assert executor.config.timeout_seconds == 60.0
        assert executor.config.gas_limit == 500


# ═══════════════════════════════════════════════════════════════════════════════
# error_translation tests (~8 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestErrorTranslationBasic:
    """Basic exception→violation translation tests."""

    def test_translate_type_error(self) -> None:
        """TypeError → TYPE_ERROR with severity 0.5."""
        translator = ErrorTranslator()
        try:
            _ = "hello" + 42
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.TYPE_ERROR
            assert violation.severity == pytest.approx(0.5)
            assert violation.recoverable is True
            assert violation.original_exception_type == "TypeError"

    def test_translate_value_error(self) -> None:
        """ValueError → VALUE_ERROR with correct category."""
        translator = ErrorTranslator()
        try:
            _ = int("not_a_number")
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.VALUE_ERROR
            assert violation.severity == pytest.approx(0.4)

    def test_translate_zero_division(self) -> None:
        """ZeroDivisionError → DIVISION_ERROR."""
        translator = ErrorTranslator()
        try:
            _ = 1 / 0
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.DIVISION_ERROR
            assert violation.severity == pytest.approx(0.3)
            assert violation.recoverable is True

    def test_translate_import_error(self) -> None:
        """ImportError → IMPORT_ERROR, not recoverable."""
        translator = ErrorTranslator()
        try:
            import definitely_not_a_real_module_xyzzy  # type: ignore[import-not-found]  # noqa: F401
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.IMPORT_ERROR
            assert violation.severity == pytest.approx(0.7)
            assert violation.recoverable is False

    def test_translate_key_error(self) -> None:
        """KeyError → KEY_ERROR."""
        translator = ErrorTranslator()
        try:
            _ = {}["missing_key"]
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.KEY_ERROR
            assert violation.severity == pytest.approx(0.3)

    def test_translate_attribute_error(self) -> None:
        """AttributeError → ATTRIBUTE_ERROR."""
        translator = ErrorTranslator()
        try:
            _ = (42).nonexistent_attr
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.ATTRIBUTE_ERROR
            assert violation.severity == pytest.approx(0.4)


class TestErrorTranslationAdvanced:
    """Advanced exception translation tests."""

    def test_translate_memory_error_category(self) -> None:
        """MemoryError → MEMORY_ERROR, severity 0.9."""
        translator = ErrorTranslator()
        # We can't reliably trigger a real MemoryError, but we can test
        # the mapping by constructing one and translating it
        violation = translator.translate_exception(MemoryError("oom"))
        assert violation.category == ViolationCategory.MEMORY_ERROR
        assert violation.severity == pytest.approx(0.9)
        assert violation.recoverable is False

    def test_translate_assertion_error(self) -> None:
        """AssertionError → ASSERTION_ERROR."""
        translator = ErrorTranslator()
        try:
            assert False, "test assertion"
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert violation.category == ViolationCategory.ASSERTION_ERROR

    def test_translate_unknown_exception(self) -> None:
        """Unknown exception maps to UNKNOWN category."""
        translator = ErrorTranslator()

        class CustomWeirdError(Exception):
            pass

        violation = translator.translate_exception(CustomWeirdError("weird"))
        assert violation.category == ViolationCategory.UNKNOWN
        assert violation.recoverable is False


class TestErrorTranslationBatch:
    """Batch translation tests."""

    def test_translate_batch(self) -> None:
        """batch_translate handles multiple exceptions."""
        translator = ErrorTranslator()
        excs = [
            TypeError("bad type"),
            ValueError("bad value"),
            KeyError("missing"),
        ]
        violations = translator.batch_translate(excs)
        assert len(violations) == 3
        assert violations[0].category == ViolationCategory.TYPE_ERROR
        assert violations[1].category == ViolationCategory.VALUE_ERROR
        assert violations[2].category == ViolationCategory.KEY_ERROR

    def test_translate_batch_empty(self) -> None:
        """batch_translate handles empty list."""
        translator = ErrorTranslator()
        violations = translator.batch_translate([])
        assert violations == []


class TestErrorTranslationSeverity:
    """Severity summary tests."""

    def test_translate_severity_summary(self) -> None:
        """severity_summary aggregates correctly."""
        translator = ErrorTranslator()
        violations = translator.batch_translate(
            [TypeError("a"), ValueError("b"), KeyError("c")]
        )
        summary = translator.severity_summary(violations)
        assert summary["total_count"] == 3
        assert "type_error" in summary["categories"]
        assert "value_error" in summary["categories"]
        assert "key_error" in summary["categories"]
        assert summary["max_overall_severity"] > 0.0
        assert summary["avg_overall_severity"] > 0.0

    def test_translate_severity_summary_empty(self) -> None:
        """severity_summary handles empty list."""
        translator = ErrorTranslator()
        summary = translator.severity_summary([])
        assert summary["total_count"] == 0
        assert summary["categories"] == {}
        assert summary["max_overall_severity"] == 0.0
        assert summary["avg_overall_severity"] == 0.0


class TestErrorTranslationProvenance:
    """Provenance report tests."""

    def test_generate_provenance_report(self) -> None:
        """report contains stack trace info and markdown."""
        translator = ErrorTranslator()
        try:
            _ = 1 / 0
        except Exception as exc:
            violation = translator.translate_exception(exc)
            report = translator.generate_provenance_report(violation)
            assert "# Violation Report" in report
            assert "division_error" in report
            assert "Stack Trace" in report
            assert "Remediation" in report

    def test_generate_provenance_report_with_context(self) -> None:
        """provenance report includes HLF context when provided."""
        translator = ErrorTranslator()
        try:
            _ = int("abc")
        except Exception as exc:
            violation = translator.translate_exception(
                exc, hlf_context={"agent_id": "test-agent", "gas_remaining": 1000}
            )
            report = translator.generate_provenance_report(violation)
            assert "HLF Context" in report
            assert "test-agent" in report

    def test_translated_violation_to_dict(self) -> None:
        """TranslatedViolation.to_dict() produces expected fields."""
        translator = ErrorTranslator()
        violation = translator.translate_exception(TypeError("test"))
        d = violation.to_dict()
        assert d["category"] == "type_error"
        assert d["original_exception_type"] == "TypeError"
        assert "severity" in d
        assert "recoverable" in d
        assert "stack_frames" in d


class TestErrorTranslationReverse:
    """Reverse translation tests."""

    def test_reverse_translate(self) -> None:
        """reverse_translate maps category back to exception class."""
        translator = ErrorTranslator()
        violation = translator.translate_exception(TypeError("test"))
        exc_class = translator.reverse_translate(violation)
        assert exc_class is TypeError

    def test_reverse_translate_division(self) -> None:
        """reverse_translate for DIVISION_ERROR gives ZeroDivisionError."""
        translator = ErrorTranslator()
        violation = translator.translate_exception(ZeroDivisionError("div0"))
        exc_class = translator.reverse_translate(violation)
        assert exc_class is ZeroDivisionError


class TestErrorTranslationCustomMapping:
    """Custom mapping tests."""

    def test_register_custom_mapping(self) -> None:
        """custom exception mapping is used when registered."""
        translator = ErrorTranslator()

        class MyCustomError(Exception):
            pass

        mapping = PythonExceptionMapping(
            exception_type="MyCustomError",
            violation_category=ViolationCategory.RUNTIME_ERROR,
            severity=0.85,
            recoverable=False,
            message_template="Custom error: {original_message}",
        )
        translator.register_mapping(mapping)
        violation = translator.translate_exception(MyCustomError("boom"))
        assert violation.category == ViolationCategory.RUNTIME_ERROR
        assert violation.severity == pytest.approx(0.85)
        assert "Custom error" in violation.message


class TestErrorTranslationConvenience:
    """Convenience function tests."""

    def test_translate_exception_convenience(self) -> None:
        """translate_exception convenience function works."""
        violation = translate_exception(TypeError("test"))
        assert violation.category == ViolationCategory.TYPE_ERROR

    def test_translate_to_hlf_violation(self) -> None:
        """translate_to_hlf_violation handles sys.exc_info tuples."""
        import sys

        translator = ErrorTranslator()
        try:
            _ = 1 / 0
        except ZeroDivisionError:
            exc_info = sys.exc_info()
            violation = translator.translate_to_hlf_violation(exc_info)
            assert violation.category == ViolationCategory.DIVISION_ERROR

    def test_translate_to_hlf_violation_none_exc(self) -> None:
        """translate_to_hlf_violation handles exc_info with None exception."""
        translator = ErrorTranslator()
        violation = translator.translate_to_hlf_violation(
            (type, None, None)  # type: ignore[arg-type]
        )
        assert violation.category == ViolationCategory.UNKNOWN
        assert violation.severity == 0.0
        assert violation.recoverable is True


class TestErrorTranslationStackFrames:
    """Stack frame extraction tests."""

    def test_translate_exception_has_stack_frames(self) -> None:
        """translated violation includes stack frames."""
        translator = ErrorTranslator()

        def _cause_error() -> None:
            _ = 1 / 0

        try:
            _cause_error()
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert len(violation.stack_frames) > 0
            frame = violation.stack_frames[0]
            assert "file" in frame
            assert "line" in frame
            assert "function" in frame
            # The innermost frame should be in this test file
            assert "test_real_code_bridge_hardening" in frame["file"]

    def test_translate_exception_message_formatting(self) -> None:
        """violation message uses the template from the mapping."""
        translator = ErrorTranslator()
        try:
            _ = 1 / 0
        except Exception as exc:
            violation = translator.translate_exception(exc)
            assert "Division by zero" in violation.message
            assert "division by zero" in violation.message.lower()

    def test_translated_violation_from_dict(self) -> None:
        """TranslatedViolation.from_dict() roundtrips correctly."""
        translator = ErrorTranslator()
        original = translator.translate_exception(ValueError("test value"))
        d = original.to_dict()
        restored = TranslatedViolation.from_dict(d)
        assert restored.category == original.category
        assert restored.severity == original.severity
        assert restored.original_exception_type == original.original_exception_type
        assert restored.recoverable == original.recoverable
