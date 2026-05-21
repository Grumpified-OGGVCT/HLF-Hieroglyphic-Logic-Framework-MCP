"""
Tests for Rust SDK Generation (ecosystem/schema_translator.py).

Validates:
  - HLF type → Rust type mapping (_hlf_type_to_rust_type)
  - Rust InputContract generation (_generate_rust_input)
  - Rust OutputContract generation (_generate_rust_output)
  - Serde derives (#[derive(Debug, Clone, Serialize, Deserialize)])
  - Vec<T>, HashSet<T>, HashMap<String, T> fields
  - Edge cases: empty params, unknown types, lifetime correctness
"""

from __future__ import annotations

import os
import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())

from hlf_mcp.ecosystem.schema_translator import SchemaTranslator
from hlf_mcp.hlf.typed_contracts import (
    HlfType,
    InputContract,
    OutputContract,
    TypeContract,
    ParametricType,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def translator() -> SchemaTranslator:
    """A non-strict translator for Rust SDK generation tests."""
    return SchemaTranslator(name="test-rust", strict_mode=False)


@pytest.fixture
def rust_input_contract() -> InputContract:
    """InputContract: analyze(text: String, threshold: Number)."""
    return InputContract(
        function_name="analyze",
        parameters=[
            TypeContract(
                name="text",
                hlf_type=HlfType.STRING,
                json_schema_type="string",
                required=True,
                constraints={"description": "Text to analyze"},
            ),
            TypeContract(
                name="threshold",
                hlf_type=HlfType.NUMBER,
                json_schema_type="number",
                required=False,
                constraints={"description": "Confidence threshold", "default": 0.5},
            ),
        ],
    )


@pytest.fixture
def empty_input_contract() -> InputContract:
    """InputContract with no parameters."""
    return InputContract(function_name="ping", parameters=[])


@pytest.fixture
def rust_output_contract() -> OutputContract:
    """OutputContract returning String."""
    return OutputContract(function_name="analyze", return_type=HlfType.STRING)


# ═══════════════════════════════════════════════════════════════════════════════
# Type mapping tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRustTypeMapping:
    """Tests for _hlf_type_to_rust_type static method."""

    def test_string_to_string(self) -> None:
        """string → String"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.STRING) == "String"

    def test_integer_to_i64(self) -> None:
        """integer → i64"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.INTEGER) == "i64"

    def test_number_to_f64(self) -> None:
        """number → f64"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.NUMBER) == "f64"

    def test_real_to_f64(self) -> None:
        """real → f64"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.REAL) == "f64"

    def test_rational_to_f64(self) -> None:
        """rational → f64"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.RATIONAL) == "f64"

    def test_boolean_to_bool(self) -> None:
        """boolean → bool"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.BOOLEAN) == "bool"

    def test_json_to_serde_value(self) -> None:
        """json → serde_json::Value"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.JSON) == "serde_json::Value"

    def test_any_to_serde_value(self) -> None:
        """any → serde_json::Value"""
        assert SchemaTranslator._hlf_type_to_rust_type(HlfType.ANY) == "serde_json::Value"

    def test_list_parametric_to_vec(self) -> None:
        """List<String> → Vec<String>"""
        pt = ParametricType(base=HlfType.LIST, params=(HlfType.STRING,))
        assert SchemaTranslator._hlf_type_to_rust_type(pt) == "Vec<String>"

    def test_set_parametric_to_hash_set(self) -> None:
        """Set<Integer> → HashSet<i64>"""
        pt = ParametricType(base=HlfType.SET, params=(HlfType.INTEGER,))
        assert "HashSet" in SchemaTranslator._hlf_type_to_rust_type(pt)
        assert "i64" in SchemaTranslator._hlf_type_to_rust_type(pt)

    def test_map_parametric_to_hash_map(self) -> None:
        """Map<String, Boolean> → HashMap<String, bool>"""
        pt = ParametricType(base=HlfType.MAP, params=(HlfType.STRING, HlfType.BOOLEAN))
        result = SchemaTranslator._hlf_type_to_rust_type(pt)
        assert "HashMap<String, bool>" in result

    def test_unknown_hfl_type_defaults_to_serde_value(self) -> None:
        """Unknown type falls back to serde_json::Value."""
        assert SchemaTranslator._hlf_type_to_rust_type("invalid_type") == "serde_json::Value"

    def test_list_without_params_defaults_to_vec_value(self) -> None:
        """List() → Vec<serde_json::Value>"""
        pt = ParametricType(base=HlfType.LIST, params=())
        assert SchemaTranslator._hlf_type_to_rust_type(pt) == "Vec<serde_json::Value>"


# ═══════════════════════════════════════════════════════════════════════════════
# Rust SDK generation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRustInputGeneration:
    """Tests for Rust InputContract code generation."""

    def test_generates_rust_struct_with_serde_derives(
        self, translator: SchemaTranslator, rust_input_contract: InputContract
    ) -> None:
        """Rust input struct includes serde derives."""
        code = translator.generate_client_sdk(rust_input_contract, language="rust")
        assert "#[derive(Debug, Clone, Serialize, Deserialize)]" in code
        assert "pub struct" in code
        assert "AnalyzeInput" in code

    def test_includes_serde_import(self, translator: SchemaTranslator, rust_input_contract: InputContract) -> None:
        """Rust code includes serde use statement."""
        code = translator.generate_client_sdk(rust_input_contract, language="rust")
        assert "use serde::{Deserialize, Serialize}" in code

    def test_field_types_in_struct(self, translator: SchemaTranslator, rust_input_contract: InputContract) -> None:
        """Struct fields use correct Rust types."""
        code = translator.generate_client_sdk(rust_input_contract, language="rust")
        assert "text: String" in code
        assert "threshold: f64" in code

    def test_serde_rename_attributes(self, translator: SchemaTranslator, rust_input_contract: InputContract) -> None:
        """Fields have #[serde(rename = "...")] attributes."""
        code = translator.generate_client_sdk(rust_input_contract, language="rust")
        assert '#[serde(rename = "text")]' in code
        assert '#[serde(rename = "threshold")]' in code

    def test_empty_parameters_generates_valid_struct(
        self, translator: SchemaTranslator, empty_input_contract: InputContract
    ) -> None:
        """Empty params generate a struct with a comment."""
        code = translator.generate_client_sdk(empty_input_contract, language="rust")
        assert "pub struct" in code
        assert "Serialize, Deserialize" in code

    def test_vec_field_generates_vec_type(self, translator: SchemaTranslator) -> None:
        """A list field produces Vec<T>."""
        contract = InputContract(
            function_name="batch_process",
            parameters=[
                TypeContract(
                    name="items",
                    hlf_type=HlfType.LIST,
                    json_schema_type="array",
                    required=True,
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="rust")
        assert "Vec<" in code

    def test_hash_set_field_imports_std_collections(self, translator: SchemaTranslator) -> None:
        """Set type includes std::collections::HashSet import."""
        contract = InputContract(
            function_name="deduplicate",
            parameters=[
                TypeContract(
                    name="values",
                    hlf_type=HlfType.SET,
                    json_schema_type="array",
                    required=True,
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="rust")
        assert "use std::collections::HashSet" in code

    def test_hash_map_field_imports_std_collections(self, translator: SchemaTranslator) -> None:
        """Map type includes std::collections::HashMap import."""
        contract = InputContract(
            function_name="configure",
            parameters=[
                TypeContract(
                    name="options",
                    hlf_type=HlfType.MAP,
                    json_schema_type="object",
                    required=True,
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="rust")
        assert "use std::collections::HashMap" in code

    def test_description_becomes_doc_comment(self, translator: SchemaTranslator) -> None:
        """Parameter description becomes a /// doc comment."""
        contract = InputContract(
            function_name="describe",
            parameters=[
                TypeContract(
                    name="input",
                    hlf_type=HlfType.STRING,
                    json_schema_type="string",
                    required=True,
                    constraints={"description": "The input text to process"},
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="rust")
        assert "/// The input text to process" in code


class TestRustOutputGeneration:
    """Tests for Rust OutputContract code generation."""

    def test_generates_output_struct(self, translator: SchemaTranslator, rust_output_contract: OutputContract) -> None:
        """Output contract generates a Rust struct with 'result' field."""
        code = translator.generate_client_sdk(rust_output_contract, language="rust")
        assert "pub struct" in code
        assert "AnalyzeOutput" in code
        assert "pub result:" in code
        assert "#[derive(Debug, Clone, Serialize, Deserialize)]" in code

    def test_output_type_mapping(self, translator: SchemaTranslator) -> None:
        """Output type maps correctly to Rust."""
        contract = OutputContract(function_name="count", return_type=HlfType.INTEGER)
        code = translator.generate_client_sdk(contract, language="rust")
        assert "result: i64" in code


class TestRustSDKIntegration:
    """Integration-style tests for Rust SDK generation via generate_client_sdk."""

    def test_generate_input_returns_string(self, translator: SchemaTranslator, rust_input_contract: InputContract) -> None:
        result = translator.generate_client_sdk(rust_input_contract, language="rust")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_output_returns_string(self, translator: SchemaTranslator, rust_output_contract: OutputContract) -> None:
        result = translator.generate_client_sdk(rust_output_contract, language="rust")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unsupported_language_raises(self, translator: SchemaTranslator, rust_input_contract: InputContract) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            translator.generate_client_sdk(rust_input_contract, language="csharp")
