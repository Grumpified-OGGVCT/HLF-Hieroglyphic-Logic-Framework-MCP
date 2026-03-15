"""
Minimal Host-Function Set for HLF P0 Profile

5 essential functions that enable full HLF intelligence:
1. READ_FILE - Read file contents
2. WRITE_FILE - Write file contents
3. WEB_SEARCH - Search web via Ollama Cloud
4. STRUCTURED_OUTPUT - Emit validated JSON
5. SELF_OBSERVE - Emit compiler meta-intent

This set provides:
- Self-observation (READ_FILE + SELF_OBSERVE)
- Coordination (WRITE_FILE + STRUCTURED_OUTPUT)
- External knowledge (WEB_SEARCH)
- Validation (STRUCTURED_OUTPUT)

With zero unnecessary complexity.
"""

import os
import json
import time
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HostFunctionError(Exception):
    """Error executing host function"""
    pass


class FunctionTier(Enum):
    """Security tier for host functions"""
    FORGE = "forge"  # Development/debugging
    SOVEREIGN = "sovereign"  # Production use
    CRITICAL = "critical"  # Requires explicit approval


@dataclass
class FunctionSpec:
    """Specification for a host function"""
    name: str
    args: List[Dict[str, Any]]
    returns: str
    tier: List[str]
    gas: int
    backend: str
    sensitive: bool
    description: str


class MinimalHostFunctions:
    """
    Minimal host-function dispatcher for P0 profile.
    
    Implements 5 essential functions:
    - READ_FILE: Read file system
    - WRITE_FILE: Write file system
    - WEB_SEARCH: Web search via Ollama Cloud
    - STRUCTURED_OUTPUT: JSON validation
    - SELF_OBSERVE: Compiler introspection
    """
    
    # Function specifications
    SPECS = {
        "READ_FILE": FunctionSpec(
            name="READ_FILE",
            args=[{"name": "path", "type": "string", "required": True}],
            returns="string",
            tier=["forge", "sovereign"],
            gas=2,
            backend="file_system",
            sensitive=False,
            description="Read contents of a file"
        ),
        "WRITE_FILE": FunctionSpec(
            name="WRITE_FILE",
            args=[
                {"name": "path", "type": "string", "required": True},
                {"name": "content", "type": "string", "required": True},
                {"name": "mode", "type": "string", "required": False, "default": "w"}
            ],
            returns="string",
            tier=["forge", "sovereign"],
            gas=3,
            backend="file_system",
            sensitive=True,
            description="Write content to a file"
        ),
        "WEB_SEARCH": FunctionSpec(
            name="WEB_SEARCH",
            args=[{"name": "query", "type": "string", "required": True}],
            returns="string",
            tier=["forge", "sovereign"],
            gas=5,
            backend="ollama_web_search",
            sensitive=False,
            description="Search the web via Ollama Cloud"
        ),
        "STRUCTURED_OUTPUT": FunctionSpec(
            name="STRUCTURED_OUTPUT",
            args=[
                {"name": "schema", "type": "object", "required": True},
                {"name": "data", "type": "any", "required": True}
            ],
            returns="boolean",
            tier=["forge", "sovereign"],
            gas=4,
            backend="json_schema_validator",
            sensitive=False,
            description="Validate data against JSON Schema"
        ),
        "SELF_OBSERVE": FunctionSpec(
            name="SELF_OBSERVE",
            args=[{"name": "meta_intent", "type": "object", "required": True}],
            returns="string",
            tier=["forge", "sovereign"],
            gas=1,
            backend="infinite_rag_hot_store",
            sensitive=False,
            description="Emit compiler meta-intent for self-observation"
        ),
    }
    
    def __init__(self, hot_store=None, ollama_gateway=None, allowed_paths: Optional[List[str]] = None):
        """
        Initialize minimal host functions.
        
        Args:
            hot_store: Hot store instance for SELF_OBSERVE
            ollama_gateway: Ollama gateway for WEB_SEARCH
            allowed_paths: List of allowed file paths for READ/WRITE
        """
        self.hot_store = hot_store
        self.ollama_gateway = ollama_gateway
        self.allowed_paths = allowed_paths or ["./data", "./spec", "./logs"]
        self.gas_meter = 0
        self.call_log = []
    
    def call(self, function_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a host function.
        
        Args:
            function_name: Name of function to call
            args: Arguments for the function
            
        Returns:
            Dictionary with 'success', 'result', 'gas_used', and optional 'error'
        """
        start_time = time.time()
        
        # Validate function exists
        if function_name not in self.SPECS:
            return {
                "success": False,
                "error": f"Unknown function: {function_name}",
                "gas_used": 0,
                "latency_ms": 0
            }
        
        spec = self.SPECS[function_name]
        
        # Validate required args
        for arg in spec.args:
            if arg.get("required", True) and arg["name"] not in args:
                return {
                    "success": False,
                    "error": f"Missing required arg: {arg['name']}",
                    "gas_used": 0,
                    "latency_ms": 0
                }
        
        # Apply defaults for optional args
        for arg in spec.args:
            if not arg.get("required", True) and arg["name"] not in args:
                args[arg["name"]] = arg.get("default")
        
        # Execute function
        try:
            handler = getattr(self, f"_handle_{function_name.lower()}")
            result = handler(args)
            
            latency_ms = (time.time() - start_time) * 1000
            self.gas_meter += spec.gas
            
            self.call_log.append({
                "function": function_name,
                "args": {k: v for k, v in args.items() if k != "content"},  # Don't log content
                "timestamp": time.time(),
                "gas": spec.gas,
                "latency_ms": latency_ms
            })
            
            return {
                "success": True,
                "result": result,
                "gas_used": spec.gas,
                "latency_ms": round(latency_ms, 2)
            }
            
        except HostFunctionError as e:
            latency_ms = (time.time() - start_time) * 1000
            return {
                "success": False,
                "error": str(e),
                "gas_used": spec.gas,
                "latency_ms": round(latency_ms, 2)
            }
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(f"Host function {function_name} error: {e}")
            return {
                "success": False,
                "error": f"Internal error: {e}",
                "gas_used": 0,
                "latency_ms": round(latency_ms, 2)
            }
    
    def _validate_path(self, path: str) -> str:
        """Validate and normalize file path"""
        # Normalize path
        path = os.path.normpath(path)
        abs_path = os.path.abspath(path)
        
        # Check if in allowed paths
        for allowed in self.allowed_paths:
            abs_allowed = os.path.abspath(allowed)
            if abs_path.startswith(abs_allowed):
                return abs_path
        
        raise HostFunctionError(f"Path not allowed: {path}")
    
    def _handle_read_file(self, args: Dict[str, Any]) -> str:
        """Handle READ_FILE function"""
        path = self._validate_path(args["path"])
        
        if not os.path.exists(path):
            raise HostFunctionError(f"File not found: {path}")
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except UnicodeDecodeError:
            # Try binary
            with open(path, "rb") as f:
                return f.read().decode("utf-8", errors="replace")
    
    def _handle_write_file(self, args: Dict[str, Any]) -> str:
        """Handle WRITE_FILE function"""
        path = self._validate_path(args["path"])
        content = args["content"]
        mode = args.get("mode", "w")
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        
        return f"Written {len(content)} characters to {path}"
    
    def _handle_web_search(self, args: Dict[str, Any]) -> str:
        """Handle WEB_SEARCH function via Ollama Cloud"""
        query = args["query"]
        
        if not self.ollama_gateway:
            raise HostFunctionError("Ollama gateway not configured for web search")
        
        # Use Ollama Cloud's web search capability
        messages = [
            {
                "role": "system",
                "content": "You are a web search assistant. Search the web for the user's query and return relevant information."
            },
            {"role": "user", "content": f"Search: {query}"}
        ]
        
        # Try structured output first
        schema = {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "url": {"type": "string"},
                            "snippet": {"type": "string"}
                        }
                    }
                }
            }
        }
        
        response = self.ollama_gateway.generate_structured(
            prompt=f"Search the web for: {query}",
            schema=schema
        )
        
        if response.success and response.structured_output:
            results = response.structured_output.get("results", [])
            if results:
                return json.dumps(results, indent=2)
        
        # Fallback to text response
        response = self.ollama_gateway.chat(messages)
        if response.success:
            return response.content
        
        raise HostFunctionError(f"Web search failed: {response.error}")
    
    def _handle_structured_output(self, args: Dict[str, Any]) -> bool:
        """Handle STRUCTURED_OUTPUT function"""
        schema = args["schema"]
        data = args["data"]
        
        try:
            # Use jsonschema if available
            try:
                from jsonschema import validate, ValidationError
                validate(instance=data, schema=schema)
                return True
            except ImportError:
                # Fallback: basic type checking
                return self._basic_schema_validate(data, schema)
        except Exception as e:
            logger.warning(f"Schema validation error: {e}")
            return False
    
    def _basic_schema_validate(self, data: Any, schema: Dict[str, Any]) -> bool:
        """Basic schema validation without jsonschema library"""
        schema_type = schema.get("type")
        
        if schema_type == "object":
            if not isinstance(data, dict):
                return False
            properties = schema.get("properties", {})
            for key, prop_schema in properties.items():
                if key in data:
                    if not self._basic_schema_validate(data[key], prop_schema):
                        return False
            return True
        
        elif schema_type == "array":
            if not isinstance(data, list):
                return False
            items_schema = schema.get("items")
            if items_schema:
                for item in data:
                    if not self._basic_schema_validate(item, items_schema):
                        return False
            return True
        
        elif schema_type == "string":
            return isinstance(data, str)
        
        elif schema_type == "integer":
            return isinstance(data, int)
        
        elif schema_type == "number":
            return isinstance(data, (int, float))
        
        elif schema_type == "boolean":
            return isinstance(data, bool)
        
        return True
    
    def _handle_self_observe(self, args: Dict[str, Any]) -> str:
        """Handle SELF_OBSERVE function"""
        meta_intent = args["meta_intent"]
        
        if not self.hot_store:
            raise HostFunctionError("Hot store not configured for self-observation")
        
        # Add timestamp if not present
        if "timestamp" not in meta_intent:
            meta_intent["timestamp"] = time.time()
        
        # Add profile if not present
        if "profile" not in meta_intent:
            meta_intent["profile"] = os.getenv("HLF_PROFILE", "P0")
        
        key = self.hot_store.add_meta_intent(meta_intent)
        
        return key
    
    def get_gas_used(self) -> int:
        """Get total gas used"""
        return self.gas_meter
    
    def get_call_log(self) -> List[Dict[str, Any]]:
        """Get call history"""
        return self.call_log.copy()
    
    def reset_gas(self):
        """Reset gas meter"""
        self.gas_meter = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Export function specs as dictionary"""
        return {
            name: {
                "name": spec.name,
                "args": spec.args,
                "returns": spec.returns,
                "tier": spec.tier,
                "gas": spec.gas,
                "backend": spec.backend,
                "sensitive": spec.sensitive,
                "description": spec.description
            }
            for name, spec in self.SPECS.items()
        }


# Convenience functions
def create_host_functions(profile: str = "P0", hot_store=None, ollama_gateway=None):
    """
    Create appropriate host functions for profile.
    
    Args:
        profile: "P0", "P1", or "P2"
        hot_store: Hot store instance
        ollama_gateway: Ollama gateway instance
        
    Returns:
        HostFunctions instance
    """
    if profile in ["P0", "P1"]:
        # Minimal set for P0/P1
        return MinimalHostFunctions(
            hot_store=hot_store,
            ollama_gateway=ollama_gateway
        )
    else:
        # P2 would have extended set
        return MinimalHostFunctions(
            hot_store=hot_store,
            ollama_gateway=ollama_gateway
        )
