# HLF MCP Build Guide

## Test Results

All 6 basic tests pass:

```
Test 1: MCP Resources... PASS
  - 5 resources available (grammar, bytecode, dictionaries, version, ast-schema)
  - Resource templates for programs and profiles

Test 2: MCP Tools... PASS
  - 10 tools available (compile, execute, validate, friction_log, etc.)
  - Tool schemas validated

Test 3: MCP Prompts... PASS
  - 7 prompts available (initialize_agent, express_intent, etc.)
  - Init prompt: 3017 characters

Test 4: MCP Server... PASS
  - Protocol version: 2024-11-05
  - Capabilities: resources, tools, prompts, logging, roots

Test 5: MCP Client... PASS
  - Base URL: configurable
  - Cache TTL: 3600 seconds

Test 6: MCP Metrics... PASS
  - Metrics stored in: ~/.sovereign/mcp_metrics/stats.json
  - Tracks: total_uses, tool_calls, errors, compilations, executions
```

---

## Quick Start

```bash
# Navigate to project
cd C:\Users\gerry\generic_workspace\HLF_MCP

# Run tests
python run_tests.py

# Start MCP server (HTTP mode)
python -m hlf.mcp_server_complete

# Start MCP server (stdio mode)
python -m hlf.mcp_server_complete --stdio
```

---

## Integration for Existing Agents

### Option 1: MCP Client (Recommended)

```python
from hlf.mcp_client import HLFMCPClient

# Connect to MCP server
client = HLFMCPClient("http://localhost:8000")

# Get system prompt with full grammar
system_prompt = client.get_system_prompt(tier="forge", profile="P0")

# Inject into your agent
your_agent.set_system_message(system_prompt)

# Compile HLF source
result = client.compile(
    source="module test { fn main() { ret 0 } }",
    profile="P0",
    tier="forge"
)

# Execute bytecode
execution = client.execute(
    bytecode=result['bytecode'],
    gas_limit=100000
)

# Validate HLF
validation = client.validate(source="...")

# Log friction (optional)
client.friction_log(
    source_snippet="...",
    failure_type="expression",
    attempted_intent="I wanted to express X"
)
```

### Option 2: Direct Import

```python
# Import directly (no MCP server needed)
from hlf.mcp_resources import HLFResourceProvider
from hlf.mcp_tools import HLFToolProvider
from hlf.mcp_prompts import HLFPromptProvider

# Use locally
resources = HLFResourceProvider(repo_root=Path("."))
grammar = resources.read_resource("hlf://grammar")
dictionaries = resources.read_resource("hlf://dictionaries")
```

### Option 3: HTTP API

```bash
# Get grammar
curl http://localhost:8000/resource/grammar

# Get dictionaries
curl http://localhost:8000/resource/dictionaries

# Compile HLF
curl -X POST http://localhost:8000/tool/compile \
  -H "Content-Type: application/json" \
  -d '{"source": "module test { fn main() { ret 0 } }"}'

# Execute bytecode
curl -X POST http://localhost:8000/tool/execute \
  -H "Content-Type: application/json" \
  -d '{"bytecode": "...", "gas_limit": 100000}'
```

---

## File Structure

```
HLF_MCP/
├── hlf/
│   ├── __init__.py              # Package init (minimal imports)
│   ├── mcp_resources.py         # MCP Resources implementation
│   ├── mcp_tools.py             # MCP Tools implementation
│   ├── mcp_prompts.py           # MCP Prompts implementation
│   ├── mcp_server_complete.py   # Complete MCP server
│   ├── mcp_client.py            # HTTP client for agents
│   ├── mcp_metrics.py           # Usage metrics tracking
│   ├── forge_agent.py           # Friction watcher
│   ├── lexer.py                 # (pre-existing)
│   ├── parser.py                # (pre-existing)
│   ├── ast_nodes.py             # (pre-existing, fixed forward ref)
│   └── ...
├── scripts/
│   ├── gen_dictionary.py        # (TODO) Dictionary generator
│   └── generate_token.py        # (TODO) CI token generator
├── mcp_resources/               # (TODO) Generated resources
│   ├── dictionaries.json
│   └── grammar.md
├── TODO.md                      # Task checklist
├── BUILD_GUIDE.md               # This file
└── run_tests.py                 # Basic test runner
```

---

## MCP Protocol Support

The HLF MCP server implements MCP 2024-11-05 with these capabilities:

| Capability | Status | Description |
|------------|--------|-------------|
| `resources` | ✅ | List/read resources (grammar, dictionaries, etc.) |
| `resources/subscribe` | ✅ | Subscribe to resource changes |
| `tools` | ✅ | List/call tools (compile, execute, etc.) |
| `prompts` | ✅ | List/get prompts (initialize_agent, etc.) |
| `logging` | ✅ | Structured logging |
| `roots` | ✅ | List accessible directories |

### Resources

| URI | Description |
|-----|-------------|
| `hlf://grammar` | Canonical grammar specification |
| `hlf://bytecode` | VM opcode definitions |
| `hlf://dictionaries` | Compression dictionaries |
| `hlf://version` | Version info with SHA256 |
| `hlf://ast-schema` | JSON Schema for AST |

### Tools

| Tool | Description |
|------|-------------|
| `hlf_compile` | Compile HLF source to bytecode |
| `hlf_execute` | Execute bytecode on VM |
| `hlf_validate` | Validate HLF source |
| `hlf_friction_log` | Log friction event |
| `hlf_self_observe` | Emit meta-intent |
| `hlf_get_version` | Get grammar version |
| `hlf_compose` | Compose multiple programs |
| `hlf_decompose` | Decompose program into components |

### Prompts

| Prompt | Description |
|--------|-------------|
| `hlf_initialize_agent` | Initialize agent with grammar |
| `hlf_express_intent` | Compress intent to HLF |
| `hlf_troubleshoot` | Diagnose HLF issues |
| `hlf_propose_extension` | Propose grammar extension |
| `hlf_compose_agents` | Compose multi-agent system |

---

## Metrics and Improvement Suggestions

The MCP tracks usage metrics that agents can query:

```python
from hlf.mcp_metrics import get_metrics, record_tool_call

# Get current metrics
metrics = get_metrics()
print(f"Total uses: {metrics.total_uses}")
print(f"Tool calls: {metrics.tool_calls}")
print(f"Errors: {metrics.errors}")

# Record usage
record_tool_call('hlf_compile', success=True, duration_ms=150)
```

### Improvement Suggestions

Agents can analyze metrics to suggest improvements:

```python
metrics = get_metrics()

# High error rate on compile?
if metrics.errors.get('compile', 0) > metrics.total_uses * 0.1:
    print("SUGGESTION: Review grammar for ambiguity")

# Many friction reports?
if metrics.friction_reports > 5:
    print("SUGGESTION: Review grammar gaps")

# Most-used tools
for tool, count in sorted(metrics.tool_calls.items(), key=lambda x: -x[1])[:5]:
    print(f"TOP TOOL: {tool} ({count} calls)")
```

---

## Remaining Work

See `TODO.md` for the complete task list. Key remaining items:

1. **Dictionary Generator** (`scripts/gen_dictionary.py`)
2. **CI Integration** (GitHub Actions workflows)
3. **Docker** (Dockerfile.mcp, Dockerfile.forge)
4. **Documentation** (Integration docs)

---

## Testing

```bash
# Run all tests
python run_tests.py

# Test specific components
python -c "from hlf.mcp_resources import HLFResourceProvider; print('Resources OK')"
python -c "from hlf.mcp_tools import HLFToolProvider; print('Tools OK')"
python -c "from hlf.mcp_prompts import HLFPromptProvider; print('Prompts OK')"
python -c "from hlf.mcp_server_complete import MCPServer; print('Server OK')"
python -c "from hlf.mcp_client import HLFMCPClient; print('Client OK')"
python -c "from hlf.mcp_metrics import get_metrics; print('Metrics OK')"
```

---

## Ethical Governor Architecture

HLF includes a **core ethical governor** that differentiates it from corporate AI systems:

| Corporate AI | HLF Approach |
|--------------|--------------|
| "We know better than you" | "You're the human, you decide within law" |
| Blocks are mysterious, no appeal | Constraints are documented, transparent |
| We protect you from yourself | We enable you to work safely |
| Research is suspicious | Research is valuable, declare it |
| Trust the AI | Trust the human, verify the AI |

### Core Principles

1. **Language-level safety** — Constraints built into grammar, not external filters
2. **Transparent rules** — No black-box moderation
3. **Human priority** — No "AI nanny"
4. **Legitimate research support** — Red-hat with declarations, not hostility
5. **Self-termination** — System shuts down rather than cause harm

### Implementation Files

```
hlf/ethics/
├── constitution.py      # Constitutional constraints layer
├── termination.py       # Self-termination protocol
├── red_hat.py          # Legitimate security research declarations
├── rogue_detection.py  # Compromised/hallucinating agent detection
└── compliance.py       # Transparent governance interaction
```

### Intent Capsule Tiers

| Tier | Capsabilities | Authorization |
|------|---------------|---------------|
| `sovereign` | Full capability | User-authorized |
| `hearth` | Standard operations | Agent-authorized |
| `forge` | Limited, sandboxed | Program-authorized |

An agent declared as "forge" tier **cannot** perform operations reserved for "sovereign", even if compromised.

### Self-Termination Triggers

- Constitutional violation detected
- Illegal intent detected
- Unauthorized escalation attempt
- Rogue agent signature detected

**See:** `HLF_ETHICAL_GOVERNOR_ARCHITECTURE.md` for full specification.

---

## License

Same as HLF_MCP project.