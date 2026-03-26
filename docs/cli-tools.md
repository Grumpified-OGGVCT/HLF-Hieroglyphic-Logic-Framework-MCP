# HLF CLI Tools

Packaged command-line reference for this repository.

This file replaces the drifted upstream CLI page with the commands that actually ship from `pyproject.toml` today. The authoritative entry-point map lives in `[project.scripts]`.

## Installed Commands

| Command | Entry Point | Purpose |
| --- | --- | --- |
| `hlf-mcp` | `hlf_mcp.server:main` | Start the packaged FastMCP server |
| `hlfc` | `hlf_mcp.hlf.compiler:main` | Compile HLF source to JSON AST |
| `hlffmt` | `hlf_mcp.hlf.formatter:main` | Canonicalize HLF source formatting |
| `hlflint` | `hlf_mcp.hlf.linter:main` | Run static analysis over HLF source |
| `hlfrun` | `hlf_mcp.hlf.runtime:main` | Compile, encode, and execute an HLF program |
| `hlfpm` | `hlf_mcp.hlf.hlfpm:main` | Install and manage HLF modules |
| `hlfsh` | `hlf_mcp.hlf.hlfsh:main` | Launch the interactive HLF shell |
| `hlflsp` | `hlf_mcp.hlf.hlflsp:main` | Start the HLF language server |
| `hlftest` | `hlf_mcp.hlf.hlftest:main` | Compile and lint HLF snippets, files, or directories |
| `hlf-evidence` | `hlf_mcp.evidence_query:main` | Query governed weekly evidence artifacts and operator review state |
| `hlf-operator` | `hlf_mcp.operator_cli:main` | Run packaged operator-facing review and governance commands |

Examples below use `uv run`, but the commands also work directly after installing the package.

## `hlf-mcp`

Start the packaged FastMCP server.

```bash
uv run hlf-mcp
HLF_TRANSPORT=sse HLF_PORT=<explicit-port> uv run hlf-mcp
HLF_TRANSPORT=streamable-http HLF_PORT=<explicit-port> uv run hlf-mcp
```

Notes:

- Transport is controlled by `HLF_TRANSPORT`.
- Supported values are `stdio`, `sse`, and `streamable-http`.
- `HLF_HOST` and `HLF_PORT` configure the HTTP transports.
- `HLF_PORT` must be set explicitly for `sse` and `streamable-http`; do not assume a default HTTP port in wrapper docs or launch commands.
- The HTTP wrapper exposes `/health` in addition to the MCP endpoints.

## `hlfc`

Compile an HLF source file and print the JSON AST.

```bash
uv run hlfc fixtures/hello_world.hlf
```

Current behavior:

- Accepts one file path.
- Prints the compiled AST as JSON.
- Exits non-zero on compile failure.

## `hlffmt`

Format HLF source.

```bash
uv run hlffmt fixtures/hello_world.hlf
uv run hlffmt fixtures/hello_world.hlf --check
```

Current flags:

- `--check`: exit with status `1` if the file would be reformatted.

The formatter prints formatted source to stdout; it does not edit files in place.

## `hlflint`

Lint HLF source.

```bash
uv run hlflint fixtures/hello_world.hlf
uv run hlflint fixtures/security_audit.hlf --json
uv run hlflint fixtures/hello_world.hlf --gas-limit 500 --token-limit 40
```

Current flags:

- `--gas-limit`: maximum permitted gas estimate for lint checks.
- `--token-limit`: per-line token budget.
- `--json`: emit diagnostics as JSON.

The command exits non-zero when lint diagnostics include errors.

## `hlfrun`

Compile and execute an HLF program through the bytecode VM.

```bash
uv run hlfrun fixtures/hello_world.hlf
uv run hlfrun fixtures/hello_world.hlf --gas 500 --var name=world
```

Current flags:

- `--gas`: execution gas limit.
- `--var KEY=VALUE`: inject one or more runtime variables.

The command prints the runtime result as JSON and exits non-zero when execution does not finish with `status == "ok"`.

## `hlfpm`

Manage HLF modules.

```bash
uv run hlfpm list
uv run hlfpm install collections@v1.0.0
uv run hlfpm search math
uv run hlfpm freeze
uv run hlfpm update collections
uv run hlfpm uninstall collections
```

Supported subcommands:

- `list`
- `install PACKAGE`
- `uninstall PACKAGE`
- `search QUERY`
- `freeze`
- `update PACKAGE`

Current packaged behavior includes an offline-friendly stub install path when OCI access is unavailable.

## `hlfsh`

Interactive shell for the packaged compiler and linter surfaces.

```bash
uv run hlfsh
uv run hlfsh --gas-limit 500
uv run hlfsh --no-color
```

Built-in shell commands:

| Command | Meaning |
| --- | --- |
| `:help` | Show help |
| `:env` | Show current `SET` bindings |
| `:gas` | Show gas usage summary |
| `:reset` | Clear shell state |
| `:load FILE` | Load and evaluate an HLF file |
| `:ast` | Print the last compiled AST |
| `:lint` | Lint the last input |
| `:quit` | Exit the shell |

## `hlflsp`

Start the HLF language server.

```bash
uv run hlflsp
uv run hlflsp --tcp 2087 --host 127.0.0.1
```

Current flags:

- `--tcp PORT`: run in TCP mode instead of stdio.
- `--host`: host to bind in TCP mode.

## `hlftest`

Compile and lint HLF snippets, files, or directories.

```bash
uv run hlftest fixtures
uv run hlftest fixtures --strict
uv run hlftest fixtures --gas-limit 50
```

Current flags:

- `--strict`: treat lint warnings as failures.
- `--gas-limit N`: record a gas limit for the test runner.

The packaged module also exposes assertion helpers for Python tests:

```python
from hlf_mcp.hlf.hlftest import assert_compiles, assert_lints_clean, assert_gas_under

assert_compiles('[HLF-v3]\nRESULT 0 "ok"\nΩ')
assert_lints_clean('[HLF-v3]\nRESULT 0 "ok"\nΩ')
assert_gas_under('[HLF-v3]\nRESULT 0 "ok"\nΩ', 50)
```

## `hlf-evidence`

Query governed weekly evidence artifacts and inspect operator-facing review details.

```bash
uv run hlf-evidence list --status promoted
uv run hlf-evidence show weekly_demo
uv run hlf-evidence show weekly_demo --json
uv run hlf-evidence summary
```

Supported subcommands:

- `list`
- `show ARTIFACT_ID`
- `decide ARTIFACT_ID`
- `summary`

Current `summary` behavior:

- reports artifact, verification, and distribution counts
- includes persona-review rollups for the recorded weekly artifacts:
	- total artifacts with attached vs normalized-fallback persona contracts
	- owner persona counts
	- pending persona gate count

Current `show` behavior:

- `--json` prints the full stored artifact payload.
- plain `show` prints an operator-oriented summary.
- when a governed review is present, the plain view includes the persona handoff contract:
	- change class
	- owner persona
	- review personas
	- required gates
	- escalation target
	- operator summary
	- handoff template reference

Example plain output shape:

```text
Artifact: weekly_demo
Status: promoted
Source: weekly-code-quality
Generated: 2026-03-19T00:00:00+00:00
Verified: yes
Distribution eligible: yes

Governed review:
	Summary: No governed review contract was attached for weekly-code-quality.
	Severity: info
	Change class: security_sensitive
	Owner persona: sentinel
	Review personas: strategist, steward, cove
	Required gates: strategist_review, sentinel_review, steward_review, cove_review, operator_promotion
	Escalate to: none
	Operator summary: Owner persona sentinel; review personas strategist, steward, cove; required gates strategist_review, sentinel_review, steward_review, cove_review, operator_promotion.
	Handoff template: governance/templates/persona_review_handoff.md
```

## `hlf-operator`

Run packaged operator-facing governance and review surfaces without starting the MCP server.

```bash
uv run hlf-operator weekly-evidence-summary --json
uv run hlf-operator witness-status --json
uv run hlf-operator governed-route --json
uv run hlf-operator instinct-status --json
uv run hlf-operator formal-verifier --json
uv run hlf-operator entropy-anchor --json
uv run hlf-operator approval-review --json
uv run hlf-operator approval-bypass-review --json
uv run hlf-operator persona-review --json
uv run hlf-operator persona-review --artifact-id weekly_demo --json
uv run hlf-operator daemon-transparency --json
```

Current operator-focused subcommands include:

- `weekly-evidence-summary`
- `provenance-summary`
- `witness-status`
- `governed-route`
- `instinct-status`
- `formal-verifier`
- `entropy-anchor`
- `approval-review`
- `approval-bypass-review`
- `persona-review`
- `daemon-transparency`
- `daemon-transparency-report`
- `memory-govern`
- `resource`

Current `provenance-summary` behavior:

- renders the packaged provenance contract summary used by the operator status resources
- includes the shared `persona_contract_summary` rollup used by provenance, witness, and approval-review surfaces
- reports how many weekly artifacts are currently tracked by persona review and how many persona gates remain pending

Current witness-status behavior:

- use `uv run hlf-operator witness-status --json` for the global witness summary
- use `uv run hlf-operator witness-status --subject-agent-id AGENT_ID --json` for a subject-specific view
- both witness resources now include `persona_review_summary`, so trust-state review and persona gate posture share one visible operator contract

Current governed-route behavior:

- use `uv run hlf-operator governed-route --json` for the latest packaged routing trace
- use `uv run hlf-operator governed-route --agent-id AGENT_ID --json` for an agent-scoped route trace
- the named command surfaces the same operator summary, fallback summary, and policy-basis summary used by the route resources

Current instinct-status behavior:

- use `uv run hlf-operator instinct-status --json` for the current mission list
- use `uv run hlf-operator instinct-status --mission-id MISSION_ID --json` for mission-specific lifecycle state
- the packaged resource now summarizes proof state, phase completion, execution coverage, verification posture, CoVE gate state, seal state, and active blockers instead of only dumping raw mission state

Current formal-verifier behavior:

- use `uv run hlf-operator formal-verifier --json` for the packaged formal-verification surface
- the named command exposes solver status plus recent proof events and audit-linked evidence refs without requiring the generic `resource` command

Current entropy-anchor behavior:

- use `uv run hlf-operator entropy-anchor --json` for the packaged drift-review surface
- the named command exposes recent entropy-anchor evaluations, policy actions, similarity thresholds, and audit-linked evidence refs without requiring the generic `resource` command

Current approval-review behavior:

- use `uv run hlf-operator approval-review --json` for the queue summary
- use `uv run hlf-operator approval-review --request-id REQUEST_ID --json` for a single request history
- approval queue resources now include the same `persona_review_summary` rollup surfaced by provenance and witness status, without inventing per-request persona authority

Current `persona-review` behavior:

- without `--artifact-id`, renders the packaged `hlf://status/persona_review` surface
- with `--artifact-id`, renders `hlf://status/persona_review/{artifact_id}`
- reports owner persona counts, review personas, required gates, gate status rollups, and whether each artifact used an attached governed review or a normalized fallback contract

## Related References

- `docs/HLF_REFERENCE.md`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_STDLIB_REFERENCE.md`
