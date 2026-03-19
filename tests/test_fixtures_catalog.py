from pathlib import Path

from hlf_mcp.hlf.compiler import HLFCompiler


def test_all_shipped_fixtures_compile() -> None:
    compiler = HLFCompiler()
    fixtures_dir = Path(__file__).resolve().parent.parent / "fixtures"
    fixture_paths = sorted(fixtures_dir.glob("*.hlf"))

    assert len(fixture_paths) >= 11

    for fixture_path in fixture_paths:
        source = fixture_path.read_text(encoding="utf-8")
        result = compiler.compile(source)
        assert result["ast"]["kind"] == "program", fixture_path.name
        assert result["gas_estimate"] > 0, fixture_path.name
