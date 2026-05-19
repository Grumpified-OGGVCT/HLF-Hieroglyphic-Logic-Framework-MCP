# Constraint Usage Audit — HLF EffectClass & Glossary Tags

*Generated: 2026-05-19 | Source: hlf_mcp/hlf/*.py, docs/CONSTRAINT_GLOSSARY.md*

## Part 1: EffectClass Enum — Definition vs Usage

The `EffectClass` enum in `hlf_mcp/hlf/typed_contracts.py` defines **32** canonical
effect classes. This audit tracks which ones are wired into the three downstream
consumers: tool-name resolution (`effect_extractor._TOOL_TO_EFFECT`), glyph+tag
resolution (`effect_extractor._GLYPH_TAG_TO_EFFECT`), and the capability/trust
mappings (`capability_manifest.EFFECT_TO_CAPABILITY`, `EFFECT_TO_TRUST_TIER`).

### Legend

| Column | Meaning |
|--------|---------|
| **Tool** | Has ≥1 tool name mapped in `_TOOL_TO_EFFECT` |
| **Glyph+Tag** | Has ≥1 (glyph, tag) pair in `_GLYPH_TAG_TO_EFFECT` |
| **Glyph-only** | Maps via fallback `_glyph_only` dict (glyph without tag) |
| **Capability** | Present in `EFFECT_TO_CAPABILITY` |
| **Trust Tier** | Present in `EFFECT_TO_TRUST_TIER` |
| **Checker** | Has a dedicated `_check_*` method in `constraint_glossary_bridge.py` |

### Full Audit Table

| # | EffectClass | Tool | Glyph+Tag | Capability | Trust Tier | Active? |
|---|-------------|------|-----------|------------|------------|---------|
| 1 | `AGENT_DELEGATION` | ✅ delegate, agent_call | ✅ ⨝.DELEGATE, ⌘.DELEGATE | agent | trusted | **active** |
| 2 | `ASSERTION` | ❌ | ✅ Ж.ENFORCE, Ж.CONSTRAINT | local | advisory | **glyph-only** |
| 3 | `AUDIT_LOG` | ✅ audit_log | ✅ Σ.AUDIT | audit | approved | **active** |
| 4 | `CRYPTOGRAPHIC_HASH` | ✅ hash, sign | ❌ | crypto | advisory | **active** |
| 5 | `EMBEDDING_GENERATION` | ✅ embedding | ❌ | model | watched | **active** |
| 6 | `ENVIRONMENT_READ` | ❌ | ✅ ∇.SOURCE, ∇.PARAM | environment | advisory | **glyph-only** |
| 7 | `FILE_READ` | ✅ file_read, read_file | ✅ Δ.READ, ∇.IMPORT | filesystem | approved | **active** |
| 8 | `FILE_WRITE` | ✅ file_write, write_file | ❌ | filesystem | watched | **active** |
| 9 | `FORMAL_VERIFICATION` | ✅ formal_verify | ❌ | verifier | trusted | **active** |
| 10 | `GUARDED_ACTUATION` | ✅ actuate | ❌ | embodied | hearth | **active** |
| 11 | `GOVERNANCE_VOTE` | ✅ vote | ✅ ⨝.VOTE, ⨝.CONSENSUS | governance | trusted | **active** |
| 12 | `LOCAL_ANALYSIS` | ❌ (default) | ✅ Δ.RELATE, Δ.ANALYZE, ⩕.SCORE, Σ.EXPORT, Σ.SUMMARY | local | advisory | **active (default)** |
| 13 | `MEMORY_READ` | ✅ memory_read, recall | ✅ ⌂.RECALL | memory | approved | **active** |
| 14 | `MEMORY_WRITE` | ✅ memory_write, remember | ✅ ⌂.STORE, ⌂.ANCHOR | memory | watched | **active** |
| 15 | `MERKLE_APPEND` | ✅ merkle_append | ❌ | audit | approved | **active** |
| 16 | `MODEL_INFERENCE` | ✅ model_inference, infer, llm_call | ✅ Δ.INFER | model | watched | **active** |
| 17 | `MULTIMODAL_AUDIO` | ✅ audio | ❌ | model | watched | **active** |
| 18 | `MULTIMODAL_OCR` | ✅ ocr | ❌ | model | watched | **active** |
| 19 | `MULTIMODAL_VIDEO` | ✅ video | ❌ | model | watched | **active** |
| 20 | `MULTIMODAL_VISION` | ✅ vision | ❌ | model | watched | **active** |
| 21 | `NETWORK_READ` | ✅ network_read, http_get, fetch_url | ✅ Δ.QUERY, Δ.FETCH | network | approved | **active** |
| 22 | `NETWORK_WRITE` | ✅ network_write, http_post | ❌ | network | trusted | **active** |
| 23 | `PROCESS_SPAWN` | ✅ exec, spawn, shell | ✅ ⌘.EXEC, ⌘.SPAWN, ⌘.SHELL | exec | trusted | **active** |
| 24 | `ROUTE_SELECTION` | ✅ route | ✅ ⌘.ROUTE, ⩕.PRIORITY | routing | approved | **active** |
| 25 | `SAFETY_STOP` | ✅ safety_stop | ✅ Ж.GUARD | embodied | hearth | **active** |
| 26 | `SENSOR_READ` | ✅ sensor_read | ❌ | embodied | hearth | **active** |
| 27 | `SIMILARITY_MATH` | ✅ similarity | ❌ | local | advisory | **active** |
| 28 | `TIMING` | ✅ timer | ❌ | local | advisory | **active** |
| 29 | `TOKEN_TRANSFORM` | ✅ token_transform | ❌ | local | advisory | **active** |
| 30 | `TRAJECTORY_PLAN` | ❌ | ❌ | embodied | hearth | ⚠️ **unused** |
| 31 | `VERIFICATION` | ✅ verify | ✅ Ж.VERIFY, Ж.CHECK, Σ.VERIFY | verifier | trusted | **active** |
| 32 | `WEB_SEARCH` | ✅ web_search | ✅ Δ.SEARCH | network | approved | **active** |

### Summary Statistics

| Metric | Count | % of 32 |
|--------|-------|---------|
| Has tool mapping | 28 | 87.5% |
| Has glyph+tag mapping | 14 | 43.8% |
| Has BOTH tool + glyph | 11 | 34.4% |
| Has NEITHER tool nor glyph (TRAJECTORY_PLAN only) | 1 | 3.1% |
| Glyph-only (no tool name, only reachable via HLF glyph syntax) | 2 | 6.25% |
| In capability manifest | 32 | 100% |
| In trust tier map | 32 | 100% |

### Key Findings

1. **`TRAJECTORY_PLAN` is orphaned** — defined in the enum, capability map, and trust
   tier map, but has zero tool-name or glyph+tag mappings. Agents can never produce
   this effect through normal HLF compilation. Either add a tool name or glyph mapping,
   or document it as a future/reserved effect.

2. **`ASSERTION` and `ENVIRONMENT_READ` are glyph-only** — they have no direct tool
   names. They can only be triggered through HLF glyph syntax (`Ж [ENFORCE]`,
   `∇ [SOURCE]`). This is by design (they represent constraint-level operations,
   not user-callable tools), but worth documenting.

3. **Duplicate in `EFFECT_TO_CAPABILITY`**: `TRAJECTORY_PLAN` appears at lines 84 and
   97 of `capability_manifest.py`, both mapping to `"embodied"`. Harmless but
   redundant.

4. **10 effects have no glyph mapping**: CRYPTOGRAPHIC_HASH, EMBEDDING_GENERATION,
   FILE_WRITE, FORMAL_VERIFICATION, GUARDED_ACTUATION, MERKLE_APPEND,
   MULTIMODAL_* (4), SENSOR_READ, SIMILARITY_MATH, TIMING, TOKEN_TRANSFORM.
   These are only reachable via direct tool calls — reasonable.

---

## Part 2: CONSTRAINT_GLOSSARY.md Tags — Definition vs Runtime Checking

The frozen `docs/CONSTRAINT_GLOSSARY.md` defines **34** constraint tags across
7 categories. The `constraint_glossary_bridge.py` provides runtime enforcement.

### Tags with Runtime Checkers

Only **3 of 34** tags (8.8%) have dedicated `_check_*` methods:

| Tag | Checker Method | Verifies |
|-----|---------------|----------|
| `COMMONJS` | `_check_commonjs()` | File uses `require`/`module.exports`, not ES imports |
| `NULL-ON-MISSING` | `_check_null_on_missing()` | `findById` returns null, doesn't throw |
| `NO-INSTALL` | `_check_no_install()` | No `npm install` commands in output |

The ownership constraints (`MIGRATION-OWNERSHIP`, `ENTRY-POINT-OWNERSHIP`) are
enforced by `check_ownership_violations()` in the bridge and also wired into
`agent_spawner.py` as prompt-level warnings.

### Tags Referenced in Agent Spawner Code

| Tag | Where | How |
|-----|-------|-----|
| `COMMONJS` | `agent_spawner.py:588-592` | Conflict detection (COMMONJS vs ESMODULE) |
| `ESMODULE` | `agent_spawner.py:588-592` | Conflict detection (not in glossary!) |
| `MIGRATION-OWNERSHIP` | `agent_spawner.py:257-259` | Prompt-level ownership warning |
| `ENTRY-POINT-OWNERSHIP` | `agent_spawner.py:257-259` | Prompt-level ownership warning |

### Tags Without Any Runtime Enforcement (31 of 34)

The following glossary tags parse correctly but have **no runtime checker** and are
**never referenced** in agent code beyond the glossary parser:

`FACTORY-EXPORT`, `FACTORY-SERVICE`, `FACTORY-SIGNATURE`, `SLUG-GENERATION`,
`STATUS-FSM`, `PURCHASE-VERIFY`, `JEST`, `SUPERTEST`, `DESCRIBE-BLOCKS`,
`COVERS-CRUD`, `ROLE-CHECKS`, `REUSABLE-HELPERS`, `NO-DUPLICATE-MIGRATIONS`,
`SEQUENTIAL-NUMBERS`, `NAMING-CONVENTION`, `ROUTE-NAMING`, `IMPORT-PATHS`,
`SQL-VALID`, `FK-CONSTRAINTS`, `INDEXES-DEFINED`, `DOMAIN-COVERAGE`,
`NODE-18+`, `PG-DB`, `EXPRESS-WIRING`, `SECURITY-MIDDLEWARE`,
`EXPRESS-MIDDLEWARE`, `JSON-ERRORS`, `JWT-SECRET-ENV`, `BCRYPTJS`, `ROLE-AWARE`

### Architecture Tags (10)

The architecture block tags (`express`, `node-18+`, `postgresql`, `knex`,
`jwt-bcrypt`, `commonjs`, `jest-supertest`, `factory-export`, `middleware-chain`,
`error-first`) are defined as a separate table in the glossary. They are parsed
by the bridge but have **no runtime checkers** — they serve as declarative
environment constraints for the swarm compiler's `architecture {}` block.

---

## Part 3: Ж-Glyph Constraint Tags (constraints.hlf)

`hlf_mcp/bridges/msty_claw/constraints.hlf` defines a separate constraint system
using Ж-glyph syntax. These are tool-safety constraints (not output-quality):

| Glyph | Tag | Count | Examples |
|-------|-----|-------|----------|
| Ж | `FORBID` | 22 | `rm -rf`, `/etc/*` writes, secret file reads, internal network |
| Ж | `ALLOW` | 4 | `/workspace/*`, `./*` read/write |
| Ж | `REQUIRE_APPROVAL` | 1 | `http_request` to any host |

These are enforced by the `constraint_bridge.py` (`msty_claw` bridge),
**not** by the glossary bridge. They represent pre-execution safety gates,
not post-output quality checks.

---

## Recommendations

1. **Add a tool or glyph mapping for `TRAJECTORY_PLAN`** or deprecate it.
2. **Build checkers for the top 5 most critical unenforced glossary tags:**
   `FACTORY-EXPORT`, `SQL-VALID`, `STATUS-FSM`, `FK-CONSTRAINTS`, `JWT-SECRET-ENV`.
3. **Remove the duplicate `TRAJECTORY_PLAN`** line in `EFFECT_TO_CAPABILITY`.
4. **Add `ESMODULE` to CONSTRAINT_GLOSSARY.md** if it's a first-class constraint
   tag referenced by the agent spawner.
5. **Consider a `ConstraintSeverity` enum** to distinguish advisory vs blocking
   glossary constraints at the bridge level.
