"""Tests for output schema variants in swarm worker templates."""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.swarm_mechanics import (
    SCHEMA_VARIANTS,
    WORKER_TEMPLATE,
    resolve_schema_variant,
    validate_schema_variant,
)
from hlf_mcp.hlf.swarm_compiler import SwarmCompiler, AgentDecl


class TestSchemaVariants:
    """Output schema variant definitions and validation."""

    def test_all_variants_defined(self) -> None:
        assert "full" in SCHEMA_VARIANTS
        assert "summary" in SCHEMA_VARIANTS
        assert "delta" in SCHEMA_VARIANTS
        assert "proof" in SCHEMA_VARIANTS
        assert len(SCHEMA_VARIANTS) == 4

    def test_full_template_has_all_fields(self) -> None:
        template = WORKER_TEMPLATE["full"]
        assert "fields" in template
        assert "agent_id" in template["fields"]
        assert "role" in template["fields"]
        assert "hlf_source" in template["fields"]
        assert "metrics" in template["fields"]

    def test_summary_template_condensed(self) -> None:
        template = WORKER_TEMPLATE["summary"]
        assert "fields" in template
        assert len(template["fields"]) < len(WORKER_TEMPLATE["full"]["fields"])

    def test_delta_template_focused_on_changes(self) -> None:
        template = WORKER_TEMPLATE["delta"]
        assert "changed_fields" in template["fields"]
        assert "previous_hash" in template["fields"]
        assert "new_hash" in template["fields"]

    def test_proof_template_verification_focused(self) -> None:
        template = WORKER_TEMPLATE["proof"]
        assert "proof" in template["fields"]
        assert "evidence_chain" in template["fields"]
        assert "verification_status" in template["fields"]

    def test_resolve_schema_variant_full(self) -> None:
        result = resolve_schema_variant("full")
        assert result["description"] == "Complete output with all fields"

    def test_resolve_schema_variant_summary(self) -> None:
        result = resolve_schema_variant("summary")
        assert "Key fields only" in result["description"]

    def test_resolve_schema_variant_delta(self) -> None:
        result = resolve_schema_variant("delta")
        assert "Changes only" in result["description"]

    def test_resolve_schema_variant_proof(self) -> None:
        result = resolve_schema_variant("proof")
        assert "Verification-focused" in result["description"]

    def test_resolve_schema_variant_case_insensitive(self) -> None:
        result = resolve_schema_variant("FULL")
        assert result["description"] == "Complete output with all fields"

    def test_resolve_schema_variant_invalid_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown schema variant"):
            resolve_schema_variant("nonexistent")

    def test_validate_schema_variant_true(self) -> None:
        assert validate_schema_variant("full") is True
        assert validate_schema_variant("summary") is True
        assert validate_schema_variant("delta") is True
        assert validate_schema_variant("proof") is True

    def test_validate_schema_variant_false(self) -> None:
        assert validate_schema_variant("unknown") is False
        assert validate_schema_variant("") is False


class TestAgentDeclSchemaVariant:
    """AgentDecl supports schema_variant parameter."""

    def test_agent_decl_defaults_to_full(self) -> None:
        agent = AgentDecl(
            name="TestAgent",
            role="builder",
            input_spec="none",
            output_spec="none",
        )
        assert agent.schema_variant == "full"

    def test_agent_decl_accepts_variant(self) -> None:
        agent = AgentDecl(
            name="TestAgent",
            role="builder",
            input_spec="none",
            output_spec="none",
            schema_variant="proof",
        )
        assert agent.schema_variant == "proof"

    def test_agent_decl_all_variants_accepted(self) -> None:
        for variant in ("full", "summary", "delta", "proof"):
            agent = AgentDecl(
                name=f"Agent_{variant}",
                role="builder",
                input_spec="none",
                output_spec="none",
                schema_variant=variant,
            )
            assert agent.schema_variant == variant


class TestSwarmCompilerSchemaVariant:
    """SwarmCompiler parses schema_variant from .hlf agent blocks."""

    def test_parse_agent_with_schema_variant(self) -> None:
        source = """\
agent TestAgent {
  role: BUILDER
  schema_variant: "proof"
  input: none
  output: none
}
"""
        compiler = SwarmCompiler()
        spec = compiler.parse(source)
        agent = spec.agents["TestAgent"]
        assert agent.schema_variant == "proof"

    def test_parse_agent_without_schema_variant_defaults(self) -> None:
        source = """\
agent TestAgent {
  role: BUILDER
  input: none
  output: none
}
"""
        compiler = SwarmCompiler()
        spec = compiler.parse(source)
        agent = spec.agents["TestAgent"]
        assert agent.schema_variant == "full"

    def test_parse_agent_with_delta_variant(self) -> None:
        source = """\
agent DeltaAgent {
  role: REVIEWER
  schema_variant: "delta"
  input: none
  output: none
}
"""
        compiler = SwarmCompiler()
        spec = compiler.parse(source)
        agent = spec.agents["DeltaAgent"]
        assert agent.schema_variant == "delta"

    def test_parse_agent_with_summary_variant(self) -> None:
        source = """\
agent SummaryAgent {
  role: OVERSEE
  schema_variant: "summary"
  input: none
  output: none
}
"""
        compiler = SwarmCompiler()
        spec = compiler.parse(source)
        agent = spec.agents["SummaryAgent"]
        assert agent.schema_variant == "summary"
