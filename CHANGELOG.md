# Changelog

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