"""Interactive shell for the packaged HLF compiler and linter surfaces."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

from hlf_mcp.hlf.compiler import CompileError, HLFCompiler
from hlf_mcp.hlf import hlf_llm_bridge
from hlf_mcp.hlf.linter import HLFLinter

_COLORS_ENABLED = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(text: str, code: str) -> str:
    if _COLORS_ENABLED:
        return f"\033[{code}m{text}\033[0m"
    return text


def _green(text: str) -> str:
    return _c(text, "32")


def _yellow(text: str) -> str:
    return _c(text, "33")


def _red(text: str) -> str:
    return _c(text, "31")


def _dim(text: str) -> str:
    return _c(text, "2")


def _bold(text: str) -> str:
    return _c(text, "1")


HELP_TEXT = """
HLF Interactive Shell (hlfsh) - Commands:
  :help     Show this help message
  :env      Display current SET bindings
  :gas      Show gas meter status
  :reset    Clear environment and gas meter
  :load F   Load and evaluate a .hlf file
  :ast      Show AST of last evaluation
  :lint     Lint last input
  :model M  Set active LLM model for :gen / :certify
  :models   List available models on the Ollama server
  :gen D    Generate HLF from a natural-language description
  :certify  Run self-test certification across canonical prompts
  :quit     Exit the REPL (also :exit, :q)
""".strip()


def _ensure_program(source: str) -> str:
    stripped = source.strip()
    if not stripped:
        return stripped
    if stripped.startswith("[HLF-v"):
        return stripped
    return f"[HLF-v3]\n{stripped}\nΩ"


def _value_to_string(value: Any) -> str:
    if isinstance(value, dict):
        if value.get("kind") == "value":
            return str(value.get("value", ""))
        if "value" in value:
            return str(value["value"])
    return str(value)


class HLFShell:
    """Interactive HLF shell session."""

    PROMPT = "hlf> "

    # ── Certification prompt bank ──────────────────────────────────────────
    CERTIFY_PROMPTS: list[tuple[str, str]] = [
        ("SET", "Create an HLF program that sets x to 42"),
        ("INTENT", "Create an HLF program declaring an INTENT to complete a task"),
        ("CONSTRAINT", "Define a CONSTRAINT that enforces a boundary condition"),
        ("DELEGATE", "Create a DELEGATE to assign a subtask to an agent"),
        ("RESULT", "Define a RESULT with status ok and message done"),
        ("MEMORY", "Write an HLF program with two sequential SET statements"),
    ]

    def __init__(self, gas_limit: int = 1000, model: str | None = None,
                 ollama_url: str = "http://localhost:11434") -> None:
        self.env: dict[str, Any] = {}
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.last_ast: dict[str, Any] | None = None
        self.last_input: str = ""
        self.history_path = Path.home() / ".hlf_history"
        self.statement_count = 0
        self._compiler = HLFCompiler()
        self._linter = HLFLinter()
        # LLM bridge state
        self._bridge: "hlf_llm_bridge.HLFLLMBridge | None" = None
        self._model: str | None = model
        self._ollama_url: str = ollama_url

    # ── LLM bridge properties ─────────────────────────────────────────────

    @property
    def active_model(self) -> str:
        """Return the currently selected model name (or bridge default)."""
        if self._model:
            return self._model
        return os.environ.get("HLF_DEFAULT_MODEL", "deepseek-v4-pro:cloud")

    @property
    def ollama_url(self) -> str:
        """Return the configured Ollama server URL."""
        return self._ollama_url.rstrip("/")

    @property
    def bridge(self) -> "hlf_llm_bridge.HLFLLMBridge":
        """Lazily create and return the HLF-to-LLM bridge."""
        if self._bridge is None:
            self._bridge = hlf_llm_bridge.HLFLLMBridge(
                model=self._model,
                ollama_url=self._ollama_url,
            )
        return self._bridge

    def eval(self, source: str) -> str:
        self.last_input = source.strip()
        if not self.last_input:
            return ""

        candidate = _ensure_program(self.last_input)
        try:
            compiled = self._compiler.compile(candidate)
        except CompileError as exc:
            return _red(f"Compile error: {exc}")

        ast = compiled["ast"]
        self.last_ast = ast
        gas_cost = compiled["gas_estimate"]
        self.gas_used += gas_cost
        self.statement_count += 1

        lines: list[str] = []
        for node in ast.get("statements", []):
            if not isinstance(node, dict):
                continue
            if node.get("kind") == "set_stmt":
                name = node.get("name", "")
                value = _value_to_string(node.get("value"))
                if name:
                    self.env[name] = value
                    lines.append(_green(f"  {name} = {value}"))
            elif node.get("kind") == "result_stmt":
                message = _value_to_string(node.get("message"))
                code = _value_to_string(node.get("code"))
                lines.append(_green(f"  result[{code}] {message}"))
            elif node.get("kind") == "glyph_stmt" and node.get("tag") == "RESULT":
                args = node.get("arguments", [])
                parts: list[str] = []
                for arg in args:
                    if isinstance(arg, dict) and arg.get("kind") == "kv_arg":
                        parts.append(f"{arg.get('name')}={_value_to_string(arg.get('value'))}")
                if parts:
                    lines.append(_green("  result " + " ".join(parts)))

        remaining = self.gas_limit - self.gas_used
        lines.append(
            _dim(
                f"  gas: {gas_cost} this run ({self.gas_used}/{self.gas_limit} total, {remaining} remaining)"
            )
        )
        if self.gas_used >= self.gas_limit:
            lines.append(_yellow("  gas limit reached - use :reset or raise --gas-limit"))
        return "\n".join(lines)

    def handle_command(self, command: str) -> str | None:
        cmd = command.strip()
        if not cmd.startswith(":"):
            return None

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        # Let the LLM dispatch layer intercept new-style commands
        action_key = action.lstrip(":")
        if self._dispatch_command(action_key, arg):
            return None  # handled by dispatch (prints internally)

        if action == ":help":
            return HELP_TEXT
        if action == ":env":
            if not self.env:
                return _dim("(empty environment)")
            return "\n".join(f"  {key} = {value}" for key, value in sorted(self.env.items()))
        if action == ":gas":
            remaining = self.gas_limit - self.gas_used
            pct = (self.gas_used / self.gas_limit * 100) if self.gas_limit else 0
            return (
                f"  Gas used:      {self.gas_used}\n"
                f"  Gas remaining: {remaining}\n"
                f"  Gas limit:     {self.gas_limit}\n"
                f"  Utilization:   {pct:.1f}%\n"
                f"  Statements:    {self.statement_count}"
            )
        if action == ":reset":
            self.env.clear()
            self.gas_used = 0
            self.last_ast = None
            self.last_input = ""
            self.statement_count = 0
            return _green("Session reset")
        if action == ":load":
            if not arg:
                return _red("Usage: :load <filepath.hlf>")
            path = Path(arg)
            if not path.exists():
                return _red(f"File not found: {path}")
            return self.eval(path.read_text(encoding="utf-8"))
        if action == ":ast":
            if self.last_ast is None:
                return _dim("(no AST - evaluate something first)")
            return json.dumps(self.last_ast, indent=2, ensure_ascii=False)
        if action == ":lint":
            if not self.last_input:
                return _dim("(no input to lint)")
            diagnostics = self._linter.lint(_ensure_program(self.last_input))
            if not diagnostics:
                return _green("No lint issues")
            return "\n".join(f"  {diag['level']}: {diag['message']}" for diag in diagnostics)
        if action in {":quit", ":exit", ":q"}:
            raise SystemExit(0)
        return _red(f"Unknown command: {action}. Type :help for commands.")

    # ── dispatch layer for LLM-aware commands ─────────────────────────────

    def _dispatch_command(self, cmd: str, arg: str) -> bool:
        """Route an HLF shell command to the appropriate handler.

        Returns True if the command was handled (so the REPL should not
        fall through to static commands), False otherwise.
        """
        if cmd in ("gen",):
            asyncio.run(self._cmd_gen(arg))
            return True
        if cmd in ("certify",):
            asyncio.run(self._cmd_certify(arg))
            return True
        if cmd in ("model",):
            self._cmd_model(arg)
            return True
        if cmd in ("models",):
            self._cmd_models()
            return True
        return False

    # ── :model <name> ─────────────────────────────────────────────────────

    def _cmd_model(self, name: str) -> None:
        """Switch the active LLM model."""
        if not name or not name.strip():
            print(_yellow(f"Current model: {self.active_model}"))
            return
        self._model = name.strip()
        # Rebuild bridge so the new model takes effect
        self._bridge = None
        print(_green(f"Switched to '{self.active_model}'"))

    # ── :models ───────────────────────────────────────────────────────────

    def _cmd_models(self) -> None:
        """List available Ollama models."""
        try:
            req = urllib.request.Request(
                f"{self._ollama_url}/api/tags",
                headers={"Accept": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            models = data.get("models", [])
        except Exception:
            # Try CLI fallback
            try:
                result = subprocess.check_output(
                    ["ollama", "list"], timeout=10, text=True,
                )
                lines = result.strip().split("\n")[1:]  # skip header
                models = [{"name": l.split()[0]} for l in lines if l.strip()]
            except Exception:
                print(_red("Cannot reach Ollama — is the server running?"))
                return

        if not models:
            print(_dim("(no models available)"))
            return

        print(_bold("Available models:"))
        for m in sorted(models, key=lambda x: x["name"]):
            marker = _green("  (active)") if m["name"] == self.active_model else ""
            print(f"  {m['name']}{marker}")

    # ── :gen <description> ────────────────────────────────────────────────

    async def _cmd_gen(self, description: str) -> None:
        """Generate HLF from a natural-language description via the LLM bridge."""
        if not description or not description.strip():
            print(_red(f"Usage: :gen <description>  (model: {self.active_model})"))
            return

        bridge = self.bridge
        try:
            result = await bridge.send(description.strip())
        except Exception as exc:
            print(_red(f"LLM call failed: {exc}"))
            return

        model_used = getattr(result, "model_used", self.active_model)
        latency = getattr(result, "latency_s", 0.0)
        raw = getattr(result, "raw_response", "")
        extracted = getattr(result, "extracted", False)
        hlf_output = getattr(result, "hlf_output", raw)

        print(_bold(f"\nGenerated HLF") + _dim(f"  ({model_used}, {latency:.1f}s)"))
        if not extracted:
            print(_dim("\nRaw LLM response:"))
            print(raw[:2000])
            return

        try:
            compiled = self._compiler.compile(hlf_output)
        except CompileError as exc:
            print(_red(f"\n✗ Compile failed: {exc}"))
            return

        ast = compiled["ast"]
        self.last_ast = ast
        self.last_input = hlf_output
        gas_cost = compiled["gas_estimate"]
        self.gas_used += gas_cost
        self.statement_count += 1

        print(_green("✓ Compiled successfully"))
        print(_dim(f"  gas: {gas_cost} this run ({self.gas_used}/{self.gas_limit} total)"))

        # Evaluate statements
        for node in ast.get("statements", []):
            if not isinstance(node, dict):
                continue
            if node.get("kind") == "set_stmt":
                name = node.get("name", "")
                value = _value_to_string(node.get("value"))
                if name:
                    self.env[name] = value
                    print(_green(f"  {name} = {value}"))
            elif node.get("kind") == "result_stmt":
                message = _value_to_string(node.get("message"))
                code = _value_to_string(node.get("code"))
                print(_green(f"  result[{code}] {message}"))

    # ── :certify [filter] ─────────────────────────────────────────────────

    async def _cmd_certify(self, filter_str: str = "") -> None:
        """Run certification self-test across known HLF prompts.

        Each prompt is sent through the bridge; a passing prompt must
        return extractable HLF that compiles cleanly.
        """
        prompts = self.CERTIFY_PROMPTS
        if filter_str and filter_str.strip():
            lower = filter_str.strip().lower()
            prompts = [(l, p) for (l, p) in prompts if lower in p.lower()]
            if not prompts:
                print(_red(f"No certification prompts match '{filter_str.strip()}'"))
                return

        bridge = self.bridge
        total = len(prompts)
        passed = 0
        print(_bold("HLF Certification") + _dim(f" — {total} prompt(s), model: {self.active_model}"))
        print()

        for label, prompt in prompts:
            try:
                result = await bridge.send(prompt)
            except Exception as exc:
                print(_red(f"  [{label}] FAIL (LLM error): {exc}"))
                continue
            hlf_output = getattr(result, "hlf_output", "")
            extracted = getattr(result, "extracted", False)
            if not extracted or not hlf_output.strip():
                print(_red(f"  [{label}] FAIL (no HLF extracted)"))
                continue
            try:
                self._compiler.compile(hlf_output)
            except CompileError as exc:
                print(_red(f"  [{label}] FAIL (compile): {exc}"))
                continue
            passed += 1
            print(_green(f"  [{label}] PASS  {prompt}"))

        print()
        pct = (passed / total * 100) if total else 0
        if pct >= 80:
            rating = "FLUENT"
        elif pct >= 50:
            rating = "PARTIAL"
        else:
            rating = "NOT fluent"
        print(_bold(f"Score: {passed}/{total} ({rating})"))

    def _setup_readline(self) -> None:
        try:
            import readline

            if self.history_path.exists():
                readline.read_history_file(str(self.history_path))
            readline.set_history_length(1000)
        except (ImportError, OSError):
            pass

    def _save_history(self) -> None:
        try:
            import readline

            readline.write_history_file(str(self.history_path))
        except (ImportError, OSError):
            pass

    def run(self) -> None:
        self._setup_readline()
        print(_bold("HLF Interactive Shell") + _dim(f" (gas limit: {self.gas_limit})"))
        print(_dim("Type :help for commands, :quit to exit\n"))
        try:
            while True:
                try:
                    line = input(self.PROMPT)
                except EOFError:
                    print()
                    break

                cmd_result = self.handle_command(line)
                if cmd_result is not None:
                    print(cmd_result)
                    continue

                output = self.eval(line)
                if output:
                    print(output)
        except (KeyboardInterrupt, SystemExit):
            pass
        finally:
            self._save_history()
            print(_dim("\nGoodbye."))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="HLF Interactive Shell")
    parser.add_argument("--gas-limit", type=int, default=1000, help="Gas budget")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    args = parser.parse_args()

    if args.no_color:
        global _COLORS_ENABLED
        _COLORS_ENABLED = False

    HLFShell(gas_limit=args.gas_limit).run()


if __name__ == "__main__":  # pragma: no cover
    main()
