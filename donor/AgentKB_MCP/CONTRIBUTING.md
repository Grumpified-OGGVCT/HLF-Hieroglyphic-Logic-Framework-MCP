# Contributing

## Principle

This fork exists to remain compatible with upstream (`Cranot/agentskb-mcp`) while allowing improvements that can be upstreamed.

Read: `FORK_POLICY.md`.

## What We Accept

- Documentation improvements that keep upstream config valid
- Non-breaking enhancements behind opt-in env vars / flags
- Automation that helps keep the fork in sync with upstream

## What We Avoid

- Breaking changes to tool names/meaning
- Changes that require users to change the basic upstream config
- Divergent defaults that make upstream merges painful

## Development

This repo is intentionally minimal; runtime is delegated to the official CLI:

```bash
npm start
```

## Upstreaming

If a change is generally useful and not fork-specific:

1. Open a PR here
2. Once stable, open a PR to upstream (`Cranot/agentskb-mcp`) with the same change
