# Fork Policy (Upstream Compatibility)

This repo is a fork of the upstream reference implementation.

- **Upstream**: `Cranot/agentskb-mcp` ([GitHub](https://github.com/Cranot/agentskb-mcp))
- **Fork**: `Grumpified-OGGVCT/agentskb-mcp` ([GitHub](https://github.com/Grumpified-OGGVCT/agentskb-mcp))

## Primary Goal

**Maintain backwards compatibility with upstream by default** while allowing improvements that are **upstreamable**.

## Compatibility Requirements (Non‑Negotiable)

- **Default entrypoint stays the same**: `npx @agentskb/cli mcp`
- **MCP tool surface stays compatible**:
  - Tool names and semantics must match upstream:
    - `ask_question`
    - `preflight_check`
    - `search_questions`
    - `get_stats`
  - Do not rename tools or change meanings.
- **Configuration examples remain valid upstream**:
  - The minimal config from upstream must keep working.
  - Additions must be opt‑in and must not break existing setups.
- **No breaking changes in defaults**:
  - Enhancements must be behind env vars / flags and documented.

## Dependency Policy

- Keep `@agentskb/cli` dependency compatible with upstream.
- Prefer pinned semver ranges (e.g. `^0.1.0-beta.8`) to avoid unexpected breakage.
- When upgrading the CLI version:
  - Document why.
  - Validate that the upstream README config still works.

## Upstream Sync Workflow

- Regularly sync from upstream (rebase/merge).
- If a conflict occurs:
  - Preserve upstream behavior first.
  - Reapply fork improvements as opt‑in changes.

## Contribution Rules

Any change must answer:

- "Does upstream still work unchanged?"
- "Can this be proposed upstream as a PR?"

## References

- Upstream repo: `https://github.com/Cranot/agentskb-mcp`
- Fork repo: `https://github.com/Grumpified-OGGVCT/agentskb-mcp`
