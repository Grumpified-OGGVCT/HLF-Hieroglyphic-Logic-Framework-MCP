"""
Tests for Java SDK Generation (ecosystem/schema_translator.py).

Validates:
  - HLF type → Java type mapping (_hlf_type_to_java_type)
  - Java InputContract generation (_generate_java_input)
  - Java OutputContract generation (_generate_java_output)
  - Jackson annotations (@JsonProperty, @JsonCreator)
  - Nested objects, list/set fields
  - Edge cases: empty params, unknown types
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
    """A non-strict translator for SDK generation tests."""
    return SchemaTranslator(name="test-java", strict_mode=False)


@pytest.fixture
def simple_input_contract() -> InputContract:
    """InputContract: read_file(path: String, max_lines: Integer)."""
    return InputContract(
        function_name="read_file",
        parameters=[
            TypeContract(
                name="path",
                hlf_type=HlfType.STRING,
                json_schema_type="string",
                required=True,
                constraints={"description": "File path to read"},
            ),
            TypeContract(
                name="max_lines",
                hlf_type=HlfType.INTEGER,
                json_schema_type="integer",
                required=False,
                constraints={"description": "Maximum lines to read", "default": 100},
            ),
        ],
    )


@pytest.fixture
def empty_input_contract() -> InputContract:
    """InputContract with no parameters."""
    return InputContract(function_name="noop", parameters=[])


@pytest.fixture
def output_contract() -> OutputContract:
    """OutputContract for read_file returning String."""
    return OutputContract(function_name="read_file", return_type=HlfType.STRING)


# ═══════════════════════════════════════════════════════════════════════════════
# Type mapping tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJavaTypeMapping:
    """Tests for _hlf_type_to_java_type static method."""

    def test_string_to_string(self) -> None:
        """string → String"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.STRING) == "String"

    def test_integer_to_int(self) -> None:
        """integer → int"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.INTEGER) == "int"

    def test_number_to_double(self) -> None:
        """number → double"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.NUMBER) == "double"

    def test_float_to_double(self) -> None:
        """float → double (real type)"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.REAL) == "double"

    def test_bool_to_boolean(self) -> None:
        """boolean → boolean"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.BOOLEAN) == "boolean"

    def test_json_to_json_node(self) -> None:
        """json → JsonNode"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.JSON) == "JsonNode"

    def test_any_to_object(self) -> None:
        """any → Object"""
        assert SchemaTranslator._hlf_type_to_java_type(HlfType.ANY) == "Object"

    def test_list_parametric(self) -> None:
        """List<String> → List<String>"""
        pt = ParametricType(base=HlfType.LIST, params=(HlfType.STRING,))
        assert SchemaTranslator._hlf_type_to_java_type(pt) == "List<String>"

    def test_set_parametric(self) -> None:
        """Set<Integer> → Set<Integer>"""
        pt = ParametricType(base=HlfType.SET, params=(HlfType.INTEGER,))
        assert SchemaTranslator._hlf_type_to_java_type(pt) == "Set<int>"

    def test_map_parametric(self) -> None:
        """Map<String, Boolean> → Map<String, Boolean>"""
        pt = ParametricType(base=HlfType.MAP, params=(HlfType.STRING, HlfType.BOOLEAN))
        assert SchemaTranslator._hlf_type_to_java_type(pt) == "Map<String, boolean>"

    def test_unknown_hfl_type_defaults_to_object(self) -> None:
        """Unknown HlfType string defaults to Object."""
        assert SchemaTranslator._hlf_type_to_java_type("unknown_type") == "Object"

    def test_empty_list_parametric(self) -> None:
        """List with no params → List<Object>"""
        pt = ParametricType(base=HlfType.LIST, params=())
        assert SchemaTranslator._hlf_type_to_java_type(pt) == "List<Object>"


# ═══════════════════════════════════════════════════════════════════════════════
# Java SDK generation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestJavaInputGeneration:
    """Tests for Java InputContract code generation."""

    def test_generates_java_record_with_jackson_annotations(
        self, translator: SchemaTranslator, simple_input_contract: InputContract
    ) -> None:
        """Java input includes record, @JsonCreator, and @JsonProperty."""
        code = translator.generate_client_sdk(simple_input_contract, language="java")
        assert "public record" in code
        assert "ReadFileInput" in code
        assert "@JsonCreator" in code
        assert "@JsonProperty" in code
        assert "fasterxml.jackson" in code

    def test_includes_imports(self, translator: SchemaTranslator, simple_input_contract: InputContract) -> None:
        """Java code includes Jackson imports."""
        code = translator.generate_client_sdk(simple_input_contract, language="java")
        assert "import com.fasterxml.jackson.annotation.JsonCreator" in code
        assert "import com.fasterxml.jackson.annotation.JsonProperty" in code

    def test_field_types_in_record(self, translator: SchemaTranslator, simple_input_contract: InputContract) -> None:
        """Record parameters use correct Java types."""
        code = translator.generate_client_sdk(simple_input_contract, language="java")
        assert "String path" in code
        assert "int max_lines" in code

    def test_empty_parameters_generates_record_without_fields(
        self, translator: SchemaTranslator, empty_input_contract: InputContract
    ) -> None:
        """Empty params generate a valid but empty record."""
        code = translator.generate_client_sdk(empty_input_contract, language="java")
        assert "public record" in code
        assert "JsonCreator" in code
        # should still be valid Java

    def test_nested_object_type(self, translator: SchemaTranslator) -> None:
        """A contract with a collection field generates proper imports."""
        contract = InputContract(
            function_name="list_items",
            parameters=[
                TypeContract(
                    name="items",
                    hlf_type=HlfType.LIST,
                    json_schema_type="array",
                    required=True,
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="java")
        assert "import java.util.List" in code
        assert "List<Object>" in code

    def test_set_field_generates_set_import(self, translator: SchemaTranslator) -> None:
        """Set type generates Set import."""
        contract = InputContract(
            function_name="unique_tags",
            parameters=[
                TypeContract(
                    name="tags",
                    hlf_type=HlfType.SET,
                    json_schema_type="array",
                    required=True,
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="java")
        assert "import java.util.Set" in code
        assert "Set<Object>" in code

    def test_map_field_generates_map_import(self, translator: SchemaTranslator) -> None:
        """Map type generates Map import."""
        contract = InputContract(
            function_name="config",
            parameters=[
                TypeContract(
                    name="settings",
                    hlf_type=HlfType.MAP,
                    json_schema_type="object",
                    required=True,
                ),
            ],
        )
        code = translator.generate_client_sdk(contract, language="java")
        assert "import java.util.Map" in code
        assert "Map<String, Object>" in code


class TestJavaOutputGeneration:
    """Tests for Java OutputContract code generation."""

    def test_generates_output_record(self, translator: SchemaTranslator, output_contract: OutputContract) -> None:
        """Output contract generates a Java record with 'result' field."""
        code = translator.generate_client_sdk(output_contract, language="java")
        assert "public record" in code
        assert "ReadFileOutput" in code
        assert "result" in code
        assert "@JsonProperty" in code
        assert "@JsonCreator" in code

    def test_output_type_mapping(self, translator: SchemaTranslator) -> None:
        """Output type maps correctly to Java."""
        contract = OutputContract(function_name="count", return_type=HlfType.INTEGER)
        code = translator.generate_client_sdk(contract, language="java")
        assert "int result" in code


class TestJavaSDKIntegration:
    """Integration-style tests for Java SDK generation via generate_client_sdk."""

    def test_generate_input_returns_string(self, translator: SchemaTranslator, simple_input_contract: InputContract) -> None:
        result = translator.generate_client_sdk(simple_input_contract, language="java")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_output_returns_string(self, translator: SchemaTranslator, output_contract: OutputContract) -> None:
        result = translator.generate_client_sdk(output_contract, language="java")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unsupported_language_raises(self, translator: SchemaTranslator, simple_input_contract: InputContract) -> None:
        with pytest.raises(ValueError, match="Unsupported language"):
            translator.generate_client_sdk(simple_input_contract, language="kotlin")
