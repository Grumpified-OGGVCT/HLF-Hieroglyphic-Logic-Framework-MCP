# HLF Reference

Packaged language and runtime reference for this repository.

This document is intentionally narrower than the upstream manifesto-style reference. It describes the HLF surfaces that are actually present in this standalone repo today and points to the more specific references that already exist here.

## What HLF Is In This Repo

HLF is a deterministic orchestration language and protocol built around:

- hieroglyphic and ASCII-authored source forms
- a packaged compiler in `hlf_mcp/hlf/compiler.py`
- a bytecode VM in `hlf_mcp/hlf/runtime.py`
- tooling for formatting, linting, testing, translation, and decompilation
- FastMCP exposure through `hlf_mcp/server.py`

Minimal example:

```hlf
[HLF-v3]
Δ [INTENT] action="audit" target="/security/seccomp.json"
Ж [CONSTRAINT] mode="ro"
RESULT 0 "ok"
Ω
```

## Core Surfaces

| Surface | Packaged Location | Purpose |
| --- | --- | --- |
| Compiler | `hlf_mcp/hlf/compiler.py` | Parse, normalize, validate, and compile HLF source |
| Formatter | `hlf_mcp/hlf/formatter.py` | Canonicalize source formatting |
| Linter | `hlf_mcp/hlf/linter.py` | Static analysis and policy checks |
| Translator | `hlf_mcp/hlf/translator.py` | English-to-HLF and HLF-to-English helpers |
| Bytecode | `hlf_mcp/hlf/bytecode.py` | Encode, decode, and disassemble HLF bytecode |
| Runtime | `hlf_mcp/hlf/runtime.py` | Execute bytecode with gas metering |
| Capsules | `hlf_mcp/hlf/capsules.py` | Tier-aware AST validation and execution constraints |
| Tool Dispatch | `hlf_mcp/hlf/tool_dispatch.py` | Host/tool registry and dispatch safety |
| MCP Server | `hlf_mcp/server.py` | Expose packaged HLF capabilities over MCP |

## Language Shape

Current packaged authoring revolves around these concepts:

- required version header such as `[HLF-v3]`
- required terminator `Ω`
- glyph-prefixed statements such as `Δ`, `Ж`, `⌘`, and `⨝`
- keyword forms such as `SET`, `ASSIGN`, `IF`, `FUNCTION`, `CALL`, `RESULT`, and `LOG`
- structured tags like `INTENT`, `CONSTRAINT`, `EXPECT`, `RESULT`, `MEMORY`, and `RECALL`

For the precise grammar, use `docs/HLF_GRAMMAR_REFERENCE.md`.

## Execution Model

The packaged execution path is:

1. Author HLF source.
2. Compile source into AST with `HLFCompiler`.
3. Encode AST into bytecode with `HLFBytecode`.
4. Run bytecode in `HLFRuntime` with a gas budget.
5. Optionally decompile or translate the result for audit and review.

The runtime is deterministic relative to the source, compiler rules, bytecode encoder, and provided inputs.

## Governance And Safety

The standalone repo currently anchors governance in:

- `governance/align_rules.json`
- `governance/bytecode_spec.yaml`
- `governance/host_functions.json`
- `governance/tag_i18n.yaml`
- `governance/MANIFEST.sha256`

The packaged server checks the governance manifest at startup. Higher-trust surfaces also flow through capsules, host-function policy, and lifecycle/state-machine checks rather than relying on prompt text alone.

## Memory And Lifecycle

Two adjacent packaged subsystems matter for the broader HLF story in this repo:

- Infinite RAG memory at `hlf_mcp/rag/memory.py`
- Instinct lifecycle at `hlf_mcp/instinct/lifecycle.py`

The lifecycle system is documented separately in `docs/INSTINCT_REFERENCE.md`.

## Tooling Entry Points

The packaged CLI surface is:

- `hlf-mcp`
- `hlfc`
- `hlffmt`
- `hlflint`
- `hlfrun`
- `hlfpm`
- `hlfsh`
- `hlflsp`
- `hlftest`

Use `docs/cli-tools.md` for the concrete flags and usage patterns.

## Recommended Reading Order

1. Start here for the repo-level picture.
2. Read `docs/HLF_GRAMMAR_REFERENCE.md` for syntax.
3. Read `docs/HLF_TAG_REFERENCE.md` for tag inventory.
4. Read `docs/stdlib.md` and `docs/HLF_STDLIB_REFERENCE.md` for the Python-backed stdlib surface.
5. Read `docs/INSTINCT_REFERENCE.md` for the lifecycle/state-machine layer.
6. Use `docs/cli-tools.md` when working from the command line.
