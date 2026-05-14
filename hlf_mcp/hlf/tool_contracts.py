"""Typed contract definitions for key HLF MCP server tools.

These contracts provide the bridge (B2) typed-contract surface for
MCP tool functions without interfering with the FastMCP ``@mcp.tool()``
decorator chain.  The :class:`ContractRegistry` can consume these
definitions and feed them into the formal verifier's
``verify_ast(contracts=...)`` path.

Each contract maps to a tool name that agents call through the MCP
protocol.  The schemas mirror the JSON Schema shapes that ``FastMCP``
derives from the function annotations.
"""

from __future__ import annotations

from hlf_mcp.hlf.typed_contracts import (
    ContractRegistry,
    EffectClass,
    FailureMode,
    ProofRequirement,
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
)


# ---------------------------------------------------------------------------
# Individual contract definitions
# ---------------------------------------------------------------------------

VERIFY_FORMAL_AST_CONTRACT = TypedEffectDeclaration(
    function_name="hlf_verify_formal_ast",
    input_contract=InputContract.from_json_schema(
        "hlf_verify_formal_ast",
        {
            "type": "object",
            "properties": {
                "ast": {
                    "type": "object",
                    "description": "Pre-built HLF AST dict (mutually exclusive with source).",
                },
                "source": {
                    "type": "string",
                    "description": "Raw HLF source text (mutually exclusive with ast).",
                },
                "gas_budget": {
                    "type": "integer",
                    "description": "Maximum gas budget for the verification pass.",
                },
                "agent_id": {"type": "string"},
                "trust_state": {
                    "type": "string",
                    "enum": ["healthy", "degraded", "restricted", "provisional"],
                },
                "requested_tier": {"type": "string", "enum": ["hearth"]},
                "mode": {
                    "type": "string",
                    "enum": ["enforce", "advisory", "report"],
                },
            },
        },
    ),
    output_contract=OutputContract.from_json_schema(
        "hlf_verify_formal_ast",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "report": {"type": "object"},
                "admission": {"type": "object"},
            },
            "required": ["status"],
        },
    ),
    effect_class=EffectClass.LOCAL_ANALYSIS,
    failure_modes=[FailureMode.EXECUTION_ERROR],
    proof_requirement=ProofRequirement.VERIFICATION_ADMITTED,
    safety_class="read_only",
    review_posture="audit_log",
    execution_mode="direct",
    side_effects=["audit_log_write", "memory_query", "witness_observation"],
)


VERIFY_GAS_BUDGET_CONTRACT = TypedEffectDeclaration(
    function_name="hlf_verify_gas_budget",
    input_contract=InputContract.from_json_schema(
        "hlf_verify_gas_budget",
        {
            "type": "object",
            "properties": {
                "task_costs": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "List of per-task gas costs to sum.",
                },
                "budget": {
                    "type": "integer",
                    "description": "Total gas budget ceiling.",
                },
                "agent_id": {"type": "string"},
                "trust_state": {"type": "string"},
                "requested_tier": {"type": "string"},
                "mode": {"type": "string"},
                "property_name": {"type": "string"},
            },
            "required": ["task_costs", "budget"],
        },
    ),
    output_contract=OutputContract.from_json_schema(
        "hlf_verify_gas_budget",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "within_budget": {"type": "boolean"},
                "total_cost": {"type": "integer"},
                "budget": {"type": "integer"},
            },
            "required": ["status"],
        },
    ),
    effect_class=EffectClass.LOCAL_ANALYSIS,
    failure_modes=[FailureMode.EXECUTION_ERROR],
    proof_requirement=ProofRequirement.RECOMMENDED,
    safety_class="read_only",
    review_posture="audit_log",
    execution_mode="direct",
    side_effects=["audit_log_write"],
)


COMPILE_CONTRACT = TypedEffectDeclaration(
    function_name="hlf_compile",
    input_contract=InputContract.from_json_schema(
        "hlf_compile",
        {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Raw HLF source text to compile.",
                },
            },
            "required": ["source"],
        },
    ),
    output_contract=OutputContract.from_json_schema(
        "hlf_compile",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "ast": {"type": "object"},
                "bytecode_hex": {"type": "string"},
                "compressed_size": {"type": "integer"},
                "source_size": {"type": "integer"},
            },
            "required": ["status"],
        },
    ),
    effect_class=EffectClass.LOCAL_ANALYSIS,
    failure_modes=[FailureMode.COMPILE_ERROR],
    proof_requirement=ProofRequirement.NONE,
    safety_class="read_only",
    review_posture="none",
    execution_mode="direct",
    side_effects=[],
)


CODE_EXECUTE_CONTRACT = TypedEffectDeclaration(
    function_name="hlf_code_execute",
    input_contract=InputContract.from_json_schema(
        "hlf_code_execute",
        {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Raw HLF MODULE/FUNCTION/[CODE] source.",
                },
                "entrypoint": {"type": "string"},
                "gas_limit": {"type": "integer"},
                "tier": {"type": "string"},
                "variables": {"type": "object"},
                "dry_run": {"type": "boolean"},
            },
            "required": ["source"],
        },
    ),
    output_contract=OutputContract.from_json_schema(
        "hlf_code_execute",
        {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "result": {},
                "gas_used": {"type": "integer"},
                "output": {"type": "string"},
            },
            "required": ["status"],
        },
    ),
    effect_class=EffectClass.SIDE_EFFECTING,
    failure_modes=[FailureMode.EXECUTION_ERROR, FailureMode.GAS_EXHAUSTION],
    proof_requirement=ProofRequirement.RECOMMENDED,
    safety_class="sandboxed",
    review_posture="audit_log",
    execution_mode="sandbox",
    side_effects=["vm_execution", "gas_consumption", "audit_log_write"],
)

# ---------------------------------------------------------------------------
# Registry populated from definitions
# ---------------------------------------------------------------------------

def build_tool_contracts_registry() -> ContractRegistry:
    """Return a :class:`ContractRegistry` seeded with the B2 typed contracts."""
    registry = ContractRegistry()
    for decl in (
        VERIFY_FORMAL_AST_CONTRACT,
        VERIFY_GAS_BUDGET_CONTRACT,
        COMPILE_CONTRACT,
        CODE_EXECUTE_CONTRACT,
    ):
        registry.register(decl)
    return registry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    "VERIFY_FORMAL_AST_CONTRACT",
    "VERIFY_GAS_BUDGET_CONTRACT",
    "COMPILE_CONTRACT",
    "CODE_EXECUTE_CONTRACT",
    "build_tool_contracts_registry",
]
