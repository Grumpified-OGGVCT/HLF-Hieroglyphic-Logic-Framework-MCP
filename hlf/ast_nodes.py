"""
HLF Abstract Syntax Tree (AST)
Represents parsed HLF programs before compilation
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union

# Base AST node - MUST be defined first
@dataclass
class ASTNode:
    """Base class for all AST nodes"""
    source_pos: Optional[Dict[str, int]] = None  # line, column, offset
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        result = {}
        for key, value in self.__dict__.items():
            if value is None:
                continue
            if isinstance(value, ASTNode):
                result[key] = value.to_dict()
            elif isinstance(value, list):
                result[key] = [
                    item.to_dict() if isinstance(item, ASTNode) else item
                    for item in value
                ]
            elif isinstance(value, dict):
                result[key] = {
                    k: v.to_dict() if isinstance(v, ASTNode) else v
                    for k, v in value.items()
                }
            else:
                result[key] = value
        return result

# Position tracking
@dataclass
class Position:
    """Source code position"""
    line: int = 1
    column: int = 1
    offset: int = 0
    
    def advance(self, char: str = None):
        """Advance position by one character"""
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
    
    def clone(self) -> 'Position':
        """Create a copy of this position"""
        return Position(self.line, self.column)

@dataclass
class Location:
    """Source code location (start and end positions)"""
    start: Position = field(default_factory=Position)
    end: Position = field(default_factory=Position)
    source: Optional[str] = None
    
    def clone(self) -> 'Location':
        """Create a copy of this location"""
        return Location(self.start.clone(), self.end.clone())

# Expressions
@dataclass
class Expression(ASTNode):
    """Base class for all expressions"""
    pass

@dataclass
class Literal(Expression):
    """Literal value: 42, "hello", true"""
    type: str = "Literal"
    value: Union[str, int, float, bool, None] = None

@dataclass
class Identifier(Expression):
    """Identifier: x, myVar, _private"""
    type: str = "Identifier"
    name: str = ""

@dataclass
class BinaryOp(Expression):
    """Binary operation: left + right"""
    type: str = "BinaryOp"
    operator: str = ""  # +, -, *, /, %, ==, !=, <, >, <=, >=, &&, ||
    left: 'Expression' = None
    right: 'Expression' = None

@dataclass
class UnaryOp(Expression):
    """Unary operation: -x, !x"""
    type: str = "UnaryOp"
    operator: str = ""  # -, !, ~
    operand: 'Expression' = None

@dataclass
class Call(Expression):
    """Function call: func(arg1, arg2)"""
    type: str = "Call"
    function: 'Expression' = None
    args: List['Expression'] = field(default_factory=list)

# Program - root node
@dataclass  
class Program(ASTNode):
    """Root program node"""
    type: str = "Program"
    surface: str = "ascii"  # "ascii", "glyph", "json"
    version: str = "0.1.0"
    imports: List['ImportDecl'] = field(default_factory=list)
    specs: List['SpecDecl'] = field(default_factory=list)
    effects: List['EffectDecl'] = field(default_factory=list)
    agents: List['AgentDecl'] = field(default_factory=list)
    procs: List['ProcDecl'] = field(default_factory=list)
    bindings: List['Binding'] = field(default_factory=list)
    body: List['Statement'] = field(default_factory=list)

# Import declaration
@dataclass
class ImportDecl(ASTNode):
    """Import statement: IMPORT path AS alias"""
    type: str = "ImportDecl"
    path: str = ""  # e.g., "std/http", "@lib/utils"
    alias: Optional[str] = None
    selective: List[str] = field(default_factory=list)  # IMPORT lib {foo, bar}

# Spec declaration
@dataclass
class SpecDecl(ASTNode):
    """Spec block: SPEC name { ... }"""
    type: str = "SpecDecl"
    name: str = ""
    body: List['Statement'] = field(default_factory=list)

# Effect declaration
@dataclass
class EffectDecl(ASTNode):
    """Effect declaration: EFFECT name { ... }"""
    type: str = "EffectDecl"
    name: str = ""
    params: List['Param'] = field(default_factory=list)
    body: List['Statement'] = field(default_factory=list)

# Agent declaration
@dataclass
class AgentDecl(ASTNode):
    """Agent declaration: AGENT name { ... }"""
    type: str = "AgentDecl"
    name: str = ""
    clauses: List['AgentClause'] = field(default_factory=list)
    body: List['Statement'] = field(default_factory=list)

# Agent clause (WHEN, ON, DO)
@dataclass
class AgentClause(ASTNode):
    """Agent clause: WHEN event ON condition DO action"""
    type: str = "AgentClause"
    when: Optional['Expression'] = None
    on: Optional['Expression'] = None
    do: List['Statement'] = field(default_factory=list)

# Procedure declaration
@dataclass
class ProcDecl(ASTNode):
    """Procedure: PROC name(params) { ... }"""
    type: str = "ProcDecl"
    name: str = ""
    params: List['Param'] = field(default_factory=list)
    return_type: Optional[str] = None
    body: List['Statement'] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)

# Function declaration (alias for ProcDecl for semantic clarity)
@dataclass
class FunctionDecl(ASTNode):
    """Function: DEF name(params) { ... }"""
    type: str = "FunctionDecl"
    name: str = ""
    params: List['Param'] = field(default_factory=list)
    return_type: Optional[str] = None
    body: List['Statement'] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)

# Parameter
@dataclass
class Param(ASTNode):
    """Function/procedure parameter"""
    type: str = "Param"
    name: str = ""
    param_type: str = "any"
    default: Optional['Expression'] = None

# Binding
@dataclass
class Binding(ASTNode):
    """Variable binding: LET x = value"""
    type: str = "Binding"
    name: str = ""
    value: 'Expression' = None
    is_mutable: bool = False
    is_spec: bool = False

# =============================================================================
# STATEMENTS
# =============================================================================

Statement = Union['LetStmt', 'IfStmt', 'GuardStmt', 'ReturnStmt', 
                  'ExprStmt', 'LoopStmt', 'MatchStmt', 'BlockStmt']

@dataclass
class LetStmt(ASTNode):
    """Let statement: LET x = expr"""
    type: str = "LetStmt"
    name: str = ""
    value: 'Expression' = None
    is_mutable: bool = False

@dataclass
class IfStmt(ASTNode):
    """If statement: IF cond { ... } [ELIF cond { ... }] [ELSE { ... }]"""
    type: str = "IfStmt"
    condition: 'Expression' = None
    then_body: List[Statement] = field(default_factory=list)
    elif_branches: List['ElifBranch'] = field(default_factory=list)
    else_body: List[Statement] = field(default_factory=list)

@dataclass
class ElifBranch(ASTNode):
    """Elif branch"""
    type: str = "ElifBranch"
    condition: 'Expression' = None
    body: List[Statement] = field(default_factory=list)

@dataclass
class GuardStmt(ASTNode):
    """Guard statement: GUARD condition OTHERWISE { ... }"""
    type: str = "GuardStmt"
    condition: 'Expression' = None
    otherwise_body: List[Statement] = field(default_factory=list)

@dataclass
class WhileStmt(ASTNode):
    """While loop: WHILE condition { ... }"""
    type: str = "WhileStmt"
    condition: 'Expression' = None
    body: List[Statement] = field(default_factory=list)

@dataclass
class ReturnStmt(ASTNode):
    """Return statement: RETURN expr"""
    type: str = "ReturnStmt"
    value: Optional['Expression'] = None

@dataclass
class ExprStmt(ASTNode):
    """Expression as statement"""
    type: str = "ExprStmt"
    expression: 'Expression' = None

@dataclass
class LoopStmt(ASTNode):
    """Loop statement: LOOP { ... } [WHILE cond] [FOR x IN iterable]"""
    type: str = "LoopStmt"
    loop_type: str = "infinite"  # "infinite", "while", "for"
    condition: Optional['Expression'] = None
    iterator: Optional[str] = None
    iterable: Optional['Expression'] = None
    body: List[Statement] = field(default_factory=list)

@dataclass
class MatchStmt(ASTNode):
    """Match statement: MATCH expr { CASE pattern => { ... } ... }"""
    type: str = "MatchStmt"
    value: 'Expression' = None
    cases: List['MatchCase'] = field(default_factory=list)

@dataclass
class MatchCase(ASTNode):
    """Match case: CASE pattern [IF guard] => { ... }"""
    type: str = "MatchCase"
    pattern: 'Pattern' = None
    guard: Optional['Expression'] = None
    body: List[Statement] = field(default_factory=list)

@dataclass
class BlockStmt(ASTNode):
    """Block statement: { ... }"""
    type: str = "BlockStmt"
    statements: List[Statement] = field(default_factory=list)

# =============================================================================
# EXPRESSIONS
# =============================================================================

Expression = Union['LiteralExpr', 'IdentifierExpr', 'BinaryExpr', 'UnaryExpr',
                   'CallExpr', 'AccessExpr', 'IndexExpr', 'ConditionalExpr',
                   'LambdaExpr', 'ListExpr', 'DictExpr', 'HostCallExpr',
                   'ToolCallExpr', 'AgentCallExpr', 'StructLiteralExpr']

@dataclass
class LiteralExpr(ASTNode):
    """Literal value: 42, "hello", true, nil"""
    type: str = "LiteralExpr"
    value: Any = None
    literal_type: str = "unknown"  # "int", "float", "string", "bool", "nil"

@dataclass
class IdentifierExpr(ASTNode):
    """Variable reference: foo"""
    type: str = "IdentifierExpr"
    name: str = ""

@dataclass
class BinaryExpr(ASTNode):
    """Binary operation: a + b, x == y"""
    type: str = "BinaryExpr"
    operator: str = ""  # +, -, *, /, ==, !=, <, >, <=, >=, &&, ||, etc.
    left: 'Expression' = None
    right: 'Expression' = None

@dataclass
class UnaryExpr(ASTNode):
    """Unary operation: -x, !cond"""
    type: str = "UnaryExpr"
    operator: str = ""  # -, !, ~
    operand: 'Expression' = None

@dataclass
class CallExpr(ASTNode):
    """Function call: foo(a, b)"""
    type: str = "CallExpr"
    callee: 'Expression' = None
    args: List['Expression'] = field(default_factory=list)
    is_host_call: bool = False
    is_tool_call: bool = False
    is_agent_call: bool = False

@dataclass
class AccessExpr(ASTNode):
    """Field access: obj.field"""
    type: str = "AccessExpr"
    object: 'Expression' = None
    field: str = ""

@dataclass
class IndexExpr(ASTNode):
    """Index access: arr[i]"""
    type: str = "IndexExpr"
    object: 'Expression' = None
    index: 'Expression' = None

@dataclass
class ConditionalExpr(ASTNode):
    """Ternary conditional: cond ? then_expr : else_expr"""
    type: str = "ConditionalExpr"
    condition: 'Expression' = None
    then_expr: 'Expression' = None
    else_expr: 'Expression' = None

@dataclass
class LambdaExpr(ASTNode):
    """Lambda expression: \\x -> expr"""
    type: str = "LambdaExpr"
    params: List[str] = field(default_factory=list)
    body: 'Expression' = None

@dataclass
class ListExpr(ASTNode):
    """List literal: [a, b, c]"""
    type: str = "ListExpr"
    elements: List['Expression'] = field(default_factory=list)

@dataclass
class DictExpr(ASTNode):
    """Dictionary literal: {key: value, ...}"""
    type: str = "DictExpr"
    pairs: List[tuple] = field(default_factory=list)  # [(key, value), ...]

@dataclass
class HostCallExpr(ASTNode):
    """Host function call: HOST_CALL(func, args)"""
    type: str = "HostCallExpr"
    function: str = ""  # e.g., "READ_FILE"
    args: Dict[str, 'Expression'] = field(default_factory=dict)
    capabilities: List[str] = field(default_factory=list)

@dataclass
class ToolCallExpr(ASTNode):
    """Tool call: TOOL_CALL(tool, args)"""
    type: str = "ToolCallExpr"
    tool: str = ""
    args: Dict[str, 'Expression'] = field(default_factory=dict)

@dataclass
class AgentCallExpr(ASTNode):
    """Agent delegation: AGENT_CALL(agent, intent)"""
    type: str = "AgentCallExpr"
    agent: str = ""
    intent: Dict[str, Any] = field(default_factory=dict)

@dataclass
class StructLiteralExpr(ASTNode):
    """Struct literal: TypeName { field: value, ... }"""
    type: str = "StructLiteralExpr"
    struct_type: str = ""
    fields: Dict[str, 'Expression'] = field(default_factory=dict)

# =============================================================================
# PATTERNS (for match expressions)
# =============================================================================

Pattern = Union['LiteralPattern', 'IdentifierPattern', 'WildcardPattern',
                'StructPattern', 'ListPattern']

@dataclass
class LiteralPattern(ASTNode):
    """Literal pattern"""
    type: str = "LiteralPattern"
    value: Any = None

@dataclass
class IdentifierPattern(ASTNode):
    """Binding pattern: x"""
    type: str = "IdentifierPattern"
    name: str = ""

@dataclass
class WildcardPattern(ASTNode):
    """Wildcard pattern: _"""
    type: str = "WildcardPattern"

@dataclass
class StructPattern(ASTNode):
    """Struct destructuring: Point { x, y }"""
    type: str = "StructPattern"
    struct_type: str = ""
    fields: Dict[str, Pattern] = field(default_factory=dict)

@dataclass
class ListPattern(ASTNode):
    """List destructuring: [first, ...rest]"""
    type: str = "ListPattern"
    elements: List[Pattern] = field(default_factory=list)
    rest: Optional[str] = None  # capture rest as variable

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def create_program() -> Program:
    """Create an empty program"""
    return Program()

def serialize_ast(node: ASTNode) -> Dict[str, Any]:
    """Serialize AST to dictionary (for JSON output)"""
    return node.to_dict()

def deserialize_ast(data: Dict[str, Any]) -> ASTNode:
    """Deserialize dictionary to AST (basic implementation)"""
    node_type = data.get("type", "Unknown")
    
    # This would need full implementation for production use
    # For now, return a generic node
    return ASTNode()
