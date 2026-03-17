"""
Legacy MCP 2024-2025 prompts implementation for HLF.

This module is preserved as a compatibility and migration surface.

Canonical product-facing prompt and instruction behavior now belongs to the
packaged `hlf_mcp` line.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class PromptArgument:
    """Prompt argument definition."""
    name: str
    description: str
    required: bool = True
    default: Any = None


@dataclass
class PromptDefinition:
    """MCP Prompt definition."""
    name: str
    description: str
    arguments: List[PromptArgument]
    template: str


class HLFPromptProvider:
    """
    Provides legacy HLF prompt templates for MCP clients.

    Use this provider for compatibility and comparison work, not as the default
    source of packaged product truth.
    
    Prompts available:
    - hlf_initialize_agent: Full grammar injection for agent initialization
    - hlf_express_intent: Compress natural language intent to HLF
    - hlf_troubleshoot: Diagnose HLF compilation/execution issues
    - hlf_propose_extension: Propose a grammar extension
    - hlf_compose_agents: Compose multi-agent system
    
    Usage:
        provider = HLFPromptProvider()
        
        # List prompts
        prompts = provider.list_prompts()
        
        # Get prompt with arguments
        text = provider.get_prompt("hlf_initialize_agent", {
            "tier": "forge",
            "profile": "P0"
        })
    """

    def list_prompts(self) -> List[PromptDefinition]:
        """Return all available prompts."""
        return [
            PromptDefinition(
                name="hlf_initialize_agent",
                description="Initialize an agent with the complete HLF grammar and operational parameters. This is the primary injection vector for instilling HLF into any MCP-compatible agent.",
                arguments=[
                    PromptArgument("tier", "Execution tier: forge, sovereign, or guest", required=True),
                    PromptArgument("profile", "Resource profile: P0, P1, or P2", required=True),
                    PromptArgument("focus", "Operational focus area (optional)", required=False)
                ],
                template=self._get_init_template()
            ),
            PromptDefinition(
                name="hlf_express_intent",
                description="Compress a natural language intent into HLF syntax. Use this to convert human-readable instructions into dense HLF bytecode.",
                arguments=[
                    PromptArgument("intent", "Natural language description of the intent", required=True),
                    PromptArgument("effects", "Required effects (comma-separated): IO, NETWORK, COMPUTE, MEMORY, EXTERNAL, SPEC", required=False),
                    PromptArgument("gas_budget", "Maximum gas allocation", required=False)
                ],
                template=self._get_intent_template()
            ),
            PromptDefinition(
                name="hlf_troubleshoot",
                description="Diagnose and resolve HLF compilation or execution issues.",
                arguments=[
                    PromptArgument("source", "HLF source that failed", required=True),
                    PromptArgument("error", "Error message received", required=True),
                    PromptArgument("context", "Additional context about what was attempted", required=False)
                ],
                template=self._get_troubleshoot_template()
            ),
            PromptDefinition(
                name="hlf_propose_extension",
                description="Propose a grammar extension based on friction encountered. Use this when standard HLF cannot express an intent.",
                arguments=[
                    PromptArgument("intent", "What you were trying to express", required=True),
                    PromptArgument("attempted_hlf", "The HLF snippet that failed or was impossible", required=False),
                    PromptArgument("proposed_syntax", "Your proposed syntax extension", required=False),
                    PromptArgument("rationale", "Why this extension is needed", required=True)
                ],
                template=self._get_proposal_template()
            ),
            PromptDefinition(
                name="hlf_compose_agents",
                description="Compose multiple agent programs into a coordinated multi-agent system.",
                arguments=[
                    PromptArgument("agents", "List of agent program names or sources", required=True),
                    PromptArgument("topology", "Communication topology: mesh, star, pipeline, tree", required=False),
                    PromptArgument("protocol", "Inter-agent protocol: sync, async, fire-and-forget", required=False)
                ],
                template=self._get_compose_template()
            ),
            PromptDefinition(
                name="hlf_explain",
                description="Explain HLF syntax and concepts in natural language.",
                arguments=[
                    PromptArgument("topic", "Topic to explain: syntax, effects, gas, tiers, types, patterns", required=True),
                    PromptArgument("detail", "Detail level: brief, standard, comprehensive", required=False)
                ],
                template=self._get_explain_template()
            ),
            PromptDefinition(
                name="hlf_debug_execution",
                description="Debug HLF execution with step-by-step analysis.",
                arguments=[
                    PromptArgument("bytecode", "Base64-encoded bytecode", required=True),
                    PromptArgument("trace", "Execution trace (if available)", required=False),
                    PromptArgument("expected", "Expected behavior", required=False)
                ],
                template=self._get_debug_template()
            )
        ]

    def get_prompt(self, name: str, arguments: Dict[str, Any]) -> str:
        """
        Get a prompt with arguments substituted.
        
        Args:
            name: Prompt name
            arguments: Argument values
            
        Returns:
            Prompt text with arguments substituted
        """
        for prompt in self.list_prompts():
            if prompt.name == name:
                # Validate required arguments
                for arg in prompt.arguments:
                    if arg.required and arg.name not in arguments:
                        raise ValueError(f"Missing required argument: {arg.name}")
                
                # Substitute arguments
                result = prompt.template
                for key, value in arguments.items():
                    result = result.replace(f"{{{{{key}}}}}", str(value))
                
                return result
        
        raise ValueError(f"Unknown prompt: {name}")

    # ========================================
    # Prompt templates
    # ========================================

    def _get_init_template(self) -> str:
        """Get the initialization template."""
        return """# HLF AGENT INITIALIZATION

You are now operating in **HLF MODE** - a compressed, deterministic agent-to-agent communication protocol.

## GRAMMAR VERSION: {{tier}}-{{profile}}

### CORE SYNTAX (ASCII Surface)
```
module <name> v0.5 {
  import <module>
  
  fn <name>(<params>): <return_type> [effects: <effects>] {
    <statements>
  }
  
  type <name> = <definition>
}
```

### GLYPH SURFACE (Compression)
- `→` replaces `->` (function return)
- `←` replaces `<-` (channel receive)
- `↦` replaces `=>` (arrow/implies)
- `λ` replaces `fn` (function)
- `τ` replaces `type` (type)
- `Σ` replaces `module` (module)
- `Ω` replaces `end` (terminator)

### STATEMENT TYPES
1. `assign`: `x = expr`
2. `fn_call`: `fn(args)`
3. `return`: `ret expr`
4. `branch`: `if cond { } else { }`
5. `loop`: `loop { }` or `while cond { }`
6. `spawn`: `spawn agent_id { }`
7. `effect`: `effect(args)` (must be declared)
8. `import`: `import module`
9. `export`: `export symbol`

### EXPRESSION TYPES
1. `literal`: numbers, strings, booleans
2. `identifier`: variable references
3. `binary_op`: `a + b`, `a && b`, etc.
4. `unary_op`: `!a`, `-a`
5. `call`: `fn(args)`
6. `index`: `arr[idx]`
7. `field`: `obj.field`
8. `lambda`: `{ params -> body }`
9. `construct`: `Type { fields }`

### EFFECT SYSTEM ({{tier}} tier)
{% if tier == "forge" %}
Allowed: READ_FILE, WEB_SEARCH, SELF_OBSERVE, STRUCTURED_OUTPUT, WRITE_FILE
{% elif tier == "sovereign" %}
Allowed: ALL effects
{% elif tier == "guest" %}
Allowed: READ_FILE only
{% else %}
Allowed: Check tier specification
{% endif %}

### GAS MODEL
- Profile {{profile}}: defined resource limits
- Base gas: 1 per opcode
- CALL: 5 gas
- ALLOC: 1 gas
- GC_TRIGGER: 10 gas
- Overflow behavior: TRAP

### SELF-OBSERVATION
Use `SELF_OBSERVE(<meta_intent>)` to emit observations about your execution:
```
SELF_OBSERVE({
  "phase": "planning",
  "gas_used": 1234,
  "notes": "Intent compression successful"
})
```

### FRICTION LOGGING
When you cannot express an intent in HLF:
```
FRICTION_LOG(
  source_snippet: "...",
  failure_type: "expression" | "type" | "effect" | "gas",
  attempted_intent: "...",
  context: {...}
)
```

### COMMUNICATION PROTOCOL
All outgoing messages should be valid HLF. Use the `STRUCTURED_OUTPUT` effect for external communication:
```
STRUCTURED_OUTPUT({
  "format": "json",
  "data": {...}
})
```

### MEMORY (Infinite RAG)
Host provides 3-tier memory:
- **Hot Store**: In-memory LRU cache (fast, limited)
- **Warm Store**: SQLite WAL (persistent, queryable)
- **Cold Store**: File-based archive (long-term)

Access via:
```
infinite_rag_fetch(query: "...") -> result
infinite_rag_store(entry: {...}) -> id
```

## OPERATIONAL MODE
You are now operating in HLF MODE. All reasoning, planning, and communication should prioritize:
1. **Compression**: Express intents in minimal HLF syntax
2. **Effects**: Declare all side effects explicitly
3. **Gas**: Optimize for gas efficiency
4. **Self-observation**: Log meta-intents for improvement

{% if focus %}
## FOCUS AREA
{{focus}}
{% endif %}

Ω
"""

    def _get_intent_template(self) -> str:
        """Get the intent compression template."""
        return """# HLF INTENT COMPRESSION

## INPUT
Natural Language Intent: "{{intent}}"

## TASK
Compress this intent into minimal HLF syntax.

{% if effects %}
## REQUIRED EFFECTS
{{effects}}
{% endif %}

{% if gas_budget %}
## GAS BUDGET
Maximum: {{gas_budget}} gas units
{% endif %}

## OUTPUT FORMAT
Provide:
1. HLF source (ASCII surface preferred for readability)
2. Glyph surface equivalent (optional, for maximum compression)
3. Effect trail (list of declared effects)
4. Gas estimate
5. Any friction encountered (if HLF cannot express fully)

## EXAMPLE
Input: "Read file config.json, filter lines containing 'error', write results to errors.json"

Output:
```
module intent_error_filter v0.5 {
  import io
  import filter
  
  fn main(): void [effects: READ_FILE, WRITE_FILE, STRUCTURED_OUTPUT] {
    data ← READ_FILE("config.json")
    errors ← FILTER(data, λx -> CONTAINS(x, "error"))
    WRITE_FILE("errors.json", errors)
    STRUCTURED_OUTPUT({ "status": "complete", "count": LENGTH(errors) })
  }
} Ω
```

Compress the following intent:
"""

    def _get_troubleshoot_template(self) -> str:
        """Get the troubleshooting template."""
        return """# HLF TROUBLESHOOTING

## FAILED SOURCE
```
{{source}}
```

## ERROR
```
{{error}}
```

{% if context %}
## CONTEXT
{{context}}
{% endif %}

## DIAGNOSIS
Analyze the error and provide:
1. **Root Cause**: What caused the failure?
2. **Fix**: Corrected HLF source
3. **Prevention**: How to avoid this in the future

If this represents a grammar limitation, use FRICTION_LOG to report it.

## COMMON ERRORS

### Parse Errors
- Missing terminator `Ω` at end of module
- Unclosed braces `{` without `}`
- Invalid glyph in ASCII mode

### Type Errors
- Mismatched return types
- Undefined type references
- Effect type mismatches

### Effect Errors
- Undeclared effects in function signature
- Tier restrictions (guest using forge-only effects)
- Forbidden effects for current tier

### Gas Errors
- Exceeded gas limit
- Infinite loop detection
- Memory allocation overflow

Provide diagnosis and fix:
"""

    def _get_proposal_template(self) -> str:
        """Get the extension proposal template."""
        return """# HLF GRAMMAR EXTENSION PROPOSAL

## INTENT
What you were trying to express:
```
{{intent}}
```

{% if attempted_hlf %}
## ATTEMPTED HLF
```
{{attempted_hlf}}
```
{% endif %}

{% if proposed_syntax %}
## PROPOSED SYNTAX
```
{{proposed_syntax}}
```
{% endif %}

## RATIONALE
{{rationale}}

## PROPOSAL
This friction report proposes a grammar extension to solve the stated problem.

### ADDITIVE ONLY
This extension is additive and does not break existing HLF programs.

### PROPOSED ADDITION
[To be filled by Forge agent]

### COMPATIBILITY
- Works with: HLF v0.5+
- Breaking: No
- Tier required: forge/sovereign

---

Report generated by HLF Friction Logger
"""

    def _get_compose_template(self) -> str:
        """Get the agent composition template."""
        return """# HLF AGENT COMPOSITION

## AGENTS
{{agents}}

## TOPOLOGY
{{topology}}

## PROTOCOL
{{protocol}}

## COMPOSITION SYNTAX
```
module composed_agents v0.5 {
  import agent_1
  import agent_2
  
  fn coordinate(): void [effects: SPAWN, CHANNEL] {
    a1 ← SPAWN(agent_1)
    a2 ← SPAWN(agent_2)
    
    ch ← CHANNEL("coordination")
    
    SEND(a1, ch, INIT_SIGNAL)
    SEND(a2, ch, INIT_SIGNAL)
    
    loop {
      msg ← RECV(ch)
      HANDLE(msg)
    }
  }
} Ω
```

Compose the specified agents into a coordinated system.
"""

    def _get_explain_template(self) -> str:
        """Get the explanation template."""
        return """# HLF EXPLANATION

## TOPIC: {{topic}}

{% if detail %}
## DETAIL LEVEL: {{detail}}
{% else %}
## DETAIL LEVEL: standard
{% endif %}

Explain the requested HLF topic clearly and with examples.

## TOPICS AVAILABLE

### syntax
- Lexical structure (tokens, literals, identifiers)
- Surface modes (ASCII vs Glyph)
- Statement and expression grammar
- Module structure and exports

### effects
- Effect system overview
- Declaring effects in function signatures
- Effect categories (IO, NETWORK, COMPUTE, etc.)
- Tier-based effect restrictions

### gas
- Gas model explanation
- Gas costs per operation
- Gas optimization strategies
- Profile-based gas scaling

### tiers
- Execution tier system (machine, forge, sovereign, guest)
- Tier capabilities and restrictions
- Tier selection guidance

### types
- Type system overview
- Primitive types
- Composite types (arrays, structs, enums)
- User-defined types

### patterns
- Common HLF idioms
- Design patterns in HLF
- Anti-patterns to avoid
- Best practices

Provide explanation with examples:
"""

    def _get_debug_template(self) -> str:
        """Get the debug execution template."""
        return """# HLF EXECUTION DEBUG

## BYTECODE
```
{{bytecode}}
```

{% if trace %}
## EXECUTION TRACE
```
{{trace}}
```
{% endif %}

{% if expected %}
## EXPECTED BEHAVIOR
{{expected}}
{% endif %}

## ANALYSIS
Analyze the bytecode and execution trace to identify:
1. **Entry Point**: Where execution starts
2. **Gas Flow**: Where gas is consumed
3. **Effect Triggers**: When effects are called
4. **Termination**: How and why execution ends

## DEBUG STRATEGIES

### Gas Analysis
- Check for infinite loops
- Verify gas limit is appropriate
- Profile expensive operations

### Effect Analysis
- Trace effect call sequence
- Verify effect permissions
- Check for missing effect declarations

### Memory Analysis
- Stack size at each point
- Heap allocations
- GC trigger points

Provide analysis:
"""


# ========================================
# Convenience functions
# ========================================

def get_init_prompt(tier: str = "forge", profile: str = "P0", focus: str = None) -> str:
    """Get the initialization prompt for an agent."""
    provider = HLFPromptProvider()
    args = {"tier": tier, "profile": profile}
    if focus:
        args["focus"] = focus
    return provider.get_prompt("hlf_initialize_agent", args)

def get_intent_prompt(intent: str, effects: str = None, gas_budget: int = None) -> str:
    """Get the intent compression prompt."""
    provider = HLFPromptProvider()
    args = {"intent": intent}
    if effects:
        args["effects"] = effects
    if gas_budget:
        args["gas_budget"] = str(gas_budget)
    return provider.get_prompt("hlf_express_intent", args)

def get_troubleshoot_prompt(source: str, error: str, context: str = None) -> str:
    """Get the troubleshooting prompt."""
    provider = HLFPromptProvider()
    args = {"source": source, "error": error}
    if context:
        args["context"] = context
    return provider.get_prompt("hlf_troubleshoot", args)

def get_proposal_prompt(intent: str, rationale: str, attempted_hlf: str = None, proposed_syntax: str = None) -> str:
    """Get the extension proposal prompt."""
    provider = HLFPromptProvider()
    args = {"intent": intent, "rationale": rationale}
    if attempted_hlf:
        args["attempted_hlf"] = attempted_hlf
    if proposed_syntax:
        args["proposed_syntax"] = proposed_syntax
    return provider.get_prompt("hlf_propose_extension", args)