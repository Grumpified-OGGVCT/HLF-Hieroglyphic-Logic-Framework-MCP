# SwarmGlass — Govern, Observe, and Audit Agent Swarms

**SwarmGlass is a governance platform for multi-agent systems.** It gives you real-time observability into what your agents are doing, validates their outputs against your rules, cryptographically proves every decision they make, and contains them within secure execution boundaries — all exposed as MCP tools your agents can call directly.

SwarmGlass doesn't dictate how your agents coordinate. Natural language coordination is the recommended path — it's faster, cheaper, and equally effective. SwarmGlass layers governance, audit, and security around whatever coordination style you already use.

**127 MCP tools across 7 domains:**
- **Observe** — Real-time SSE events, TUI dashboards, GPU/RAM tracking, agent liveness
- **Validate** — Multi-format constraint checking, auto-correction, intent normalization
- **Audit** — SHA-256 hash chains, Merkle-signed backups, typed governance proofs, HITL gates
- **Secure** — Gas-metered sandboxing, PII detection/redaction, AES-256-GCM encryption, network isolation
- **Coordinate** — DAG + Saga execution, crypto handoff receipts, Merkle consensus (optional primitives)
- **Memory** — 2800+ line SQLite RAG store with provenance tracking and hybrid BM25+vector+reranker search
- **Models** — Registry, MoE routing, Ollama health monitoring, task-to-model dispatch

**Quick start:**
```bash
pip install swarmglass
swarmglass serve    # Start the MCP server
```
