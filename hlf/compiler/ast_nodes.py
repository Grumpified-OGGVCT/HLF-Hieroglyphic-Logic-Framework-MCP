"""
HLF Abstract Syntax Tree Node Definitions
Python classes representing all AST nodes per spec/core/ast_schema.json
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum, auto

# ============================================================================
# Location Information
# ============================================================================

@dataclass
class Position:
    """Source position"""
    line: int
    column: int
    offset: int
    
    def to_dict(self) -> Dict[str, int]:
        return {"line": self.line, "column": self.column, "offset": self.offset}

@dataclass
class Location:
    """Source location span"""
    start: Position
    end: Position
    source: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "start": self.start.to_dict(),
            "end": self.end.to_dict()
        }
        if self.source:
            result["source"] = self.source
        return result

# ============================================================================
# Base Node
# ============================================================================

@dataclass
class ASTNode:
    """Base class for all AST nodes"""
    loc: Optional[Location] = field(default=None, kw_only=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict per ast_schema.json"""
        raise NotImplementedError
    
    def node_type(self) -> str:
        """Return the node type name"""
        return self.__class__.__name__

# ============================================================================
# Literals
# ============================================================================

class LiteralType(Enum):
    INT = "int"
    FLOAT = "float"
    STRING = "string"
    BOOL = "bool"
    ATOM = "atom"
    UNIT = "unit"

@dataclass
class Literal(ASTNode):
    """Literal value"""
    literal_type: LiteralType
    value: Any
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Literal",
            "literalType": self.literal_type.value,
            "value": self.value
        }
    
    @classmethod
    def int(cls, value: int, loc: Optional[Location] = None) -> "Literal":
        return cls(loc=loc, literal_type=LiteralType.INT, value=value)
    
    @classmethod
    def float(cls, value: float, loc: Optional[Location] = None) -> "Literal":
        return cls(loc=loc, literal_type=LiteralType.FLOAT, value=value)
    
    @classmethod
    def string(cls, value: str, loc: Optional[Location] = None) -> "Literal":
        return cls(loc=loc, literal_type=LiteralType.STRING, value=value)
    
    @classmethod
    def bool(cls, value: bool, loc: Optional[Location] = None) -> "Literal":
        return cls(loc=loc, literal_type=LiteralType.BOOL, value=value)
    
    @classmethod
    def atom(cls, value: str, loc: Optional[Location] = None) -> "Literal":
        return cls(loc=loc, literal_type=LiteralType.ATOM, value=value)
    
    @classmethod
    def unit(cls, loc: Optional[Location] = None) -> "Literal":
        return cls(loc=loc, literal_type=LiteralType.UNIT, value=None)

# ============================================================================
# Identifiers
# ============================================================================

@dataclass
class Identifier(ASTNode):
    """Identifier reference"""
    name: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "Identifier",
            "name": self.name
        }

# ============================================================================
# Types
# ============================================================================

@dataclass
class Type(ASTNode):
    """Type expression"""
    pass

@dataclass
class PrimitiveType(Type):
    """Primitive type (int, float, bool, string, atom, unit)"""
    name: str  # int, float, bool, string, atom, unit
    
    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "primitive", "name": self.name}

@dataclass
class NamedType(Type):
    """Named type reference"""
    name: str
    module: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"kind": "named", "name": self.name}
        if self.module:
            result["module"] = self.module
        return result

@dataclass
class FunctionType(Type):
    """Function type"""
    params: List[Type]
    return_type: Type
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "function",
            "params": [p.to_dict() for p in self.params],
            "return": self.return_type.to_dict()
        }

@dataclass
class GenericType(Type):
    """Generic type (e.g., List<T>)"""
    name: str
    args: List[Type]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "generic",
            "name": self.name,
            "args": [a.to_dict() for a in self.args]
        }

@dataclass
class RecordType(Type):
    """Record type"""
    fields: List[Dict[str, Any]]  # {name, type, optional}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "record",
            "fields": [
                {
                    "name": f["name"],
                    "type": f["type"].to_dict(),
                    "optional": f.get("optional", False)
                }
                for f in self.fields
            ]
        }

@dataclass
class ListType(Type):
    """List type"""
    element: Type
    
    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "list", "element": self.element.to_dict()}

@dataclass
class OptionType(Type):
    """Option type (T?)"""
    inner: Type
    
    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "option", "inner": self.inner.to_dict()}

@dataclass
class ResultType(Type):
    """Result type (Result<T, E>)"""
    ok: Type
    err: Type
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": "result",
            "ok": self.ok.to_dict(),
            "err": self.err.to_dict()
        }

# ============================================================================
# Effects
# ============================================================================

@dataclass
class Effect(ASTNode):
    """Effect annotation"""
    name: str
    args: List[Any] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "args": self.args}

# ============================================================================
# Patterns
# ============================================================================

@dataclass
class Pattern(ASTNode):
    """Pattern for matching"""
    pass

@dataclass
class LiteralPattern(Pattern):
    """Match literal value"""
    value: Literal
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": "LiteralPattern", "value": self.value.to_dict()}

@dataclass
class IdentPattern(Pattern):
    """Bind to identifier"""
    name: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {"type": "IdentPattern", "name": self.name}

@dataclass
class WildcardPattern(Pattern):
    """Wildcard (_)"""
    def to_dict(self) -> Dict[str, Any]:
        return {"type": "WildcardPattern"}

@dataclass
class ConstructorPattern(Pattern):
    """Constructor pattern (e.g., Some(x))"""
    constructor: Identifier
    fields: List[Dict[str, Pattern]]  # {name, pattern}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "ConstructorPattern",
            "constructor": self.constructor.to_dict(),
            "fields": [
                {"name": f["name"], "pattern": f["pattern"].to_dict()}
                for f in self.fields
            ]
        }

# ============================================================================
# Expressions
# ============================================================================

@dataclass
class Expression(ASTNode):
    """Expression node"""
    pass

@dataclass
class BinaryExpr(Expression):
    """Binary operation"""
    operator: str
    left: Expression
    right: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "BinaryExpr",
            "operator": self.operator,
            "left": self.left.to_dict(),
            "right": self.right.to_dict()
        }

@dataclass
class UnaryExpr(Expression):
    """Unary operation"""
    operator: str
    operand: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "UnaryExpr",
            "operator": self.operator,
            "operand": self.operand.to_dict()
        }

@dataclass
class CallExpr(Expression):
    """Function call"""
    callee: Expression
    arguments: List[Expression]
    keyword_args: Dict[str, Expression] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": "CallExpr",
            "callee": self.callee.to_dict(),
            "arguments": [a.to_dict() for a in self.arguments]
        }
        if self.keyword_args:
            result["keywordArgs"] = {
                k: v.to_dict() for k, v in self.keyword_args.items()
            }
        return result

@dataclass
class FieldExpr(Expression):
    """Field access (obj.field)"""
    obj: Expression
    field: Identifier
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "FieldExpr",
            "object": self.obj.to_dict(),
            "field": self.field.to_dict()
        }

@dataclass
class IndexExpr(Expression):
    """Index access (obj[index])"""
    obj: Expression
    index: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "IndexExpr",
            "object": self.obj.to_dict(),
            "index": self.index.to_dict()
        }

@dataclass
class IfExpr(Expression):
    """If-then-else expression"""
    condition: Expression
    then_branch: Expression
    else_branch: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "IfExpr",
            "condition": self.condition.to_dict(),
            "thenBranch": self.then_branch.to_dict(),
            "elseBranch": self.else_branch.to_dict()
        }

@dataclass
class MatchArm(ASTNode):
    """Match arm"""
    pattern: Pattern
    body: Expression
    guard: Optional[Expression] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "pattern": self.pattern.to_dict(),
            "body": self.body.to_dict()
        }
        if self.guard:
            result["guard"] = self.guard.to_dict()
        return result

@dataclass
class MatchExpr(Expression):
    """Match expression"""
    subject: Expression
    arms: List[MatchArm]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "MatchExpr",
            "subject": self.subject.to_dict(),
            "arms": [a.to_dict() for a in self.arms]
        }

@dataclass
class BlockExpr(Expression):
    """Block expression { stmts; result }"""
    statements: List["Statement"]
    result: Optional[Expression] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": "BlockExpr",
            "statements": [s.to_dict() for s in self.statements]
        }
        if self.result:
            result["result"] = self.result.to_dict()
        return result

@dataclass
class Parameter(ASTNode):
    """Function parameter"""
    name: str
    param_type: Optional[Type] = None
    default: Optional[Expression] = None
    optional: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"name": self.name}
        if self.param_type:
            result["type"] = self.param_type.to_dict()
        if self.default:
            result["default"] = self.default.to_dict()
        if self.optional:
            result["optional"] = True
        return result

@dataclass
class LambdaExpr(Expression):
    """Lambda expression (fn params => body)"""
    params: List[Parameter]
    body: Expression
    return_type: Optional[Type] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": "LambdaExpr",
            "params": [p.to_dict() for p in self.params],
            "body": self.body.to_dict()
        }
        if self.return_type:
            result["returnType"] = self.return_type.to_dict()
        return result

@dataclass
class RecordField(ASTNode):
    """Record field"""
    name: str
    value: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "value": self.value.to_dict()}

@dataclass
class RecordExpr(Expression):
    """Record expression {field: value, ...}"""
    fields: List[RecordField]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "RecordExpr",
            "fields": [f.to_dict() for f in self.fields]
        }

@dataclass
class ListExpr(Expression):
    """List expression [elem, ...]"""
    elements: List[Expression]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "ListExpr",
            "elements": [e.to_dict() for e in self.elements]
        }

@dataclass
class TupleExpr(Expression):
    """Tuple expression (elem, ...)"""
    elements: List[Expression]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "TupleExpr",
            "elements": [e.to_dict() for e in self.elements]
        }

@dataclass
class PipelineExpr(Expression):
    """Pipeline expression (a |> b)"""
    left: Expression
    right: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "PipelineExpr",
            "left": self.left.to_dict(),
            "right": self.right.to_dict()
        }

# ============================================================================
# Statements
# ============================================================================

@dataclass
class Statement(ASTNode):
    """Statement node"""
    pass

@dataclass
class LetStmt(Statement):
    """Let statement"""
    name: Identifier
    value: Expression
    mutable: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "LetStmt",
            "name": self.name.to_dict(),
            "value": self.value.to_dict(),
            "mutable": self.mutable
        }

@dataclass
class ConstStmt(Statement):
    """Const statement"""
    name: Identifier
    value: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "ConstStmt",
            "name": self.name.to_dict(),
            "value": self.value.to_dict()
        }

@dataclass
class ExprStmt(Statement):
    """Expression statement"""
    expression: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "ExprStmt",
            "expression": self.expression.to_dict()
        }

@dataclass
class ReturnStmt(Statement):
    """Return statement"""
    value: Optional[Expression] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"type": "ReturnStmt"}
        if self.value:
            result["value"] = self.value.to_dict()
        return result

@dataclass
class Block(ASTNode):
    """Block of statements"""
    statements: List[Statement]
    
    def to_dict(self) -> Dict[str, Any]:
        return {"statements": [s.to_dict() for s in self.statements]}

@dataclass
class GuardStmt(Statement):
    """Guard statement (compatibility)"""
    condition: Expression = None
    otherwise_body: Optional[List[Statement]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "GuardStmt"}

@dataclass
class LoopStmt(Statement):
    """Loop statement (compatibility)"""
    condition: Optional[Expression] = None
    body: List[Statement] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "LoopStmt"}

@dataclass
class BlockStmt(Statement):
    """Block statement (compatibility)"""
    statements: List[Statement] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "BlockStmt"}

@dataclass
class AgentClause(ASTNode):
    """Agent clause (compatibility)"""
    when: Optional[Expression] = None
    on: Optional[Expression] = None
    do: List[Statement] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "AgentClause"}

@dataclass
class IfStmt(Statement):
    """If statement"""
    condition: Expression
    then_block: Block
    else_block: Optional[Block] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": "IfStmt",
            "condition": self.condition.to_dict(),
            "thenBlock": self.then_block.to_dict()
        }
        if self.else_block:
            result["elseBlock"] = self.else_block.to_dict()
        return result

@dataclass
class MatchStmt(Statement):
    """Match statement"""
    subject: Expression
    arms: List["MatchStmtArm"]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "MatchStmt",
            "subject": self.subject.to_dict(),
            "arms": [a.to_dict() for a in self.arms]
        }

@dataclass
class MatchStmtArm(ASTNode):
    """Match statement arm"""
    pattern: Pattern
    body: Block
    guard: Optional[Expression] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "pattern": self.pattern.to_dict(),
            "body": self.body.to_dict()
        }
        if self.guard:
            result["guard"] = self.guard.to_dict()
        return result

@dataclass
class ForStmt(Statement):
    """For statement"""
    variable: Identifier
    iterable: Expression
    body: Block
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": "ForStmt",
            "variable": self.variable.to_dict(),
            "iterable": self.iterable.to_dict(),
            "body": self.body.to_dict()
        }

@dataclass
class BreakStmt(Statement):
    """Break statement"""
    def to_dict(self) -> Dict[str, Any]:
        return {"type": "BreakStmt"}

@dataclass
class ContinueStmt(Statement):
    """Continue statement"""
    def to_dict(self) -> Dict[str, Any]:
        return {"type": "ContinueStmt"}

# ============================================================================
# Declarations
# ============================================================================

@dataclass
class Import(ASTNode):
    """Import statement"""
    path: str
    alias: Optional[str] = None
    items: Optional[List[str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {"path": self.path}
        if self.alias:
            result["alias"] = self.alias
        if self.items:
            result["items"] = self.items
        return result

@dataclass
class Constraint(ASTNode):
    """Spec constraint"""
    constraint_type: str  # invariant, ensures, requires
    expression: Expression
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.constraint_type,
            "expression": self.expression.to_dict()
        }

@dataclass
class Declaration(ASTNode):
    """Base declaration"""
    pass

@dataclass
class FunctionDecl(Declaration):
    """Function declaration"""
    name: Identifier
    params: List[Parameter]
    body: Block
    return_type: Optional[Type] = None
    effects: List[Effect] = field(default_factory=list)
    tiers: List[str] = field(default_factory=list)
    gas: Optional[int] = None
    doc: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "kind": "function",
            "name": self.name.to_dict(),
            "params": [p.to_dict() for p in self.params],
            "body": self.body.to_dict()
        }
        if self.return_type:
            result["returnType"] = self.return_type.to_dict()
        if self.effects:
            result["effects"] = [e.to_dict() for e in self.effects]
        if self.tiers:
            result["tiers"] = self.tiers
        if self.gas:
            result["gas"] = self.gas
        if self.doc:
            result["doc"] = self.doc
        return result

@dataclass
class SpecDecl(Declaration):
    """Spec declaration"""
    name: Identifier
    constraints: List[Constraint] = field(default_factory=list)
    doc: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "kind": "spec",
            "name": self.name.to_dict()
        }
        if self.constraints:
            result["constraints"] = [c.to_dict() for c in self.constraints]
        if self.doc:
            result["doc"] = self.doc
        return result

@dataclass
class TypeDecl(Declaration):
    """Type declaration"""
    name: Identifier
    definition: Type
    doc: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "kind": "type",
            "name": self.name.to_dict(),
            "definition": self.definition.to_dict()
        }
        if self.doc:
            result["doc"] = self.doc
        return result

@dataclass
class ConstDecl(Declaration):
    """Constant declaration"""
    name: Identifier
    value: Expression
    doc: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "kind": "const",
            "name": self.name.to_dict(),
            "value": self.value.to_dict()
        }
        if self.doc:
            result["doc"] = self.doc
        return result

# ============================================================================
# Module
# ============================================================================

@dataclass
class Module(ASTNode):
    """Module (compilation unit)"""
    name: str
    version: str = "0.1.0"
    doc: Optional[str] = None
    imports: List[Import] = field(default_factory=list)
    declarations: List[Declaration] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        result = {
            "astVersion": "0.5.0",
            "module": {
                "name": self.name,
                "version": self.version,
                "imports": [i.to_dict() for i in self.imports],
                "declarations": [d.to_dict() for d in self.declarations]
            }
        }
        if self.doc:
            result["module"]["doc"] = self.doc
        return result
    
    def to_json(self) -> str:
        """Serialize to JSON string"""
        import json
        return json.dumps(self.to_dict(), indent=2)

# ============================================================================
# Compatibility aliases for the old root ast_nodes names
# ============================================================================

Program = Module

@dataclass
class DictExpr(Expression):
    """Dictionary expression (alias for record construction)"""
    pairs: List[tuple] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "DictExpr", "pairs": len(self.pairs)}

@dataclass
class HostCallExpr(Expression):
    """Host function call"""
    function: str = ""
    args: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "HostCallExpr", "function": self.function}

@dataclass
class EffectDecl(Declaration):
    """Effect declaration (compatibility)"""
    name: Identifier = None
    operations: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "effect", "name": self.name.to_dict() if self.name else ""}

@dataclass
class AgentDecl(Declaration):
    """Agent declaration (compatibility)"""
    name: Identifier = None
    clauses: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "agent", "name": self.name.to_dict() if self.name else ""}

@dataclass
class ProcDecl(Declaration):
    """Procedure declaration (compatibility)"""
    name: Identifier = None
    params: List[Parameter] = field(default_factory=list)
    body: Optional[Block] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": "proc", "name": self.name.to_dict() if self.name else ""}

@dataclass
class Binding(ASTNode):
    """Variable binding (compatibility)"""
    name: str = ""
    value: Optional[Expression] = None

    def to_dict(self) -> Dict[str, Any]:
        return {"type": "Binding", "name": self.name}

# Expression type aliases (old names -> new names)
LiteralExpr = Literal
IdentifierExpr = Identifier
ConditionalExpr = IfExpr
AccessExpr = FieldExpr
