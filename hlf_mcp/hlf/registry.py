"""
HLF Host Function Registry — JSON-backed registry with tier/gas/backend dispatch.

Loads from governance/host_functions.json at init. Falls back to built-in
defaults if JSON is not found (Docker/test environments).
"""

from __future__ import annotations
import dataclasses
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

@dataclasses.dataclass
class HostFunction:
    name: str
    args: list[dict[str, str]]  # [{"name": "path", "type": "path"}]
    returns: str
    tiers: list[str]
    gas: int
    backend: str
    sensitive: bool = False
    binary_path: str | None = None
    binary_sha256: str | None = None

    def validate_args(self, call_args: list[Any]) -> None:
        if len(call_args) != len(self.args):
            raise ValueError(f"{self.name}: expected {len(self.args)} args, got {len(call_args)}")

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

class HostFunctionRegistry:
    """Registry of available host functions."""

    def __init__(self, json_path: str | None = None):
        self._functions: dict[str, HostFunction] = {}
        self._load(json_path)

    def _load(self, json_path: str | None) -> None:
        path = None
        if json_path:
            path = Path(json_path)
        else:
            # Try governance dir relative to package
            candidates = [
                Path(__file__).parent.parent.parent / "governance" / "host_functions.json",
                Path("governance") / "host_functions.json",
            ]
            for c in candidates:
                if c.exists():
                    path = c
                    break

        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for fd in data.get("functions", []):
                    fn = HostFunction(
                        name=fd["name"],
                        args=fd.get("args", []),
                        returns=fd.get("returns", "any"),
                        tiers=fd.get("tier", ["hearth", "forge", "sovereign"]),
                        gas=fd.get("gas", 1),
                        backend=fd.get("backend", "builtin"),
                        sensitive=fd.get("sensitive", False),
                        binary_path=fd.get("binary_path"),
                        binary_sha256=fd.get("binary_sha256"),
                    )
                    self._functions[fn.name] = fn
                logger.debug("Loaded %d host functions from %s", len(self._functions), path)
                return
            except Exception as exc:
                logger.warning("Failed to load host_functions.json: %s", exc)

        # Built-in defaults
        self._load_defaults()

    def _load_defaults(self) -> None:
        defaults = [
            ("READ",       [{"name":"path","type":"path"}],        "string", ["hearth","forge","sovereign"], 1,  "dapr_file_read",  False),
            ("WRITE",      [{"name":"path","type":"path"},{"name":"data","type":"string"}], "bool", ["hearth","forge","sovereign"], 2, "dapr_file_write", False),
            ("HTTP_GET",   [{"name":"url","type":"string"}],        "string", ["forge","sovereign"],          3,  "dapr_http_proxy", False),
            ("HTTP_POST",  [{"name":"url","type":"string"},{"name":"body","type":"string"}], "string", ["forge","sovereign"], 5, "dapr_http_proxy", False),
            ("SPAWN",      [{"name":"image","type":"string"},{"name":"env","type":"map"}], "string", ["forge","sovereign"], 5, "docker_orchestrator", False),
            ("SLEEP",      [{"name":"ms","type":"int"}],            "bool",   ["hearth","forge","sovereign"], 0,  "builtin",         False),
            ("WEB_SEARCH", [{"name":"query","type":"string"}],      "string", ["forge","sovereign"],          5,  "dapr_http_proxy", True),
            ("analyze",    [{"name":"target","type":"string"}],     "string", ["hearth","forge","sovereign"], 2,  "builtin",         False),
            ("hash_sha256",[{"name":"data","type":"string"}],       "string", ["hearth","forge","sovereign"], 2,  "builtin",         False),
            ("log_emit",   [{"name":"msg","type":"string"}],        "bool",   ["hearth","forge","sovereign"], 1,  "builtin",         False),
            ("memory_store",[{"name":"key","type":"string"},{"name":"value","type":"any"}], "bool", ["hearth","forge","sovereign"], 5, "builtin", False),
            ("memory_recall",[{"name":"key","type":"string"}],      "any",    ["hearth","forge","sovereign"], 5,  "builtin",         False),
            ("get_tier",   [],                                       "string", ["hearth","forge","sovereign"], 1,  "builtin",         False),
            ("get_vram",   [],                                       "string", ["hearth","forge","sovereign"], 1,  "builtin",         False),
            ("vote",       [{"name":"config","type":"string"}],     "bool",   ["hearth","forge","sovereign"], 1,  "builtin",         False),
            ("delegate",   [{"name":"agent","type":"string"},{"name":"goal","type":"string"}], "any", ["forge","sovereign"], 3, "builtin", False),
            ("route",      [{"name":"strategy","type":"string"}],   "any",    ["forge","sovereign"],          2,  "builtin",         False),
        ]
        for row in defaults:
            name, args, returns, tiers, gas, backend, sensitive = row
            self._functions[name] = HostFunction(name=name, args=args, returns=returns,
                tiers=tiers, gas=gas, backend=backend, sensitive=sensitive)

    def get(self, name: str) -> HostFunction | None:
        return self._functions.get(name)

    def call(self, name: str, args: list[Any], tier: str = "hearth") -> dict[str, Any]:
        """Dispatch a host function call (simulated for MCP context)."""
        fn = self._functions.get(name)
        if not fn:
            raise ValueError(f"Unknown host function: {name}")
        if tier not in fn.tiers:
            raise PermissionError(f"Function {name!r} not available in tier {tier!r}")
        fn.validate_args(args)
        # Hash sensitive outputs
        result = {"host_fn": name, "status": "simulated", "tier": tier, "gas": fn.gas}
        if fn.sensitive:
            result["result_hash"] = hashlib.sha256(str(args).encode()).hexdigest()[:16]
        else:
            result["args"] = args[:4]  # Limit for safety
        return result

    def list_all(self) -> list[dict[str, Any]]:
        return [fn.to_dict() for fn in self._functions.values()]

    def list_for_tier(self, tier: str) -> list[dict[str, Any]]:
        return [fn.to_dict() for fn in self._functions.values() if tier in fn.tiers]
