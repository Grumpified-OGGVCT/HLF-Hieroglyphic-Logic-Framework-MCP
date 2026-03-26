from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _persona_matrix_path() -> Path:
    return _repo_root() / "docs" / "HLF_PERSONA_OWNERSHIP_MATRIX.json"


def _agent_registry_path() -> Path:
    return _repo_root() / "hlf_source" / "config" / "agent_registry.json"


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


@lru_cache(maxsize=1)
def load_persona_runtime_catalog() -> dict[str, dict[str, Any]]:
    matrix = _load_json_file(_persona_matrix_path())
    registry = _load_json_file(_agent_registry_path())

    matrix_personas = matrix.get("personas") if isinstance(matrix.get("personas"), dict) else {}
    registry_personas = (
        registry.get("hat_agents") if isinstance(registry.get("hat_agents"), dict) else {}
    )
    lane = str(matrix.get("lane") or "bridge-true")

    catalog: dict[str, dict[str, Any]] = {}
    known_persona_names = {
        str(name).strip().lower()
        for name in list(matrix_personas.keys()) + list(registry_personas.keys())
        if isinstance(name, str) and name.strip()
    }

    for normalized_name in sorted(known_persona_names):
        matrix_details = (
            matrix_personas.get(normalized_name)
            if isinstance(matrix_personas.get(normalized_name), dict)
            else {}
        )
        registry_details = (
            registry_personas.get(normalized_name)
            if isinstance(registry_personas.get(normalized_name), dict)
            else {}
        )

        catalog[normalized_name] = {
            "persona": normalized_name,
            "lane": lane,
            "runtime_authority": False,
            "internal_role": str(matrix_details.get("internal_role") or ""),
            "maintainer_mode": str(
                matrix_details.get("maintainer_mode") or "preserved_context_only"
            ),
            "hat": str(registry_details.get("hat") or ""),
            "role": str(registry_details.get("role") or ""),
            "upstream_source": str(
                matrix_details.get("upstream_source") or "hlf_source/config/agent_registry.json"
            ),
            "cross_awareness": [
                str(value)
                for value in registry_details.get("cross_awareness") or []
                if isinstance(value, str) and value
            ],
        }

    return catalog


def resolve_persona_runtime_metadata(role_value: Any) -> dict[str, Any] | None:
    if not isinstance(role_value, str) or not role_value.strip():
        return None
    normalized_role = role_value.strip().lower()
    entry = load_persona_runtime_catalog().get(normalized_role)
    if entry is None:
        return None
    return {
        "persona": entry["persona"],
        "lane": entry["lane"],
        "runtime_authority": entry["runtime_authority"],
        "internal_role": entry["internal_role"],
        "maintainer_mode": entry["maintainer_mode"],
        "hat": entry["hat"],
        "role": entry["role"],
        "upstream_source": entry["upstream_source"],
        "cross_awareness": list(entry["cross_awareness"]),
    }