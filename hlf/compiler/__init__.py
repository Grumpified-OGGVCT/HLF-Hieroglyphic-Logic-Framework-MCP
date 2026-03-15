"""
HLF Compiler Package
Converts HLF source code to bytecode
"""

from .lexer import Lexer, Token, TokenType
from .parser import Parser, ParseError
from .ast_nodes import *
from .compiler import Compiler, CompileError
from .codegen import BytecodeGenerator

__all__ = [
    'Lexer',
    'Token',
    'TokenType',
    'Parser',
    'ParseError',
    'Compiler',
    'CompileError',
    'BytecodeGenerator',
    # AST nodes
    'Module',
    'FunctionDecl',
    'SpecDecl',
    'TypeDecl',
    'ConstDecl',
    'Identifier',
    'Literal',
    'BinaryExpr',
    'UnaryExpr',
    'CallExpr',
    'IfExpr',
    'MatchExpr',
    'BlockExpr',
    'LambdaExpr',
    'RecordExpr',
    'ListExpr',
    'TupleExpr',
    'PipelineExpr',
    'LetStmt',
    'ConstStmt',
    'ExprStmt',
    'ReturnStmt',
    'IfStmt',
    'MatchStmt',
    'ForStmt',
]

__version__ = "0.5.0"
