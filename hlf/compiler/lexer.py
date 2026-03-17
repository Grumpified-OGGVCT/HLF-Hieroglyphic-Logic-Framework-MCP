"""
HLF Compiler Lexer Re-export
Thin shim so compiler.parser.parse() convenience function works:
    from .lexer import tokenize
"""

from ..lexer import Lexer, Token, TokenType, LexerError, tokenize

__all__ = ['Lexer', 'Token', 'TokenType', 'LexerError', 'tokenize']
