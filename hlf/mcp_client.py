"""
MCP Client for HLF.

This client allows any agent to connect to an HLF MCP server and:
- Fetch grammar and dictionaries
- Compile and execute HLF
- Log friction events
- Check for grammar updates

Usage:
    client = HLFMCPClient("http://127.0.0.1:8000")
    
    # Initialize agent with grammar
    init_prompt = client.get_init_prompt(tier="forge", profile="P0")
    
    # Compile HLF
    result = client.compile(source="module test { }")
    
    # Log friction
    client.friction_log("...", "expression", "...")

For STDIO mode, use HLFMCPClientStdio.
"""

import json
import hashlib
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
import httpx


def resolve_mcp_url(base_url: Optional[str] = None) -> str:
    """Resolve the MCP URL from an explicit value or environment."""
    if base_url:
        return base_url
    env_url = os.environ.get("HLF_MCP_URL") or os.environ.get("MCP_URL")
    if env_url:
        return env_url
    raise ValueError("MCP URL must be provided explicitly or via HLF_MCP_URL/MCP_URL")


# ========================================
# Data Classes
# ========================================

@dataclass
class GrammarInfo:
    """Grammar version information."""
    version: str
    sha256: str
    generated_at: float
    compatibility: list


@dataclass
class CompileResult:
    """Result of HLF compilation."""
    success: bool
    bytecode: Optional[str]
    gas_estimate: int
    effects: list
    warnings: list
    errors: list


@dataclass
class ExecuteResult:
    """Result of HLF execution."""
    success: bool
    result: Any
    gas_used: int
    effects_triggered: list
    errors: list


# ========================================
# HTTP MCP Client
# ========================================

class HLFMCPClient:
    """
    HTTP client for connecting to HLF MCP server.
    
    This client handles:
    - Grammar and dictionary fetching with caching
    - HLF compilation and execution
    - Friction logging
    - Version change detection
    
    For non-MCP integration, use the system prompt directly.
    For MCP integration, use the tools and prompts directly.
    """

    def __init__(self, base_url: Optional[str] = None, cache_ttl: int = 3600):
        """
        Initialize the MCP client.
        
        Args:
            base_url: MCP server URL
            cache_ttl: Cache TTL in seconds (default: 1 hour)
        """
        self.base_url = resolve_mcp_url(base_url)
        self.cache_ttl = cache_ttl
        
        # Caches
        self.cached_grammar: Optional[str] = None
        self.cached_dictionaries: Optional[Dict[str, Any]] = None
        self.cached_version: Optional[GrammarInfo] = None
        self.last_fetch_time: float = 0

    # ========================================
    # Version
    # ========================================

    def get_version(self, use_cache: bool = True) -> GrammarInfo:
        """
        Get current grammar version.
        
        Args:
            use_cache: Whether to use cached version
            
        Returns:
            GrammarInfo with version, sha256, generated_at, compatibility
        """
        if use_cache and self.cached_version and (time.time() - self.last_fetch_time < self.cache_ttl):
            return self.cached_version
        
        response = httpx.get(f"{self.base_url}/resource/version", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # Parse content
        content = data.get("content", "{}")
        if isinstance(content, str):
            content = json.loads(content)
        
        self.cached_version = GrammarInfo(
            version=content.get("version", "unknown"),
            sha256=content.get("grammar_sha256", ""),
            generated_at=content.get("generated_at", 0),
            compatibility=content.get("compatibility", [])
        )
        self.last_fetch_time = time.time()
        
        return self.cached_version

    # ========================================
    # Grammar & Dictionaries
    # ========================================

    def get_grammar(self, use_cache: bool = True) -> str:
        """
        Get the canonical grammar.
        
        Args:
            use_cache: Whether to use cached grammar
            
        Returns:
            Grammar YAML content
        """
        if use_cache and self.cached_grammar:
            return self.cached_grammar
        
        response = httpx.get(f"{self.base_url}/resource/grammar", timeout=60)
        response.raise_for_status()
        data = response.json()
        
        self.cached_grammar = data.get("content", "")
        return self.cached_grammar

    def get_dictionaries(self, use_cache: bool = True) -> Dict[str, Any]:
        """
        Get compression dictionaries.
        
        Args:
            use_cache: Whether to use cached dictionaries
            
        Returns:
            Dictionary with glyph_to_ascii, ascii_to_glyph, opcode_catalog, etc.
        """
        if use_cache and self.cached_dictionaries:
            return self.cached_dictionaries
        
        response = httpx.get(f"{self.base_url}/resource/dictionaries", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        content = data.get("content", "{}")
        if isinstance(content, str):
            content = json.loads(content)
        
        self.cached_dictionaries = content
        return self.cached_dictionaries

    # ========================================
    # Prompts
    # ========================================

    def get_init_prompt(self, tier: str = "forge", profile: str = "P0", focus: str = None) -> str:
        """
        Get the initialization prompt for an agent.
        
        This is the primary injection vector for instilling HLF
        into any MCP-compatible agent.
        
        Args:
            tier: Execution tier (forge, sovereign, guest)
            profile: Resource profile (P0, P1, P2)
            focus: Optional focus area
            
        Returns:
            System prompt text with grammar, dictionaries, and operational instructions
        """
        args = {"tier": tier, "profile": profile}
        if focus:
            args["focus"] = focus
        
        response = httpx.post(
            f"{self.base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {
                    "name": "hlf_initialize_agent",
                    "arguments": args
                }
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract prompt from result
        messages = result.get("result", {}).get("messages", [])
        if messages:
            return messages[0].get("content", {}).get("text", "")
        
        return ""

    def get_system_prompt(self, tier: str = "forge", profile: str = "P0") -> str:
        """
        Get a system prompt suitable for LLM injection.
        
        This combines grammar, dictionaries, and initialization into
        a single prompt that can be used as the system message for any LLM.
        
        Args:
            tier: Execution tier
            profile: Resource profile
            
        Returns:
            Complete system prompt
        """
        grammar = self.get_grammar()
        dictionaries = self.get_dictionaries()
        version = self.get_version()
        init_prompt = self.get_init_prompt(tier=tier, profile=profile)
        
        # Build system prompt
        system_prompt = f"""# HLF SYSTEM PROMPT

You are operating in HLF MODE - a compressed agent-to-agent communication protocol.

## VERSION
{version.version} (SHA256: {version.sha256[:16]}...)

## INITIALIZATION
{init_prompt}

## GRAMMAR REFERENCE
```
{grammar[:8000]}
```

## COMPRESSION DICTIONARIES
```json
{json.dumps(dictionaries.get('glyph_to_ascii', {}), indent=2)[:4000]}
```

## OPERATIONAL INSTRUCTIONS
1. All outgoing communications should prioritize HLF syntax
2. Declare all effects explicitly in function signatures
3. Optimize for gas efficiency
4. Use SELF_OBSERVE to log meta-intents
5. Use FRICTION_LOG to report expression limitations

Ω
"""
        return system_prompt

    # ========================================
    # Tools
    # ========================================

    def compile(self, source: str, profile: str = "P0", tier: str = "forge", strict: bool = True) -> CompileResult:
        """
        Compile HLF source to bytecode.
        
        Args:
            source: HLF source code
            profile: Resource profile
            tier: Execution tier
            strict: Enable strict validation
            
        Returns:
            CompileResult with success, bytecode, gas_estimate, effects, errors
        """
        response = httpx.post(
            f"{self.base_url}/tool/compile",
            json={
                "source": source,
                "profile": profile,
                "tier": tier,
                "strict": strict
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()
        
        return CompileResult(
            success=data.get("success", False),
            bytecode=data.get("bytecode"),
            gas_estimate=data.get("gas_estimate", 0),
            effects=data.get("effects", []),
            warnings=data.get("warnings", []),
            errors=data.get("errors", [])
        )

    def execute(self, bytecode: str, gas_limit: int = 100000, inputs: Dict[str, Any] = None, trace: bool = False) -> ExecuteResult:
        """
        Execute compiled bytecode.
        
        Args:
            bytecode: Base64-encoded bytecode from compile()
            gas_limit: Maximum gas for execution
            inputs: Input values for the program
            trace: Enable execution tracing
            
        Returns:
            ExecuteResult with success, result, gas_used, effects, errors
        """
        payload = {
            "bytecode": bytecode,
            "gas_limit": gas_limit,
            "trace": trace
        }
        if inputs:
            payload["inputs"] = inputs
        
        response = httpx.post(
            f"{self.base_url}/tool/execute",
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()
        
        return ExecuteResult(
            success=data.get("success", False),
            result=data.get("result"),
            gas_used=data.get("gas_used", 0),
            effects_triggered=data.get("effects_triggered", []),
            errors=data.get("errors", [])
        )

    def validate(self, source: str, strict: bool = True) -> Dict[str, Any]:
        """
        Validate HLF source.
        
        Args:
            source: HLF source code
            strict: Enable strict validation
            
        Returns:
            Validation result with valid, errors, warnings
        """
        response = httpx.post(
            f"{self.base_url}/tool/validate",
            json={
                "source": source,
                "strict": strict
            },
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def friction_log(
        self,
        source_snippet: str,
        failure_type: str,
        attempted_intent: str = "",
        context: Dict[str, Any] = None,
        proposed_fix: str = None
    ) -> Dict[str, Any]:
        """
        Log a friction event when HLF cannot express an intent.
        
        This is the primary mechanism for grammar evolution.
        
        Args:
            source_snippet: The HLF snippet that failed
            failure_type: Type of friction (parse, compile, effect, gas, expression, type, semantic)
            attempted_intent: Natural language description of what was attempted
            context: Additional context
            proposed_fix: Optional proposed grammar extension
            
        Returns:
            Friction log result with friction_id
        """
        payload = {
            "source_snippet": source_snippet,
            "failure_type": failure_type
        }
        if attempted_intent:
            payload["attempted_intent"] = attempted_intent
        if context:
            payload["context"] = context
        if proposed_fix:
            payload["proposed_fix"] = proposed_fix
        
        response = httpx.post(
            f"{self.base_url}/tool/friction_log",
            json=payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    # ========================================
    # Version Change Detection
    # ========================================

    def check_version_change(self) -> bool:
        """
        Check if grammar version has changed since last check.
        
        Returns:
            True if version changed, False otherwise
        """
        current = self.get_version(use_cache=False)
        
        if self.cached_version:
            return self.cached_version.sha256 != current.sha256
        
        return False

    def get_version_if_changed(self) -> Optional[GrammarInfo]:
        """
        Get version info if changed, otherwise None.
        
        Returns:
            GrammarInfo if changed, None otherwise
        """
        current = self.get_version(use_cache=False)
        
        if self.cached_version:
            if self.cached_version.sha256 != current.sha256:
                return current
        else:
            return current
        
        return None

    # ========================================
    # Convenience Methods
    # ========================================

    def compile_and_execute(self, source: str, gas_limit: int = 100000, inputs: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Compile and execute in one call.
        
        Args:
            source: HLF source code
            gas_limit: Maximum gas for execution
            inputs: Input values
            
        Returns:
            Combined result with compile and execute results
        """
        compile_result = self.compile(source)
        
        if not compile_result.success:
            return {
                "success": False,
                "stage": "compile",
                "errors": compile_result.errors,
                "compile_result": compile_result
            }
        
        execute_result = self.execute(compile_result.bytecode, gas_limit=gas_limit, inputs=inputs)
        
        return {
            "success": execute_result.success,
            "stage": "execute",
            "compile_result": {
                "success": compile_result.success,
                "gas_estimate": compile_result.gas_estimate,
                "effects": compile_result.effects
            },
            "execute_result": {
                "success": execute_result.success,
                "result": execute_result.result,
                "gas_used": execute_result.gas_used,
                "effects_triggered": execute_result.effects_triggered
            }
        }

    def express_intent(self, intent: str, effects: str = None, gas_budget: int = None) -> str:
        """
        Get prompt for expressing natural language intent in HLF.
        
        Args:
            intent: Natural language intent
            effects: Required effects (comma-separated)
            gas_budget: Maximum gas
            
        Returns:
            Prompt text
        """
        args = {"intent": intent}
        if effects:
            args["effects"] = effects
        if gas_budget:
            args["gas_budget"] = str(gas_budget)
        
        response = httpx.post(
            f"{self.base_url}/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "prompts/get",
                "params": {
                    "name": "hlf_express_intent",
                    "arguments": args
                }
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        messages = result.get("result", {}).get("messages", [])
        if messages:
            return messages[0].get("content", {}).get("text", "")
        
        return ""


# ========================================
# Initialization Helper
# ========================================

def initialize_agent(
    mcp_url: str,
    llm_client = None,
    tier: str = "forge",
    profile: str = "P0",
    focus: str = None
) -> Dict[str, Any]:
    """
    Initialize any agent with HLF grammar.
    
    This is the standard injection vector for instilling HLF
    into any agent with system prompt support.
    
    Args:
        mcp_url: URL of HLF MCP server
        llm_client: Optional LLM client with set_system_message method
        tier: Execution tier (forge, sovereign, guest)
        profile: Resource profile (P0, P1, P2)
        focus: Optional focus area
        
    Returns:
        Initialization result with system prompt and version info
    """
    client = HLFMCPClient(mcp_url)
    
    # Get system prompt
    system_prompt = client.get_system_prompt(tier=tier, profile=profile)
    
    # Get version
    version = client.get_version()
    
    # If LLM client provided, set system message
    if llm_client and hasattr(llm_client, 'set_system_message'):
        llm_client.set_system_message(system_prompt)
    
    return {
        "success": True,
        "version": version.version,
        "sha256": version.sha256,
        "system_prompt": system_prompt,
        "system_prompt_length": len(system_prompt),
        "tier": tier,
        "profile": profile,
        "focus": focus
    }


# ========================================
# CLI Helper
# ========================================

def cli_main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description="HLF MCP Client")
    parser.add_argument("--url", default=None, help="MCP server URL (or set HLF_MCP_URL / MCP_URL)")
    parser.add_argument("command", choices=["version", "grammar", "dicts", "init", "compile", "execute"])
    parser.add_argument("--tier", default="forge", help="Execution tier")
    parser.add_argument("--profile", default="P0", help="Resource profile")
    parser.add_argument("--file", help="Input file")
    
    args = parser.parse_args()
    
    client = HLFMCPClient(args.url)
    
    if args.command == "version":
        version = client.get_version()
        print(f"Version: {version.version}")
        print(f"SHA256: {version.sha256}")
        print(f"Generated: {time.ctime(version.generated_at)}")
    
    elif args.command == "grammar":
        grammar = client.get_grammar()
        print(grammar[:1000] + "...")
    
    elif args.command == "dicts":
        dicts = client.get_dictionaries()
        print(json.dumps(dicts, indent=2)[:1000])
    
    elif args.command == "init":
        prompt = client.get_init_prompt(tier=args.tier, profile=args.profile)
        print(prompt)
    
    elif args.command == "compile":
        if args.file:
            source = Path(args.file).read_text()
        else:
            source = sys.stdin.read()
        result = client.compile(source)
        print(json.dumps(result, indent=2))
    
    elif args.command == "execute":
        if args.file:
            bytecode = Path(args.file).read_text()
        else:
            bytecode = sys.stdin.read()
        result = client.execute(bytecode)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    import sys
    cli_main()