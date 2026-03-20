# HLF VS Code Bridge

This folder scaffolds the VS Code extension boundary for HLF as a bridge-lane operator shell over the packaged `hlf_mcp/` server.

Current scope:

- managed launch or attach configuration
- transport-aware settings for `stdio`, `sse`, and `streamable-http`
- diagnostics for host, port, endpoint, health, and attach mode
- commands for start, stop, restart, health, diagnostics, and connection-copy
- claim-lane visibility for `current-true`, `bridge-true`, and `vision-true` operator framing
- packaged trust and evidence panels driven by packaged HLF resources and `hlf-operator` during managed local launch
- attached `streamable-http` mode now proxies packaged trust and operator actions through the real MCP session contract; attached `sse` mode still covers diagnostics, health checks, and connection state only

Current non-claims:

- this is not a second HLF implementation line
- this is not a full operator GUI yet
- this document defines the Marketplace publication path, but does not claim the extension is already published there

The packaged Python server remains the implementation authority.

## Claim-Lane Visibility

The extension now surfaces claim-lane context directly in the operator UI:

- `Claim Lanes` tree section in the HLF Operator view
- `HLF: Show Claim-Lane Context` command
- claim-lane overview at the top of the trust panel
- `HLF: Open Claim-Lane Doctrine` command to open `docs/HLF_CLAIM_LANES.md`

Use those surfaces to keep present-tense operator claims exact:

- `current-true`: implemented and validated packaged truth now
- `bridge-true`: bounded convergence work that is real but not full target-state completion
- `vision-true`: north-star doctrine that remains constitutive even when not fully shipped

## Local Validation And Packaging

From `extensions/hlf-vscode/`:

```bash
npm install
npm run validate
npm run package -- --out ../../artifacts/hlf-vscode-local.vsix
```

`npm run package` now runs the acceptance suite before creating the VSIX.

## Offline VSIX Install Flow

Use offline install when you want controlled local distribution without Marketplace publication.

1. Produce a VSIX artifact:

```bash
npm run package -- --out ../../artifacts/hlf-vscode.vsix
```

1. Install it in VS Code with either:

```bash
code --install-extension ../../artifacts/hlf-vscode.vsix
```

or the VS Code command palette action `Extensions: Install from VSIX...`.

1. Reload VS Code and run `HLF: Run First-Run Validation`.

Offline VSIX install is current-true once the package command succeeds locally or in CI.

## Marketplace Publication Flow

Publisher identity in the manifest is currently `grumpified-oggvct`.

Marketplace publication is defined as a bridge-to-release path, not a claim that publication already happened.

Recommended publication flow:

1. Keep local validation green:

```bash
npm run validate
npm run package
```

1. Confirm manifest and docs stay honest:

- publisher remains correct in `package.json`
- claim-lane wording does not upgrade bridge surfaces into shipped authority
- README install steps match the actual package path

1. Publish through the VS Code Marketplace publisher account when release conditions are met:

```bash
npx vsce publish
```

1. After publication, update this README only with claims that are current-true, such as the actual Marketplace availability.

## Publishability Boundary

For this repo, `publishable` means:

- acceptance suite passes locally and in CI
- `vsce package` produces a reproducible VSIX artifact
- publisher identity is explicit
- offline VSIX install path is documented
- Marketplace publication remains opt-in and does not overclaim release state
