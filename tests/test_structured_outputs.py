"""Tests for hlf_mcp.hlf.structured_outputs — Pydantic + Instructor structured output generation."""

from __future__ import annotations

import json
import pytest

from hlf_mcp.hlf.structured_outputs import (
    BatchStructuredOutput,
    SchemaDefinition,
    StructuredOutput,
    StructuredOutputGenerator,
)


# ── Schema Tests ───────────────────────────────────────────────────────


class TestSchemaDefinition:
    def test_schema_creation(self) -> None:
        schema = SchemaDefinition(
            name="test_schema",
            description="A test schema",
            json_schema={"type": "object", "properties": {}},
            required_fields=["name"],
            field_types={"name": str},
        )
        assert schema.name == "test_schema"
        assert schema.required_fields == ["name"]
        assert schema.field_types == {"name": str}

    def test_schema_to_dict(self) -> None:
        schema = SchemaDefinition(
            name="test",
            description="desc",
            json_schema={"type": "object"},
            required_fields=["x"],
            field_types={"x": int},
            examples=[{"x": 1}],
        )
        d = schema.to_dict()
        assert d["name"] == "test"
        assert d["field_types"] == {"x": "int"}
        assert d["examples"] == [{"x": 1}]

    def test_schema_examples_default_empty(self) -> None:
        schema = SchemaDefinition(
            name="s",
            description="d",
            json_schema={},
            required_fields=[],
            field_types={},
        )
        assert schema.examples == []


# ── Output Tests ────────────────────────────────────────────────────────


class TestStructuredOutput:
    def test_valid_output(self) -> None:
        output = StructuredOutput(
            output_id="so-1",
            schema_name="test",
            raw_response='{"name": "hello"}',
            parsed_output={"name": "hello"},
            is_valid=True,
            validation_errors=[],
            model_used="test-model",
            latency_ms=100.0,
        )
        assert output.is_valid
        assert output.parsed_output == {"name": "hello"}
        assert output.validation_errors == []

    def test_invalid_output(self) -> None:
        output = StructuredOutput(
            output_id="so-2",
            schema_name="test",
            raw_response='{"bad": "data"}',
            parsed_output={},
            is_valid=False,
            validation_errors=["Missing field: name"],
            model_used="test-model",
            latency_ms=50.0,
        )
        assert not output.is_valid
        assert "Missing field: name" in output.validation_errors

    def test_to_dict(self) -> None:
        output = StructuredOutput(
            output_id="so-3",
            schema_name="test",
            raw_response="{}",
            parsed_output={},
            is_valid=True,
            validation_errors=[],
            model_used="m",
            latency_ms=10.0,
            token_count=50,
            cost_estimate=0.001,
        )
        d = output.to_dict()
        assert d["output_id"] == "so-3"
        assert d["token_count"] == 50
        assert d["cost_estimate"] == 0.001


class TestBatchStructuredOutput:
    def test_batch_basic(self) -> None:
        outputs = [
            StructuredOutput(
                output_id="b1", schema_name="s", raw_response="{}",
                parsed_output={}, is_valid=True, validation_errors=[],
                model_used="m", latency_ms=10.0,
            ),
            StructuredOutput(
                output_id="b2", schema_name="s", raw_response="{}",
                parsed_output={}, is_valid=False, validation_errors=["err"],
                model_used="m", latency_ms=20.0,
            ),
        ]
        batch = BatchStructuredOutput(
            batch_id="batch-1",
            schema_name="s",
            total=2,
            valid_count=1,
            invalid_count=1,
            outputs=outputs,
            total_latency_ms=30.0,
            avg_latency_ms=15.0,
        )
        assert batch.success_rate == 0.5
        assert batch.valid_count == 1
        assert batch.invalid_count == 1
        assert batch.total == 2

    def test_batch_all_valid(self) -> None:
        outputs = [
            StructuredOutput(
                output_id=f"b{i}", schema_name="s", raw_response="{}",
                parsed_output={}, is_valid=True, validation_errors=[],
                model_used="m", latency_ms=1.0,
            )
            for i in range(3)
        ]
        batch = BatchStructuredOutput(
            batch_id="batch-2", schema_name="s", total=3,
            valid_count=3, invalid_count=0, outputs=outputs,
            total_latency_ms=3.0, avg_latency_ms=1.0,
        )
        assert batch.success_rate == 1.0

    def test_batch_empty(self) -> None:
        batch = BatchStructuredOutput(
            batch_id="batch-0", schema_name="s", total=0,
            valid_count=0, invalid_count=0, outputs=[],
            total_latency_ms=0.0, avg_latency_ms=0.0,
        )
        assert batch.success_rate == 0.0

    def test_batch_to_dict(self) -> None:
        outputs = [
            StructuredOutput(
                output_id="b1", schema_name="s", raw_response="{}",
                parsed_output={}, is_valid=True, validation_errors=[],
                model_used="m", latency_ms=10.0,
            ),
        ]
        batch = BatchStructuredOutput(
            batch_id="batch-1", schema_name="s", total=1,
            valid_count=1, invalid_count=0, outputs=outputs,
            total_latency_ms=10.0, avg_latency_ms=10.0,
        )
        d = batch.to_dict()
        assert d["batch_id"] == "batch-1"
        assert len(d["outputs"]) == 1


# ── Generator Tests ─────────────────────────────────────────────────────


class TestStructuredOutputGenerator:
    def test_register_schema(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        gen._schemas.clear()  # clean start
        schema = gen.register_schema(
            name="test_schema",
            description="test",
            json_schema={"type": "object", "properties": {"name": {"type": "string"}}},
            required_fields=["name"],
            field_types={"name": str},
        )
        assert schema.name == "test_schema"
        assert "test_schema" in gen.list_schemas()

    def test_register_duplicate_raises(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        gen._schemas.clear()
        gen.register_schema(
            name="dup", description="d", json_schema={},
            required_fields=[], field_types={},
        )
        with pytest.raises(ValueError, match="already registered"):
            gen.register_schema(
                name="dup", description="d", json_schema={},
                required_fields=[], field_types={},
            )

    def test_get_schema_exists(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        gen._schemas.clear()
        gen.register_schema(
            name="findable", description="d", json_schema={},
            required_fields=[], field_types={},
        )
        schema = gen.get_schema("findable")
        assert schema is not None
        assert schema.name == "findable"

    def test_get_schema_missing(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        gen._schemas.clear()
        assert gen.get_schema("nonexistent") is None

    def test_list_schemas_includes_standard(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        schemas = gen.list_schemas()
        assert "security_audit" in schemas
        assert "code_review" in schemas
        assert "classification" in schemas

    def test_generate_raises_for_unknown_schema(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        with pytest.raises(ValueError, match="not registered"):
            gen.generate("test prompt", "nonexistent")

    # ── Validation Tests ──────────────────────────────────────────

    def test_validate_missing_required_field(self) -> None:
        schema = SchemaDefinition(
            name="s", description="d",
            json_schema={"type": "object"},
            required_fields=["name", "age"],
            field_types={"name": str, "age": int},
        )
        is_valid, errors = StructuredOutputGenerator.validate_output(
            {"name": "test"}, schema
        )
        assert not is_valid
        assert any("age" in e for e in errors)

    def test_validate_null_required_field(self) -> None:
        schema = SchemaDefinition(
            name="s", description="d",
            json_schema={"type": "object"},
            required_fields=["name"],
            field_types={"name": str},
        )
        is_valid, errors = StructuredOutputGenerator.validate_output(
            {"name": None}, schema
        )
        assert not is_valid
        assert any("None" in e for e in errors)

    def test_validate_wrong_type(self) -> None:
        schema = SchemaDefinition(
            name="s", description="d",
            json_schema={"type": "object"},
            required_fields=["count"],
            field_types={"count": int},
        )
        is_valid, errors = StructuredOutputGenerator.validate_output(
            {"count": "not-an-int"}, schema
        )
        assert not is_valid
        assert any("int" in e for e in errors)

    def test_validate_int_as_float_ok(self) -> None:
        schema = SchemaDefinition(
            name="s", description="d",
            json_schema={"type": "object"},
            required_fields=["score"],
            field_types={"score": float},
        )
        is_valid, errors = StructuredOutputGenerator.validate_output(
            {"score": 85}, schema
        )
        assert is_valid

    def test_validate_all_passes(self) -> None:
        schema = SchemaDefinition(
            name="s", description="d",
            json_schema={"type": "object"},
            required_fields=["name", "count"],
            field_types={"name": str, "count": int},
        )
        is_valid, errors = StructuredOutputGenerator.validate_output(
            {"name": "test", "count": 5}, schema
        )
        assert is_valid
        assert errors == []

    def test_validate_extra_fields_ok(self) -> None:
        """Extra fields beyond required should not cause validation failure."""
        schema = SchemaDefinition(
            name="s", description="d",
            json_schema={"type": "object"},
            required_fields=["name"],
            field_types={"name": str},
        )
        is_valid, errors = StructuredOutputGenerator.validate_output(
            {"name": "test", "extra": "value"}, schema
        )
        assert is_valid

    # ── JSON Extraction Tests ─────────────────────────────────────

    def test_extract_json_direct(self) -> None:
        result = StructuredOutputGenerator._extract_json('{"hello": "world"}')
        assert result == {"hello": "world"}

    def test_extract_json_markdown_block(self) -> None:
        raw = '```json\n{"key": "value"}\n```'
        result = StructuredOutputGenerator._extract_json(raw)
        assert result == {"key": "value"}

    def test_extract_json_plain_markdown_block(self) -> None:
        raw = '```\n{"x": 1}\n```'
        result = StructuredOutputGenerator._extract_json(raw)
        assert result == {"x": 1}

    def test_extract_json_nested_in_text(self) -> None:
        raw = 'Here is the result: {"a": 1, "b": 2}. Hope that helps.'
        result = StructuredOutputGenerator._extract_json(raw)
        assert result == {"a": 1, "b": 2}

    def test_extract_json_nested_braces(self) -> None:
        raw = '{"outer": {"inner": [1, 2, 3]}}'
        result = StructuredOutputGenerator._extract_json(raw)
        assert result == {"outer": {"inner": [1, 2, 3]}}

    def test_extract_json_array(self) -> None:
        raw = '[{"x": 1}, {"x": 2}]'
        result = StructuredOutputGenerator._extract_json(raw)
        assert result == [{"x": 1}, {"x": 2}]

    def test_extract_json_invalid(self) -> None:
        with pytest.raises(ValueError, match="Could not extract JSON"):
            StructuredOutputGenerator._extract_json("just some plain text")


# ── Standard Schema Tests ───────────────────────────────────────────────


class TestStandardSchemas:
    def test_security_audit_schema(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        schema = gen.get_schema("security_audit")
        assert schema is not None
        assert "findings" in schema.required_fields
        assert "risk_score" in schema.required_fields
        assert len(schema.examples) > 0

    def test_code_review_schema(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        schema = gen.get_schema("code_review")
        assert schema is not None
        assert "overall_grade" in schema.required_fields

    def test_classification_schema(self) -> None:
        gen = StructuredOutputGenerator(model_gateway=None)
        schema = gen.get_schema("classification")
        assert schema is not None
        assert "primary_label" in schema.required_fields
        assert schema.field_types["confidence"] == float


# ── Convenience Function Tests ──────────────────────────────────────────


class TestConvenienceFunctions:
    def test_get_generator_returns_instance(self) -> None:
        from hlf_mcp.hlf.structured_outputs import get_generator
        gen = get_generator()
        assert isinstance(gen, StructuredOutputGenerator)

    def test_get_generator_is_singleton(self) -> None:
        from hlf_mcp.hlf.structured_outputs import get_generator
        g1 = get_generator()
        g2 = get_generator()
        assert g1 is g2
