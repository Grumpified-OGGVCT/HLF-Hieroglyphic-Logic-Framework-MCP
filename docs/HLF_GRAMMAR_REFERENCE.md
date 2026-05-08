# HLF Grammar Reference

Packaged grammar reference for this repository.

This document is grounded in the current parser and metadata surfaces in:

- `hlf_mcp/hlf/grammar.py`
- `governance/templates/dictionary.json`
- `docs/HLF_TAG_REFERENCE.md`

It replaces the upstream reference as the authoritative guide for the packaged repo.

## Truth Boundary

Two distinct surfaces matter here:

1. The packaged parser in `hlf_mcp/hlf/grammar.py` defines what compiles now.
2. The extracted dictionary in `governance/templates/dictionary.json` enriches tags and glyphs for tooling, docs, and LSP behavior.

Those surfaces overlap, but they are not identical yet. This document prioritizes parser truth and calls out the remaining drift where it matters.

## Required Program Shape

- Programs start with a version header such as `[HLF-v3]`.
- Programs terminate with `Ω`.
- `# ...` starts a comment.
- Strings use double quotes.
- Variable references use `$NAME`.

Minimal example:

```hlf
[HLF-v3]
SET goal = "deploy"
Δ [INTENT] action="ship" target="/app"
RESULT 0 "ok"
Ω
```

## Top-Level Statement Forms

The packaged grammar currently exposes 21 top-level statement forms.

| Form | Syntax Shape | Notes |
| --- | --- | --- |
| Glyph statement | `Δ [TAG] ...` | Generic glyph-prefixed statement with optional tag and args |
| Immutable bind | `SET name = value` | Canonical immutable binding |
| Mutable assign | `ASSIGN name = expr` | Mutable assignment form |
| Block `IF` | `IF expr { ... }` | Supports `ELIF` and `ELSE` blocks |
| Flat `IF` | `IF name CMP value` | Backward-compat single-line conditional |
| `FOR` loop | `FOR name IN expr { ... }` | Iteration block |
| `PARALLEL` | `PARALLEL { ... } { ... }+` | Concurrent block fan-out |
| Function block | `FUNCTION name(args) { ... }` | Block-bodied function definition |
| Intent block | `INTENT name ... { ... }` | Capsule-scoped structured intent |
| Tool call | `TOOL name ...` | Explicit tool invocation |
| Function call | `CALL name ...` | Explicit call site |
| Return | `RETURN value?` | Optional return payload |
| Result | `RESULT expr (expr)?` | Result code and optional message |
| Log | `LOG value` | Structured logging |
| Import | `IMPORT path` | Parser currently treats import targets as path-like operands |
| Memory write | `MEMORY[Name] ...` | Memory node capture |
| Memory recall | `RECALL[Name]` | Memory retrieval |
| Spec define | `SPEC_DEFINE ...` | Instinct lifecycle surface |
| Spec gate | `SPEC_GATE ...` | Instinct lifecycle surface |
| Spec update | `SPEC_UPDATE ...` | Instinct lifecycle surface |
| Spec seal | `SPEC_SEAL ...` | Instinct lifecycle surface |

## Glyph Surface

The parser accepts nine statement glyphs through the generic glyph-statement production. `Ω` remains the required terminator, not a statement glyph. This is metadata/tooling restoration plus generic glyph compilation, not full parser restoration for every v0.4/v0.5 construct.

| Glyph | Canonical Name | Semantic Role | ASCII Alias |
| --- | --- | --- | --- |
| `Δ` | `DELTA` | analyze / primary action | `ANALYZE`, `ANALYSE` |
| `Ж` | `ZHE` | enforce / constrain | `ENFORCE`, `CONSTRAIN` |
| `⨝` | `JOIN` | consensus / vote / merge | `JOIN`, `CONSENSUS`, `VOTE` |
| `⌘` | `COMMAND` | command / delegate / route | `CMD`, `COMMAND` |
| `∇` | `NABLA` | source / parameter / data flow | `SOURCE` |
| `⩕` | `BOWTIE` | priority / weighting | `PRIORITY` |
| `⊎` | `UNION` | branch / union / capsule fan-out | `BRANCH`, `UNION` |
| `⌂` | `HOUSE` | memory anchor / provenance | `MEMORY_ANCHOR` |
| `Σ` | `SIGMA` | summary / aggregate / report | `SUMMARY`, `SUMMARIZE`, `AGGREGATE` |

`Ω` is the required terminator, not a statement glyph.

## Tag Surface

The packaged repo carries a tooling dictionary for canonical and bridge-pressure tags. The current recognized metadata surface now includes intent/capsule, thought/observation/plan/action, module/function/code/import/call/return, memory/recall/provenance, governance/gate/spec lifecycle, routing/delegation/consensus, relation, and result tags.

For current tag arity and traits, use [HLF_TAG_REFERENCE.md](HLF_TAG_REFERENCE.md).

## Expressions

Block-form control flow supports these expression families:

| Family | Operators |
| --- | --- |
| Logical | `AND`, `OR`, `NOT` |
| Comparison | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| Arithmetic | `+`, `-`, `*`, `/`, `%` |
| Primary atoms | string, int, float, `$VAR`, identifier, path |

## Current Drift To Know About

The packaged repo still has a few surfaces in active reconciliation.

### Import semantics

The parser currently defines `IMPORT` against a path-like token. The extracted stdlib and LSP surfaces also expose logical module names such as `math`, `crypto`, and `string`.

That means the repo already has a useful stdlib catalog, but the exact import authoring story is not fully unified yet. Treat the stdlib module list as authoritative for what exists, and the parser as authoritative for what compiles today.


### Restored metadata boundary

This restoration aligns metadata, linter recognition, generated TextMate scopes, LSP completions, and tag docs with the broader authority lanes. It does not claim that every dictionary tag has a dedicated AST node or runtime semantics. Dedicated parser productions remain limited to the statement forms above; broader tags compile today only when carried by supported generic glyph statements or existing keyword statements.

### Parser vs. tag dictionary

The dictionary is broader than the strict parser grammar. That is intentional for tooling, but it means not every documented tag implies a dedicated parser production. Some tags are currently consumed through generic glyph statements or tooling layers rather than bespoke grammar rules.

## Authoring Guidance

- Prefer the packaged keyword forms such as `SET`, `ASSIGN`, `IF`, `FUNCTION`, `CALL`, `RESULT`, and `LOG` when you need parser certainty.
- Use glyph-prefixed statements when you want the hieroglyphic surface and the relevant tag is understood by the consuming toolchain.
- End every program with `Ω`.
- Keep [HLF_TAG_REFERENCE.md](HLF_TAG_REFERENCE.md) and [HLF_STDLIB_REFERENCE.md](HLF_STDLIB_REFERENCE.md) nearby when authoring.
