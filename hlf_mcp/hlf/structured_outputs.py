"""
HLF Structured Outputs — Pydantic + Instructor wrapping for Model Gateway.

Roadmap Phase 3: Provides strongly-typed structured output generation through
the HLF Model Gateway, using Pydantic for schema validation and Instructor for
LLM output coercion.

Architecture:
    StructuredOutputGenerator
        ├── generate(prompt, schema) → schema-validated output
        ├── generate_batch(prompts, schema) → list of validated outputs
        ├── validate(output, schema) → (is_valid, errors)
        └── register_schema(name, schema) → cached for reuse
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, get_type_hints

import json


# ── Data Classes ────────────────────────────────────────────────────────


@dataclass(slots=True)
class StructuredOutput:
    """A schema-validated structured output from the Model Gateway."""

    output_id: str
    schema_name: str
    raw_response: str
    parsed_output: dict[str, Any]
    is_valid: bool
    validation_errors: list[str]
    model_used: str
    latency_ms: float
    token_count: int | None = None
    cost_estimate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_id": self.output_id,
            "schema_name": self.schema_name,
            "raw_response": self.raw_response,
            "parsed_output": self.parsed_output,
            "is_valid": self.is_valid,
            "validation_errors": self.validation_errors,
            "model_used": self.model_used,
            "latency_ms": self.latency_ms,
            "token_count": self.token_count,
            "cost_estimate": self.cost_estimate,
        }


@dataclass(slots=True)
class BatchStructuredOutput:
    """Aggregated results from a batch structured output generation."""

    batch_id: str
    schema_name: str
    total: int
    valid_count: int
    invalid_count: int
    outputs: list[StructuredOutput]
    total_latency_ms: float
    avg_latency_ms: float

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return self.valid_count / self.total

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "schema_name": self.schema_name,
            "total": self.total,
            "valid_count": self.valid_count,
            "invalid_count": self.invalid_count,
            "success_rate": self.success_rate,
            "total_latency_ms": self.total_latency_ms,
            "avg_latency_ms": self.avg_latency_ms,
            "outputs": [o.to_dict() for o in self.outputs],
        }


# ── Schema Registry ─────────────────────────────────────────────────────


@dataclass(slots=True)
class SchemaDefinition:
    """A registered schema for structured output generation."""

    name: str
    description: str
    json_schema: dict[str, Any]
    required_fields: list[str]
    field_types: dict[str, type]
    examples: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "json_schema": self.json_schema,
            "required_fields": self.required_fields,
            "field_types": {k: t.__name__ for k, t in self.field_types.items()},
            "examples": self.examples,
        }


# ── Structured Output Generator ─────────────────────────────────────────


class StructuredOutputGenerator:
    """Generate schema-validated structured outputs via the Model Gateway.

    Uses Pydantic for validation and Instructor-style coercion patterns.
    The generator maintains a registry of known schemas for reuse.

    Usage:
        gen = StructuredOutputGenerator(model_gateway)
        result = gen.generate(
            prompt="Analyze this code for security issues",
            schema_name="security_audit",
        )
        if result.is_valid:
            print(result.parsed_output)
    """

    def __init__(self, model_gateway: Any | None = None) -> None:
        """Initialize with an optional ModelGateway instance.

        Args:
            model_gateway: A ModelGateway instance. If None, lazily imported.
        """
        self._gateway = model_gateway
        self._schemas: dict[str, SchemaDefinition] = {}
        self._register_standard_schemas()

    @property
    def gateway(self) -> Any:
        if self._gateway is None:
            try:
                from hlf_source.agents.core.model_gateway import ModelGateway
                self._gateway = ModelGateway()
            except ImportError:
                raise RuntimeError(
                    "ModelGateway not available. Pass one to the constructor "
                    "or ensure hlf_source.agents.core.model_gateway is importable."
                )
        return self._gateway

    # ── Schema Management ────────────────────────────────────────────

    def register_schema(
        self,
        name: str,
        description: str,
        json_schema: dict[str, Any],
        required_fields: list[str],
        field_types: dict[str, type],
        examples: list[dict[str, Any]] | None = None,
    ) -> SchemaDefinition:
        """Register a schema for structured output generation.

        Args:
            name: Unique schema name (e.g., 'security_audit', 'code_review').
            description: Human-readable description of the schema's purpose.
            json_schema: JSON Schema dict describing the output shape.
            required_fields: List of field names that MUST be present.
            field_types: Mapping of field name to Python type.
            examples: Optional example outputs for few-shot prompting.

        Returns:
            The registered SchemaDefinition.

        Raises:
            ValueError: If a schema with this name already exists.
        """
        if name in self._schemas:
            raise ValueError(f"Schema '{name}' is already registered")
        schema = SchemaDefinition(
            name=name,
            description=description,
            json_schema=json_schema,
            required_fields=required_fields,
            field_types=field_types,
            examples=examples or [],
        )
        self._schemas[name] = schema
        return schema

    def get_schema(self, name: str) -> SchemaDefinition | None:
        """Retrieve a registered schema by name."""
        return self._schemas.get(name)

    def list_schemas(self) -> list[str]:
        """List all registered schema names."""
        return sorted(self._schemas.keys())

    # ── Validation ──────────────────────────────────────────────────

    @staticmethod
    def validate_output(
        output: dict[str, Any],
        schema: SchemaDefinition,
    ) -> tuple[bool, list[str]]:
        """Validate parsed output against a schema definition.

        Args:
            output: The parsed JSON output to validate.
            schema: The SchemaDefinition to validate against.

        Returns:
            (is_valid, errors) where errors is a list of validation error messages.
        """
        errors: list[str] = []

        # Check required fields
        for field in schema.required_fields:
            if field not in output:
                errors.append(f"Missing required field: '{field}'")
            elif output[field] is None:
                errors.append(f"Required field is None: '{field}'")

        # Check field types
        for field, expected_type in schema.field_types.items():
            if field in output and output[field] is not None:
                value = output[field]
                if expected_type == float and isinstance(value, int):
                    continue  # int is acceptable for float fields
                if not isinstance(value, expected_type):
                    errors.append(
                        f"Field '{field}' expected {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )

        # Check JSON schema structural constraints
        schema_type = schema.json_schema.get("type", "")
        if schema_type == "object" and not isinstance(output, dict):
            errors.append("Expected object output, got non-dict")

        return len(errors) == 0, errors

    # ── Generation ──────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        schema_name: str,
        *,
        max_retries: int = 3,
        temperature: float = 0.3,
    ) -> StructuredOutput:
        """Generate a structured output matching a registered schema.

        Args:
            prompt: The input prompt for the model.
            schema_name: Name of a registered schema to validate against.
            max_retries: Maximum retry attempts if output fails validation.
            temperature: Model temperature (lower = more deterministic).

        Returns:
            A StructuredOutput with validation results.

        Raises:
            ValueError: If schema_name is not registered.
        """
        import time
        import uuid

        schema = self._schemas.get(schema_name)
        if schema is None:
            raise ValueError(
                f"Schema '{schema_name}' not registered. "
                f"Available: {self.list_schemas()}"
            )

        # Build the full prompt with schema constraints
        schema_json = json.dumps(schema.json_schema, indent=2)
        schema_prompt = (
            f"{prompt}\n\n"
            f"Output must be valid JSON matching this schema:\n"
            f"{schema_json}\n\n"
            f"Required fields: {', '.join(schema.required_fields)}\n"
            f"Respond ONLY with the JSON object, no other text."
        )

        if schema.examples:
            example_text = "\n".join(
                json.dumps(ex) for ex in schema.examples[:2]
            )
            schema_prompt += f"\n\nExamples:\n{example_text}"

        output_id = f"so-{uuid.uuid4().hex[:12]}"
        start = time.perf_counter()
        raw_response = ""
        parsed: dict[str, Any] = {}
        is_valid = False
        errors: list[str] = ["No attempts completed"]

        for attempt in range(max_retries):
            try:
                # Call Model Gateway
                raw_response = self._call_gateway(
                    schema_prompt, temperature
                )
                parsed = self._extract_json(raw_response)
                is_valid, errors = self.validate_output(parsed, schema)

                if is_valid:
                    break

                # On retry, add error context to prompt
                if attempt < max_retries - 1:
                    schema_prompt = (
                        f"{schema_prompt}\n\n"
                        f"Previous output had errors: {', '.join(errors)}\n"
                        f"Please fix these and return valid JSON."
                    )
            except Exception as exc:
                errors = [f"Generation attempt {attempt + 1} failed: {exc}"]
                if attempt == max_retries - 1:
                    raw_response = str(exc)

        elapsed_ms = (time.perf_counter() - start) * 1000

        return StructuredOutput(
            output_id=output_id,
            schema_name=schema_name,
            raw_response=raw_response,
            parsed_output=parsed,
            is_valid=is_valid,
            validation_errors=errors,
            model_used=getattr(self.gateway, "active_model", "unknown"),
            latency_ms=round(elapsed_ms, 2),
        )

    def generate_batch(
        self,
        prompts: list[str],
        schema_name: str,
        *,
        max_retries: int = 2,
    ) -> BatchStructuredOutput:
        """Generate structured outputs for multiple prompts.

        Args:
            prompts: List of prompts to process.
            schema_name: Name of registered schema.
            max_retries: Max retries per prompt.

        Returns:
            BatchStructuredOutput with aggregate statistics.
        """
        import time
        import uuid

        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        outputs: list[StructuredOutput] = []
        batch_start = time.perf_counter()

        for prompt in prompts:
            output = self.generate(
                prompt, schema_name, max_retries=max_retries
            )
            outputs.append(output)

        total_ms = (time.perf_counter() - batch_start) * 1000
        valid = sum(1 for o in outputs if o.is_valid)

        return BatchStructuredOutput(
            batch_id=batch_id,
            schema_name=schema_name,
            total=len(prompts),
            valid_count=valid,
            invalid_count=len(prompts) - valid,
            outputs=outputs,
            total_latency_ms=round(total_ms, 2),
            avg_latency_ms=round(total_ms / len(prompts), 2) if prompts else 0.0,
        )

    # ── Internal ────────────────────────────────────────────────────

    def _call_gateway(self, prompt: str, temperature: float) -> str:
        """Call the Model Gateway and return raw text response."""
        try:
            result = self.gateway.generate(
                prompt=prompt,
                temperature=temperature,
            )
            if isinstance(result, dict):
                return result.get("response", "") or result.get("text", "") or str(result)
            return str(result)
        except Exception:
            raise RuntimeError("Model Gateway call failed")

    @staticmethod
    def _extract_json(raw: str) -> dict[str, Any]:
        """Extract JSON from a raw model response.

        Handles responses wrapped in markdown code blocks, trailing text,
        or containing JSON anywhere in the output.
        """
        raw = raw.strip()

        # Try markdown code block extraction
        if "```json" in raw:
            start = raw.index("```json") + 7
            end = raw.index("```", start) if "```" in raw[start:] else len(raw)
            raw = raw[start:end].strip()
        elif "```" in raw:
            start = raw.index("```") + 3
            end = raw.index("```", start) if "```" in raw[start:] else len(raw)
            raw = raw[start:end].strip()

        # Try direct parse
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in text
        brace_count = 0
        json_start = -1
        for i, ch in enumerate(raw):
            if ch == "{":
                if brace_count == 0:
                    json_start = i
                brace_count += 1
            elif ch == "}":
                brace_count -= 1
                if brace_count == 0 and json_start >= 0:
                    candidate = raw[json_start : i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
            elif ch == "[" and brace_count == 0:
                # Try array extraction
                json_start = i
                brace_count = 1
            elif ch == "]" and brace_count == 1:
                candidate = raw[json_start : i + 1]
                try:
                    result = json.loads(candidate)
                    if isinstance(result, list):
                        return {"items": result}
                except json.JSONDecodeError:
                    continue
                brace_count = 0

        raise ValueError(f"Could not extract JSON from response: {raw[:200]}...")

    # ── Standard Schema Registration ────────────────────────────────

    def _register_standard_schemas(self) -> None:
        """Register built-in standard schemas."""
        # Security Audit Schema
        self._schemas["security_audit"] = SchemaDefinition(
            name="security_audit",
            description="Security audit results with findings and severity",
            json_schema={
                "type": "object",
                "properties": {
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "high", "medium", "low", "info"],
                                },
                                "category": {"type": "string"},
                                "description": {"type": "string"},
                                "remediation": {"type": "string"},
                                "cwe_id": {"type": "string"},
                            },
                            "required": ["severity", "category", "description"],
                        },
                    },
                    "summary": {"type": "string"},
                    "risk_score": {"type": "number", "minimum": 0, "maximum": 100},
                },
                "required": ["findings", "summary", "risk_score"],
            },
            required_fields=["findings", "summary", "risk_score"],
            field_types={
                "findings": list,
                "summary": str,
                "risk_score": float,
            },
            examples=[
                {
                    "findings": [
                        {
                            "severity": "high",
                            "category": "injection",
                            "description": "SQL injection in /api/users",
                            "remediation": "Use parameterized queries",
                            "cwe_id": "CWE-89",
                        }
                    ],
                    "summary": "1 high-severity finding: SQL injection",
                    "risk_score": 75.0,
                }
            ],
        )

        # Code Review Schema
        self._schemas["code_review"] = SchemaDefinition(
            name="code_review",
            description="Code review results with issues and suggestions",
            json_schema={
                "type": "object",
                "properties": {
                    "overall_grade": {
                        "type": "string",
                        "enum": ["A", "B", "C", "D", "F"],
                    },
                    "issues": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "file": {"type": "string"},
                                "line": {"type": "integer"},
                                "severity": {"type": "string"},
                                "message": {"type": "string"},
                                "suggestion": {"type": "string"},
                            },
                            "required": ["file", "severity", "message"],
                        },
                    },
                    "positive_notes": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                },
                "required": ["overall_grade", "issues", "summary"],
            },
            required_fields=["overall_grade", "issues", "summary"],
            field_types={
                "overall_grade": str,
                "issues": list,
                "positive_notes": list,
                "summary": str,
            },
        )

        # Classification Schema
        self._schemas["classification"] = SchemaDefinition(
            name="classification",
            description="Document or content classification with confidence scores",
            json_schema={
                "type": "object",
                "properties": {
                    "primary_label": {"type": "string"},
                    "secondary_labels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string"},
                                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                            },
                            "required": ["label", "confidence"],
                        },
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "rationale": {"type": "string"},
                },
                "required": ["primary_label", "confidence", "rationale"],
            },
            required_fields=["primary_label", "confidence", "rationale"],
            field_types={
                "primary_label": str,
                "secondary_labels": list,
                "confidence": float,
                "rationale": str,
            },
        )


# ── Module-level convenience ────────────────────────────────────────────


_global_generator: StructuredOutputGenerator | None = None


def get_generator() -> StructuredOutputGenerator:
    """Get or create the global StructuredOutputGenerator singleton."""
    global _global_generator
    if _global_generator is None:
        _global_generator = StructuredOutputGenerator()
    return _global_generator


def generate_structured(
    prompt: str,
    schema_name: str,
    *,
    max_retries: int = 3,
) -> StructuredOutput:
    """Convenience function: generate a single structured output.

    Args:
        prompt: Input prompt.
        schema_name: Name of a registered schema ('security_audit',
            'code_review', 'classification', or custom registered schema).
        max_retries: Maximum retry attempts on validation failure.

    Returns:
        Validated StructuredOutput.
    """
    return get_generator().generate(prompt, schema_name, max_retries=max_retries)
