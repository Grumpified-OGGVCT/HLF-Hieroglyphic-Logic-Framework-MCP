from __future__ import annotations

import collections
import hashlib
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.governance_events import GovernanceEvent
from hlf_mcp.hlf.governance_proofs import verify_event_chain

_ZERO_HASH = "0" * 64
_DEFAULT_DIR = Path(__file__).resolve().parents[2] / "observability" / "openllmetry"


def _canonical_payload(event: str, data: dict[str, Any]) -> str:
    return json.dumps({"event": event, "data": data}, sort_keys=True, ensure_ascii=False)


def _compute_trace_id(prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}{payload}".encode()).hexdigest()


def _replay_entry_hash(entry: dict[str, Any]) -> str:
    payload = _canonical_payload(str(entry.get("event") or ""), dict(entry.get("data") or {}))
    return _compute_trace_id(str(entry.get("parent_trace_hash") or _ZERO_HASH), payload)


class AuditChain:
    def __init__(self, log_path: str | None = None, last_hash_path: str | None = None) -> None:
        configured_log = log_path or os.environ.get("HLF_AUDIT_CHAIN_LOG")
        configured_last_hash = last_hash_path or os.environ.get("HLF_AUDIT_CHAIN_LAST_HASH")
        default_log = _DEFAULT_DIR / "hlf_mcp.audit.jsonl"
        default_last_hash = _DEFAULT_DIR / "hlf_mcp.last_hash.txt"
        self._log_path = Path(configured_log) if configured_log else default_log
        self._last_hash_path = (
            Path(configured_last_hash) if configured_last_hash else default_last_hash
        )
        self._lock = threading.Lock()
        self._recent: collections.deque[dict[str, Any]] = collections.deque(maxlen=200)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash_path.parent.mkdir(parents=True, exist_ok=True)

    def _read_last_hash(self) -> str:
        try:
            if self._last_hash_path.exists():
                return self._last_hash_path.read_text(encoding="utf-8").strip() or _ZERO_HASH
        except Exception:
            return _ZERO_HASH
        return _ZERO_HASH

    def _write_last_hash(self, trace_id: str) -> None:
        try:
            self._last_hash_path.write_text(trace_id, encoding="utf-8")
        except Exception:
            pass

    def log(
        self,
        event: str,
        data: dict[str, Any] | None = None,
        *,
        agent_role: str = "hlf_mcp",
        goal_id: str = "",
        confidence_score: float = 1.0,
        anomaly_score: float = 0.0,
        token_cost: int = 0,
    ) -> dict[str, Any]:
        payload_data = data or {}
        with self._lock:
            prev_hash = self._read_last_hash()
            payload = _canonical_payload(event, payload_data)
            trace_id = _compute_trace_id(prev_hash, payload)
            entry = {
                "trace_id": trace_id,
                "parent_trace_hash": prev_hash,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()),
                "goal_id": goal_id,
                "agent_role": agent_role,
                "event": event,
                "data": payload_data,
                "confidence_score": confidence_score,
                "anomaly_score": anomaly_score,
                "token_cost": token_cost,
            }
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
            self._write_last_hash(trace_id)
            self._recent.append(entry)
            return entry

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        size = max(1, min(limit, 200))
        with self._lock:
            entries = list(self._recent)
        entries.reverse()
        return entries[:size]

    def iter_entries(self, limit: int = 1000) -> list[dict[str, Any]]:
        size = max(1, min(limit, 10000))
        if not self._log_path.is_file():
            return []
        entries: list[dict[str, Any]] = []
        try:
            with self._log_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        entries.append(item)
        except Exception:
            return []
        return entries[-size:]

    def verify_integrity(self, limit: int = 1000) -> dict[str, Any]:
        entries = self.iter_entries(limit=limit)
        errors: list[str] = []
        prev_hash = _ZERO_HASH
        for index, entry in enumerate(entries):
            parent = str(entry.get("parent_trace_hash") or "")
            if parent != prev_hash and index > 0:
                errors.append(f"entry {index} parent_trace_hash mismatch")
            expected = _replay_entry_hash(entry)
            if expected != str(entry.get("trace_id") or ""):
                errors.append(f"entry {index} trace_id mismatch")
            prev_hash = str(entry.get("trace_id") or "")
        return {
            "status": "ok" if not errors else "error",
            "verified": not errors,
            "checked": len(entries),
            "error_count": len(errors),
            "errors": errors,
            "head_hash": prev_hash if entries else _ZERO_HASH,
            "boundary": {
                "integrity": "sha256_hash_chain",
                "cryptographic_claim": "tamper-evident content hashing only",
                "signature": "none",
                "non_repudiation": False,
            },
            "log_path": str(self._log_path),
        }

    def verify_governance_proof(self, proof: dict[str, Any]) -> dict[str, Any]:
        chain = proof.get("chain") if isinstance(proof.get("chain"), dict) else proof
        return verify_event_chain(chain)

    def human_report(self, limit: int = 20) -> str:
        verification = self.verify_integrity(limit=max(limit, 1))
        lines = [
            "# HLF Audit Chain Report",
            "",
            f"- Status: {verification['status']}",
            f"- Checked entries: {verification['checked']}",
            f"- Head hash: {verification['head_hash']}",
            "- Boundary: SHA-256 hash-chain integrity only; no signature or non-repudiation claimed.",
            "",
            "## Recent events",
        ]
        for entry in self.iter_entries(limit=limit)[-limit:]:
            lines.append(f"- {entry.get('timestamp')} `{entry.get('event')}` trace={entry.get('trace_id')}")
        return "\n".join(lines) + "\n"

    def log_governance_event(
        self,
        event: GovernanceEvent,
        *,
        agent_role: str = "governance_spine",
        goal_id: str = "",
        confidence_score: float = 1.0,
        anomaly_score: float = 0.0,
        token_cost: int = 0,
    ) -> dict[str, Any]:
        audit_entry = self.log(
            "governance_event",
            event.audit_payload(),
            agent_role=agent_role,
            goal_id=goal_id or event.goal_id,
            confidence_score=confidence_score,
            anomaly_score=anomaly_score,
            token_cost=token_cost,
        )
        event.trace_id = str(audit_entry.get("trace_id", ""))
        return audit_entry
