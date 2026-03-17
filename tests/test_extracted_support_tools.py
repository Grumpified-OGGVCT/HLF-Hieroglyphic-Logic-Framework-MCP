from __future__ import annotations

import importlib.util
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script_module(name: str):
    script_path = REPO_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_generate_tm_grammar_contains_core_scopes(tmp_path: Path) -> None:
    module = _load_script_module("generate_tm_grammar")
    grammar = module.build_textmate_grammar()

    assert grammar["scopeName"] == "source.hlf"
    assert "glyph" in grammar["repository"]
    assert "canonical_tag" in grammar["repository"]

    output_path = tmp_path / "hlf.tmLanguage.json"
    module.write_textmate_grammar(output_path)
    assert output_path.exists()
    assert '"scopeName": "source.hlf"' in output_path.read_text(encoding="utf-8")


def test_gen_docs_writes_tag_and_stdlib_references(tmp_path: Path) -> None:
    module = _load_script_module("gen_docs")

    repo_root = tmp_path / "repo"
    docs_dir = repo_root / "docs"
    gov_dir = repo_root / "governance" / "templates"
    root_gov_dir = repo_root / "governance"
    docs_dir.mkdir(parents=True)
    gov_dir.mkdir(parents=True)
    root_gov_dir.mkdir(parents=True, exist_ok=True)
    source_dict = REPO_ROOT / "governance" / "templates" / "dictionary.json"
    source_host_functions = REPO_ROOT / "governance" / "host_functions.json"
    source_gen_from_spec = REPO_ROOT / "docs" / "gen_from_spec.py"
    gov_dir.joinpath("dictionary.json").write_text(source_dict.read_text(encoding="utf-8"), encoding="utf-8")
    root_gov_dir.joinpath("host_functions.json").write_text(
        source_host_functions.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    docs_dir.joinpath("gen_from_spec.py").write_text(
        source_gen_from_spec.read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    written = module.generate_docs(repo_root)
    assert len(written) == 3

    tag_ref = (docs_dir / "HLF_TAG_REFERENCE.md").read_text(encoding="utf-8")
    stdlib_ref = (docs_dir / "HLF_STDLIB_REFERENCE.md").read_text(encoding="utf-8")
    host_ref = (docs_dir / "HLF_HOST_FUNCTIONS_REFERENCE.md").read_text(encoding="utf-8")

    assert "# HLF Tag Reference" in tag_ref
    assert "`INTENT`" in tag_ref
    assert "# HLF Stdlib Reference" in stdlib_ref
    assert "MATH_ABS" in stdlib_ref
    assert "# HLF Host Functions Reference" in host_ref
    assert "| READ |" in host_ref


def test_hlf_token_lint_reports_header_and_budget_violations() -> None:
    module = _load_script_module("hlf_token_lint")
    import tiktoken

    encoder = tiktoken.get_encoding("cl100k_base")
    text = 'INTENT without header\n' + ('word ' * 40) + '\n'
    errors = module.lint_text(text, encoder, max_file_tokens=20, max_line_tokens=10)

    assert any("Missing [HLF-v2] or [HLF-v3] header" in error for error in errors)
    assert any("Missing Ω terminator" in error for error in errors)
    assert any("per-line token budget" in error for error in errors)


def test_hlf_token_lint_discovers_files_in_directory(tmp_path: Path) -> None:
    module = _load_script_module("hlf_token_lint")
    fixture = tmp_path / "sample.hlf"
    fixture.write_text("[HLF-v3]\nΔ [INTENT] goal=\"ok\"\nΩ\n", encoding="utf-8")

    discovered = module.discover_hlf_files([str(tmp_path)])
    assert discovered == [fixture]