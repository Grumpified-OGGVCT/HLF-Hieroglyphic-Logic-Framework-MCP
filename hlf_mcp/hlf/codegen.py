"""Programmatic builder for packaged HLF v3 source."""

from __future__ import annotations

from typing import Any

from hlf_mcp.hlf.compiler import HLFCompiler


class HLFCodeGenerator:
    """Small builder API for generating parser-compatible HLF programs."""

    def __init__(self, version: str = "HLF-v3") -> None:
        self._version = version
        self._lines: list[str] = []

    def set(self, name: str, value: Any) -> HLFCodeGenerator:
        self._lines.append(f"SET {name} = {_format_value(value)}")
        return self

    def assign(self, name: str, value: Any) -> HLFCodeGenerator:
        self._lines.append(f"ASSIGN {name} = {_format_value(value)}")
        return self

    def intent(self, goal: str, target: str | None = None, **fields: Any) -> HLFCodeGenerator:
        parts = ["Δ [INTENT]", f"goal={_format_value(goal)}"]
        if target is not None:
            parts.append(f"target={_format_value(target)}")
        parts.extend(_format_fields(fields))
        self._lines.append(" ".join(parts))
        return self

    def constraint(self, **fields: Any) -> HLFCodeGenerator:
        parts = ["Ж [CONSTRAINT]"] + _format_fields(fields)
        self._lines.append(" ".join(parts))
        return self

    def expect(self, **fields: Any) -> HLFCodeGenerator:
        parts = ["Ж [EXPECT]"] + _format_fields(fields)
        self._lines.append(" ".join(parts))
        return self

    def delegate(self, agent: str, goal: str, **fields: Any) -> HLFCodeGenerator:
        parts = ["⌘ [DELEGATE]", f"agent={_format_value(agent)}", f"goal={_format_value(goal)}"]
        parts.extend(_format_fields(fields))
        self._lines.append(" ".join(parts))
        return self

    def vote(self, **fields: Any) -> HLFCodeGenerator:
        parts = ["⨝ [VOTE]"] + _format_fields(fields)
        self._lines.append(" ".join(parts))
        return self

    def log(self, value: Any) -> HLFCodeGenerator:
        self._lines.append(f"LOG {_format_value(value)}")
        return self

    def memory(self, slot: str, value: Any) -> HLFCodeGenerator:
        self._lines.append(f"MEMORY [{slot}] value={_format_value(value)}")
        return self

    def recall(self, slot: str) -> HLFCodeGenerator:
        self._lines.append(f"RECALL [{slot}]")
        return self

    def import_module(self, path: str) -> HLFCodeGenerator:
        self._lines.append(f"IMPORT {_format_value(path)}")
        return self

    def result(self, code: int = 0, message: str = "ok") -> HLFCodeGenerator:
        self._lines.append(f"RESULT {code} {_format_value(message)}")
        return self

    def raw(self, line: str) -> HLFCodeGenerator:
        self._lines.append(line)
        return self

    def build(self) -> str:
        return "\n".join([f"[{self._version}]", *self._lines, "Ω", ""])

    def build_and_compile(self) -> dict[str, Any]:
        compiler = HLFCompiler()
        return compiler.compile(self.build())

    def __repr__(self) -> str:
        return f"HLFCodeGenerator(version={self._version!r}, statements={len(self._lines)})"


def _format_fields(fields: dict[str, Any]) -> list[str]:
    return [f"{key}={_format_value(value)}" for key, value in fields.items()]


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text.startswith("$"):
        return text
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


__all__ = ["HLFCodeGenerator"]
