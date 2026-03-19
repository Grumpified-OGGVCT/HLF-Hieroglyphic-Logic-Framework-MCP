from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_verify_chain_accepts_valid_chain() -> None:
    module = _load_module("verify_chain_module", "scripts/verify_chain.py")

    first = {"event": "compile", "data": {"file": "hello.hlf"}}
    second = {"event": "run", "data": {"status": "ok"}}

    first["trace_id"] = hashlib.sha256(
        (
            module.ZERO_HASH
            + json.dumps({"event": "compile", "data": {"file": "hello.hlf"}}, sort_keys=True)
        ).encode()
    ).hexdigest()
    second["trace_id"] = hashlib.sha256(
        (
            first["trace_id"]
            + json.dumps({"event": "run", "data": {"status": "ok"}}, sort_keys=True)
        ).encode()
    ).hexdigest()

    ok, errors, final_hash = module.verify_chain(
        [first, second], expected_last_hash=second["trace_id"]
    )
    assert ok is True
    assert errors == []
    assert final_hash == second["trace_id"]


def test_verify_chain_reports_mismatch() -> None:
    module = _load_module("verify_chain_module_bad", "scripts/verify_chain.py")

    entry = {"event": "compile", "data": {"file": "hello.hlf"}, "trace_id": "bad"}
    ok, errors, _ = module.verify_chain([entry])

    assert ok is False
    assert errors
    assert "trace_id mismatch" in errors[0]
