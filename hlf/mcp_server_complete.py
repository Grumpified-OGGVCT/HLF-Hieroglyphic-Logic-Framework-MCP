"""
Legacy MCP 2024-2025 Server for HLF.

This module is preserved as a compatibility and reference surface.

Canonical product authority now lives in `hlf_mcp/server.py` and the packaged
`hlf_mcp.hlf.*` implementation line.

Use this module when you explicitly need the older provider stack or legacy test
coverage, not as the default source of present-tense product truth.

This server implements the full MCP specification on the legacy stack:
- Resources (grammar, dictionaries, programs)
- Tools (compile, execute, validate, friction)
- Prompts (initialization, intent compression, troubleshooting)
- Logging (structured logs)
- Roots (accessible directories)
- Sampling (request LLM generation - optional)

The server can run in two modes:
1. STDIO mode (standard MCP transport): python -m hlf.mcp_server_complete --stdio
2. HTTP mode (alternative transport): python -m hlf.mcp_server_complete

Protocol version: MCP-2025-03-26
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime

# Import metrics module (from same directory)
try:
    from hlf.mcp_metrics import get_metrics, handle_metrics_tool, metrics_tools, VERIFIED_METRICS
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

# ========================================
# MCP Protocol Constants
# ========================================

MCP_PROTOCOL_VERSION = "2025-03-26"
MCP_COMPATIBLE_VERSIONS = ["2024-11-05", "2025-03-26"]

# ========================================
# Server Implementation
# ========================================

class MCPServer:
    """
    MCP 2024-2025 compliant server for the legacy HLF stack.

    Prefer `hlf_mcp.server` for current packaged behavior.

    This server provides:
    - Resources: grammar, dictionaries, programs, versions
    - Tools: compile, execute, validate, friction_log, etc.
    - Prompts: initialize_agent, express_intent, troubleshoot, etc.
    - Logging: structured log messages
    - Roots: accessible directories

    Usage:
        server = MCPServer(repo_root, friction_drop)

        # Handle a message
        response = await server.handle_message(message)
    """

    def __init__(self, repo_root: Path, friction_drop: Path = None):
        """
        Initialize the MCP server.
        
        Args:
            repo_root: Path to HLF repository root
            friction_drop: Path to friction drop directory
        """
        self.repo_root = Path(repo_root)
        self.friction_drop = friction_drop or (Path.home() / ".sovereign" / "friction")

        self.friction_drop.mkdir(parents=True, exist_ok=True)
        
        # Import providers
        from hlf.mcp_resources import HLFResourceProvider
        from hlf.mcp_tools import HLFToolProvider
        from hlf.mcp_prompts import HLFPromptProvider
        
        self.resources = HLFResourceProvider(self.repo_root)
        self.tools = HLFToolProvider(self.resources, None, self.friction_drop)
        self.prompts = HLFPromptProvider()
        
        # Server capabilities
        self.capabilities = {
            "resources": {
                "subscribe": True,
                "listChanged": True
            },
            "tools": {},
            "prompts": {},
            "logging": {},
            "roots": {
                "listChanged": True
            }
        }
        
        # Server info
        self.server_info = {
            "name": "hlf-mcp-server",
            "version": "0.5.0",
            "description": "HLF MCP Server - Grammar, Tools, and Prompts for HLF"
        }
        
        # Resource subscriptions
        self._subscriptions: Dict[str, List[str]] = {}
        
        # Logging
        self._log_level = logging.INFO
        self._logger = logging.getLogger("hlf.mcp")

    # ========================================
    # Protocol Lifecycle
    # ========================================

    async def initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle initialize request."""
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": self.capabilities,
            "serverInfo": self.server_info
        }

    async def initialized(self, params: Dict[str, Any]) -> None:
        """Handle initialized notification."""
        self._logger.info("Client initialized")

    # ========================================
    # Resources
    # ========================================

    async def resources_list(self) -> Dict[str, Any]:
        """List all available resources."""
        resources = self.resources.list_resources()
        templates = self.resources.list_resource_templates()
        
        return {
            "resources": [
                {
                    "uri": r.uri,
                    "name": r.name,
                    "description": r.description,
                    "mimeType": r.mime_type
                }
                for r in resources
            ],
            "resourceTemplates": [
                {
                    "uriTemplate": t.uri_template,
                    "name": t.name,
                    "description": t.description,
                    "mimeType": t.mime_type
                }
                for t in templates
            ]
        }

    async def resources_read(self, uri: str) -> Dict[str, Any]:
        """Read a specific resource."""
        resource = self.resources.read_resource(uri)
        
        if resource.content is not None:
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "text": resource.content
                    }
                ]
            }
        elif resource.blob is not None:
            return {
                "contents": [
                    {
                        "uri": uri,
                        "mimeType": resource.mime_type,
                        "blob": resource.blob.hex()
                    }
                ]
            }
        
        raise ValueError(f"Resource has no content: {uri}")

    async def resources_subscribe(self, uri: str, subscription_id: str) -> Dict[str, Any]:
        """Subscribe to resource updates."""
        if uri not in self._subscriptions:
            self._subscriptions[uri] = []
        self._subscriptions[uri].append(subscription_id)
        
        return {
            "subscriptionId": subscription_id,
            "uri": uri
        }

    async def resources_unsubscribe(self, subscription_id: str) -> None:
        """Unsubscribe from resource updates."""
        for uri in self._subscriptions:
            if subscription_id in self._subscriptions[uri]:
                self._subscriptions[uri].remove(subscription_id)

    async def _notify_resource_changed(self, uri: str) -> None:
        """Send notification that a resource changed."""
        # In production, would send to subscribed clients
        self._logger.info(f"Resource changed: {uri}")

    # ========================================
    # Tools
    # ========================================

    async def tools_list(self) -> Dict[str, Any]:
        """List all available tools."""
        tools = self.tools.list_tools()
        
        return {
            "tools": [
                {
                    "name": t.name,
                    "description": t.description,
                    "inputSchema": t.input_schema
                }
                for t in tools
            ]
        }

    async def tools_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool."""
        try:
            result = self.tools.call_tool(name, arguments)
            
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(result, indent=2)
                    }
                ],
                "isError": not result.get("success", True)
            }
        except Exception as e:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps({
                            "success": False,
                            "error": str(e)
                        }, indent=2)
                    }
                ],
                "isError": True
            }

    # ========================================
    # Prompts
    # ========================================

    async def prompts_list(self) -> Dict[str, Any]:
        """List all available prompts."""
        prompts = self.prompts.list_prompts()
        
        return {
            "prompts": [
                {
                    "name": p.name,
                    "description": p.description,
                    "arguments": [
                        {
                            "name": a.name,
                            "description": a.description,
                            "required": a.required
                        }
                        for a in p.arguments
                    ]
                }
                for p in prompts
            ]
        }

    async def prompts_get(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Get a prompt with arguments."""
        try:
            prompt_text = self.prompts.get_prompt(name, arguments)
            
            return {
                "description": f"Prompt {name} with arguments",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": prompt_text
                        }
                    }
                ]
            }
        except Exception as e:
            return {
                "description": f"Error generating prompt",
                "messages": [
                    {
                        "role": "assistant",
                        "content": {
                            "type": "text",
                            "text": f"Error: {str(e)}"
                        }
                    }
                ]
            }

    # ========================================
    # Logging
    # ========================================

    async def logging_set_level(self, level: str) -> None:
        """Set logging level."""
        level_map = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "notice": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL
        }
        self._log_level = level_map.get(level.lower(), logging.INFO)
        self._logger.setLevel(self._log_level)

    # ========================================
    # Roots
    # ========================================

    async def roots_list(self) -> Dict[str, Any]:
        """List accessible roots."""
        return {
            "roots": [
                {
                    "uri": f"file://{self.repo_root / 'examples'}",
                    "name": "HLF Programs"
                },
                {
                    "uri": f"file://{self.friction_drop}",
                    "name": "Friction Drop"
                },
                {
                    "uri": f"file://{self.repo_root / 'hlf' / 'spec'}",
                    "name": "Grammar Specs"
                },
                {
                    "uri": f"file://{self.friction_drop.parent}",
                    "name": "Sovereign Home"
                }
            ]
        }

    # ========================================
    # Sampling (Optional)
    # ========================================

    async def create_message(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Request LLM generation from server.
        This is optional and requires a connected LLM.
        """
        # Would integrate with local LLM if available
        return {
            "content": {
                "type": "text",
                "text": "[HLF MCP Server] Sampling requires connected LLM."
            },
            "model": "hlf-mcp-server",
            "stopReason": "endTurn"
        }

    # ========================================
    # Message Handling
    # ========================================

    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Handle an incoming MCP message.
        
        Args:
            message: JSON-RPC message
            
        Returns:
            Response message or None for notifications
        """
        method = message.get("method")
        params = message.get("params", {})
        request_id = message.get("id")
        
        # Handler mapping
        handlers = {
            "initialize": lambda: self.initialize(params),
            "notifications/initialized": lambda: self.initialized(params),
            "resources/list": lambda: self.resources_list(),
            "resources/read": lambda: self.resources_read(params.get("uri", "")),
            "resources/subscribe": lambda: self.resources_subscribe(params.get("uri", ""), params.get("subscriptionId", "")),
            "resources/unsubscribe": lambda: self.resources_unsubscribe(params.get("subscriptionId", "")),
            "tools/list": lambda: self.tools_list(),
            "tools/call": lambda: self.tools_call(params.get("name", ""), params.get("arguments", {})),
            "prompts/list": lambda: self.prompts_list(),
            "prompts/get": lambda: self.prompts_get(params.get("name", ""), params.get("arguments", {})),
            "logging/setLevel": lambda: self.logging_set_level(params.get("level", "info")),
            "roots/list": lambda: self.roots_list(),
            "sampling/createMessage": lambda: self.create_message(params)
        }
        
        if method in handlers:
            try:
                handler = handlers[method]
                
                result = handler()
                if asyncio.iscoroutine(result):
                    result = await result
                
                if request_id is not None:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result
                    }
                return None  # Notification
                
            except Exception as e:
                self._logger.error(f"Error handling {method}: {e}")
                if request_id is not None:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32000,
                            "message": str(e)
                        }
                    }
                return None
        
        # Method not found
        if request_id is not None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        return None


# ========================================
# STDIO Server (MCP Standard Transport)
# ========================================

async def run_stdio_server(repo_root: Path = None):
    """
    Run MCP server over stdio (standard MCP transport).
    
    This is the standard way MCP servers communicate.
    """
    if repo_root is None:
        repo_root = Path(__file__).parent.parent
    
    friction_drop = Path.home() / ".sovereign" / "friction"
    friction_drop.mkdir(parents=True, exist_ok=True)
    
    server = MCPServer(repo_root, friction_drop)
    
    # Log to stderr
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )
    
    # Handle initialize first
    # Read from stdin, write to stdout
    async for line in sys.stdin:
        try:
            message = json.loads(line)
            response = await server.handle_message(message)
            if response:
                print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal error",
                    "data": str(e)
                }
            }
            print(json.dumps(error_response), flush=True)


# ========================================
# HTTP Server (Alternative Transport)
# ========================================

def create_http_app(repo_root: Path = None):
    """
    Create FastAPI app for HTTP transport.
    
    This provides an alternative to stdio for web-based clients.
    """
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    from fastapi.middleware.cors import CORSMiddleware
    
    if repo_root is None:
        repo_root = Path(__file__).parent.parent
    
    app = FastAPI(
        title="HLF MCP Server",
        description="Model Context Protocol server for HLF Grammar",
        version="0.5.0"
    )
    
    # CORS for web clients
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    friction_drop = Path.home() / ".sovereign" / "friction"
    friction_drop.mkdir(parents=True, exist_ok=True)
    
    server = MCPServer(repo_root, friction_drop)
    
    @app.get("/health")
    async def health():
        return {"status": "healthy", "version": "0.5.0"}
    
    @app.get("/mcp/version")
    async def mcp_version():
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "compatibility": MCP_COMPATIBLE_VERSIONS
        }
    
    @app.post("/mcp")
    async def handle_mcp(message: Dict[str, Any]):
        response = await server.handle_message(message)
        return response or {"status": "notification received"}
    
    @app.get("/resource/grammar")
    async def get_grammar():
        resource = server.resources.read_resource("hlf://grammar")
        return JSONResponse(content={"content": resource.content})
    
    @app.get("/resource/dictionaries")
    async def get_dictionaries():
        resource = server.resources.read_resource("hlf://dictionaries")
        return JSONResponse(content={"content": resource.content})
    
    @app.get("/resource/version")
    async def get_version():
        resource = server.resources.read_resource("hlf://version")
        return JSONResponse(content={"content": resource.content})
    
    @app.get("/resource/{uri:path}")
    async def get_resource(uri: str):
        try:
            resource = server.resources.read_resource(f"hlf://{uri}")
            return JSONResponse(content={"content": resource.content})
        except ValueError as e:
            raise HTTPException(404, str(e))
    
    @app.post("/tool/compile")
    async def compile_hlf(request: Dict[str, Any]):
        result = server.tools.call_tool("hlf_compile", request)
        return JSONResponse(content=result)
    
    @app.post("/tool/execute")
    async def execute_hlf(request: Dict[str, Any]):
        result = server.tools.call_tool("hlf_execute", request)
        return JSONResponse(content=result)
    
    @app.post("/tool/validate")
    async def validate_hlf(request: Dict[str, Any]):
        result = server.tools.call_tool("hlf_validate", request)
        return JSONResponse(content=result)
    
    @app.post("/tool/friction_log")
    async def friction_log(request: Dict[str, Any]):
        result = server.tools.call_tool("hlf_friction_log", request)
        return JSONResponse(content=result)
    
    @app.post("/prompt/{name}")
    async def get_prompt(name: str, arguments: Dict[str, Any]):
        try:
            prompt = server.prompts.get_prompt(name, arguments)
            return JSONResponse(content={"prompt": prompt})
        except ValueError as e:
            raise HTTPException(404, str(e))
    
    return app


# ========================================
# Entry Point
# ========================================

def main():
    """Legacy entry point for the pre-packaged MCP server."""
    import argparse
    
    parser = argparse.ArgumentParser(description="HLF MCP Server")
    parser.add_argument("--stdio", action="store_true", help="Run in stdio mode")
    parser.add_argument("--http", action="store_true", help="Run in HTTP mode")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    parser.add_argument("--host", default="0.0.0.0", help="HTTP host")
    parser.add_argument("--repo", default=None, help="Repository root")
    
    args = parser.parse_args()
    
    repo_root = Path(args.repo) if args.repo else Path(__file__).parent.parent
    
    if args.stdio:
        asyncio.run(run_stdio_server(repo_root))
    elif args.http:
        import uvicorn
        app = create_http_app(repo_root)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        # Default: try stdio, fall back to HTTP
        if sys.stdin.isatty():
            # Interactive terminal, use HTTP
            import uvicorn
            app = create_http_app(repo_root)
            uvicorn.run(app, host=args.host, port=args.port)
        else:
            # Piped input, use stdio
            asyncio.run(run_stdio_server(repo_root))


if __name__ == "__main__":
    main()