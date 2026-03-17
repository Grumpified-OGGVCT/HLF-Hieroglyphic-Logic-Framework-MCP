"""
Legacy MCP 2024-2025 resources implementation for HLF.

This module is preserved as a compatibility and migration surface.

Canonical product-facing resources now belong to the packaged `hlf_mcp` line,
especially `hlf_mcp/server.py` and `hlf_mcp/hlf/mcp_resources.py`.

Use this module when you need the older resource provider stack for regression
coverage, comparison, or forward-port analysis.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path
import json
import hashlib
import time

# Try to import yaml, fall back gracefully
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    yaml = None


@dataclass
class Resource:
    """MCP Resource definition."""
    uri: str  # e.g., "hlf://grammar"
    name: str
    description: str
    mime_type: str
    content: Optional[str] = None
    blob: Optional[bytes] = None


@dataclass
class ResourceTemplate:
    """MCP Resource Template for parameterized resources."""
    uri_template: str  # e.g., "hlf://programs/{name}"
    name: str
    description: str
    mime_type: str
    parameters: Dict[str, Any]  # JSON Schema


class HLFResourceProvider:
    """Provides legacy HLF grammar, dictionaries, and programs as MCP resources.

    This provider is not the packaged product authority.
    """
    
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.grammar_path = repo_root / "hlf" / "spec" / "core" / "grammar.yaml"
        self.bytecode_path = repo_root / "hlf" / "spec" / "vm" / "bytecode_spec.yaml"
        self.programs_dir = repo_root / "examples"
        self.dictionaries_path = repo_root / "mcp_resources" / "dictionaries.json"
        self.ast_schema_path = repo_root / "hlf" / "spec" / "core" / "ast_schema.json"
        
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
            if not self.ast_schema_path.exists():
                raise FileNotFoundError(f"AST schema not found: {self.ast_schema_path}")
            return Resource(
                uri=uri,
                name="HLF AST Schema",
                description="JSON Schema for AST",
                mime_type="application/schema+json",
                content=self.ast_schema_path.read_text(encoding="utf-8")
            )
        
        # Handle template URIs
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
            raise FileNotFoundError(f"Program not found: {name}")
        
        elif uri.startswith("hlf://profiles/"):
            tier = uri.split("/")[-1]
            profiles_path = self.repo_root / "hlf" / "profiles" / f"{tier.lower()}.json"
            if profiles_path.exists():
                return Resource(
                    uri=uri,
                    name=f"HLF Profile: {tier}",
                    description=f"Profile configuration for {tier}",
                    mime_type="application/json",
                    content=profiles_path.read_text(encoding="utf-8")
                )
            raise FileNotFoundError(f"Profile not found: {tier}")
        
        raise ValueError(f"Unknown resource: {uri}")
    
    def _load_grammar(self) -> str:
        """Load canonical grammar."""
        if self._grammar_cache is None:
            if not self.grammar_path.exists():
                raise FileNotFoundError(f"Grammar not found: {self.grammar_path}")
            self._grammar_cache = self.grammar_path.read_text(encoding="utf-8")
        return self._grammar_cache
    
    def _load_bytecode(self) -> str:
        """Load bytecode specification."""
        if not self.bytecode_path.exists():
            raise FileNotFoundError(f"Bytecode spec not found: {self.bytecode_path}")
        return self.bytecode_path.read_text(encoding="utf-8")
    
    def _load_dictionaries(self) -> str:
        """Load or generate dictionaries."""
        if self._dictionaries_cache is None:
            if self.dictionaries_path.exists():
                self._dictionaries_cache = self.dictionaries_path.read_text(encoding="utf-8")
            else:
                # Generate if missing
                self._dictionaries_cache = json.dumps(
                    self._generate_dictionaries(), indent=2
                )
        return self._dictionaries_cache
    
    def _get_version_info(self) -> Dict[str, Any]:
        """Get version with checksum."""
        grammar_content = self._load_grammar()
        grammar_sha = hashlib.sha256(grammar_content.encode()).hexdigest()
        
        # Parse version from grammar
        version = "0.5.0"  # Default
        if YAML_AVAILABLE:
            try:
                grammar_data = yaml.safe_load(grammar_content)
                version = grammar_data.get("version", version)
            except:
                pass
        
        return {
            "version": version,
            "grammar_sha256": grammar_sha,
            "generated_at": time.time(),
            "spec_version": "MCP-2025-03-26",
            "compatibility": ["MCP-2024-11-05", "MCP-2025-03-26"]
        }
    
    def _generate_dictionaries(self) -> Dict[str, Any]:
        """Generate compression dictionaries from grammar and programs."""
        grammar_content = self._load_grammar()
        
        dictionaries = {
            "version": "0.5.0",
            "generated_at": time.time(),
            "glyph_to_ascii": {},
            "ascii_to_glyph": {},
            "opcode_catalog": {},
            "effect_index": {},
            "pattern_examples": []
        }
        
        # Extract glyph mappings from grammar if YAML available
        if YAML_AVAILABLE:
            try:
                grammar_data = yaml.safe_load(grammar_content)
                
                # Extract version
                dictionaries["version"] = grammar_data.get("version", "0.5.0")
                
                # Extract glyph mappings from surface section
                surface = grammar_data.get("surface", {})
                glyph_surface = surface.get("glyph", {})
                
                if "mappings" in glyph_surface:
                    for category, mappings in glyph_surface["mappings"].items():
                        if isinstance(mappings, dict):
                            for glyph, ascii_form in mappings.items():
                                dictionaries["glyph_to_ascii"][glyph] = ascii_form
                                dictionaries["ascii_to_glyph"][ascii_form] = glyph
                
                # Extract effect index
                effects = grammar_data.get("effects", {})
                for category, effect_list in effects.get("categories", {}).items():
                    if isinstance(effect_list, list):
                        dictionaries["effect_index"][category] = effect_list
            except Exception as e:
                # Fallback to defaults
                pass
        
        # Load bytecode spec if available
        if self.bytecode_path.exists() and YAML_AVAILABLE:
            try:
                bytecode_content = self._load_bytecode()
                bytecode_data = yaml.safe_load(bytecode_content)
                
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
            except:
                pass
        
        # Extract pattern examples from programs directory
        if self.programs_dir.exists():
            for hlf_file in self.programs_dir.glob("**/*.hlf"):
                try:
                    content = hlf_file.read_text(encoding="utf-8")
                    lines = content.strip().split("\n")
                    for line in lines[:20]:  # First 20 lines
                        line = line.strip()
                        if line and any(kw in line for kw in ["module", "fn", "effect", "type", "import"]):
                            dictionaries["pattern_examples"].append({
                                "file": str(hlf_file.relative_to(self.repo_root)),
                                "pattern": line
                            })
                except:
                    pass
        
        # Limit examples
        dictionaries["pattern_examples"] = dictionaries["pattern_examples"][:50]
        
        return dictionaries
    
    def subscribe_resource(self, uri: str, callback=None) -> str:
        """
        Subscribe to resource updates (MCP 2024 feature).
        Returns subscription ID.
        """
        import uuid
        subscription_id = str(uuid.uuid4())[:16]
        # In production, would store callback for file watcher notification
        return subscription_id
    
    def unsubscribe_resource(self, subscription_id: str):
        """Unsubscribe from resource updates."""
        # In production, would remove from subscription registry
        pass
    
    def clear_cache(self):
        """Clear all caches."""
        self._grammar_cache = None
        self._dictionaries_cache = None
        self._version_cache = None