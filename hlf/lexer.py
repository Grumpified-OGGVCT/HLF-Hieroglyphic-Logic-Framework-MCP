"""
HLF Lexer - Tokenizes HLF source code
Supports both ASCII and Glyph surfaces
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Optional, Iterator, Dict
from .ast_nodes import Position, Location

class TokenType(Enum):
    # Literals
    INT = auto()
    FLOAT = auto()
    STRING = auto()
    BOOL = auto()
    ATOM = auto()
    UNIT = auto()
    
    # Identifiers
    IDENT = auto()
    CAPITAL_IDENT = auto()  # Type names, constructors
    
    # Keywords
    FN = auto()
    LET = auto()
    CONST = auto()
    MUT = auto()
    IF = auto()
    THEN = auto()
    ELSE = auto()
    MATCH = auto()
    WITH = auto()
    FOR = auto()
    IN = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    SPEC = auto()
    TYPE = auto()
    IMPORT = auto()
    FROM = auto()
    AS = auto()
    EFFECT = auto()
    TIER = auto()
    GAS = auto()
    
    # Symbols
    ARROW = auto()          # =>
    FAT_ARROW = auto()      # =>
    PIPE = auto()           # |
    DOUBLE_PIPE = auto()    # ||
    AMPERSAND = auto()      # &
    DOUBLE_AMPERSAND = auto() # &&
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    CARET = auto()
    TILDE = auto()
    
    # Comparisons
    EQ = auto()             # ==
    NE = auto()             # !=
    LT = auto()             # <
    LE = auto()             # <=
    GT = auto()             # >
    GE = auto()             # >=
    
    # Assignment
    ASSIGN = auto()         # =
    
    # Delimiters
    LPAREN = auto()         # (
    RPAREN = auto()         # )
    LBRACE = auto()         # {
    RBRACE = auto()         # }
    LBRACKET = auto()       # [
    RBRACKET = auto()       # ]
    
    # Separators
    COMMA = auto()          # ,
    SEMICOLON = auto()      # ;
    COLON = auto()          # :
    DOUBLE_COLON = auto()   # ::
    DOT = auto()            # .
    QUESTION = auto()       # ?
    BANG = auto()           # !
    
    # Pipeline
    PIPELINE = auto()       # |>
    COMPOSITION = auto()    # >>
    
    # Glyph keywords (ASCII equivalents)
    GLYPH_ARROW = auto()    # →
    GLYPH_LAMBDA = auto()   # λ
    GLYPH_PIPE = auto()     # ⊎
    GLYPH_RETURNS = auto()  # ⟹
    GLYPH_AND = auto()      # ∧
    GLYPH_OR = auto()       # ∨
    GLYPH_NOT = auto()      # ¬
    GLYPH_IMPLIES = auto()  # ⇒
    GLYPH_FORALL = auto()   # ∀
    GLYPH_EXISTS = auto()   # ∃
    GLYPH_IN = auto()       # ∈
    GLYPH_NOT_IN = auto()   # ∉
    
    # Special
    EOF = auto()
    NEWLINE = auto()
    COMMENT = auto()
    WHITESPACE = auto()
    
    # Error
    ERROR = auto()

@dataclass
class Token:
    type: TokenType
    value: str
    pos: Position
    loc: Optional[Location] = None
    
    def __repr__(self) -> str:
        return f"Token({self.type.name}, {self.value!r})"

class LexerError(Exception):
    def __init__(self, message: str, pos: Position):
        self.message = message
        self.pos = pos
        super().__init__(f"{message} at line {pos.line}, column {pos.column}")

class Lexer:
    """HLF Lexer supporting both ASCII and Glyph surfaces"""
    
    KEYWORDS: Dict[str, TokenType] = {
        'fn': TokenType.FN,
        'let': TokenType.LET,
        'const': TokenType.CONST,
        'mut': TokenType.MUT,
        'if': TokenType.IF,
        'then': TokenType.THEN,
        'else': TokenType.ELSE,
        'match': TokenType.MATCH,
        'with': TokenType.WITH,
        'for': TokenType.FOR,
        'in': TokenType.IN,
        'return': TokenType.RETURN,
        'break': TokenType.BREAK,
        'continue': TokenType.CONTINUE,
        'spec': TokenType.SPEC,
        'type': TokenType.TYPE,
        'import': TokenType.IMPORT,
        'from': TokenType.FROM,
        'as': TokenType.AS,
        'effect': TokenType.EFFECT,
        'tier': TokenType.TIER,
        'gas': TokenType.GAS,
        'true': TokenType.BOOL,
        'false': TokenType.BOOL,
        'unit': TokenType.UNIT,
    }
    
    GLYPH_KEYWORDS: Dict[str, str] = {
        '→': '=>',
        'λ': 'fn',
        '⊎': 'spec',
        '⟹': '=>',
        '∧': '&&',
        '∨': '||',
        '¬': '!',
        '⇒': '=>',
        '∀': 'for',
        '∃': 'exists',
        '∈': 'in',
        '∉': 'not in',
    }
    
    def __init__(self, source: str, filename: str = "<input>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        
    def error(self, message: str) -> LexerError:
        pos = Position(self.line, self.column, self.pos)
        return LexerError(message, pos)
    
    def current_pos(self) -> Position:
        return Position(self.line, self.column, self.pos)
    
    def peek(self, offset: int = 0) -> str:
        idx = self.pos + offset
        if idx >= len(self.source):
            return '\0'
        return self.source[idx]
    
    def advance(self) -> str:
        if self.pos >= len(self.source):
            return '\0'
        char = self.source[self.pos]
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return char
    
    def match(self, expected: str) -> bool:
        if self.peek() == expected:
            self.advance()
            return True
        return False
    
    def skip_whitespace(self) -> None:
        while self.peek() in ' \t\r':
            self.advance()
    
    def skip_comment(self) -> None:
        if self.peek() == '/' and self.peek(1) == '/':
            while self.peek() != '\n' and self.peek() != '\0':
                self.advance()
        elif self.peek() == '/' and self.peek(1) == '*':
            self.advance()  # /
            self.advance()  # *
            depth = 1
            while depth > 0 and self.peek() != '\0':
                if self.peek() == '/' and self.peek(1) == '*':
                    self.advance()
                    self.advance()
                    depth += 1
                elif self.peek() == '*' and self.peek(1) == '/':
                    self.advance()
                    self.advance()
                    depth -= 1
                else:
                    self.advance()
    
    def read_string(self) -> Token:
        start = self.current_pos()
        quote = self.advance()  # " or '
        value = ""
        
        while self.peek() != quote and self.peek() != '\0':
            if self.peek() == '\\':
                self.advance()
                escape = self.advance()
                if escape == 'n':
                    value += '\n'
                elif escape == 't':
                    value += '\t'
                elif escape == 'r':
                    value += '\r'
                elif escape == '\\':
                    value += '\\'
                elif escape == quote:
                    value += quote
                elif escape == '0':
                    value += '\0'
                else:
                    raise self.error(f"Invalid escape sequence: \\{escape}")
            else:
                value += self.advance()
        
        if self.peek() != quote:
            raise self.error("Unterminated string")
        
        self.advance()  # closing quote
        end = self.current_pos()
        loc = Location(start, end, self.filename)
        
        return Token(TokenType.STRING, value, start, loc)
    
    def read_number(self) -> Token:
        start = self.current_pos()
        value = ""
        
        # Handle negative sign (if not preceded by number)
        if self.peek() == '-':
            value += self.advance()
        
        # Integer part
        while self.peek().isdigit():
            value += self.advance()
        
        # Decimal part
        if self.peek() == '.' and self.peek(1).isdigit():
            value += self.advance()  # .
            while self.peek().isdigit():
                value += self.advance()
            
            # Exponent
            if self.peek() in 'eE':
                value += self.advance()
                if self.peek() in '+-':
                    value += self.advance()
                while self.peek().isdigit():
                    value += self.advance()
            
            end = self.current_pos()
            loc = Location(start, end, self.filename)
            return Token(TokenType.FLOAT, value, start, loc)
        
        end = self.current_pos()
        loc = Location(start, end, self.filename)
        return Token(TokenType.INT, value, start, loc)
    
    def read_atom(self) -> Token:
        start = self.current_pos()
        self.advance()  # :
        value = ""
        
        if not (self.peek().isalpha() or self.peek() == '_'):
            raise self.error("Atom must start with letter or underscore")
        
        while self.peek().isalnum() or self.peek() in '_!?':
            value += self.advance()
        
        end = self.current_pos()
        loc = Location(start, end, self.filename)
        return Token(TokenType.ATOM, value, start, loc)
    
    def read_identifier(self) -> Token:
        start = self.current_pos()
        value = ""
        
        # Check for capitalized identifier (type/constructor)
        is_capital = self.peek().isupper()
        
        while self.peek().isalnum() or self.peek() == '_' or self.peek() == '?' or \
              (self.peek() == '!' and value):  # Trailing ! for predicates
            value += self.advance()
        
        # Check for glyph keyword
        if value in self.GLYPH_KEYWORDS:
            ascii_equiv = self.GLYPH_KEYWORDS[value]
            if ascii_equiv in self.KEYWORDS:
                token_type = self.KEYWORDS[ascii_equiv]
            else:
                token_type = TokenType.IDENT
            end = self.current_pos()
            loc = Location(start, end, self.filename)
            return Token(token_type, ascii_equiv, start, loc)
        
        # Check for regular keyword
        if value in self.KEYWORDS:
            token_type = self.KEYWORDS[value]
        elif is_capital:
            token_type = TokenType.CAPITAL_IDENT
        else:
            token_type = TokenType.IDENT
        
        end = self.current_pos()
        loc = Location(start, end, self.filename)
        return Token(token_type, value, start, loc)
    
    def read_glyph(self) -> Token:
        """Read Unicode glyph keyword"""
        start = self.current_pos()
        glyph = self.advance()
        
        if glyph in self.GLYPH_KEYWORDS:
            ascii_equiv = self.GLYPH_KEYWORDS[glyph]
            if ascii_equiv in self.KEYWORDS:
                token_type = self.KEYWORDS[ascii_equiv]
            else:
                token_type = TokenType.IDENT
            end = self.current_pos()
            loc = Location(start, end, self.filename)
            return Token(token_type, ascii_equiv, start, loc)
        
        # Unknown glyph
        raise self.error(f"Unknown glyph: {glyph}")
    
    def next_token(self) -> Token:
        self.skip_whitespace()
        
        # Check for comments
        if (self.peek() == '/' and self.peek(1) in '/*') or \
           (self.peek() == '-' and self.peek(1) == '-'):
            self.skip_comment()
            return self.next_token()
        
        start = self.current_pos()
        char = self.peek()
        
        # EOF
        if char == '\0':
            return Token(TokenType.EOF, "", start, None)
        
        # Newline
        if char == '\n':
            self.advance()
            end = self.current_pos()
            loc = Location(start, end, self.filename)
            return Token(TokenType.NEWLINE, "\n", start, loc)
        
        # String literal
        if char in '"\'':
            return self.read_string()
        
        # Number
        if char.isdigit() or (char == '-' and self.peek(1).isdigit()):
            return self.read_number()
        
        # Atom
        if char == ':':
            return self.read_atom()
        
        # Identifier or keyword
        if char.isalpha() or char == '_':
            return self.read_identifier()
        
        # Glyph keywords (Unicode)
        if ord(char) > 127:
            return self.read_glyph()
        
        # Two-character operators
        two_char = char + self.peek(1)
        two_char_tokens = {
            '=>': TokenType.ARROW,
            '==': TokenType.EQ,
            '!=': TokenType.NE,
            '<=': TokenType.LE,
            '>=': TokenType.GE,
            '&&': TokenType.DOUBLE_AMPERSAND,
            '||': TokenType.DOUBLE_PIPE,
            '::': TokenType.DOUBLE_COLON,
            '|>': TokenType.PIPELINE,
            '>>': TokenType.COMPOSITION,
        }
        
        if two_char in two_char_tokens:
            self.advance()
            self.advance()
            end = self.current_pos()
            loc = Location(start, end, self.filename)
            return Token(two_char_tokens[two_char], two_char, start, loc)
        
        # Single-character tokens
        single_tokens = {
            '+': TokenType.PLUS,
            '-': TokenType.MINUS,
            '*': TokenType.STAR,
            '/': TokenType.SLASH,
            '%': TokenType.PERCENT,
            '^': TokenType.CARET,
            '~': TokenType.TILDE,
            '<': TokenType.LT,
            '>': TokenType.GT,
            '=': TokenType.ASSIGN,
            '&': TokenType.AMPERSAND,
            '|': TokenType.PIPE,
            '(': TokenType.LPAREN,
            ')': TokenType.RPAREN,
            '{': TokenType.LBRACE,
            '}': TokenType.RBRACE,
            '[': TokenType.LBRACKET,
            ']': TokenType.RBRACKET,
            ',': TokenType.COMMA,
            ';': TokenType.SEMICOLON,
            ':': TokenType.COLON,
            '.': TokenType.DOT,
            '?': TokenType.QUESTION,
            '!': TokenType.BANG,
        }
        
        if char in single_tokens:
            self.advance()
            end = self.current_pos()
            loc = Location(start, end, self.filename)
            return Token(single_tokens[char], char, start, loc)
        
        # Unknown character
        raise self.error(f"Unexpected character: {char}")
    
    def tokenize(self) -> List[Token]:
        """Tokenize entire source"""
        tokens = []
        while True:
            token = self.next_token()
            tokens.append(token)
            if token.type == TokenType.EOF:
                break
        return tokens
    
    def __iter__(self) -> Iterator[Token]:
        """Iterate over tokens"""
        return iter(self.tokenize())

# Convenience function
def tokenize(source: str, filename: str = "<input>") -> List[Token]:
    """Tokenize HLF source code"""
    return Lexer(source, filename).tokenize()
