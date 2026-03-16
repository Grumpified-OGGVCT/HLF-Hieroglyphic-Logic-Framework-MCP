import json
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
    assert 'DROP_AND_QUARANTINE' in text