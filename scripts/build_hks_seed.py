#!/usr/bin/env python3
"""
build_hks_seed.py — Build the HKS seed database from HLF typed contract exemplars.

Reads the EffectClass taxonomy from typed_contracts.py and creates a SQLite
database (hks_seed.db) with curated TypedEffectDeclaration exemplars organized
by category.  The seed DB provides day-1, high-quality reference patterns for
HKS consumers (agent spawner recall, evaluation loop, RAGMemory).

Output: hks_seed.db in the repository root.

Usage:
    python scripts/build_hks_seed.py [--output PATH] [--force]

Schema:
    exemplars (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        category        TEXT NOT NULL,       -- EffectClass value
        hlf_source      TEXT NOT NULL,       -- originating module
        compiled_json   TEXT NOT NULL,       -- JSON-serialized TypedEffectDeclaration
        capability_tags TEXT NOT NULL,       -- comma-separated capabilities
        difficulty      TEXT NOT NULL,       -- basic | intermediate | advanced
        description     TEXT NOT NULL,       -- human-readable description
        created_at      TEXT NOT NULL        -- ISO 8601 timestamp
    )
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════════
# Schema
# ═══════════════════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS exemplars (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT NOT NULL,
    hlf_source      TEXT NOT NULL,
    compiled_json   TEXT NOT NULL,
    capability_tags TEXT NOT NULL DEFAULT '',
    difficulty      TEXT NOT NULL DEFAULT 'intermediate',
    description     TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_exemplars_category ON exemplars(category);
CREATE INDEX IF NOT EXISTS idx_exemplars_difficulty ON exemplars(difficulty);
"""


# ═══════════════════════════════════════════════════════════════════════════════
# Curated exemplar definitions
# ═══════════════════════════════════════════════════════════════════════════════

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_exemplar(
    category: str,
    source: str,
    compiled: dict,
    caps: list[str],
    difficulty: str,
    description: str,
) -> tuple:
    return (
        category,
        source,
        json.dumps(compiled, sort_keys=True, ensure_ascii=False),
        ",".join(sorted(caps)),
        difficulty,
        description,
        _now(),
    )


def build_exemplars() -> list[tuple]:
    """Return curated exemplar rows.  Each tuple matches the INSERT column order."""
    now = _now()
    exemplars: list[tuple] = []

    # ── Filesystem effects ──────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="file_read",
        source="typed_contracts.py::EffectClass.FILE_READ",
        compiled={
            "function_name": "read_file",
            "effect_class": "file_read",
            "input_contract": {
                "function_name": "read_file",
                "parameters": [
                    {"name": "path", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"pattern": "^[^*?]+$"}}
                ],
            },
            "output_contract": {
                "function_name": "read_file",
                "return_type": "string",
                "output_schema": {"type": "string"},
            },
            "failure_modes": ["io_error", "policy_denied"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["filesystem:read"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["filesystem"],
        difficulty="basic",
        description="Reads a file from the filesystem. Requires filesystem capability. "
                    "Path is validated against glob patterns. Failure modes: io_error (missing file), "
                    "policy_denied (permission).",
    ))

    exemplars.append(_make_exemplar(
        category="file_write",
        source="typed_contracts.py::EffectClass.FILE_WRITE",
        compiled={
            "function_name": "write_file",
            "effect_class": "file_write",
            "input_contract": {
                "function_name": "write_file",
                "parameters": [
                    {"name": "path", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "content", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "write_file",
                "return_type": "boolean",
                "output_schema": {"type": "boolean"},
            },
            "failure_modes": ["io_error", "policy_denied", "validation_error"],
            "proof_requirement": "verification_admitted",
            "safety_class": "bounded",
            "review_posture": "post_action_review",
            "execution_mode": "direct",
            "side_effects": ["filesystem:write"],
            "required_evidence": ["file_hash_after"],
            "egress_validation": {"mode": "hash_verify"},
            "supervisory_only": False,
        },
        caps=["filesystem"],
        difficulty="intermediate",
        description="Writes content to a filesystem path. Mutating effect — requires "
                    "verification_admitted proof and post_action_review. Produces file hash "
                    "for egress validation. Trust tier: watched.",
    ))

    # ── Network effects ─────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="network_read",
        source="typed_contracts.py::EffectClass.NETWORK_READ",
        compiled={
            "function_name": "http_get",
            "effect_class": "network_read",
            "input_contract": {
                "function_name": "http_get",
                "parameters": [
                    {"name": "url", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"pattern": "^https?://"}},
                    {"name": "headers", "hlf_type": "json", "json_schema_type": "object",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "http_get",
                "return_type": "json",
                "output_schema": {"type": "object"},
            },
            "failure_modes": ["network_error", "timeout_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["network:egress:read"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["network"],
        difficulty="basic",
        description="HTTP GET request. Requires network capability. URL validated against "
                    "http/https pattern. Failure modes include network_error and timeout_error. "
                    "Trust tier: approved.",
    ))

    exemplars.append(_make_exemplar(
        category="network_write",
        source="typed_contracts.py::EffectClass.NETWORK_WRITE",
        compiled={
            "function_name": "http_post",
            "effect_class": "network_write",
            "input_contract": {
                "function_name": "http_post",
                "parameters": [
                    {"name": "url", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"pattern": "^https?://"}},
                    {"name": "body", "hlf_type": "json", "json_schema_type": "object",
                     "required": True, "constraints": {}},
                    {"name": "headers", "hlf_type": "json", "json_schema_type": "object",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "http_post",
                "return_type": "json",
                "output_schema": {"type": "object"},
            },
            "failure_modes": ["network_error", "timeout_error", "policy_denied"],
            "proof_requirement": "verification_admitted",
            "safety_class": "bounded",
            "review_posture": "post_action_review",
            "execution_mode": "direct",
            "side_effects": ["network:egress:write"],
            "required_evidence": ["response_status", "response_body_hash"],
            "egress_validation": {"mode": "status_verify"},
            "supervisory_only": False,
        },
        caps=["network"],
        difficulty="intermediate",
        description="HTTP POST — mutating network egress. Requires verification_admitted proof. "
                    "Captures response status and body hash for audit. Trust tier: trusted.",
    ))

    exemplars.append(_make_exemplar(
        category="web_search",
        source="typed_contracts.py::EffectClass.WEB_SEARCH",
        compiled={
            "function_name": "web_search",
            "effect_class": "web_search",
            "input_contract": {
                "function_name": "web_search",
                "parameters": [
                    {"name": "query", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1, "max_length": 500}},
                    {"name": "max_results", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 1, "maximum": 20}},
                ],
            },
            "output_contract": {
                "function_name": "web_search",
                "return_type": "json",
                "output_schema": {"type": "array", "items": {"type": "object"}},
            },
            "failure_modes": ["network_error", "timeout_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["network:egress:read", "model:external_search"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["network"],
        difficulty="basic",
        description="Web search via external API. Produces dual side effects: network egress "
                    "read AND model external search. Query length bounded at 500 chars.",
    ))

    # ── Memory effects ──────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="memory_read",
        source="typed_contracts.py::EffectClass.MEMORY_READ",
        compiled={
            "function_name": "recall",
            "effect_class": "memory_read",
            "input_contract": {
                "function_name": "recall",
                "parameters": [
                    {"name": "key", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "namespace", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "recall",
                "return_type": "any",
                "output_schema": {},
            },
            "failure_modes": ["memory_error", "validation_error"],
            "proof_requirement": "none",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["memory:read"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["memory"],
        difficulty="basic",
        description="Recall a value from agent memory by key. Non-mutating. Optional "
                    "namespace for scoping. Failure: memory_error if key not found.",
    ))

    exemplars.append(_make_exemplar(
        category="memory_write",
        source="typed_contracts.py::EffectClass.MEMORY_WRITE",
        compiled={
            "function_name": "remember",
            "effect_class": "memory_write",
            "input_contract": {
                "function_name": "remember",
                "parameters": [
                    {"name": "key", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "value", "hlf_type": "any", "json_schema_type": "any",
                     "required": True, "constraints": {}},
                    {"name": "ttl_seconds", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 1}},
                ],
            },
            "output_contract": {
                "function_name": "remember",
                "return_type": "boolean",
                "output_schema": {"type": "boolean"},
            },
            "failure_modes": ["memory_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["memory:write"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["memory"],
        difficulty="basic",
        description="Store a value in agent memory. Mutating — writes to memory layer. "
                    "Optional TTL for automatic expiry. Trust tier: watched.",
    ))

    # ── Model inference ─────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="model_inference",
        source="typed_contracts.py::EffectClass.MODEL_INFERENCE",
        compiled={
            "function_name": "llm_call",
            "effect_class": "model_inference",
            "input_contract": {
                "function_name": "llm_call",
                "parameters": [
                    {"name": "prompt", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "model", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                    {"name": "temperature", "hlf_type": "real", "json_schema_type": "number",
                     "required": False, "constraints": {"minimum": 0.0, "maximum": 2.0}},
                    {"name": "max_tokens", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 1, "maximum": 32768}},
                ],
            },
            "output_contract": {
                "function_name": "llm_call",
                "return_type": "string",
                "output_schema": {"type": "string"},
            },
            "failure_modes": ["inference_error", "timeout_error", "governance_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "bounded",
            "review_posture": "audit_log",
            "execution_mode": "direct",
            "side_effects": ["model:inference"],
            "required_evidence": ["token_count", "model_name"],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["model"],
        difficulty="intermediate",
        description="Call an LLM for inference. Requires model capability. Temperature "
                    "bounded [0.0, 2.0], max_tokens bounded [1, 32768]. Produces token "
                    "count evidence. Trust tier: watched.",
    ))

    exemplars.append(_make_exemplar(
        category="embedding_generation",
        source="typed_contracts.py::EffectClass.EMBEDDING_GENERATION",
        compiled={
            "function_name": "embedding",
            "effect_class": "embedding_generation",
            "input_contract": {
                "function_name": "embedding",
                "parameters": [
                    {"name": "text", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "model", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "embedding",
                "return_type": "json",
                "output_schema": {"type": "array", "items": {"type": "number"}},
            },
            "failure_modes": ["inference_error", "timeout_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["model:embedding"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["model"],
        difficulty="basic",
        description="Generate vector embeddings from text. Returns float array. "
                    "Non-mutating model effect. Trust tier: watched.",
    ))

    # ── Multimodal effects ──────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="multimodal_vision",
        source="typed_contracts.py::EffectClass.MULTIMODAL_VISION",
        compiled={
            "function_name": "vision",
            "effect_class": "multimodal_vision",
            "input_contract": {
                "function_name": "vision",
                "parameters": [
                    {"name": "image_path", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"pattern": "\\.(png|jpg|jpeg|webp)$"}},
                    {"name": "prompt", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "vision",
                "return_type": "string",
                "output_schema": {"type": "string"},
            },
            "failure_modes": ["io_error", "inference_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["model:multimodal", "filesystem:read"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["model", "filesystem"],
        difficulty="intermediate",
        description="Vision model inference on an image file. Produces dual side effects: "
                    "model multimodal AND filesystem read. Image path validated against "
                    "supported formats.",
    ))

    exemplars.append(_make_exemplar(
        category="multimodal_ocr",
        source="typed_contracts.py::EffectClass.MULTIMODAL_OCR",
        compiled={
            "function_name": "ocr",
            "effect_class": "multimodal_ocr",
            "input_contract": {
                "function_name": "ocr",
                "parameters": [
                    {"name": "image_path", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"pattern": "\\.(png|jpg|jpeg|pdf|tiff)$"}},
                    {"name": "language", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "ocr",
                "return_type": "string",
                "output_schema": {"type": "string"},
            },
            "failure_modes": ["io_error", "inference_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["model:multimodal", "filesystem:read"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["model", "filesystem"],
        difficulty="intermediate",
        description="OCR text extraction from image/PDF. Dual side effects: model multimodal "
                    "AND filesystem read. Supports png, jpg, pdf, tiff.",
    ))

    # ── Process execution ───────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="process_spawn",
        source="typed_contracts.py::EffectClass.PROCESS_SPAWN",
        compiled={
            "function_name": "exec",
            "effect_class": "process_spawn",
            "input_contract": {
                "function_name": "exec",
                "parameters": [
                    {"name": "command", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "args", "hlf_type": "json", "json_schema_type": "array",
                     "required": False, "constraints": {}},
                    {"name": "timeout_ms", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 0, "maximum": 300000}},
                ],
            },
            "output_contract": {
                "function_name": "exec",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "stdout": {"type": "string"},
                        "stderr": {"type": "string"},
                        "exit_code": {"type": "integer"},
                    },
                },
            },
            "failure_modes": ["execution_error", "timeout_error", "policy_denied"],
            "proof_requirement": "operator_review_or_verified_admission",
            "safety_class": "high",
            "review_posture": "operator_review",
            "execution_mode": "simulation_preferred",
            "side_effects": ["process:spawn"],
            "required_evidence": ["exit_code", "stdout_hash", "stderr_hash"],
            "egress_validation": {"mode": "full_capture"},
            "supervisory_only": False,
        },
        caps=["exec"],
        difficulty="advanced",
        description="Spawn a child process. HIGH safety class — requires operator review "
                    "or verified admission. Execution mode: simulation_preferred. "
                    "Full egress capture. Trust tier: trusted. Timeout capped at 300s.",
    ))

    # ── Agent delegation ────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="agent_delegation",
        source="typed_contracts.py::EffectClass.AGENT_DELEGATION",
        compiled={
            "function_name": "delegate",
            "effect_class": "agent_delegation",
            "input_contract": {
                "function_name": "delegate",
                "parameters": [
                    {"name": "agent_id", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "task", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "role", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {}},
                    {"name": "gas_budget", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 1}},
                ],
            },
            "output_contract": {
                "function_name": "delegate",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "agent_id": {"type": "string"},
                        "status": {"type": "string"},
                        "result": {},
                    },
                },
            },
            "failure_modes": ["execution_error", "timeout_error", "governance_error"],
            "proof_requirement": "verification_admitted",
            "safety_class": "high",
            "review_posture": "post_action_review",
            "execution_mode": "direct",
            "side_effects": ["agent:delegate"],
            "required_evidence": ["agent_output_hash", "gas_consumed"],
            "egress_validation": {"mode": "hash_verify"},
            "supervisory_only": False,
        },
        caps=["agent", "governance"],
        difficulty="advanced",
        description="Delegate a task to another agent. HIGH safety class. Requires "
                    "verification_admitted proof. Post-action review with output hash "
                    "verification. Trust tier: trusted.",
    ))

    # ── Governance ──────────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="governance_vote",
        source="typed_contracts.py::EffectClass.GOVERNANCE_VOTE",
        compiled={
            "function_name": "vote",
            "effect_class": "governance_vote",
            "input_contract": {
                "function_name": "vote",
                "parameters": [
                    {"name": "proposal_id", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "decision", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"enum": ["approve", "reject", "abstain"]}},
                    {"name": "rationale", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "vote",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "vote_id": {"type": "string"},
                        "recorded": {"type": "boolean"},
                    },
                },
            },
            "failure_modes": ["governance_error", "validation_error"],
            "proof_requirement": "verification_admitted",
            "safety_class": "critical",
            "review_posture": "operator_review",
            "execution_mode": "direct",
            "side_effects": ["governance:vote"],
            "required_evidence": ["vote_receipt"],
            "egress_validation": {"mode": "receipt_verify"},
            "supervisory_only": False,
        },
        caps=["governance"],
        difficulty="advanced",
        description="Cast a governance vote. CRITICAL safety class — decisions are "
                    "binding. Decision constrained to approve/reject/abstain. "
                    "Requires verification_admitted proof and vote receipt. "
                    "Trust tier: trusted.",
    ))

    # ── Verification ────────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="formal_verification",
        source="typed_contracts.py::EffectClass.FORMAL_VERIFICATION",
        compiled={
            "function_name": "formal_verify",
            "effect_class": "formal_verification",
            "input_contract": {
                "function_name": "formal_verify",
                "parameters": [
                    {"name": "ast", "hlf_type": "json", "json_schema_type": "object",
                     "required": True, "constraints": {}},
                    {"name": "gas_budget", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 1, "maximum": 100000}},
                ],
            },
            "output_contract": {
                "function_name": "formal_verify",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "all_proven": {"type": "boolean"},
                        "proven_count": {"type": "integer"},
                        "total_count": {"type": "integer"},
                        "solver_name": {"type": "string"},
                    },
                },
            },
            "failure_modes": ["verification_error", "execution_error", "timeout_error"],
            "proof_requirement": "verification_admitted",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["verifier:execute"],
            "required_evidence": ["proof_bundle_sha256"],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["verifier"],
        difficulty="advanced",
        description="Run formal verification (Z3 solver) on an HLF AST. Gas budget "
                    "capped at 100k units. Produces proof bundle SHA-256 for audit. "
                    "Trust tier: trusted.",
    ))

    exemplars.append(_make_exemplar(
        category="verification",
        source="typed_contracts.py::EffectClass.VERIFICATION",
        compiled={
            "function_name": "verify",
            "effect_class": "verification",
            "input_contract": {
                "function_name": "verify",
                "parameters": [
                    {"name": "source", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "mode", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {"enum": ["enforce", "advisory", "report"]}},
                ],
            },
            "output_contract": {
                "function_name": "verify",
                "return_type": "json",
                "output_schema": {"type": "object"},
            },
            "failure_modes": ["verification_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["verifier:execute"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["verifier"],
        difficulty="intermediate",
        description="General verification pass on HLF source. Mode options: enforce "
                    "(block on failure), advisory (warn), report (log only). "
                    "Trust tier: trusted.",
    ))

    # ── Audit ───────────────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="audit_log",
        source="typed_contracts.py::EffectClass.AUDIT_LOG",
        compiled={
            "function_name": "audit_log",
            "effect_class": "audit_log",
            "input_contract": {
                "function_name": "audit_log",
                "parameters": [
                    {"name": "event", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "details", "hlf_type": "json", "json_schema_type": "object",
                     "required": False, "constraints": {}},
                    {"name": "severity", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {"enum": ["info", "warning", "error", "critical"]}},
                ],
            },
            "output_contract": {
                "function_name": "audit_log",
                "return_type": "boolean",
                "output_schema": {"type": "boolean"},
            },
            "failure_modes": ["io_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["audit:append"],
            "required_evidence": ["log_entry_id"],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["audit"],
        difficulty="basic",
        description="Append an event to the audit log. Mutating (writes to audit trail). "
                    "Severity constrained to standard levels. Trust tier: approved.",
    ))

    exemplars.append(_make_exemplar(
        category="merkle_append",
        source="typed_contracts.py::EffectClass.MERKLE_APPEND",
        compiled={
            "function_name": "merkle_append",
            "effect_class": "merkle_append",
            "input_contract": {
                "function_name": "merkle_append",
                "parameters": [
                    {"name": "data", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "chain_id", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "merkle_append",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "leaf_hash": {"type": "string"},
                        "root_hash": {"type": "string"},
                        "index": {"type": "integer"},
                    },
                },
            },
            "failure_modes": ["execution_error", "validation_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["audit:append"],
            "required_evidence": ["leaf_hash", "root_hash"],
            "egress_validation": {"mode": "merkle_verify"},
            "supervisory_only": False,
        },
        caps=["audit"],
        difficulty="intermediate",
        description="Append data to a Merkle chain. Returns leaf hash, root hash, and "
                    "index. Egress validation verifies Merkle proof. Trust tier: approved.",
    ))

    # ── Crypto ──────────────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="cryptographic_hash",
        source="typed_contracts.py::EffectClass.CRYPTOGRAPHIC_HASH",
        compiled={
            "function_name": "hash",
            "effect_class": "cryptographic_hash",
            "input_contract": {
                "function_name": "hash",
                "parameters": [
                    {"name": "data", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "algorithm", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {"enum": ["sha256", "sha512", "blake2b"]}},
                ],
            },
            "output_contract": {
                "function_name": "hash",
                "return_type": "string",
                "output_schema": {"type": "string", "pattern": "^[0-9a-f]{64,128}$"},
            },
            "failure_modes": ["validation_error"],
            "proof_requirement": "none",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": [],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["crypto"],
        difficulty="basic",
        description="Compute cryptographic hash. Pure computation — no side effects. "
                    "Algorithm constrained to sha256/sha512/blake2b. "
                    "Trust tier: advisory.",
    ))

    # ── Safety / Embodied ───────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="safety_stop",
        source="typed_contracts.py::EffectClass.SAFETY_STOP",
        compiled={
            "function_name": "safety_stop",
            "effect_class": "safety_stop",
            "input_contract": {
                "function_name": "safety_stop",
                "parameters": [
                    {"name": "reason", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "scope", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {"enum": ["agent", "swarm", "system"]}},
                ],
            },
            "output_contract": {
                "function_name": "safety_stop",
                "return_type": "boolean",
                "output_schema": {"type": "boolean"},
            },
            "failure_modes": ["execution_error"],
            "proof_requirement": "operator_review_or_verified_admission",
            "safety_class": "critical",
            "review_posture": "operator_review",
            "execution_mode": "direct",
            "side_effects": ["embodied:safety_stop"],
            "required_evidence": ["stop_confirmation"],
            "egress_validation": {"mode": "confirmation_required"},
            "supervisory_only": True,
        },
        caps=["embodied"],
        difficulty="advanced",
        description="Emergency safety stop. CRITICAL safety class, supervisory only. "
                    "Requires operator review or verified admission. Scope controls "
                    "blast radius (agent/swarm/system). Trust tier: hearth (maximum).",
    ))

    exemplars.append(_make_exemplar(
        category="guarded_actuation",
        source="typed_contracts.py::EffectClass.GUARDED_ACTUATION",
        compiled={
            "function_name": "actuate",
            "effect_class": "guarded_actuation",
            "input_contract": {
                "function_name": "actuate",
                "parameters": [
                    {"name": "actuator_id", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "action", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "parameters", "hlf_type": "json", "json_schema_type": "object",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "actuate",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "actuated": {"type": "boolean"},
                        "confirmation": {"type": "string"},
                    },
                },
            },
            "failure_modes": ["execution_error", "policy_denied", "timeout_error"],
            "proof_requirement": "operator_review_or_verified_admission",
            "safety_class": "critical",
            "review_posture": "operator_review",
            "execution_mode": "simulation_only",
            "side_effects": ["embodied:guarded_actuation"],
            "required_evidence": ["actuation_confirmation", "safety_check_passed"],
            "egress_validation": {"mode": "confirmation_required"},
            "supervisory_only": True,
        },
        caps=["embodied"],
        difficulty="advanced",
        description="Actuate a physical or embodied system. CRITICAL safety class, "
                    "supervisory only, simulation_only execution. Full operator review "
                    "with safety check evidence. Trust tier: hearth.",
    ))

    # ── Local analysis effects ──────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="local_analysis",
        source="typed_contracts.py::EffectClass.LOCAL_ANALYSIS",
        compiled={
            "function_name": "analyze",
            "effect_class": "local_analysis",
            "input_contract": {
                "function_name": "analyze",
                "parameters": [
                    {"name": "data", "hlf_type": "json", "json_schema_type": "object",
                     "required": True, "constraints": {}},
                    {"name": "analysis_type", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "analyze",
                "return_type": "json",
                "output_schema": {"type": "object"},
            },
            "failure_modes": ["validation_error", "execution_error"],
            "proof_requirement": "none",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": [],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["local"],
        difficulty="basic",
        description="Run local analysis on data. Pure computation — no side effects, "
                    "no system capabilities required. Default effect class for "
                    "unrecognized tool names. Trust tier: advisory.",
    ))

    exemplars.append(_make_exemplar(
        category="assertion",
        source="typed_contracts.py::EffectClass.ASSERTION",
        compiled={
            "function_name": "assert",
            "effect_class": "assertion",
            "input_contract": {
                "function_name": "assert",
                "parameters": [
                    {"name": "condition", "hlf_type": "boolean", "json_schema_type": "boolean",
                     "required": True, "constraints": {}},
                    {"name": "message", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {}},
                ],
            },
            "output_contract": {
                "function_name": "assert",
                "return_type": "boolean",
                "output_schema": {"type": "boolean"},
            },
            "failure_modes": ["validation_error"],
            "proof_requirement": "none",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": [],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["local"],
        difficulty="basic",
        description="Boolean assertion check. Pure computation — no side effects. "
                    "Reachable via Ж-glyph syntax (Ж [ENFORCE], Ж [CONSTRAINT]). "
                    "Trust tier: advisory.",
    ))

    exemplars.append(_make_exemplar(
        category="similarity_math",
        source="typed_contracts.py::EffectClass.SIMILARITY_MATH",
        compiled={
            "function_name": "similarity",
            "effect_class": "similarity_math",
            "input_contract": {
                "function_name": "similarity",
                "parameters": [
                    {"name": "vector_a", "hlf_type": "json", "json_schema_type": "array",
                     "required": True, "constraints": {}},
                    {"name": "vector_b", "hlf_type": "json", "json_schema_type": "array",
                     "required": True, "constraints": {}},
                    {"name": "metric", "hlf_type": "string", "json_schema_type": "string",
                     "required": False, "constraints": {"enum": ["cosine", "euclidean", "dot"]}},
                ],
            },
            "output_contract": {
                "function_name": "similarity",
                "return_type": "number",
                "output_schema": {"type": "number", "minimum": -1.0, "maximum": 1.0},
            },
            "failure_modes": ["validation_error"],
            "proof_requirement": "none",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": [],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["local"],
        difficulty="basic",
        description="Compute similarity between two vectors. Pure computation. "
                    "Metric constrained to cosine/euclidean/dot. "
                    "Output bounded [-1.0, 1.0]. Trust tier: advisory.",
    ))

    # ── Routing ─────────────────────────────────────────────────────────────

    exemplars.append(_make_exemplar(
        category="route_selection",
        source="typed_contracts.py::EffectClass.ROUTE_SELECTION",
        compiled={
            "function_name": "route",
            "effect_class": "route_selection",
            "input_contract": {
                "function_name": "route",
                "parameters": [
                    {"name": "destination", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "payload", "hlf_type": "json", "json_schema_type": "object",
                     "required": False, "constraints": {}},
                    {"name": "priority", "hlf_type": "integer", "json_schema_type": "integer",
                     "required": False, "constraints": {"minimum": 0, "maximum": 10}},
                ],
            },
            "output_contract": {
                "function_name": "route",
                "return_type": "json",
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "routed_to": {"type": "string"},
                        "accepted": {"type": "boolean"},
                    },
                },
            },
            "failure_modes": ["execution_error", "timeout_error"],
            "proof_requirement": "runtime_checked",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": ["routing:select"],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["routing"],
        difficulty="intermediate",
        description="Route a payload to a destination agent/module. Priority [0-10]. "
                    "Non-mutating (route selection doesn't change state). "
                    "Trust tier: approved.",
    ))

    exemplars.append(_make_exemplar(
        category="token_transform",
        source="typed_contracts.py::EffectClass.TOKEN_TRANSFORM",
        compiled={
            "function_name": "token_transform",
            "effect_class": "token_transform",
            "input_contract": {
                "function_name": "token_transform",
                "parameters": [
                    {"name": "text", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"min_length": 1}},
                    {"name": "transform", "hlf_type": "string", "json_schema_type": "string",
                     "required": True, "constraints": {"enum": ["summarize", "expand", "rephrase", "translate"]}},
                ],
            },
            "output_contract": {
                "function_name": "token_transform",
                "return_type": "string",
                "output_schema": {"type": "string"},
            },
            "failure_modes": ["validation_error", "execution_error"],
            "proof_requirement": "none",
            "safety_class": "none",
            "review_posture": "none",
            "execution_mode": "direct",
            "side_effects": [],
            "required_evidence": [],
            "egress_validation": {"mode": "none"},
            "supervisory_only": False,
        },
        caps=["local"],
        difficulty="basic",
        description="Apply a text transformation. Pure text processing — no side effects "
                    "or external capabilities. Transform type constrained to standard "
                    "operations. Trust tier: advisory.",
    ))

    return exemplars


# ═══════════════════════════════════════════════════════════════════════════════
# Build
# ═══════════════════════════════════════════════════════════════════════════════

def build_db(output_path: Path, force: bool = False) -> int:
    """Create the seed database and populate with curated exemplars.

    Returns the number of exemplars inserted.
    """
    if output_path.exists():
        if force:
            output_path.unlink()
        else:
            print(f"ERROR: {output_path} already exists. Use --force to overwrite.")
            return 0

    conn = sqlite3.connect(str(output_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        conn.executescript(SCHEMA_SQL)

        exemplars = build_exemplars()
        conn.executemany(
            """INSERT INTO exemplars
               (category, hlf_source, compiled_json, capability_tags,
                difficulty, description, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            exemplars,
        )
        conn.commit()

        # Verify
        count = conn.execute("SELECT COUNT(*) FROM exemplars").fetchone()[0]
        categories = conn.execute(
            "SELECT DISTINCT category FROM exemplars ORDER BY category"
        ).fetchall()
        print(f"✓ Built {output_path}")
        print(f"  {count} exemplars across {len(categories)} categories:")
        for (cat,) in categories:
            cat_count = conn.execute(
                "SELECT COUNT(*) FROM exemplars WHERE category = ?", (cat,)
            ).fetchone()[0]
            print(f"    {cat}: {cat_count}")
        return count
    finally:
        conn.close()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(
        description="Build the HKS seed database from HLF typed contract exemplars."
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: hks_seed.db in repo root)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing database",
    )
    args = parser.parse_args()

    if args.output:
        output_path = Path(args.output)
    else:
        # Default: repo root = 2 levels up from scripts/
        repo_root = Path(__file__).resolve().parent.parent
        output_path = repo_root / "hks_seed.db"

    count = build_db(output_path, force=args.force)
    if count == 0 and not args.force:
        sys.exit(1)


if __name__ == "__main__":
    main()
