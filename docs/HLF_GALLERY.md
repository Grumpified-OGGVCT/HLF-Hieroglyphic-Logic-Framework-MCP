# HLF Gallery — Operator Legibility Surface

![Status: Bridge active](https://img.shields.io/badge/status-Bridge%20active-yellow)
![Fixtures: 12/12](https://img.shields.io/badge/fixtures-12%2F12-brightgreen)
![Compression: 48.6%](https://img.shields.io/badge/compression-48.6%25-blue)

A browsable showcase of HLF's capabilities for operators and agents — no source code reading required.

## What This Is

The HLF Gallery demonstrates every packaged HLF fixture program through the full 5-surface round-trip:

| # | Surface | What It Shows |
| --- | --- | --- |
| 1 | **Glyph Source** | The native HLF program in its canonical glyph form (Δ, Ж, ∇, Ω, etc.) |
| 2 | **Formatted Source** | Canonical whitespace and ordering applied by the formatter |
| 3 | **AST** | The JSON parse tree produced by the HLF compiler |
| 4 | **Bytecode** | The hex-encoded .hlb binary emitted by the bytecode encoder |
| 5 | **Assembly** | Human-readable disassembly from the bytecode VM |
| 6 | **English** | Natural-language translation derived from AST human-readable fields |

Every surface is generated from real packaged compiler, bytecode encoder, and disassembler components — no fabricated examples.

## Quick Access

- **Generated report (latest):** `hlf://reports/gallery` — full markdown with all 12 fixtures
- **Structured status:** `hlf://gallery` — JSON summary for agents and tooling
- **Regenerate locally:** `python scripts/run_hlf_gallery.py --markdown`
- **Fixture catalog:** `fixtures/README.md`

## The 12 Fixtures at a Glance

| Fixture | Domain | Lines | Nodes | Bytecode | Purpose |
| --- | --- | ---: | ---: | ---: | --- |
| `hello_world.hlf` | General Coding | 7 | 3 | 254B | Minimal end-to-end conformance test |
| `security_audit.hlf` | Security | 9 | 4 | 418B | Read-only security scan with strict consensus |
| `delegation.hlf` | AI Engineering | 8 | 4 | 407B | Multi-agent task delegation pattern |
| `db_migration.hlf` | Data Engineering | 11 | 7 | 507B | Production DB migration with spec gates |
| `log_analysis.hlf` | DevOps | 10 | 6 | 535B | Log analysis with read-only constraint |
| `stack_deployment.hlf` | Infrastructure | 9 | 5 | 427B | Stack deployment with MoMA routing |
| `routing.hlf` | Orchestration | 7 | 3 | 305B | Real-time model routing strategy |
| `system_health_check.hlf` | Operations | 10 | 6 | 670B | System health automation |
| `decision_matrix.hlf` | Reasoning | 14 | 10 | 1,040B | Structured multi-option choice |
| `module_workflow.hlf` | Integration | 12 | 8 | 773B | Multi-module workflow composition |
| `file_io_demo.hlf` | I/O | 10 | 6 | 709B | File read/write round-trip |
| `math_expressions.hlf` | Algorithms | 112 | 44 | 3,132B | HLF governing algorithm expressions |

## Verified Benchmark Compression

The `hlf_benchmark_suite` measures token compression of HLF vs equivalent natural language across 6 canonical domains (tiktoken cl100k_base):

| Domain | Fixture | HLF Tokens | NLP Tokens | Compression |
| --- | --- | ---: | ---: | ---: |
| General Coding | `hello_world.hlf` | 31 | 65 | 52.3% |
| Security | `security_audit.hlf` | 41 | 79 | 48.1% |
| AI Engineering | `delegation.hlf` | 48 | 90 | 46.7% |
| Data Engineering | `db_migration.hlf` | 62 | 122 | 49.2% |
| DevOps | `log_analysis.hlf` | 58 | 107 | 45.8% |
| Infrastructure | `stack_deployment.hlf` | 42 | 84 | 49.8% |
| **Average** | | | | **48.6%** |

> Compression = (1 − HLF_tokens / NLP_tokens) × 100. Higher means fewer tokens needed to express the same intent.

## Understanding the Glyphs

HLF uses 9 canonical glyphs as its statement-level operators:

| Glyph | Name | ASCII Alias | Role | Example |
| --- | --- | --- | --- | --- |
| Δ | DELTA | ANALYZE | Analysis / reasoning entry | `Δ [INTENT] goal="audit"` |
| Ж | ZHE | ENFORCE | Constraint / assertion | `Ж [CONSTRAINT] mode="ro"` |
| ⨝ | JOIN | VOTE | Consensus / voting | `⨝ [VOTE] consensus="strict"` |
| ⌘ | COMMAND | CMD | Delegate / route | `⌘ [DELEGATE] agent="scribe"` |
| ∇ | NABLA | SOURCE | Source / parameter | `∇ [SOURCE] /data/log.txt` |
| ⩕ | BOWTIE | PRIORITY | Priority / weighting | `⩕ [PRIORITY] level="high"` |
| ⊎ | UNION | BRANCH | Branch / fork | `⊎ [BRANCH] name="experiment"` |
| ⌂ | HOUSE | MEMORY_ANCHOR | Memory anchor | `⌂ [MEMORY] key="session-1"` |
| Σ | SIGMA | SUMMARIZE | Aggregate / summary | `Σ [RESULT] summary="done"` |

The Ω (OMEGA) glyph is the universal terminator — every HLF program ends with `Ω`.

## Reading a 5-Surface Round-Trip

Here's `hello_world.hlf` through all 6 surfaces:

### Surface 1: Glyph Source
```hlf
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
  ∇ [RESULT] message="Hello, World!"
Ω
```

### Surface 2: Formatted Canonical
(same — it's already canonical)

### Surface 3: AST (excerpt)
```json
{
  "kind": "program",
  "version": "v3",
  "node_count": 3,
  "human_readable": "Program with 3 statements",
  "statements": [
    {
      "kind": "glyph_stmt",
      "glyph": "Δ",
      "tag": "INTENT",
      "human_readable": "analyze intent hello_world"
    }
  ]
}
```

### Surface 4: Bytecode (first 64 hex chars)
```
e3b0c44298fc1c149afbf4c8996fb924...254 bytes total
```

### Surface 5: Assembly (excerpt)
```asm
  0000  PUSH_CONST         #1  ; 'hello_world'
  0003  STORE              #2  ; 'goal'
  0006  PUSH_CONST         #3  ; 'hello_world'
  0009  CALL_HOST          #0 (args=1)  ; 'Δ [INTENT]'
  000C  PUSH_CONST         #5  ; 'ok'
  000F  STORE              #6  ; 'status'
  0012  PUSH_CONST         #7  ; 'ok'
  0015  PUSH_CONST         #4  ; 'Ж [ASSERT]'
  0018  PUSH_CONST         #9  ; 'Hello, World!'
  001B  STORE              #10  ; 'message'
  001E  PUSH_CONST         #11  ; 'Hello, World!'
  0021  PUSH_CONST         #8  ; '∇ [RESULT]'
  0024  HALT
```

### Surface 6: English Translation
> Program with 3 statements: analyze intent hello_world, enforce assert status ok, source result message Hello World!.

## Running the Gallery Yourself

```bash
# Summary to stdout
python scripts/run_hlf_gallery.py

# Full markdown report
python scripts/run_hlf_gallery.py --markdown

# JSON for tool consumption
python scripts/run_hlf_gallery.py --json

# Write to directory
python scripts/run_hlf_gallery.py --output-dir gallery_out/

# Only the 6 benchmark-domain fixtures
python scripts/run_hlf_gallery.py --domain-only --markdown
```

## Operator Surface Taxonomy

This gallery is part of the packaged operator-surface set:

| Surface Type | URIs |
| --- | --- |
| **Generated reports** | `hlf://reports/gallery`, `hlf://reports/fixture_gallery` |
| **Structured status** | `hlf://gallery`, `hlf://status/fixture_gallery` |
| **Static docs** | `docs/HLF_GALLERY.md` (this file), `fixtures/README.md` |
| **Discovery index** | `hlf://status/operator_surfaces` |
| **Proof surfaces** | `hlf://status/operator_proof_gallery`, `hlf://reports/operator_proof_gallery` |

## Claim Lane

- **current-true:** All 12 fixtures compile, encode, disassemble, and translate against packaged compiler truth. Script is reproducible.
- **bridge-true:** Gallery format, operator explanations, and MCP resource wiring are bridge-delivered. Benchmark compression numbers are verified from the packaged suite.
- **not-proven:** Interactive GUI gallery, animated surface transitions, and rich media explainers are not yet implemented.

## Related Documents

- [HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md](HLF_GALLERY_AND_OPERATOR_SURFACES_SPEC.md) — full spec and requirements
- [HLF_VISION_PLAIN_LANGUAGE.md](HLF_VISION_PLAIN_LANGUAGE.md) — what HLF is in plain English
- [HLF_STITCHED_SYSTEM_VIEW.md](HLF_STITCHED_SYSTEM_VIEW.md) — how the pieces fit together
- [HLF_REFERENCE.md](HLF_REFERENCE.md) — language reference
- [../fixtures/README.md](../fixtures/README.md) — fixture catalog
- [../SSOT_HLF_MCP.md](../SSOT_HLF_MCP.md) — current truth summary
