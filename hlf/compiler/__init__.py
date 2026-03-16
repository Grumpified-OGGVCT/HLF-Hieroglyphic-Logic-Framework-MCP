"""
HLF Compiler Package
Converts HLF source code to bytecode
"""

from .ast_nodes import *
from .parser import Parser, ParseError
from .full_compiler import Compiler as FullCompiler, Compiler, CompileError

# Re-export the root lexer so parser.parse() convenience function works
from ..lexer import Lexer, Token, TokenType, tokenize

__all__ = [
    'Lexer',
    'Token',
    'TokenType',
    'tokenize',
    'Parser',
    'ParseError',
    'FullCompiler',
    'CompileError',
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
