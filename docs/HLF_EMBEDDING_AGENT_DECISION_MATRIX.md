# HLF Embedding and Agent Decision Matrix

Generated for the local `integrate-sovereign` branch on 2026-03-17.

This document converts the general Ollama embedding model research into a repo-specific decision matrix for `HLF_MCP`.

It is written to be usable by:

- operators deciding what to build next
- implementers wiring the packaged `hlf_mcp` surface
- reviewers evaluating whether embeddings, agent orchestration, or both are justified for a given HLF use case
- other agents joining the discussion without needing the full chat history

## Purpose

This is not a generic model leaderboard.

This document answers four repo-specific questions:

1. Where would embeddings actually help in `HLF_MCP`?
2. Where would agents actually help in `HLF_MCP`?
3. Where should both be used together?
4. Which locally runnable Ollama embedding models are reasonable first candidates for each HLF use case?

## Truth Boundary

This document is grounded in the current packaged product surface, not only in preserved upstream context.

Canonical product authority for current behavior:

- `hlf_mcp/`
- `governance/`
- key authority docs like `SSOT_HLF_MCP.md` and `docs/HLF_AGENT_ONBOARDING.md`

Relevant implemented surfaces in this local branch:

- `hlf_mcp/rag/memory.py`
- `hlf_mcp/server_memory.py`
- `hlf_mcp/server_translation.py`
- `hlf_mcp/hlf/translator.py`
- `hlf_mcp/hlf/runtime.py`
- `hlf_mcp/server_resources.py`
- `governance/pii_policy.json`

Local-branch facts that matter here:

- Infinite RAG already exists in packaged form.
- Translation diagnostics and deterministic repair flows already exist.
- Translation contract recall already exists through packaged tools.
- Runtime memory-aware delegation and routing context are now present as optional behavior in `hlf_mcp/hlf/runtime.py`.
- Governance, ethics, and PII controls are already part of the packaged truth surface.

## Current Architectural Baseline

### What exists now

1. Memory already exists.
   Current packaged memory is in `hlf_mcp/rag/memory.py`.
   It provides SHA-256 dedup, semantic similarity scoring, confidence, provenance, tags, hot/warm tier behavior, and Merkle-chain integrity.

2. Packaged MCP memory tools already exist.
   `hlf_memory_store`, `hlf_memory_query`, and `hlf_memory_stats` are exposed through `hlf_mcp/server_memory.py`.

3. Translation memory already exists in a narrow, valuable form.
   `hlf_translation_memory_query` in `hlf_mcp/server_translation.py` already recalls known-good translation contract exemplars from memory.

4. Repair planning already exists.
   `hlf_translate_repair` and `hlf_translate_resilient` provide deterministic repair plans and bounded retry behavior.

5. Governance retrieval already exists as direct resources rather than semantic retrieval.
   `hlf_mcp/server_resources.py` exposes governance documents and registries as MCP resources.

6. Runtime memory-aware orchestration now exists in minimal optional form.
   `delegate` and `route` in `hlf_mcp/hlf/runtime.py` can optionally retrieve memory context before returning routing or delegation envelopes.

### What does not exist yet

1. The packaged memory layer does not yet use an external embedding model.
   The current implementation is a lightweight token-based vector approximation.

2. There is no repo-native evaluation harness yet that compares:
   current memory baseline
   versus Ollama-backed embeddings
   versus specific retrieval tasks over HLF corpora.

3. There is no packaged ingestion pipeline yet for long-form standards knowledge with explicit chunking, freshness, and source authority policies.

4. There is no committed rule yet for when `delegate` or `route` should consult memory by default versus opt-in.

## Decision Rules

Use these rules before adding any embedding model or new agent orchestration path.

### Prefer direct deterministic tools when

- a task has one correct transformation path
- compile, format, lint, validate, disassemble, or static governance lookup is sufficient
- replayability matters more than fuzzy semantic recall

### Prefer embeddings when

- the question is “what similar thing do we already know?”
- exact keyword match is too brittle
- the corpus is exemplars, repairs, standards, policies, code patterns, or multilingual material

### Prefer agents when

- the question is “who should do this, in what order, under what constraints?”
- staged orchestration, delegation, consensus, repair, or verification is needed

### Prefer both when

- retrieved context should shape a bounded orchestration decision
- memory should inform delegation or routing without replacing governance

## Repository-Specific Use Case Matrix

| Use Case | Current Repo State | Primary Corpus | Recommend Embeddings? | Recommend Agents? | Primary Pattern | First Model Candidate | Fallback Candidate | Why This Choice | Implementation Priority | Key Risks / Gaps |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Translation memory | Already partly implemented via `hlf_translation_memory_query` and stored translation contracts | known-good translation exemplars, multilingual intent-to-HLF pairs, reverse audit summaries | Yes | Limited | embeddings-first, agent-optional | `nomic-embed-text-v2-moe` | `embeddinggemma` | Multilingual retrieval quality matters more than orchestration here; current seed pattern already exists | High | Need real evaluation over multilingual HLF prompts; current memory backend is still lightweight |
| Repair pattern recall | Already partly implemented via deterministic repair plan generation, but exemplar recall is still narrow | failed translation attempts, repair contracts, retry guidance, known terminal failures | Yes | Yes | embeddings plus bounded repair agent flow | `embeddinggemma` | `bge-m3` | Retrieval should surface prior successful fixes; agent logic then decides retry, fail-closed exit, or escalation | High | Must avoid replaying stale or unsafe repair patterns; needs confidence and freshness rules |
| Governance / policy retrieval | Strong direct-resource support already exists via MCP resources; semantic lookup is additive, not foundational | `host_functions.json`, `align_rules.json`, `tag_i18n.yaml`, `pii_policy.json`, constitution and ethics docs | Usually no for baseline lookup; yes for semantic advisory recall | Limited | deterministic resource lookup first, embeddings second | `embeddinggemma` | `bge-m3` | Canonical governance should stay exact and authoritative; embeddings only help when finding related policy fragments or precedent-like guidance | Medium | High risk of treating advisory semantic hits as authority; must separate canonical from advisory |
| Code-pattern retrieval | Not yet first-class in packaged memory; good fit for weekly knowledge substrate | HLF snippets, compiler/runtime examples, fixtures, docs, packaged stdlib patterns, validated code idioms | Yes | Sometimes | embeddings-first with optional agent consumer | `bge-m3` | `mxbai-embed-large` | Code and docs often exceed short-context thresholds; `bge-m3` balances multilingual and longer-context utility | Medium-High | Chunking strategy not decided; code-aware ranking not implemented |
| Agent routing context | Newly enabled in minimal optional form in runtime `delegate` and `route` | prior routing decisions, known-good specialist assignments, goal-to-agent mappings, routing heuristics | Yes | Yes | retrieval-informed orchestration | `embeddinggemma` | `nomic-embed-text-v2-moe` | Routing context should remain small, fast, and optional; start with lightweight local embeddings before heavier multilingual models | Medium | Over-coupling retrieval to routing logic; must remain fail-open and governable |
| Long-form standards ingestion | Not implemented yet as a packaged ingestion system, but explicitly aligned with knowledge-substrate direction | standards docs, changelogs, framework docs, API specs, compliance references, operator handoffs | Yes | Yes, but later in pipeline | embeddings-backed ingestion plus agent-curated refresh | `bge-m3` | `qwen3-embedding:4b` | Standards are long-form and chunk-sensitive; `bge-m3` is realistic on local hardware, while `qwen3-embedding:4b` is a later option if chunk windows prove insufficient | Medium | Needs chunking, freshness model, provenance, licensing, and source trust policy before model choice matters |

## Detailed Row Guidance

### 1. Translation Memory

Current fit:

- Best immediate candidate for upgrading from lightweight semantic matching to a real embedding backend.
- Already has a packaged recall path and already stores a narrow but valuable class of exemplars.

Recommendation:

- Use embeddings.
- Do not require agents for baseline retrieval.
- Allow agent participation only when translation memory is feeding a larger retry or repair workflow.

Primary model choice:

- `nomic-embed-text-v2-moe`

Why:

- Translation memory is the strongest case for multilingual semantic recall.
- Cross-lingual intent similarity matters more than raw 512-token leaderboard performance.

Fallback:

- `embeddinggemma`

Use when:

- local hardware budget matters more than cross-lingual quality
- you want the first production proof before committing to a multilingual-heavy model

### 2. Repair Pattern Recall

Current fit:

- The repair planner exists, but retrieval of prior successful repair cases is still underdeveloped.

Recommendation:

- Use both embeddings and agents.
- Embeddings should retrieve similar prior failures and fixes.
- Agent logic should decide whether a retry is appropriate, whether a failure is terminal, and whether governance requires a fail-closed stop.

Primary model choice:

- `embeddinggemma`

Why:

- Repair records are typically shorter than standards docs.
- This path benefits from low latency more than extreme context length.

Fallback:

- `bge-m3`

Use when:

- repair exemplars or error traces become longer and more multilingual

### 3. Governance / Policy Retrieval

Current fit:

- Exact governance resource exposure is already strong.
- Semantic retrieval should not replace exact policy lookup.

Recommendation:

- Baseline: do not require embeddings or agents.
- Canonical policy access should stay deterministic through resources and governed files.
- Add embeddings only for advisory support such as “find related rule fragments” or “find similar prior governance guidance.”

Primary model choice:

- `embeddinggemma`

Why:

- If semantic policy retrieval is added, low-latency local advisory recall is more important than long-window document embedding at first.

Constraint:

- Canonical versus advisory sources must be visibly separated in the response contract.

### 4. Code-Pattern Retrieval

Current fit:

- The repo contains a meaningful corpus of fixtures, docs, runtime/compiler logic, and stdlib references.
- This is a strong candidate for weekly knowledge substrate growth.

Recommendation:

- Use embeddings.
- Optionally allow agent consumers to use retrieved patterns during synthesis, review, repair, or translation.

Primary model choice:

- `bge-m3`

Why:

- Code and docs often need longer chunk support than 512-token-class models.
- It balances multilingual utility with longer context and strong retrieval quality.

Fallback:

- `mxbai-embed-large`

Use when:

- the corpus is mostly English code and short pattern snippets
- throughput matters more than multilingual coverage

### 5. Agent Routing Context

Current fit:

- A minimal optional runtime integration now exists.
- The design should remain retrieval-informed rather than retrieval-dominated.

Recommendation:

- Use both embeddings and agents.
- The retrieval result should be advisory context for routing and delegation, not the routing policy itself.

Primary model choice:

- `embeddinggemma`

Why:

- Routing context should stay cheap and fast.
- This is a latency-sensitive path where a lightweight local model is the right first production choice.

Fallback:

- `nomic-embed-text-v2-moe`

Use when:

- routing must consume multilingual task descriptions at high fidelity

### 6. Long-Form Standards Ingestion

Current fit:

- Strategically important.
- Operationally immature.

Recommendation:

- Use both embeddings and agents, but only after ingestion discipline exists.
- Embeddings are needed for retrieval.
- Agent logic is useful for source selection, chunking review, summary generation, validation, and weekly refresh curation.

Primary model choice:

- `bge-m3`

Why:

- Realistic for local deployment.
- Better fit than short-context models for standards and docs.

Fallback:

- `qwen3-embedding:4b`

Use when:

- chunking experiments prove that 8K-class context is insufficient
- hardware allows a heavier model

Do not start with:

- `qwen3-embedding:8b`

Reason:

- operational cost is too high for the repo’s current evaluation maturity

## Recommended First Adoption Order

If the repo adopts real local embeddings, the least risky rollout order is:

1. Translation memory
2. Repair pattern recall
3. Agent routing context
4. Code-pattern retrieval
5. Governance advisory retrieval
6. Long-form standards ingestion

Why this order:

- the first two already have explicit packaged surfaces
- they build on existing memory patterns rather than inventing a new subsystem
- they create measurable wins with lower ingestion complexity
- they avoid prematurely treating standards ingestion as solved when freshness and provenance are still open

## Model Recommendations by HLF Hardware Tier

This repo appears to be operating in a local-first Windows environment where practical deployment matters more than benchmark aesthetics.

### Why lower-hardware guidance matters

This matrix should not assume every collaborator, reviewer, CI runner, or downstream operator has RTX 3060-class hardware.

Lower-tier guidance is useful for:

- contributors evaluating the design on laptops or office desktops
- CPU-only fallback deployments
- staged rollouts where retrieval quality is validated before heavier local models are adopted
- making sure the embedding path remains optional and degrades gracefully instead of silently excluding lower-resource environments

### If the target machine is RTX 3060-class

Prefer:

- `embeddinggemma`
- `nomic-embed-text-v2-moe` if multilingual retrieval is central
- `mxbai-embed-large` for English-heavy short-context code/pattern retrieval

Be cautious with:

- `bge-m3`, depending on concurrency and resident VRAM pressure

Avoid as first integration:

- `qwen3-embedding:4b`
- `qwen3-embedding:8b`

### If the target machine is below RTX 3060-class

This tier includes older consumer GPUs, smaller VRAM budgets, or mixed-use machines where local embedding load must stay light.

Prefer:

- `embeddinggemma`
- `all-minilm`
- `granite-embedding:30m`

Use cases that still make sense here:

- translation memory proofs of concept with smaller corpora
- repair pattern recall over short records
- lightweight advisory routing context
- governance-advisory semantic lookups over small local indexes

Use with caution:

- `mxbai-embed-large`
- `bge-large`

Reason:

- these may still fit on some 4 GB to 6 GB configurations, but they are less forgiving under concurrency, batch size growth, or co-resident workloads

Not recommended on this tier as a first default:

- `nomic-embed-text-v2-moe`
- `bge-m3`
- `qwen3-embedding` variants

Reason:

- they add too much operational pressure before the repo has a mature embedding evaluation harness

### If the target machine has no usable GPU

CPU-only operation should be treated as a first-class fallback, not as a failure mode.

Prefer:

- `embeddinggemma` for the best practical quality/size balance
- `all-minilm` when absolute lightness matters more than retrieval quality
- `granite-embedding:30m` if IBM ecosystem alignment or tiny footprint matters

Recommended use on CPU-only systems:

- small translation-memory indexes
- short repair-pattern corpora
- operator-side evaluation and smoke tests
- small governance-advisory retrieval indexes

Not recommended on CPU-only systems for first deployment:

- large code-pattern indexes
- long-form standards ingestion at scale
- retrieval in latency-sensitive routing loops

Reason:

- the latency budget is likely too high unless corpus size, batch size, and query frequency stay very modest

### CPU-only default recommendation

If a reviewer or downstream user says “I have no GPU, what should I run first?” the default answer should be:

1. `embeddinggemma` if they want a realistic first evaluation
2. `all-minilm` if they only need a tiny proof-of-concept or CI-friendly fallback

That recommendation is intentionally conservative. The goal is to keep the repo’s retrieval story portable, not to optimize for benchmark prestige.

## Low-Hardware Decision Addendum by Use Case

| Use Case | Best Low-Hardware Choice | CPU-Only Choice | Why |
| --- | --- | --- | --- |
| Translation memory | `embeddinggemma` | `embeddinggemma` | Best balance of quality and operational simplicity for short-to-medium multilingual-adjacent recall experiments |
| Repair pattern recall | `embeddinggemma` | `all-minilm` | Repair records are short and benefit more from fast local lookup than huge context windows |
| Governance / policy retrieval | `embeddinggemma` | `all-minilm` | This remains advisory only; exact resources still carry canonical truth |
| Code-pattern retrieval | `mxbai-embed-large` if VRAM allows, otherwise `embeddinggemma` | `embeddinggemma` for tiny corpora only | Code retrieval is useful but should not force heavy hardware as a baseline |
| Agent routing context | `embeddinggemma` | `all-minilm` | Routing context should stay lightweight and optional |
| Long-form standards ingestion | defer heavy embedding adoption or use `embeddinggemma` only for small pilots | not recommended as first CPU-only target | This use case depends more on chunking, provenance, and ingestion discipline than on squeezing weak hardware |

### If the target machine is RTX 3090-class or better

Prefer:

- `bge-m3` for code and standards retrieval
- `nomic-embed-text-v2-moe` for multilingual translation memory
- `qwen3-embedding:4b` only if evaluation proves a real long-context gain

## Evaluation Criteria Before Any Backend Swap

Do not replace the current memory backend based only on public benchmark claims.

Every candidate must be tested against a repo-native corpus and task set.

Minimum evaluation buckets:

1. Translation exemplar recall quality
2. Repair pattern recall precision
3. Governance advisory retrieval non-hallucination rate
4. Code-pattern retrieval usefulness
5. Routing-context helpfulness versus latency cost
6. Long-form chunk recall quality

Minimum metrics:

- recall at k
- precision at k
- mean reciprocal rank
- latency per query
- VRAM footprint
- corpus ingest throughput
- failure behavior under missing model or unavailable Ollama daemon

## Constraints Other Agents Must Respect

Any agent reviewing or extending this design should preserve these invariants.

### 1. Canonical governance remains exact-first

Semantic governance retrieval must never silently outrank canonical governed files.

### 2. Memory retrieval must remain advisory unless the contract says otherwise

Retrieved context can inform `delegate`, `route`, translation, or repair.
It must not silently become policy or execution authority.

### 3. Fail-open for advisory retrieval, fail-closed for governance breaches

If memory retrieval fails, orchestration may continue without context.
If governance or ethics blocks execution, the system must remain fail-closed.

### 4. PII policy still applies

Memory-backed workflows must respect governed PII handling and storage redaction behavior.

### 5. Model choice is not architecture

Switching from token-proxy vectors to Ollama embeddings does not solve:

- chunking
- freshness
- provenance
- source authority
- evaluation
- trust separation

## Open Design Questions For Other Agents

Other agents reviewing this matrix should answer these questions explicitly.

1. Should translation memory and repair memory share one embedding space, or should they be indexed separately?
2. Should governance advisory retrieval use a different index than code-pattern retrieval?
3. Should `delegate` and `route` memory context stay opt-in, or become enabled by default for specific capsules or tiers?
4. What chunking policy should apply to HLF source, docs, and long-form standards?
5. Should standards ingestion be one global index or multiple authority-scoped indexes?
6. What freshness and decay policy should apply to weekly-ingested external knowledge?
7. What confidence schema should distinguish:
   canonical repo truth
   validated retrieved exemplar
   advisory semantic neighbor
   stale or low-confidence external content?

## Brief For Reviewing Agents

If another agent joins this discussion, it should assume the following baseline:

### Repo identity

- This repo is trying to become a deterministic, governed HLF substrate rather than a generic RAG toy.
- The packaged product surface is `hlf_mcp`.
- The memory system already exists but still uses a lightweight semantic approximation.

### Current implemented anchors

- `hlf_mcp/rag/memory.py` is the active memory substrate.
- `hlf_mcp/server_memory.py` exposes packaged memory tools.
- `hlf_mcp/server_translation.py` already exposes translation-memory recall and deterministic repair flows.
- `hlf_mcp/hlf/runtime.py` now supports optional memory-aware delegation and routing context.
- `hlf_mcp/server_resources.py` exposes governance files as exact resources.

### What is being decided

Not “should we use AI somehow?”

The real question is:

- which HLF use cases deserve real local embeddings
- which deserve agent orchestration
- which deserve both
- and which should remain deterministic-only

### Default position reviewers should challenge

The default recommendation in this document is:

- embeddings are highly justified for translation memory, repair recall, code-pattern retrieval, and long-form standards ingestion
- agents are highly justified for repair workflows, routing context, and standards-refresh pipelines
- governance/policy retrieval should remain deterministic-first

If a reviewer disagrees, it should argue at the level of:

- use case
- corpus type
- governance risk
- hardware fit
- evaluation cost
- operational complexity

not vague preference.

## Recommended Next Deliverables

If this matrix is accepted, the next concrete deliverables should be:

1. A retrieval evaluation corpus for the six use cases above.
2. A benchmark harness comparing current memory baseline against `embeddinggemma`, `nomic-embed-text-v2-moe`, and `bge-m3`.
3. An authority model that separates canonical, validated, and advisory retrieval hits.
4. An ingestion design for long-form standards with chunking, freshness, provenance, and licensing policy.
5. A server/context-layer retriever injection path so runtime no longer needs even a local default model import if a packaged retriever is configured.

## Bottom Line

For `HLF_MCP`, embeddings are justified where recall quality is the bottleneck.
Agents are justified where orchestration quality is the bottleneck.
The best early wins are not evenly distributed.

The strongest first bets are:

- translation memory
- repair pattern recall
- retrieval-informed routing context

The most important thing not to get wrong is treating semantic retrieval as canonical truth.
