from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, relative_path: str):
    path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generate_host_functions_reference_uses_packaged_registry() -> None:
    module = _load_module("gen_from_spec_module", "docs/gen_from_spec.py")

    text = module.generate_host_functions_reference()

    assert "# HLF Host Functions Reference" in text
    assert "Registry version:" in text
    assert "| READ |" in text
    assert "| z3_verify |" in text
    assert "| Input Schema | Output Schema |" in text
    assert "`file_read`" in text


def test_write_host_functions_reference_writes_file(tmp_path: Path) -> None:
    module = _load_module("gen_from_spec_module_write", "docs/gen_from_spec.py")

    output = tmp_path / "HLF_HOST_FUNCTIONS_REFERENCE.md"
    written = module.write_host_functions_reference(output_path=output)

    assert written == output
    content = output.read_text(encoding="utf-8")
    assert "Generated from `governance/host_functions.json`." in content
