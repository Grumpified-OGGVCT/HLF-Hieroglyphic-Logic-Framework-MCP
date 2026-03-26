# Changelog

## 2026-03-21

### Packaged Dogfooding Milestone

This checkpoint moves the repo's recursive build-assist story from loosely documented intent to a verified packaged workflow. The packaged `hlf_mcp` server is now the explicit dogfooding entrypoint for VS Code MCP wiring, the HTTP liveness probe has been verified against the packaged runtime, and the current-truth/operator docs have been refreshed around what is actually working now.

Short summary:

> Verified the packaged `hlf_mcp` dogfooding loop, switched local MCP wiring to the packaged entrypoint, and updated the repo's plan/docs to reflect the real milestone boundary.

Included in this pass:

- verified packaged HTTP bring-up with `HLF_TRANSPORT=sse`, `HLF_PORT=8011`, and `GET /health -> 200 OK`
- switched `.vscode/mcp.json` from the legacy compatibility server to the packaged `hlf-mcp` stdio entrypoint
- refreshed `README.md`, `QUICKSTART.md`, `BUILD_GUIDE.md`, `SSOT_HLF_MCP.md`, and operator bridge docs around the bounded recursive build-assist workflow
- updated the governed-build planning surface to record the 2026-03-21 dogfooding checkpoint as real bridge progress rather than implied future work

Proof boundary retained in this release:

- packaged `stdio` remains the primary local dogfooding lane
- packaged HTTP health verification is current truth for bounded transport bring-up only
- stronger remote self-hosting and end-to-end `streamable-http` claims remain gated behind fuller initialize/smoke proof

## 2026-03-19

### Documentation Governance

This release strengthens the repo's recursive-build story by making it explicit, canonical, and easier to read across major documentation surfaces. HLF's current claim remains bounded: the packaged system already supports a local build-assist loop that helps inspect state, summarize regressions, explain intended actions, and preserve audit evidence, while stronger self-hosting claims remain gated behind additional proof.

Short summary:

> Canonicalized the recursive-build story and aligned major docs around one public-safe explanation of HLF's bounded local build-assist loop.

Included in this pass:

- added the canonical recursive-build explainer in `docs/HLF_RECURSIVE_BUILD_STORY.md`
- added the audience-specific editorial guide in `docs/HLF_MESSAGING_LADDER.md`
- aligned `README.md`, `QUICKSTART.md`, and `BUILD_GUIDE.md` to the same bounded build-assist framing
- improved intake-path reachability so readers can find both the canonical explanation and the messaging rules from the front door

Proof boundary retained in this release:

- local, bounded recursive-build assistance is current truth
- `stdio` remains the first credible build-assist lane
- stronger remote `streamable-http` self-hosting claims remain gated by end-to-end MCP proof
