from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.registry import HostFunctionRegistry
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.tool_dispatch import ToolRegistry
from hlf_mcp.instinct.lifecycle import InstinctLifecycle
from hlf_mcp.rag.memory import RAGMemory


@dataclass(slots=True)
class ServerContext:
    compiler: HLFCompiler
    formatter: HLFFormatter
    linter: HLFLinter
    runtime: HLFRuntime
    bytecoder: HLFBytecode
    benchmark: HLFBenchmark
    memory_store: RAGMemory
    instinct_mgr: InstinctLifecycle
    host_registry: HostFunctionRegistry
    tool_registry: ToolRegistry

    def store_known_good_translation_contract(
        self,
        *,
        original_text: str,
        source: str,
        language: str,
        translation: dict[str, Any],
        tier: str,
        provenance: str,
    ) -> dict[str, Any]:
        payload = {
            "kind": "hlf_translation_contract",
            "language": language,
            "tier": tier,
            "original_text": original_text,
            "hlf_source": source,
            "translation": translation,
        }
        return self.memory_store.store(
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            topic="hlf_translation_contracts",
            confidence=float(translation.get("roundtrip_fidelity_score", 1.0)),
            provenance=provenance,
            tags=["hlf", "translation", "contract", language, tier],
        )


def build_server_context() -> ServerContext:
    return ServerContext(
        compiler=HLFCompiler(),
        formatter=HLFFormatter(),
        linter=HLFLinter(),
        runtime=HLFRuntime(),
        bytecoder=HLFBytecode(),
        benchmark=HLFBenchmark(),
        memory_store=RAGMemory(),
        instinct_mgr=InstinctLifecycle(),
        host_registry=HostFunctionRegistry(),
        tool_registry=ToolRegistry(),
    )


def check_governance_manifest(logger: logging.Logger) -> None:
    """Warn if governance files have drifted from MANIFEST.sha256."""
    gov_dir = Path(__file__).resolve().parents[1] / "governance"
    manifest_path = gov_dir / "MANIFEST.sha256"
    if not manifest_path.is_file():
        return

    expected: dict[str, str] = {}
    with manifest_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split(None, 1)
                if len(parts) == 2:
                    expected[parts[1]] = parts[0]

    drift: list[str] = []
    for filename, expected_hash in expected.items():
        path = gov_dir / filename
        if not path.is_file():
            drift.append(f"{filename}: missing")
            continue
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            drift.append(f"{filename}: hash mismatch")

    if drift:
        logger.warning(
            "Governance file drift detected (MANIFEST.sha256): %s",
            ", ".join(drift),
        )