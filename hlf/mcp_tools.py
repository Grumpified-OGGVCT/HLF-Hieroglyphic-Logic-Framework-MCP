"""
MCP 2024-2025 Tools implementation for HLF.

Tools are callable functions with JSON Schema input validation.
Each tool has defined inputs, outputs, and error handling.
"""

from dataclasses import dataclass
from typing import Dict, List, Any, Optional
from pathlib import Path
import json
import time
import hashlib
import traceback

# Import metrics
from hlf.mcp_metrics import get_metrics, record_tool_call, record_friction, suggest_improvement

# Try to import from pre-existing HLF, but gracefully fall back
try:
    from hlf.lexer import Lexer
    from hlf.parser import Parser
    HAS_PARSER = True
except ImportError:
    HAS_PARSER = False
    Lexer = None
    Parser = None

try:
    from hlf.compiler.full_compiler import FullCompiler
    HAS_COMPILER = True
except ImportError:
    HAS_COMPILER = False
    FullCompiler = None

try:
    from hlf.vm.vm import VM
    from hlf.vm.bytecode import Bytecode
    HAS_VM = True
except ImportError:
    HAS_VM = False
    VM = None
    Bytecode = None


@dataclass
class ToolDefinition:
    """MCP Tool definition with JSON Schema."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Optional[Dict[str, Any]] = None


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    data: Dict[str, Any]
    errors: List[str]


class HLFToolProvider:
    """
    Provides HLF compilation, execution, and friction logging as MCP Tools.
    
    Tools:
    - hlf_compile: Compile HLF source to bytecode
    - hlf_execute: Execute compiled bytecode
    - hlf_validate: Validate HLF source
    - hlf_friction_log: Log a friction event
    - hlf_self_observe: Emit meta-intent for self-observation
    - hlf_get_version: Get grammar version
    - hlf_compose: Compose multiple HLF programs
    - hlf_decompose: Decompose an HLF program
    - hlf_analyze: Analyze HLF program structure
    - hlf_optimize: Optimize HLF for gas efficiency
    """
    
    def __init__(self, resource_provider, vm_executor=None, friction_drop: Path = None):
        """
        Initialize tool provider.
        
        Args:
            resource_provider: HLFResourceProvider instance
            vm_executor: Optional VM executor for bytecode execution
            friction_drop: Path to friction drop directory
        """
        self.resources = resource_provider
        self.vm = vm_executor
        self.friction_drop = friction_drop or (Path.home() / ".sovereign" / "friction")
        self.friction_drop.mkdir(parents=True, exist_ok=True)
    
    def list_tools(self) -> List[ToolDefinition]:
        """Return all available tools with their schemas."""
        return [
            ToolDefinition(
                name="hlf_compile",
                description="Compile HLF source code to bytecode. Returns base64-encoded bytecode ready for execution.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "HLF source code to compile"
                        },
                        "profile": {
                            "type": "string",
                            "enum": ["P0", "P1", "P2"],
                            "default": "P0",
                            "description": "Resource profile for compilation"
                        },
                        "tier": {
                            "type": "string",
                            "enum": ["forge", "sovereign", "guest"],
                            "default": "forge",
                            "description": "Execution tier"
                        },
                        "strict": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable strict validation"
                        }
                    },
                    "required": ["source"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "bytecode": {"type": "string", "description": "Base64-encoded bytecode"},
                        "gas_estimate": {"type": "integer"},
                        "effects": {"type": "array", "items": {"type": "string"}},
                        "errors": {"type": "array", "items": {"type": "string"}}
                    }
                }
            ),
            ToolDefinition(
                name="hlf_execute",
                description="Execute compiled HLF bytecode on the VM. Returns execution result.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "bytecode": {
                            "type": "string",
                            "description": "Base64-encoded bytecode from hlf_compile"
                        },
                        "gas_limit": {
                            "type": "integer",
                            "default": 100000,
                            "description": "Maximum gas for execution"
                        },
                        "inputs": {
                            "type": "object",
                            "description": "Input values for the program"
                        }
                    },
                    "required": ["bytecode"]
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "result": {"type": "string"},
                        "gas_used": {"type": "integer"},
                        "effects_triggered": {"type": "array"},
                        "errors": {"type": "array"}
                    }
                }
            ),
            ToolDefinition(
                name="hlf_validate",
                description="Validate HLF source for syntax, effects, and gas compliance.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "HLF source to validate"
                        },
                        "strict": {
                            "type": "boolean",
                            "default": True,
                            "description": "Enable strict validation"
                        }
                    },
                    "required": ["source"]
                }
            ),
            ToolDefinition(
                name="hlf_friction_log",
                description="Log a grammar friction event when HLF cannot express an intent. Use this when the language itself lacks the syntax or constructs needed.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source_snippet": {
                            "type": "string",
                            "description": "The HLF snippet that failed or was impossible to express"
                        },
                        "failure_type": {
                            "type": "string",
                            "enum": ["parse", "compile", "effect", "gas", "expression", "type", "semantic"],
                            "description": "Type of friction encountered"
                        },
                        "attempted_intent": {
                            "type": "string",
                            "description": "Natural language description of what was attempted"
                        },
                        "context": {
                            "type": "object",
                            "description": "Additional context (agent metadata, state, etc.)"
                        },
                        "proposed_fix": {
                            "type": "string",
                            "description": "Optional proposed grammar extension"
                        }
                    },
                    "required": ["source_snippet", "failure_type"]
                }
            ),
            ToolDefinition(
                name="hlf_self_observe",
                description="Emit a meta-intent for self-observation (for authorized tiers). This allows agents to log their own execution state for analysis.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "meta_intent": {
                            "type": "object",
                            "description": "The meta-intent to observe",
                            "properties": {
                                "phase": {"type": "string"},
                                "source_hash": {"type": "string"},
                                "gas_used": {"type": "integer"},
                                "profile": {"type": "string"},
                                "notes": {"type": "string"}
                            }
                        },
                        "tier": {
                            "type": "string",
                            "enum": ["forge", "sovereign"],
                            "default": "forge",
                            "description": "Execution tier (must be forge or sovereign)"
                        }
                    },
                    "required": ["meta_intent"]
                }
            ),
            ToolDefinition(
                name="hlf_get_version",
                description="Get current HLF grammar version and checksum.",
                input_schema={"type": "object", "properties": {}}
            ),
            ToolDefinition(
                name="hlf_compose",
                description="Compose multiple HLF programs into a single program.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "programs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "HLF source programs to compose"
                        },
                        "strategy": {
                            "type": "string",
                            "enum": ["sequential", "parallel", "pipeline"],
                            "default": "sequential",
                            "description": "Composition strategy"
                        }
                    },
                    "required": ["programs"]
                }
            ),
            ToolDefinition(
                name="hlf_decompose",
                description="Decompose an HLF program into components for analysis.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "HLF source to decompose"
                        },
                        "granularity": {
                            "type": "string",
                            "enum": ["module", "function", "statement"],
                            "default": "function",
                            "description": "Decomposition granularity"
                        }
                    },
                    "required": ["source"]
                }
            ),
            ToolDefinition(
                name="hlf_analyze",
                description="Analyze HLF program for complexity, effects, and potential issues.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "HLF source to analyze"
                        },
                        "metrics": {
                            "type": "array",
                            "items": {
                                "type": "string",
                                "enum": ["complexity", "effects", "gas_estimate", "dependencies"]
                            },
                            "description": "Metrics to compute"
                        }
                    },
                    "required": ["source"]
                }
            ),
            ToolDefinition(
                name="hlf_optimize",
                description="Optimize HLF source for gas efficiency.",
                input_schema={
                    "type": "object",
                    "properties": {
                        "source": {
                            "type": "string",
                            "description": "HLF source to optimize"
                        },
                        "target": {
                            "type": "string",
                            "enum": ["gas", "memory", "size"],
                            "default": "gas",
                            "description": "Optimization target"
                        }
                    },
                    "required": ["source"]
                }
            )
        ]
    
    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool and return the result."""
        
        tool_handlers = {
            "hlf_compile": self._compile,
            "hlf_execute": self._execute,
            "hlf_validate": self._validate,
            "hlf_friction_log": self._friction_log,
            "hlf_self_observe": self._self_observe,
            "hlf_get_version": self._get_version,
            "hlf_compose": self._compose,
            "hlf_decompose": self._decompose,
            "hlf_analyze": self._analyze,
            "hlf_optimize": self._optimize
        }
        
        if name not in tool_handlers:
            raise ValueError(f"Unknown tool: {name}")
        
        import time
        start_time = time.time()
        
        try:
            result = tool_handlers[name](arguments)
            record_tool_call(name, True, time.time() - start_time)
            return result
        except Exception as e:
            record_tool_call(name, False, time.time() - start_time)
            return {
                "success": False,
                "error": str(e),
                "traceback": traceback.format_exc() if __debug__ else None
            }
    
    def _compile(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Compile HLF source to bytecode."""
        source = args.get("source", "")
        profile = args.get("profile", "P0")
        tier = args.get("tier", "forge")
        strict = args.get("strict", True)
        
        if not source.strip():
            return {
                "success": False,
                "error": "Empty source",
                "bytecode": None,
                "gas_estimate": 0,
                "effects": []
            }
        
        try:
            # Try to use the real compiler if available
            if HAS_PARSER and HAS_COMPILER:
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                
                parser = Parser(tokens)
                ast = parser.parse()
                
                compiler = FullCompiler(profile=profile, tier=tier)
                bytecode_obj = compiler.compile(ast)
                
                return {
                    "success": True,
                    "bytecode": bytecode_obj.to_base64() if hasattr(bytecode_obj, 'to_base64') else base64.b64encode(bytecode_obj.to_bytes()).decode(),
                    "gas_estimate": bytecode_obj.gas_estimate if hasattr(bytecode_obj, 'gas_estimate') else len(tokens) * 5,
                    "effects": self._extract_effects(ast) if hasattr(ast, 'statements') else [],
                    "errors": []
                }
            else:
                # Fallback: estimate bytecode without parsing
                # This is a simulation for when the full compiler is not available
                estimated_gas = self._estimate_gas(source)
                detected_effects = self._detect_effects(source)
                
                # Create a placeholder bytecode
                import base64
                placeholder_bytecode = base64.b64encode(f"# Mock bytecode for: {source[:50]}...".encode()).decode()
                
                return {
                    "success": True,
                    "bytecode": placeholder_bytecode,
                    "gas_estimate": estimated_gas,
                    "effects": detected_effects,
                    "errors": ["Note: Using fallback compiler - full parser not available"]
                }
                
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Syntax error: {e}",
                "bytecode": None,
                "gas_estimate": 0,
                "effects": []
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Compilation failed: {e}",
                "bytecode": None,
                "gas_estimate": 0,
                "effects": []
            }
    
    def _execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute bytecode on the VM."""
        import base64
        
        bytecode_b64 = args.get("bytecode", "")
        gas_limit = args.get("gas_limit", 100000)
        inputs = args.get("inputs", {})
        
        if not bytecode_b64:
            return {
                "success": False,
                "error": "Empty bytecode",
                "result": None,
                "gas_used": 0
            }
        
        try:
            # Try to use the real VM if available
            if HAS_VM:
                bytecode_bytes = base64.b64decode(bytecode_b64)
                bytecode = Bytecode.from_bytes(bytecode_bytes)
                
                vm = VM(bytecode=bytecode, gas_limit=gas_limit)
                
                for key, value in inputs.items():
                    vm.set_variable(key, value)
                
                result = vm.run()
                
                return {
                    "success": True,
                    "result": str(result),
                    "gas_used": vm.gas_used,
                    "effects_triggered": getattr(vm, 'effects_log', [])
                }
            else:
                # Fallback: simulate execution
                # This is a simulation for when the VM is not available
                decoded = base64.b64decode(bytecode_b64).decode('utf-8', errors='ignore')
                
                return {
                    "success": True,
                    "result": f"Simulated execution of {len(decoded)} bytes",
                    "gas_used": min(len(decoded) * 2, gas_limit),
                    "effects_triggered": [],
                    "note": "VM not available - simulation only"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Execution failed: {e}",
                "result": None,
                "gas_used": 0
            }
    
    def _validate(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate HLF source."""
        source = args.get("source", "")
        strict = args.get("strict", True)
        
        errors = []
        warnings = []
        
        if not source.strip():
            return {
                "success": False,
                "errors": ["Empty source"],
                "warnings": []
            }
        
        try:
            if HAS_PARSER:
                lexer = Lexer(source)
                tokens = lexer.tokenize()
                errors.extend(getattr(lexer, 'errors', []))
                
                parser = Parser(tokens)
                ast = parser.parse()
                errors.extend(getattr(parser, 'errors', []))
                warnings.extend(getattr(parser, 'warnings', []))
                
                # Effect validation
                if strict:
                    effect_errors = self._validate_effects_strict(ast, source)
                    errors.extend(effect_errors)
            else:
                # Fallback validation
                errors.extend(self._validate_fallback(source))
            
            return {
                "success": len(errors) == 0,
                "errors": errors,
                "warnings": warnings,
                "ast_summary": {
                    "valid": len(errors) == 0,
                    "module_count": source.count("module"),
                    "function_count": source.count("fn"),
                    "effect_count": sum(1 for e in ["READ_FILE", "WRITE_FILE", "WEB_SEARCH"] if e in source)
                }
            }
            
        except SyntaxError as e:
            return {
                "success": False,
                "errors": [f"Syntax error: {e}"],
                "warnings": []
            }
    
    def _friction_log(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Log a friction event."""
        
        source_snippet = args.get("source_snippet", "")
        failure_type = args.get("failure_type", "expression")
        attempted_intent = args.get("attempted_intent", "")
        context = args.get("context", {})
        proposed_fix = args.get("proposed_fix", "")
        
        # Generate friction ID
        friction_id = hashlib.sha256(
            f"{source_snippet}:{failure_type}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        # Get current grammar version
        version_info = self.resources._get_version_info() if hasattr(self.resources, '_get_version_info') else {"version": "unknown"}
        
        # Build friction report
        friction_report = {
            "id": friction_id,
            "timestamp": time.time(),
            "grammar_version": version_info.get("version", "unknown"),
            "grammar_sha256": version_info.get("grammar_sha256", "unknown"),
            "source_snippet": source_snippet,
            "failure_type": failure_type,
            "attempted_intent": attempted_intent,
            "context": context,
            "proposed_fix": proposed_fix,
            "agent_metadata": {
                "tier": context.get("tier", "unknown"),
                "profile": context.get("profile", "unknown"),
                "hostname": context.get("hostname", "unknown")
            }
        }
        
        # Write to friction drop
        friction_file = self.friction_drop / f"{friction_id}.hlf"
        friction_file.write_text(json.dumps(friction_report, indent=2))
        
        return {
            "success": True,
            "friction_id": friction_id,
            "file": str(friction_file),
            "message": f"Friction logged with ID {friction_id}. The Forge agent will review this."
        }
    
    def _self_observe(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Emit a self-observation meta-intent."""
        meta_intent = args.get("meta_intent", {})
        tier = args.get("tier", "forge")
        
        if tier not in ["forge", "sovereign"]:
            return {
                "success": False,
                "error": "Self-observation requires forge or sovereign tier"
            }
        
        # Generate observation ID
        observe_id = hashlib.sha256(
            f"self_observe:{time.time()}".encode()
        ).hexdigest()[:16]
        
        # Write observation file
        observe_file = self.friction_drop / f"self_observe_{observe_id}.hlf"
        observe_file.write_text(json.dumps({
            "type": "self_observe",
            "timestamp": time.time(),
            "tier": tier,
            "meta_intent": meta_intent
        }, indent=2))
        
        return {
            "success": True,
            "observe_id": observe_id,
            "file": str(observe_file),
            "message": "Self-observation logged"
        }
    
    def _get_version(self, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get current grammar version."""
        if hasattr(self.resources, '_get_version_info'):
            return self.resources._get_version_info()
        return {
            "version": "unknown",
            "grammar_sha256": "unknown",
            "generated_at": time.time()
        }
    
    def _compose(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Compose multiple HLF programs."""
        programs = args.get("programs", [])
        strategy = args.get("strategy", "sequential")
        
        if not programs:
            return {
                "success": False,
                "error": "No programs to compose"
            }
        
        if strategy == "sequential":
            # Sequential composition
            composed_lines = ["# Composed HLF Program (sequential)"]
            composed_lines.append("")
            
            for i, prog in enumerate(programs):
                composed_lines.append(f"# Program {i+1}")
                composed_lines.append(prog)
                composed_lines.append("")
            
            composed = "\n".join(composed_lines)
            
        elif strategy == "parallel":
            # Parallel composition
            composed = "# Composed HLF Program (parallel)\n"
            composed += "parallel {\n"
            for i, prog in enumerate(programs):
                composed += f"  agent_{i}: {prog},\n"
            composed += "}\n"
            
        elif strategy == "pipeline":
            # Pipeline composition
            composed = "# Composed HLF Program (pipeline)\n"
            composed += "pipeline {\n"
            for i, prog in enumerate(programs):
                composed += f"  stage_{i}: {prog}\n"
            composed += "}\n"
        else:
            composed = "\n\n".join(programs)
        
        return {
            "success": True,
            "composed_source": composed,
            "strategy": strategy,
            "program_count": len(programs)
        }
    
    def _decompose(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Decompose an HLF program into components."""
        source = args.get("source", "")
        granularity = args.get("granularity", "function")
        
        if not source.strip():
            return {
                "success": False,
                "error": "Empty source"
            }
        
        components = []
        
        # Simple text-based decomposition
        lines = source.strip().split("\n")
        
        if granularity == "module":
            # Find module definitions
            for line in lines:
                if line.strip().startswith("module"):
                    components.append({
                        "type": "module",
                        "source": line,
                        "line": lines.index(line) + 1
                    })
                    
        elif granularity == "function":
            # Find function definitions
            for i, line in enumerate(lines):
                if line.strip().startswith("fn "):
                    # Collect the whole function
                    func_lines = [line]
                    brace_count = line.count("{") - line.count("}")
                    j = i + 1
                    while j < len(lines) and brace_count > 0:
                        func_lines.append(lines[j])
                        brace_count += lines[j].count("{") - lines[j].count("}")
                        j += 1
                    components.append({
                        "type": "function",
                        "source": "\n".join(func_lines),
                        "line": i + 1
                    })
                    
        elif granularity == "statement":
            # Find statements
            for line in lines:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    components.append({
                        "type": "statement",
                        "source": stripped,
                        "kind": self._classify_statement(stripped)
                    })
        
        return {
            "success": True,
            "components": components,
            "granularity": granularity,
            "total_count": len(components)
        }
    
    def _analyze(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze HLF program for complexity, effects, and potential issues."""
        source = args.get("source", "")
        metrics = args.get("metrics", ["complexity", "effects", "gas_estimate"])
        
        if not source.strip():
            return {
                "success": False,
                "error": "Empty source"
            }
        
        results = {
            "success": True,
            "metrics": {}
        }
        
        lines = source.strip().split("\n")
        
        if "complexity" in metrics:
            # Compute complexity
            results["metrics"]["complexity"] = {
                "lines": len(lines),
                "modules": source.count("module"),
                "functions": source.count("fn "),
                "branches": source.count("if ") + source.count("else"),
                "loops": source.count("loop") + source.count("while "),
                "cyclomatic": 1 + source.count("if ") + source.count("loop") + source.count("while ")
            }
        
        if "effects" in metrics:
            # Detect effects
            effect_keywords = {
                "READ_FILE": ["READ_FILE", "read_file"],
                "WRITE_FILE": ["WRITE_FILE", "write_file"],
                "WEB_SEARCH": ["WEB_SEARCH", "web_search"],
                "STRUCTURED_OUTPUT": ["STRUCTURED_OUTPUT", "structured_output"],
                "SELF_OBSERVE": ["SELF_OBSERVE", "self_observe"]
            }
            
            detected_effects = []
            for effect, keywords in effect_keywords.items():
                for kw in keywords:
                    if kw in source:
                        detected_effects.append(effect)
                        break
            
            results["metrics"]["effects"] = detected_effects
        
        if "gas_estimate" in metrics:
            # Estimate gas
            base_gas = len(lines)
            call_gas = source.count("(") * 5
            alloc_gas = source.count("alloc") * 10
            
            results["metrics"]["gas_estimate"] = {
                "base": base_gas,
                "calls": call_gas,
                "allocations": alloc_gas,
                "total": base_gas + call_gas + alloc_gas
            }
        
        if "dependencies" in metrics:
            # Find dependencies
            import_lines = [l for l in lines if l.strip().startswith("import")]
            dependencies = [l.split()[1] if len(l.split()) > 1 else "unknown" for l in import_lines]
            results["metrics"]["dependencies"] = dependencies
        
        return results
    
    def _optimize(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize HLF source for gas efficiency."""
        source = args.get("source", "")
        target = args.get("target", "gas")
        
        if not source.strip():
            return {
                "success": False,
                "error": "Empty source"
            }
        
        # Simple optimizations
        optimized = source
        
        # Remove redundant whitespace
        optimized = "\n".join(line.rstrip() for line in optimized.split("\n"))
        
        # Simplify common patterns (gas optimization)
        # This is a placeholder - real optimization would parse the AST
        
        results = {
            "success": True,
            "original": source,
            "optimized": optimized,
            "target": target,
            "savings_estimate": {
                "gas": len(source) - len(optimized),  # Rough estimate
                "bytes": len(source.encode()) - len(optimized.encode())
            }
        }
        
        return results
    
    def _estimate_gas(self, source: str) -> int:
        """Estimate gas for a source without full parsing."""
        lines = source.strip().split("\n")
        gas = 0
        
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            
            # Basic gas estimation
            gas += stripped.count("(") * 5  # Function calls
            gas += stripped.count("=") * 1  # Assignments
            gas += stripped.count("if") * 2  # Branches
            gas += stripped.count("loop") * 10  # Loops
            gas += 1  # Base opcode
        
        return max(gas, len(lines) * 2)
    
    def _detect_effects(self, source: str) -> List[str]:
        """Detect effects used in source."""
        effects = []
        effect_patterns = {
            "READ_FILE": ["READ_FILE", "read_file", "read("],
            "WRITE_FILE": ["WRITE_FILE", "write_file", "write("],
            "WEB_SEARCH": ["WEB_SEARCH", "web_search"],
            "STRUCTURED_OUTPUT": ["STRUCTURED_OUTPUT", "structured_output"],
            "SELF_OBSERVE": ["SELF_OBSERVE", "self_observe"]
        }
        
        for effect, patterns in effect_patterns.items():
            for pattern in patterns:
                if pattern in source:
                    effects.append(effect)
                    break
        
        return effects
    
    def _extract_effects(self, ast) -> List[str]:
        """Extract declared effects from AST."""
        effects = []
        # Walk the AST and find effect annotations
        if hasattr(ast, 'statements'):
            for stmt in ast.statements:
                if hasattr(stmt, 'effects'):
                    effects.extend(stmt.effects)
        return list(set(effects))
    
    def _validate_effects_strict(self, ast, source: str) -> List[str]:
        """Validate that declared effects are allowed."""
        errors = []
        # This would check tier permissions
        detected = self._detect_effects(source)
        declared = self._extract_effects(ast) if ast else []
        
        # Check for undeclared effects
        for effect in detected:
            if effect not in declared:
                errors.append(f"Effect {effect} used but not declared")
        
        return errors
    
    def _validate_fallback(self, source: str) -> List[str]:
        """Fallback validation when parser is not available."""
        errors = []
        
        # Check for basic structure
        if "module" not in source and "fn " in source:
            errors.append("Functions should be inside a module")
        
        # Check for unbalanced braces
        if source.count("{") != source.count("}"):
            errors.append("Unbalanced braces")
        
        # Check for unbalanced parentheses
        if source.count("(") != source.count(")"):
            errors.append("Unbalanced parentheses")
        
        return errors
    
    def _classify_statement(self, line: str) -> str:
        """Classify the type of statement."""
        if line.startswith("fn "):
            return "function_def"
        elif line.startswith("type "):
            return "type_def"
        elif line.startswith("import "):
            return "import"
        elif line.startswith("export "):
            return "export"
        elif " = " in line:
            return "assignment"
        elif line.startswith("ret "):
            return "return"
        elif line.startswith("if "):
            return "branch"
        elif line.startswith("loop") or line.startswith("while "):
            return "loop"
        else:
            return "expression"