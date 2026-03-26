# ADR-0001: Datastores for Private AgentsKB Pro Recreation

**Status**: Proposed (planning only)  
**Date**: 2025-12-31

## Context

The specification requires:

- Canonical KB content stored as Markdown files in `./kb_files/{domain}.md`
- A durable research queue (“misses” are queued and later researched)
- Optional human review workflow (queue status + approvals)
- “Self-scaling” behavior (multiple API instances should share the same queue and KB state)
- “Best and free” preference stated by the user (potential conflict with managed retrieval + paid model choices)

## Decision (planning default)

- **Canonical KB content**: Markdown files on disk (`./kb_files/`)
- **System state (queue + governance metadata)**:
  - **Local dev**: SQLite (`./queue.db`) for single-instance development and simple iteration
  - **Self-scaling**: PostgreSQL for shared, concurrent, multi-instance correctness (unique constraints + transactions)
- **MongoDB**: not required for the spec’s minimum state model (queue + statuses + audit). It may be used only if the queue/governance schema is intentionally document-oriented.

## Rationale

- The queue requires:
  - strong dedupe (`question` uniqueness)
  - safe concurrent workers (claim/lease semantics)
  - transactional status transitions (`pending → in_progress → completed/discarded/error`)
- PostgreSQL supports this directly and predictably.
- SQLite is acceptable only when “self-scaling” is not in scope (single node).

## Consequences

- “Best + free + self-scaling” is only simultaneously true if the deployment environment provides a free shared Postgres (or equivalent) tier; otherwise “free” applies to local-only deployment.
- The KB Markdown files remain the canonical source of truth; DB stores only system state and governance metadata.

## Open questions

- Does “free” mean “runs locally with no cloud cost”, or “uses managed free tiers”?
- Where will `./kb_files` live for multi-instance deployment (shared disk/object storage), and how will File Search ingestion updates be coordinated?


