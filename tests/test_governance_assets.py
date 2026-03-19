import json
import tomllib
from pathlib import Path


def test_dictionary_json_present_and_parseable() -> None:
    path = Path(__file__).resolve().parent.parent / "governance" / "templates" / "dictionary.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["version"] == "0.4.0"
    assert "glyphs" in data
    assert "tags" in data
    assert any(tag["name"] == "INTENT" for tag in data["tags"])


def test_module_import_rules_present() -> None:
    path = Path(__file__).resolve().parent.parent / "governance" / "module_import_rules.yaml"
    text = path.read_text(encoding="utf-8")

    assert 'id: "M-001"' in text
    assert 'id: "M-002"' in text
    assert "DROP_AND_QUARANTINE" in text


def test_governance_package_is_shipped_in_wheel_config() -> None:
    root = Path(__file__).resolve().parent.parent
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))

    packages = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert "governance" in packages
    assert (root / "governance" / "__init__.py").exists()


def test_server_manifest_declares_operator_responsibilities() -> None:
    root = Path(__file__).resolve().parent.parent
    data = json.loads((root / "server.json").read_text(encoding="utf-8"))

    responsibilities = data["_meta"]["com.grumpified.hlf/ethics"]["operator_responsibilities"]
    assert any("system security" in item for item in responsibilities)
    assert any("local and regional" in item for item in responsibilities)
