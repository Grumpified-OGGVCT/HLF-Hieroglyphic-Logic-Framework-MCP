"""
Tests for .github/scripts/ — spec drift check, ethics compliance check,
codebase snapshot, Ollama client (offline unit tests only — no real API calls).
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add .github/scripts to the path so we can import the modules
SCRIPTS_DIR = Path(__file__).parent.parent / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


# ── spec_drift_check tests ─────────────────────────────────────────────────────

class TestSpecDriftCheck:
    def test_load_yaml_opcodes_parses_name_code_pairs(self, tmp_path):
        from spec_drift_check import _load_yaml_opcodes
        yaml = tmp_path / "spec.yaml"
        yaml.write_text("""\
opcodes:
  - name: NOP       code: 0x00  operand: false
  - name: PUSH_CONST code: 0x01 operand: true
  - name: HALT      code: 0xFF  operand: false
""")
        result = _load_yaml_opcodes(yaml)
        assert result == {"NOP": 0x00, "PUSH_CONST": 0x01, "HALT": 0xFF}

    def test_load_py_opcodes_parses_enum_class(self, tmp_path):
        from spec_drift_check import _load_py_opcodes
        py = tmp_path / "bytecode.py"
        py.write_text("""\
class Op(int, enum.Enum):
    NOP         = 0x00
    PUSH_CONST  = 0x01
    HALT        = 0xFF

class OtherClass:
    pass
""")
        result = _load_py_opcodes(py)
        assert result == {"NOP": 0x00, "PUSH_CONST": 0x01, "HALT": 0xFF}

    def test_no_drift_when_spec_matches_implementation(self, tmp_path):
        from spec_drift_check import _load_yaml_opcodes, _load_py_opcodes
        yaml = tmp_path / "spec.yaml"
        yaml.write_text("  - name: NOP  code: 0x00\n  - name: HALT  code: 0xFF\n")
        py = tmp_path / "bytecode.py"
        py.write_text("class Op:\n    NOP = 0x00\n    HALT = 0xFF\n")
        yaml_ops = _load_yaml_opcodes(yaml)
        py_ops   = _load_py_opcodes(py)
        assert yaml_ops.keys() == py_ops.keys()
        assert all(yaml_ops[k] == py_ops[k] for k in yaml_ops)

    def test_detects_missing_opcode_in_py(self, tmp_path):
        from spec_drift_check import _load_yaml_opcodes, _load_py_opcodes
        yaml = tmp_path / "spec.yaml"
        yaml.write_text("  - name: NOP  code: 0x00\n  - name: NEW_OP  code: 0x99\n")
        py = tmp_path / "bytecode.py"
        py.write_text("class Op:\n    NOP = 0x00\n")
        yaml_ops = _load_yaml_opcodes(yaml)
        py_ops   = _load_py_opcodes(py)
        only_in_yaml = set(yaml_ops) - set(py_ops)
        assert "NEW_OP" in only_in_yaml

    def test_detects_opcode_code_mismatch(self, tmp_path):
        from spec_drift_check import _load_yaml_opcodes, _load_py_opcodes
        yaml = tmp_path / "spec.yaml"
        yaml.write_text("  - name: NOP  code: 0x00\n")
        py = tmp_path / "bytecode.py"
        py.write_text("class Op:\n    NOP = 0x01\n")  # Wrong code!
        yaml_ops = _load_yaml_opcodes(yaml)
        py_ops   = _load_py_opcodes(py)
        mismatches = {
            name: {"yaml": hex(yaml_ops[name]), "py": hex(py_ops[name])}
            for name in yaml_ops.keys() & py_ops.keys()
            if yaml_ops[name] != py_ops[name]
        }
        assert "NOP" in mismatches

    def test_count_mcp_tools(self, tmp_path):
        from spec_drift_check import _count_mcp_tools
        server = tmp_path / "server.py"
        server.write_text("""\
@mcp.tool()
def tool_one(): pass

@mcp.tool()
def tool_two(): pass

@mcp.resource("hlf://test")
def res_one(): pass
""")
        assert _count_mcp_tools(server) == 2

    def test_readme_claimed_counts_extracts_numbers(self, tmp_path):
        from spec_drift_check import _readme_claimed_counts
        readme = tmp_path / "README.md"
        readme.write_text("""\
# HLF
22 MCP tools exposed
37 opcodes in the VM
8 stdlib modules
""")
        counts = _readme_claimed_counts(readme)
        assert counts.get("tools") == 22
        assert counts.get("opcodes") == 37
        assert counts.get("stdlib_modules") == 8

    def test_run_checks_against_real_repo(self):
        """Integration test: run against the actual repo and verify JSON structure."""
        from spec_drift_check import run_checks
        findings, has_drift = run_checks()
        assert isinstance(findings, list)
        assert len(findings) >= 1
        for f in findings:
            assert "check" in f
            assert "drift" in f
        # The real repo should have no opcode drift (we fixed it)
        opcode_check = next((f for f in findings if f["check"] == "bytecode_spec_vs_op_enum"), None)
        if opcode_check:
            assert opcode_check["only_in_yaml"] == [], f"Opcodes only in yaml: {opcode_check['only_in_yaml']}"
            assert opcode_check["only_in_py"] == [], f"Opcodes only in py: {opcode_check['only_in_py']}"


# ── ethics_compliance_check tests ─────────────────────────────────────────────

class TestEthicsComplianceCheck:
    def test_checks_ethics_stubs_detects_missing_module(self, tmp_path, monkeypatch):
        from ethics_compliance_check import _check_ethics_stubs
        # Patch ETHICS_DIR to a temp dir that has no files
        import ethics_compliance_check as ecc
        monkeypatch.setattr(ecc, "ETHICS_DIR", tmp_path)
        result = _check_ethics_stubs()
        assert all(v["is_stub"] for v in result.values())
        assert all(v["status"] == "MISSING" for v in result.values())

    def test_checks_ethics_stubs_detects_implemented_module(self, tmp_path, monkeypatch):
        from ethics_compliance_check import _check_ethics_stubs
        import ethics_compliance_check as ecc
        monkeypatch.setattr(ecc, "ETHICS_DIR", tmp_path)
        # Write a "real" implementation (many non-stub lines)
        (tmp_path / "constitution.py").write_text("\n".join(
            [f"def rule_{i}(x): return x > 0" for i in range(20)]
        ))
        # Leave others missing
        result = _check_ethics_stubs()
        assert result["constitution.py"]["status"] == "IMPLEMENTED"
        assert result["termination.py"]["status"] == "MISSING"

    def test_checks_compiler_ethics_hook_detects_comment_only(self, tmp_path, monkeypatch):
        from ethics_compliance_check import _check_compiler_ethics_hook
        import ethics_compliance_check as ecc
        p = tmp_path / "compiler.py"
        p.write_text("# TODO: ethics governor hook goes here\n")
        monkeypatch.setattr(ecc, "COMPILER_PY", p)
        result = _check_compiler_ethics_hook()
        assert result["wired"] is False
        assert result["comment_placeholder_present"] is True
        assert result["status"] == "COMMENT_ONLY"

    def test_checks_compiler_ethics_hook_detects_wired(self, tmp_path, monkeypatch):
        from ethics_compliance_check import _check_compiler_ethics_hook
        import ethics_compliance_check as ecc
        p = tmp_path / "compiler.py"
        p.write_text("from hlf_mcp.hlf.ethics import constitution\nconstitution.check(tree)\n")
        monkeypatch.setattr(ecc, "COMPILER_PY", p)
        result = _check_compiler_ethics_hook()
        assert result["wired"] is True
        assert result["status"] == "WIRED"

    def test_align_rules_count(self, tmp_path, monkeypatch):
        from ethics_compliance_check import _check_align_rules
        import ethics_compliance_check as ecc
        p = tmp_path / "align_rules.json"
        p.write_text(json.dumps([
            {"id": "ALIGN-001", "pattern": "password="},
            {"id": "ALIGN-002", "pattern": "localhost"},
            {"id": "ALIGN-003", "pattern": "exec("},
            {"id": "ALIGN-004", "pattern": "../"},
            {"id": "ALIGN-005", "pattern": "exfil"},
        ]))
        monkeypatch.setattr(ecc, "ALIGN_JSON", p)
        result = _check_align_rules()
        assert result["rule_count"] == 5
        assert result["adequate"] is True

    def test_align_rules_inadequate_below_5(self, tmp_path, monkeypatch):
        from ethics_compliance_check import _check_align_rules
        import ethics_compliance_check as ecc
        p = tmp_path / "align_rules.json"
        p.write_text(json.dumps([{"id": "ALIGN-001", "pattern": "password="}]))
        monkeypatch.setattr(ecc, "ALIGN_JSON", p)
        result = _check_align_rules()
        assert result["adequate"] is False
        assert result["status"] == "NEEDS_MORE_RULES"


# ── codebase_snapshot tests ────────────────────────────────────────────────────

class TestCodebaseSnapshot:
    def test_snapshot_contains_file_tree(self, tmp_path):
        from codebase_snapshot import build_snapshot, ROOT
        # Just verify the function runs and returns a non-empty string
        # (uses the real repo root)
        result = build_snapshot(char_budget=50_000)
        assert len(result) > 100
        assert "FILE TREE" in result

    def test_snapshot_includes_priority_files(self, tmp_path):
        from codebase_snapshot import build_snapshot
        result = build_snapshot(char_budget=200_000)
        # Should include key files
        assert "compiler.py" in result or "PRIORITY" in result

    def test_snapshot_respects_budget(self):
        from codebase_snapshot import build_snapshot
        result = build_snapshot(char_budget=5_000)
        assert len(result) <= 6_000  # Small buffer for header

    def test_snapshot_writes_to_file(self, tmp_path):
        from codebase_snapshot import build_snapshot
        out = str(tmp_path / "snapshot.txt")
        build_snapshot(output_file=out, char_budget=10_000)
        assert Path(out).exists()
        assert Path(out).stat().st_size > 0


# ── ollama_client tests (offline — no real API calls) ─────────────────────────

class TestOllamaClientOffline:
    def test_extract_content_native_format(self):
        from ollama_client import extract_content
        response = {"message": {"role": "assistant", "content": "Hello, HLF!"}}
        assert extract_content(response) == "Hello, HLF!"

    def test_extract_content_openai_compat_format(self):
        from ollama_client import extract_content
        response = {"choices": [{"message": {"role": "assistant", "content": "OpenAI compat"}}]}
        assert extract_content(response) == "OpenAI compat"

    def test_extract_content_fallback(self):
        from ollama_client import extract_content
        response = {"unexpected": "structure"}
        result = extract_content(response)
        assert isinstance(result, str)

    def test_call_ollama_raises_on_missing_key(self):
        from ollama_client import call_ollama
        import urllib.error
        import urllib.request
        # Patch urlopen to raise 401
        def fake_urlopen(req, timeout=None):
            raise urllib.error.HTTPError(
                url=req.full_url, code=401,
                msg="Unauthorized",
                hdrs=None,  # type: ignore
                fp=__import__("io").BytesIO(b"Unauthorized")
            )
        with patch("urllib.request.urlopen", fake_urlopen):
            with pytest.raises((urllib.error.HTTPError, RuntimeError)):
                call_ollama(
                    model="devstral:24b",
                    system="test",
                    prompt="test",
                    api_key="invalid_key",
                )

    def test_call_ollama_returns_parsed_json_on_success(self):
        from ollama_client import call_ollama
        import io
        fake_response_data = json.dumps({
            "message": {"role": "assistant", "content": "pong"},
            "model": "devstral:24b",
        }).encode("utf-8")

        class FakeResponse:
            def read(self): return fake_response_data
            def __enter__(self): return self
            def __exit__(self, *a): pass

        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = call_ollama(
                model="devstral:24b",
                system="You are a test model.",
                prompt="ping",
                api_key="test_key",
            )
        assert result["message"]["content"] == "pong"
