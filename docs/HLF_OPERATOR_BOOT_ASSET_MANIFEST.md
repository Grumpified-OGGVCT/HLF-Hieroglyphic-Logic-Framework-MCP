---
goal: Record placeholder operator boot assets without overstating packaged UI or media maturity
version: 1.0
date_created: 2026-03-20
last_updated: 2026-03-20
owner: GitHub Copilot
status: Draft
tags: [operator, media, bridge, manifest, vscode, accessibility]
---

# HLF Operator Boot Asset Manifest

This manifest records bridge-stage operator boot assets that may exist locally before they are packaged, governed, or wired into the extension-hosted operator workbench.

Use this file to keep asset metadata explicit without claiming that packaged playback, bundled media shipping, or runtime-triggered operator splash behavior already exists.

## Manifest Entries

### Genesis Wave

- `title`: Genesis Wave
- `status`: local-only
- `asset_class`: operator boot asset
- `intended_formats`: short looping audio; optional short splash video derived from the same motif
- `loop_behavior`: brief bounded loop during operator boot or initialization; must remain optional and suppressible
- `fallback_text`: HLF operator surface initializing. Governed bridge state only. No packaged media playback is claimed.
- `future_packaged_location`: `extensions/hlf-vscode/media/operator/genesis-wave/`
- `intended_trigger`: extension-hosted operator workbench boot or attached-server initialization state
- `claim_lane`: bridge-only
- `accessibility_rule`: silent mode and text-only fallback required before any packaged adoption
- `provenance_note`: asset currently exists outside the repository as a local-only concept or draft artifact

## Governance Notes

- Assets listed here are placeholders until provenance, licensing, accessibility, packaging, and trigger semantics are all defined.
- Inclusion in this manifest does not mean the asset is shipped, bundled, or active in any packaged operator surface.
- If an asset later enters the repository, update this manifest together with the relevant operator-surface and multimodal bridge specs.
