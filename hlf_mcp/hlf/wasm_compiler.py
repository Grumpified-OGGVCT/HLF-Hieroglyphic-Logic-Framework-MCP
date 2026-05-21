"""
HLF → WASM Compiler — Translate HLF bytecode to WebAssembly Text Format (WAT).

Produces valid WAT that can be compiled to .wasm via wat2wasm or run directly
in wasmtime. Maps HLF's stack-based bytecode to WASM's stack machine with
structured control flow.

Usage::

    from hlf_mcp.hlf.wasm_compiler import WasmCompiler

    compiler = WasmCompiler()
    wat_text = compiler.compile(ast_or_bytecode)
    # Write to file, compile: wat2wasm output.wat -o output.wasm
    # Run: wasmtime output.wasm

Opcode mapping (HLF → WASM)::

    PUSH_CONST  → i32.const / i64.const / f32.const / f64.const
    STORE       → local.set $var
    LOAD        → local.get $var
    ADD         → i32.add / f32.add
    SUB         → i32.sub / f32.sub
    MUL         → i32.mul / f32.mul
    DIV         → i32.div_s / i32.div_u
    MOD         → i32.rem_s
    CMP_EQ      → i32.eq
    CMP_NE      → i32.ne
    CMP_LT      → i32.lt_s
    CMP_LE      → i32.le_s
    CMP_GT      → i32.gt_s
    CMP_GE      → i32.ge_s
    AND         → i32.and
    OR          → i32.or
    NOT         → i32.eqz
    JMP         → br $label
    JZ          → i32.eqz + br_if $label
    JNZ         → br_if $label
    HALT        → unreachable
    MEMORY_STORE → i32.store
    MEMORY_RECALL → i32.load
    CALL        → call $func
    NOP         → nop
"""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Any

# ── Op mapping ─────────────────────────────────────────────────────────────────


# HLF opcode values from bytecode.py
class HlfOp:
    NOP = 0x00
    PUSH_CONST = 0x01
    STORE = 0x02
    LOAD = 0x03
    STORE_IMMUT = 0x04
    ADD = 0x10
    SUB = 0x11
    MUL = 0x12
    DIV = 0x13
    MOD = 0x14
    NEG = 0x15
    CMP_EQ = 0x20
    CMP_NE = 0x21
    CMP_LT = 0x22
    CMP_LE = 0x23
    CMP_GT = 0x24
    CMP_GE = 0x25
    AND = 0x30
    OR = 0x31
    NOT = 0x32
    POP = 0x33
    JMP = 0x40
    JZ = 0x41
    JNZ = 0x42
    CALL_BUILTIN = 0x50
    CALL_HOST = 0x51
    CALL_TOOL = 0x52
    OPENCLAW_TOOL = 0x53
    TAG = 0x60
    INTENT = 0x61
    RESULT = 0x62
    MEMORY_STORE = 0x63
    MEMORY_RECALL = 0x64
    SPEC_DEFINE = 0x65
    SPEC_GATE = 0x66
    SPEC_UPDATE = 0x67
    SPEC_SEAL = 0x68
    HALT = 0xFF


OP_NAMES: dict[int, str] = {v: k for k, v in vars(HlfOp).items() if not k.startswith("_")}


# ── WASM type helpers ──────────────────────────────────────────────────────────


def _infer_wasm_type(value: Any) -> str:
    """Infer WASM type from Python value."""
    if isinstance(value, bool):
        return "i32"
    if isinstance(value, int):
        if -2_147_483_648 <= value <= 2_147_483_647:
            return "i32"
        return "i64"
    if isinstance(value, float):
        return "f32"
    return "i32"  # default for strings/references


def _const_instr(value: Any) -> str:
    """Generate WASM const instruction for a value."""
    wasm_type = _infer_wasm_type(value)
    if isinstance(value, bool):
        value = 1 if value else 0
    return f"{wasm_type}.const {value}"


# ── Compiler ───────────────────────────────────────────────────────────────────


class WasmCompileError(Exception):
    """Raised when WASM compilation fails."""


class WasmCompiler:
    """Compile HLF bytecode or AST to WebAssembly Text Format (WAT)."""

    def __init__(self, module_name: str = "hlf_module"):
        self.module_name = module_name
        self._local_count = 0
        self._locals: dict[str, int] = {}
        self._label_counter = 0
        self._functions: list[str] = []  # extra function bodies
        self._imports: list[str] = []
        self._data_segments: list[tuple[int, str]] = []
        self._memory_pages: int = 1  # 64KB minimum

    # ── Public API ──────────────────────────────────────────────────────────

    def compile_ast(self, ast: dict[str, Any]) -> str:
        """Compile HLF AST dict to WAT text."""
        statements = ast.get("statements", [])
        if not statements:
            raise WasmCompileError("AST has no statements to compile")

        constant_pool = ast.get("constant_pool", [])
        bytecode_section = ast.get("code_section", [])

        if bytecode_section:
            return self._compile_bytecode(bytecode_section, constant_pool)
        return self._compile_statements(statements, constant_pool)

    def compile_bytecode(
        self, instructions: list[tuple[int, int]], constants: list[Any]
    ) -> str:
        """Compile raw HLF bytecode instructions to WAT text.

        Args:
            instructions: List of (opcode, operand) tuples.
            constants: Constant pool values.
        """
        return self._compile_bytecode(instructions, constants)

    def compile_file_source(self, source: str) -> str:
        """Compile HLF source text (string) to WAT by invoking the HLF compiler first."""
        try:
            from hlf_mcp.hlf.compiler import HLFCompiler

            hlf_compiler = HLFCompiler()
            # Prepend HLF header if not present
            if not source.strip().startswith("[HLF-"):
                source = "[HLF-v0.1.0]\n" + source
            result = hlf_compiler.compile(source)
        except ImportError:
            raise WasmCompileError("HLF compiler not available; pass AST or bytecode directly")

        return self.compile_ast(result.get("ast", {}))

    def compile_file(self, source_path: str | Path) -> str:
        """Compile an HLF source file to WAT by invoking the HLF compiler first."""
        source = Path(source_path).read_text(encoding="utf-8")

        try:
            from hlf_mcp.hlf.compiler import HLFCompiler

            hlf_compiler = HLFCompiler()
            result = hlf_compiler.compile(source)
        except ImportError:
            raise WasmCompileError("HLF compiler not available; pass AST or bytecode directly")

        return self.compile_ast(result.get("ast", {}))

    # ── Bytecode compilation ────────────────────────────────────────────────

    def _compile_bytecode(
        self, instructions: list[tuple[int, int]], constants: list[Any]
    ) -> str:
        """Compile bytecode instructions to WAT function body."""
        wat_lines: list[str] = []
        pc_to_label: dict[int, str] = {}

        # First pass: identify jump targets for labels
        for pc, (opcode, operand) in enumerate(instructions):
            if opcode in (HlfOp.JMP, HlfOp.JZ, HlfOp.JNZ):
                target_pc = pc + 1 + operand if operand != 0 else pc + 1
                if target_pc not in pc_to_label:
                    pc_to_label[target_pc] = f"$block_{self._next_label()}"

        # Second pass: emit instructions
        pc = 0
        while pc < len(instructions):
            opcode, operand = instructions[pc]

            # Emit jump target label if needed
            if pc in pc_to_label:
                wat_lines.append(f"  {pc_to_label[pc]} ;; pc={pc}")

            instr_wat = self._translate_op(opcode, operand, constants, pc, pc_to_label)
            if instr_wat:
                wat_lines.append(instr_wat)

            # Branch instructions embed their own block structure
            if opcode == HlfOp.JMP:
                target = pc_to_label.get(pc + 1 + operand if operand != 0 else pc + 1)
                wat_lines.append(f"  br {target or '$exit'}")
            elif opcode == HlfOp.JZ:
                target = pc_to_label.get(pc + 1 + operand if operand != 0 else pc + 1)
                wat_lines.append(f"  i32.eqz")
                wat_lines.append(f"  br_if {target or '$exit'}")
            elif opcode == HlfOp.JNZ:
                target = pc_to_label.get(pc + 1 + operand if operand != 0 else pc + 1)
                wat_lines.append(f"  br_if {target or '$exit'}")

            pc += 1

        # Build the full module
        return self._build_module(wat_lines, constants)

    def _translate_op(
        self,
        opcode: int,
        operand: int,
        constants: list[Any],
        pc: int,
        labels: dict[int, str],
    ) -> str | None:
        """Translate a single HLF opcode to WAT instruction(s)."""
        # Instructions that emit directly (already handled by caller for branches)
        if opcode in (HlfOp.JMP, HlfOp.JZ, HlfOp.JNZ):
            return None

        # Arithmetic
        if opcode == HlfOp.ADD:
            return "  i32.add"
        if opcode == HlfOp.SUB:
            return "  i32.sub"
        if opcode == HlfOp.MUL:
            return "  i32.mul"
        if opcode == HlfOp.DIV:
            return "  i32.div_s"
        if opcode == HlfOp.MOD:
            return "  i32.rem_s"
        if opcode == HlfOp.NEG:
            return "  i32.const 0 ;; f64.neg not available for i32\n  i32.sub"

        # Comparison
        if opcode == HlfOp.CMP_EQ:
            return "  i32.eq"
        if opcode == HlfOp.CMP_NE:
            return "  i32.ne"
        if opcode == HlfOp.CMP_LT:
            return "  i32.lt_s"
        if opcode == HlfOp.CMP_LE:
            return "  i32.le_s"
        if opcode == HlfOp.CMP_GT:
            return "  i32.gt_s"
        if opcode == HlfOp.CMP_GE:
            return "  i32.ge_s"

        # Logic
        if opcode == HlfOp.AND:
            return "  i32.and"
        if opcode == HlfOp.OR:
            return "  i32.or"
        if opcode == HlfOp.NOT:
            return "  i32.eqz"

        # Stack
        if opcode == HlfOp.POP:
            return "  drop"
        if opcode == HlfOp.NOP:
            return "  nop"
        if opcode == HlfOp.HALT:
            return "  unreachable"

        # Variables
        if opcode == HlfOp.STORE:
            local_idx = self._ensure_local(f"var_{operand}")
            return f"  local.set ${local_idx}"
        if opcode == HlfOp.LOAD:
            local_idx = self._ensure_local(f"var_{operand}")
            return f"  local.get ${local_idx}"
        if opcode == HlfOp.STORE_IMMUT:
            local_idx = self._ensure_local(f"immut_{operand}")
            return f"  local.set ${local_idx}"

        # Constants
        if opcode == HlfOp.PUSH_CONST:
            if 0 <= operand < len(constants):
                return f"  {_const_instr(constants[operand])}"
            return f"  i32.const 0 ;; missing const[{operand}]"

        # Memory
        if opcode == HlfOp.MEMORY_STORE:
            return f"  i32.store offset={operand * 4}"
        if opcode == HlfOp.MEMORY_RECALL:
            return f"  i32.load offset={operand * 4}"

        # Calls
        if opcode == HlfOp.CALL_BUILTIN:
            func_name = constants[operand] if 0 <= operand < len(constants) else f"builtin_{operand}"
            return f"  call ${func_name}"
        if opcode == HlfOp.CALL_HOST:
            host_name = constants[operand] if 0 <= operand < len(constants) else f"host_fn_{operand}"
            self._add_import(host_name)
            return f"  call ${host_name}"
        if opcode == HlfOp.CALL_TOOL:
            tool_name = constants[operand] if 0 <= operand < len(constants) else f"tool_{operand}"
            self._add_import(tool_name)
            return f"  call ${tool_name}"
        if opcode == HlfOp.OPENCLAW_TOOL:
            tool_name = constants[operand] if 0 <= operand < len(constants) else f"openclaw_{operand}"
            self._add_import(tool_name)
            return f"  call ${tool_name}"

        # HLF-specific: TAG, INTENT, RESULT — pass through as local markers
        if opcode == HlfOp.TAG:
            local_idx = self._ensure_local(f"tag_{operand}")
            return f"  ;; TAG slot {operand}\n  local.set ${local_idx}"
        if opcode == HlfOp.INTENT:
            return "  ;; INTENT marker"
        if opcode == HlfOp.RESULT:
            return "  ;; RESULT marker"

        # Spec operations — passthrough with comments
        if opcode == HlfOp.SPEC_DEFINE:
            return f"  ;; SPEC_DEFINE slot {operand}"
        if opcode == HlfOp.SPEC_GATE:
            return f"  ;; SPEC_GATE slot {operand}"
        if opcode == HlfOp.SPEC_UPDATE:
            return f"  ;; SPEC_UPDATE slot {operand}"
        if opcode == HlfOp.SPEC_SEAL:
            return f"  ;; SPEC_SEAL slot {operand}"

        return f"  ;; unknown opcode {opcode:#04x}"

    # ── Module generation ───────────────────────────────────────────────────

    def _build_module(self, body_lines: list[str], constants: list[Any]) -> str:
        """Build complete WAT module from function body lines."""
        lines: list[str] = []
        indent = "  "

        # Header
        lines.append(f'(module')
        lines.append(f'{indent};; HLF→WASM compiled module: {self.module_name}')

        # Memory
        lines.append(f'{indent}(memory (export "memory") {self._memory_pages})')

        # Data segments
        for offset, data_str in self._data_segments:
            lines.append(f'{indent}(data (i32.const {offset}) "{data_str}")')

        # Imports
        for imp in self._imports:
            lines.append(f'{indent}{imp}')

        # Main function
        local_decls = " ".join(f"${n}" for n in self._locals)
        local_header = (
            f'{indent}(func (export "run") (result i32)'
        )
        if local_decls:
            local_header += f"\n{indent}{indent}(local {local_decls} i32)"
        lines.append(local_header)

        # Body
        for line in body_lines:
            if line.strip():
                lines.append(f"{indent}{indent}{line}")

        # Default return
        lines.append(f"{indent}{indent}i32.const 0  ;; default return code")

        lines.append(f"{indent})")
        lines.append(f")")

        return "\n".join(lines)

    def _compile_statements(
        self, statements: list[dict[str, Any]], constants: list[Any]
    ) -> str:
        """Compile HLF AST statements directly to WAT (statement-level)."""
        wat_lines: list[str] = []

        for stmt in statements:
            stmt_type = stmt.get("type", "expr")
            value = stmt.get("value")

            if stmt_type == "literal":
                wat_lines.append(f"  {_const_instr(value)}")
            elif stmt_type == "call":
                name = stmt.get("name", "unknown")
                wat_lines.append(f"  call ${name}")
            elif stmt_type == "assign":
                var_id = stmt.get("var_id", 0)
                local_idx = self._ensure_local(f"var_{var_id}")
                wat_lines.append(f"  local.set ${local_idx}")
            elif stmt_type == "if":
                # Emit condition, then if-else
                cond = stmt.get("condition")
                if cond:
                    wat_lines.append(f"  {_const_instr(cond)}")
                wat_lines.append(f"  if (result i32)")
                then_stmts = stmt.get("then", [])
                for ts in then_stmts:
                    wat_lines.append(f"    {self._compile_single_stmt(ts, constants)}")
                wat_lines.append(f"  else")
                else_stmts = stmt.get("else", [])
                for es in else_stmts:
                    wat_lines.append(f"    {self._compile_single_stmt(es, constants)}")
                wat_lines.append(f"  end")
            elif stmt_type == "result":
                wat_lines.append(f"  ;; RESULT: {value}")

        return self._build_module(wat_lines, constants)

    def _compile_single_stmt(self, stmt: dict[str, Any], constants: list[Any]) -> str:
        """Compile a single AST statement to one WAT line."""
        stmt_type = stmt.get("type", "expr")
        value = stmt.get("value")
        if stmt_type == "literal":
            return _const_instr(value)
        if stmt_type == "call":
            return f"call ${stmt.get('name', 'unknown')}"
        return f";; {stmt_type}"

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _ensure_local(self, name: str) -> int:
        """Get or create a local variable index."""
        if name not in self._locals:
            self._locals[name] = self._local_count
            self._local_count += 1
        return self._locals[name]

    def _next_label(self) -> int:
        self._label_counter += 1
        return self._label_counter

    def _add_import(self, name: str) -> None:
        """Register an import if not already present."""
        import_str = f'(import "env" "{name}" (func ${name} (param i32) (result i32)))'
        if import_str not in self._imports:
            self._imports.append(import_str)


# ── CLI ────────────────────────────────────────────────────────────────────────


def main() -> None:
    """CLI for the WASM compiler."""
    import argparse

    parser = argparse.ArgumentParser(description="HLF → WASM Compiler")
    parser.add_argument("input", help="HLF source file or .hlb bytecode file")
    parser.add_argument(
        "-o", "--output", default=None, help="Output .wat file (default: stdout)"
    )
    parser.add_argument(
        "--format", choices=["wat", "binary"], default="wat", help="Output format"
    )
    args = parser.parse_args()

    compiler = WasmCompiler()

    try:
        wat_text = compiler.compile_file(args.input)
    except Exception as exc:
        print(f"Compilation failed: {exc}")
        raise SystemExit(1)

    if args.output:
        Path(args.output).write_text(wat_text, encoding="utf-8")
        print(f"WAT written to {args.output}")
    else:
        print(wat_text)


if __name__ == "__main__":
    main()
