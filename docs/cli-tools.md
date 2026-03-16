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

Examples below use `uv run`, but the commands also work directly after installing the package.

## `hlf-mcp`

Start the packaged FastMCP server.

```bash
uv run hlf-mcp
HLF_TRANSPORT=sse uv run hlf-mcp
HLF_TRANSPORT=streamable-http HLF_PORT=8000 uv run hlf-mcp
```

Notes:

- Transport is controlled by `HLF_TRANSPORT`.
- Supported values are `stdio`, `sse`, and `streamable-http`.
- `HLF_HOST` and `HLF_PORT` configure the HTTP transports.
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

## Related References

- `docs/HLF_REFERENCE.md`
- `docs/HLF_GRAMMAR_REFERENCE.md`
- `docs/HLF_STDLIB_REFERENCE.md`
