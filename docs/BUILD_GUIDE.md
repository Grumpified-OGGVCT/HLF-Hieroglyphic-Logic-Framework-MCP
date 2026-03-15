# HLF MCP Build Guide

Complete implementation guide for the HLF MCP 2024-2025 integration.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    HLF MCP ARCHITECTURE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  MASTER REPO ──CI──▶ MCP SERVER ◀────AGENT A (Claude)          │
│       │                  │                  │                  │
│       │                  ├─────resources────┤                  │
│       │                  │     /grammar      │                  │
│       │                  │     /dictionaries │                  │
│       │                  │     /version     │                  │
│       │                  │                  │                  │
│       │                  ├─────tools────────┤                  │
│       │                  │     /compile     │                  │
│       │                  │     /execute      │                  │
│       │                  │     /friction_log │                  │
│       │                  │                  │                  │
│       │                  └─────prompts──────┘                  │
│       │                            │                            │
│       │                     AGENT B (GPT-4)                    │
│       │                            │                            │
│       │                     AGENT C (Local LLM)                │
│       │                                                         │
│       │   FRICTION DROP                                         │
│       │       │                                                  │
│       │       ▼                                                  │
│       │   FORGE AGENT ──▶ /tool/push_proposal ──▶ PR            │
│       │                                                         │
│       └──▶ MASTER CUSTODIAN ──▶ MERGE ──▶ CI ──▶ UPDATE       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Phase 1: Core MCP Layer

### 1.1 MCP Resources (`hlf/mcp_resources.py`)

Resources are static content that clients can read. The MCP 2024-2025 spec supports:
- `resources/list` - list all resources
- `resources/read` - read a specific resource
- `resources/subscribe` - subscribe to updates (optional)

**Resource URIs:**

| URI | Description | MIME Type |
|-----|-------------|-----------|
| `hlf://grammar` | Canonical grammar | `application/yaml` |
| `hlf://bytecode` | Opcode definitions | `application/yaml` |
| `hlf://dictionaries` | Compression tables | `application/json` |
| `hlf://version` | Version info | `application/json` |
| `hlf://ast-schema` | AST JSON Schema | `application/schema+json` |
| `hlf://programs/{name}` | HLF programs | `text/x-hlf` |
| `hlf://profiles/{tier}` | Profile configs | `application/json` |

**Implementation:**

```python
# hlf/mcp_resources.py

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import yaml
import hashlib
import time

@dataclass
class Resource:
    uri: str
    name: str
    description: str
    mime_type: str
    content: Optional[str] = None
    blob: Optional[bytes] = None

@dataclass
class ResourceTemplate:
    uri_template: str
    name: str
    description: str
    mime_type: str
    parameters: Dict[str, Any]

class HLFResourceProvider:
    """Provides HLF grammar, dictionaries, and programs as MCP Resources."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.grammar_path = repo_root / "hlf" / "spec" / "core" / "grammar.yaml"
        self.bytecode_path = repo_root / "hlf" / "spec" / "vm" / "bytecode_spec.yaml"
        self.programs_dir = repo_root / "examples"
        self.dictionaries_path = repo_root / "mcp_resources" / "dictionaries.json"

        self._grammar_cache = None
        self._dictionaries_cache = None
        self._version_cache = None

    def list_resources(self) -> List[Resource]:
        """Return all available resources."""
        return [
            Resource(
                uri="hlf://grammar",
                name="HLF Grammar Specification",
                description="Canonical HLF v0.5 grammar with lexical rules, surface mappings, type system, effect system, gas model, and tier constraints",
                mime_type="application/yaml"
            ),
            Resource(
                uri="hlf://bytecode",
                name="HLF Bytecode Specification",
                description="VM opcode definitions, operand signatures, gas costs, and effect annotations",
                mime_type="application/yaml"
            ),
            Resource(
                uri="hlf://dictionaries",
                name="HLF Compression Dictionaries",
                description="Glyph-to-ASCII mappings, opcode compression tables, and common patterns",
                mime_type="application/json"
            ),
            Resource(
                uri="hlf://version",
                name="HLF Version Info",
                description="Current grammar version, SHA256 checksum, and generation timestamp",
                mime_type="application/json"
            ),
            Resource(
                uri="hlf://ast-schema",
                name="HLF AST Schema",
                description="JSON Schema for HLF AST validation",
                mime_type="application/schema+json"
            )
        ]

    def list_resource_templates(self) -> List[ResourceTemplate]:
        """Return resource templates for parameterized resources."""
        return [
            ResourceTemplate(
                uri_template="hlf://programs/{name}",
                name="HLF Program",
                description="Load a specific HLF program by name",
                mime_type="text/x-hlf",
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Program name (without .hlf extension)"
                        }
                    },
                    "required": ["name"]
                }
            ),
            ResourceTemplate(
                uri_template="hlf://profiles/{tier}",
                name="HLF Profile",
                description="Load profile configuration by tier (P0, P1, P2)",
                mime_type="application/json",
                parameters={
                    "type": "object",
                    "properties": {
                        "tier": {
                            "type": "string",
                            "enum": ["P0", "P1", "P2"],
                            "description": "Profile tier"
                        }
                    },
                    "required": ["tier"]
                }
            )
        ]

    def read_resource(self, uri: str) -> Resource:
        """Read a specific resource by URI."""

        if uri == "hlf://grammar":
            return Resource(
                uri=uri,
                name="HLF Grammar Specification",
                description="Canonical HLF v0.5 grammar",
                mime_type="application/yaml",
                content=self._load_grammar()
            )

        elif uri == "hlf://bytecode":
            return Resource(
                uri=uri,
                name="HLF Bytecode Specification",
                description="VM opcode definitions",
                mime_type="application/yaml",
                content=self._load_bytecode()
            )

        elif uri == "hlf://dictionaries":
            return Resource(
                uri=uri,
                name="HLF Compression Dictionaries",
                description="Glyph and opcode compression tables",
                mime_type="application/json",
                content=self._load_dictionaries()
            )

        elif uri == "hlf://version":
            return Resource(
                uri=uri,
                name="HLF Version Info",
                description="Version and checksum",
                mime_type="application/json",
                content=json.dumps(self._get_version_info(), indent=2)
            )

        elif uri == "hlf://ast-schema":
            schema_path = self.repo_root / "hlf" / "spec" / "core" / "ast_schema.json"
            return Resource(
                uri=uri,
                name="HLF AST Schema",
                description="JSON Schema for AST",
                mime_type="application/schema+json",
                content=schema_path.read_text(encoding="utf-8")
            )

        elif uri.startswith("hlf://programs/"):
            name = uri.split("/")[-1]
            program_path = self.programs_dir / f"{name}.hlf"
            if program_path.exists():
                return Resource(
                    uri=uri,
                    name=f"HLF Program: {name}",
                    description=f"Program {name}",
                    mime_type="text/x-hlf",
                    content=program_path.read_text(encoding="utf-8")
                )
            raise ValueError(f"Program not found: {name}")

        raise ValueError(f"Unknown resource: {uri}")

    def _load_grammar(self) -> str:
        """Load canonical grammar."""
        if self._grammar_cache is None:
            self._grammar_cache = self.grammar_path.read_text(encoding="utf-8")
        return self._grammar_cache

    def _load_bytecode(self) -> str:
        """Load bytecode specification."""
        return self.bytecode_path.read_text(encoding="utf-8")

    def _load_dictionaries(self) -> str:
        """Load or generate dictionaries."""
        if self._dictionaries_cache is None:
            if self.dictionaries_path.exists():
                self._dictionaries_cache = self.dictionaries_path.read_text(encoding="utf-8")
            else:
                self._dictionaries_cache = json.dumps(
                    self._generate_dictionaries(), indent=2
                )
        return self._dictionaries_cache

    def _get_version_info(self) -> Dict[str, Any]:
        """Get version with checksum."""
        grammar_content = self._load_grammar()
        grammar_sha = hashlib.sha256(grammar_content.encode()).hexdigest()

        grammar_data = yaml.safe_load(grammar_content)
        version = grammar_data.get("version", "unknown")

        return {
            "version": version,
            "grammar_sha256": grammar_sha,
            "generated_at": time.time(),
            "spec_version": "MCP-2025-03-26",
            "compatibility": ["MCP-2024-11-05", "MCP-2025-03-26"]
        }

    def _generate_dictionaries(self) -> Dict[str, Any]:
        """Generate compression dictionaries from grammar and programs."""
        grammar_data = yaml.safe_load(self._load_grammar())

        dictionaries = {
            "version": grammar_data.get("version", "unknown"),
            "generated_at": time.time(),
            "glyph_to_ascii": {},
            "ascii_to_glyph": {},
            "opcode_catalog": {},
            "effect_index": {},
            "pattern_examples": []
        }

        # Extract glyph mappings
        glyph_surface = grammar_data.get("surface", {}).get("glyph", {})
        if "mappings" in glyph_surface:
            for category, mappings in glyph_surface["mappings"].items():
                if isinstance(mappings, dict):
                    for glyph, ascii_form in mappings.items():
                        dictionaries["glyph_to_ascii"][glyph] = ascii_form
                        dictionaries["ascii_to_glyph"][ascii_form] = glyph

        # Extract opcode catalog from bytecode spec
        bytecode_data = yaml.safe_load(self._load_bytecode())
        for category, opcodes in bytecode_data.get("opcodes", {}).items():
            if isinstance(opcodes, list):
                for opcode in opcodes:
                    if isinstance(opcode, dict):
                        name = opcode.get("name")
                        if name:
                            dictionaries["opcode_catalog"][name] = {
                                "category": category,
                                "gas": opcode.get("gas", 1),
                                "operands": opcode.get("operands", []),
                                "effects": opcode.get("effects", [])
                            }

        # Extract effect index
        for category, effects in grammar_data.get("effects", {}).get("categories", {}).items():
            if isinstance(effects, list):
                dictionaries["effect_index"][category] = effects

        # Extract pattern examples from programs
        for hlf_file in self.programs_dir.glob("**/*.hlf"):
            try:
                content = hlf_file.read_text(encoding="utf-8")
                lines = content.strip().split("\n")
                for line in lines[:20]:
                    if "module" in line or "fn" in line or "effect" in line:
                        dictionaries["pattern_examples"].append({
                            "file": str(hlf_file.relative_to(self.repo_root)),
                            "pattern": line.strip()
                        })
            except:
                pass

        dictionaries["pattern_examples"] = dictionaries["pattern_examples"][:50]
        return dictionaries
```

### 1.2 MCP Tools (`hlf/mcp_tools.py`)

Tools are callable functions with JSON Schema input validation.

**Tool Signatures:**

| Tool | Description | Required Params |
|------|-------------|-----------------|
| `hlf_compile` | Compile HLF to bytecode | `source` |
| `hlf_execute` | Execute bytecode | `bytecode` |
| `hlf_validate` | Validate HLF source | `source` |
| `hlf_friction_log` | Log friction event | `source_snippet`, `failure_type` |
| `hlf_self_observe` | Emit meta-intent | `meta_intent` |
| `hlf_get_version` | Get grammar version | (none) |
| `hlf_compose` | Compose programs | `programs` |
| `hlf_decompose` | Decompose program | `source` |

**Implementation:** See `hlf/mcp_tools.py` in implementation files.

### 1.3 MCP Prompts (`hlf/mcp_prompts.py`)

Prompts are templated messages that clients can use.

**Prompt Templates:**

| Prompt | Description | Required Arguments |
|--------|-------------|---------------------|
| `hlf_initialize_agent` | Full grammar injection | `tier`, `profile` |
| `hlf_express_intent` | Compress intent to HLF | `intent` |
| `hlf_troubleshoot` | Diagnose issues | `source`, `error` |
| `hlf_propose_extension` | Propose grammar change | `intent`, `rationale` |
| `hlf_compose_agents` | Multi-agent composition | `agents` |

**Implementation:** See `hlf/mcp_prompts.py` in implementation files.

---

## Phase 2: Dictionary Generator

### 2.1 Script: `scripts/gen_dictionary.py`

This script generates `mcp_resources/dictionaries.json` from the grammar and programs.

```python
#!/usr/bin/env python3
"""Generate dictionaries.json from grammar and HLF programs.

Outputs: mcp_resources/dictionaries.json
"""

import json
import yaml
import hashlib
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GRAMMAR_PATH = REPO / "hlf" / "spec" / "core" / "grammar.yaml"
BYTECODE_PATH = REPO / "hlf" / "spec" / "vm" / "bytecode_spec.yaml"
PROGRAMS_DIR = REPO / "examples"
OUTPUT_PATH = REPO / "mcp_resources" / "dictionaries.json"


def load_grammar() -> dict:
    """Load the canonical grammar."""
    with open(GRAMMAR_PATH) as f:
        return yaml.safe_load(f)


def load_bytecode() -> dict:
    """Load the bytecode specification."""
    with open(BYTECODE_PATH) as f:
        return yaml.safe_load(f)


def extract_glyph_mappings(grammar: dict) -> tuple[dict, dict]:
    """Extract glyph-to-ASCII and ASCII-to-glyph mappings."""
    glyph_to_ascii = {}
    ascii_to_glyph = {}

    surface = grammar.get("surface", {})
    glyph_surface = surface.get("glyph", {})
    mappings = glyph_surface.get("mappings", {})

    for category, items in mappings.items():
        if isinstance(items, dict):
            for glyph, ascii_form in items.items():
                glyph_to_ascii[glyph] = ascii_form
                ascii_to_glyph[ascii_form] = glyph

    return glyph_to_ascii, ascii_to_glyph


def extract_opcode_catalog(bytecode: dict) -> dict:
    """Extract opcode catalog with gas and effects."""
    catalog = {}

    for category, opcodes in bytecode.get("opcodes", {}).items():
        if isinstance(opcodes, list):
            for opcode in opcodes:
                if isinstance(opcode, dict):
                    name = opcode.get("name")
                    if name:
                        catalog[name] = {
                            "category": category,
                            "gas": opcode.get("gas", 1),
                            "operands": opcode.get("operands", []),
                            "effects": opcode.get("effects", [])
                        }

    return catalog


def extract_effect_index(grammar: dict) -> dict:
    """Extract effect categorization."""
    effect_index = {}

    for category, effects in grammar.get("effects", {}).get("categories", {}).items():
        if isinstance(effects, list):
            effect_index[category] = effects

    return effect_index


def extract_patterns(programs_dir: Path, limit: int = 100) -> list:
    """Extract pattern examples from HLF programs."""
    patterns = []

    for hlf_file in programs_dir.glob("**/*.hlf"):
        try:
            content = hlf_file.read_text(encoding="utf-8")
            lines = content.strip().split("\n")

            for line in lines[:30]:  # First 30 lines
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # Extract key patterns
                if any(kw in line for kw in ["module", "fn ", "type ", "effect ", "import ", "export "]):
                    patterns.append({
                        "file": str(hlf_file.relative_to(REPO)),
                        "pattern": line[:200]  # Truncate long lines
                    })

                    if len(patterns) >= limit:
                        return patterns
        except Exception as e:
            print(f"Warning: Could not read {hlf_file}: {e}")

    return patterns


def compute_grammar_sha() -> str:
    """Compute SHA256 of grammar file."""
    content = GRAMMAR_PATH.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode()).hexdigest()


def main():
    """Generate dictionaries.json."""
    print("Loading grammar...")
    grammar = load_grammar()

    print("Loading bytecode spec...")
    bytecode = load_bytecode()

    print("Extracting glyph mappings...")
    glyph_to_ascii, ascii_to_glyph = extract_glyph_mappings(grammar)

    print("Extracting opcode catalog...")
    opcode_catalog = extract_opcode_catalog(bytecode)

    print("Extracting effect index...")
    effect_index = extract_effect_index(grammar)

    print("Extracting patterns...")
    patterns = extract_patterns(PROGRAMS_DIR)

    print("Computing checksum...")
    grammar_sha = compute_grammar_sha()

    dictionaries = {
        "version": grammar.get("version", "unknown"),
        "grammar_sha256": grammar_sha,
        "generated_at": time.time(),
        "generated_by": "gen_dictionary.py",
        "glyph_to_ascii": glyph_to_ascii,
        "ascii_to_glyph": ascii_to_glyph,
        "opcode_catalog": opcode_catalog,
        "effect_index": effect_index,
        "pattern_examples": patterns,
        "statistics": {
            "total_glyphs": len(glyph_to_ascii),
            "total_opcodes": len(opcode_catalog),
            "total_patterns": len(patterns)
        }
    }

    # Ensure output directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Write output
    with open(OUTPUT_PATH, "w") as f:
        json.dump(dictionaries, f, indent=2)

    print(f"Generated {OUTPUT_PATH}")
    print(f"  - {len(glyph_to_ascii)} glyphs")
    print(f"  - {len(opcode_catalog)} opcodes")
    print(f"  - {len(patterns)} patterns")
    print(f"  - SHA256: {grammar_sha[:16]}...")


if __name__ == "__main__":
    main()
```

### 2.2 CI Integration

Add to `.github/workflows/ci.yml`:

```yaml
  generate-dictionaries:
    runs-on: ubuntu-latest
    needs: [grammar-tests]
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync --all-extras --frozen

      - name: Generate dictionaries
        run: python scripts/gen_dictionary.py

      - name: Copy grammar to mcp_resources
        run: |
          mkdir -p mcp_resources
          cp hlf/spec/core/grammar.yaml mcp_resources/grammar.md

      - name: Upload dictionaries artifact
        uses: actions/upload-artifact@v4
        with:
          name: mcp-resources
          path: mcp_resources/
```

---

## Phase 3: Friction Pipeline

### 3.1 Friction Drop Structure

```
~/.sovereign/
├── friction/
│   ├── <friction_id>.hlf          # Friction reports
│   ├── self_observe_<id>.hlf      # Self-observation logs
│   └── processed/
│       └── <friction_id>.processed # Moved after processing
├── grammar/
│   ├── current.yaml               # Active grammar
│   └── history/
│       └── <version>.yaml         # Grammar versions
├── cache/
│   ├── bytecode/                  # Compiled bytecode cache
│   └── dictionaries.json          # Local dictionaries
└── config/
    └── mcp.json                    # MCP client config
```

### 3.2 Host Function: FRICTION_LOG

Add to `hlf/host_functions_minimal.py`:

```python
"FRICTION_LOG": FunctionSpec(
    name="FRICTION_LOG",
    args=[
        {"name": "source_snippet", "type": "string", "required": True},
        {"name": "failure_type", "type": "string", "required": True},
        {"name": "attempted_intent", "type": "string", "required": False},
        {"name": "context", "type": "object", "required": False},
        {"name": "proposed_fix", "type": "string", "required": False}
    ],
    returns="string",
    tier=["forge", "sovereign"],
    gas=1,
    backend="friction_drop",
    sensitive=False,
    description="Log a grammar friction event for Forge review"
)

def _handle_friction_log(self, args):
    """Handle FRICTION_LOG host function."""
    import hashlib
    from pathlib import Path
    import json
    import time

    friction_id = hashlib.sha256(
        f"{args['source_snippet']}:{args['failure_type']}:{time.time()}".encode()
    ).hexdigest()[:16]

    drop_path = Path.home() / ".sovereign" / "friction"
    drop_path.mkdir(parents=True, exist_ok=True)

    friction_file = drop_path / f"{friction_id}.hlf"

    friction_report = {
        "id": friction_id,
        "timestamp": time.time(),
        "grammar_version": self.grammar_version,
        "grammar_sha256": self.grammar_sha256,
        "source_snippet": args["source_snippet"],
        "failure_type": args["failure_type"],
        "attempted_intent": args.get("attempted_intent", ""),
        "context": args.get("context", {}),
        "proposed_fix": args.get("proposed_fix"),
        "agent_metadata": {
            "tier": self.tier,
            "profile": self.profile,
            "hostname": self.hostname
        }
    }

    friction_file.write_text(json.dumps(friction_report, indent=2))

    return friction_id
```

### 3.3 Forge Agent (`hlf/forge_agent.py`)

See full implementation in `hlf/forge_agent.py`.

---

## Phase 4: CI Token Signing

### 4.1 Token Generator (`scripts/generate_token.py`)

```python
#!/usr/bin/env python3
"""Generate HMAC validation tokens for Forge proposals.

This is called by CI after successful test runs.
"""

import os
import time
import hashlib
import hmac
import json
import sys


def generate_token(ci_run_id: str, grammar_sha: str) -> str:
    """Generate a short-lived validation token."""
    secret = os.environ.get("CI_HMAC_SECRET")
    if not secret:
        raise ValueError("CI_HMAC_SECRET not set")

    payload = {
        "ci_run": ci_run_id,
        "grammar_sha": grammar_sha,
        "timestamp": int(time.time()),
        "expiry": int(time.time()) + 3600  # 1 hour
    }

    payload_json = json.dumps(payload, sort_keys=True)
    signature = hmac.new(
        secret.encode(),
        payload_json.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{payload_json}|{signature}"


def validate_token(token: str) -> bool:
    """Validate a token from CI."""
    secret = os.environ.get("CI_HMAC_SECRET")
    if not secret:
        return False

    try:
        payload_json, signature = token.rsplit("|", 1)

        expected = hmac.new(
            secret.encode(),
            payload_json.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            return False

        payload = json.loads(payload_json)

        if payload.get("expiry", 0) < time.time():
            return False

        return True
    except:
        return False


if __name__ == "__main__":
    ci_run_id = sys.argv[1] if len(sys.argv) > 1 else "local"
    grammar_sha = sys.argv[2] if len(sys.argv) > 2 else "unknown"

    token = generate_token(ci_run_id, grammar_sha)
    print(token)
```

---

## Phase 5: Docker Configuration

### 5.1 Dockerfile.mcp

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install uv && uv sync --all-extras --frozen

# Copy HLF source
COPY hlf/ ./hlf/
COPY examples/ ./examples/
COPY scripts/ ./scripts/

# Copy MCP server
COPY hlf/mcp_server_complete.py ./hlf/

# Create directories
RUN mkdir -p /root/.sovereign/friction /app/mcp_resources

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Run
CMD ["python", "-m", "hlf.mcp_server_complete"]
```

### 5.2 Dockerfile.forge

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install uv && uv sync --all-extras --frozen

# Copy HLF source
COPY hlf/ ./hlf/
COPY scripts/ ./scripts/

# Copy Forge agent
COPY hlf/forge_agent.py ./hlf/

# Create directories
RUN mkdir -p /root/.sovereign/friction

# Run
CMD ["python", "-m", "hlf.forge_agent"]
```

### 5.3 docker-compose.yml Updates

```yaml
# Add to existing docker-compose.yml

services:
  # ... existing services ...

  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    ports:
      - "8000:8000"
    volumes:
      - ./hlf:/app/hlf:ro
      - ./examples:/app/examples:ro
      - ./mcp_resources:/app/mcp_resources:ro
      - ./data/friction:/root/.sovereign/friction
      - ./data/cache:/root/.sovereign/cache
    environment:
      - MCP_HMAC_KEY=${MCP_HMAC_KEY:-change-me-in-production}
      - GITHUB_TOKEN=${GITHUB_TOKEN:-}
      - GH_REPO=${GH_REPO:-your-repo/here}
    networks:
      - sovereign-net
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  forge-agent:
    build:
      context: .
      dockerfile: Dockerfile.forge
    volumes:
      - ./data/friction:/root/.sovereign/friction
      - ./hlf:/app/hlf:ro
    environment:
      - FORGE_VALIDATION_TOKEN=${FORGE_VALIDATION_TOKEN:-}
      - MCP_URL=http://mcp-server:8000
      - GH_USER=${GH_USER:-forge-agent}
      - GH_REPO=${GH_REPO:-your-repo/here}
    networks:
      - sovereign-net
    depends_on:
      - mcp-server
    profiles:
      - forge

networks:
  sovereign-net:
    driver: bridge

volumes:
  friction_data:
  cache_data:
```

---

## Phase 6: Usage Guide

### 6.1 For External Agents (MCP Client)

```python
from hlf.mcp_client import HLFMCPClient

# Initialize client
client = HLFMCPClient("http://localhost:8000")

# Get system prompt for your agent
system_prompt = client.get_system_prompt(tier="forge", profile="P0")
your_agent.set_system_message(system_prompt)

# Compile HLF
result = client.compile(
    source="module test { fn main() { ret 0 } }",
    profile="P0",
    tier="forge"
)

if result["success"]:
    bytecode = result["bytecode"]
    
    # Execute
    exec_result = client.execute(bytecode, gas_limit=100000)
    print(f"Result: {exec_result['result']}")
    print(f"Gas used: {exec_result['gas_used']}")

# Report friction
if not result["success"]:
    client.friction_log(
        source_snippet=result["errors"][0],
        failure_type="compile",
        attempted_intent="I wanted to do X",
        proposed_fix="Add new syntax Y"
    )
```

### 6.2 For HTTP API Clients

```bash
# Get grammar
curl http://localhost:8000/resource/grammar

# Get dictionaries
curl http://localhost:8000/resource/dictionaries

# Get version
curl http://localhost:8000/resource/version

# Compile
curl -X POST http://localhost:8000/tool/compile \
  -H "Content-Type: application/json" \
  -d '{"source": "module test { fn main() { ret 0 } }"}'

# Execute
curl -X POST http://localhost:8000/tool/execute \
  -H "Content-Type: application/json" \
  -d '{"bytecode": "...", "gas_limit": 100000}'

# Log friction
curl -X POST http://localhost:8000/tool/friction_log \
  -H "Content-Type: application/json" \
  -d '{"source_snippet": "...", "failure_type": "expression"}'
```

---

## Verification

After implementation, verify:

```bash
# 1. Generate dictionaries
python scripts/gen_dictionary.py

# 2. Start MCP server
python -m hlf.mcp_server_complete

# 3. Test endpoints
curl http://localhost:8000/health
curl http://localhost:8000/resource/grammar | head -20
curl http://localhost:8000/resource/dictionaries | jq '.version'
curl http://localhost:8000/resource/version | jq '.'

# 4. Test tools
curl -X POST http://localhost:8000/tool/compile \
  -H "Content-Type: application/json" \
  -d '{"source": "module test { fn main() { ret 0 } }"}'

# 5. Run tests
python -m pytest tests/

# 6. Build Docker
docker compose build
docker compose up -d mcp-server
curl http://localhost:8000/health
```