"""
HLF Parser
Converts tokens to AST per spec/core/ast_schema.yaml
"""

from typing import List, Optional, Any
from .ast_nodes import *

class ParseError(Exception):
    """Parse error with location"""
    def __init__(self, message: str, pos: Optional[int] = None):
        self.message = message
        self.pos = pos
        super().__init__(message)

class Parser:
    """Recursive descent parser for HLF"""
    
    def __init__(self, tokens: List[Any]):
        self.tokens = tokens
        self.pos = 0
    
    def current(self) -> Any:
        """Get current token"""
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None
    
    def peek(self, offset: int = 0) -> Any:
        """Peek at token at offset"""
        idx = self.pos + offset
        if idx < len(self.tokens):
            return self.tokens[idx]
        return None
    
    def advance(self) -> Any:
        """Advance and return token"""
        token = self.current()
        self.pos += 1
        return token
    
    def expect(self, expected_type: str) -> Any:
        """Expect and consume token of type"""
        token = self.current()
        if token is None:
            raise ParseError(f"Expected {expected_type} but got EOF")
        if getattr(token, 'type', token) != expected_type:
            raise ParseError(f"Expected {expected_type} but got {getattr(token, 'type', token)}")
        return self.advance()
    
    def match(self, *types: str) -> bool:
        """Check if current token matches any type"""
        token = self.current()
        if token is None:
            return False
        return getattr(token, 'type', token) in types
    
    def consume(self, *types: str) -> bool:
        """Consume token if it matches"""
        if self.match(*types):
            self.advance()
            return True
        return False
    
    def skip_newlines(self) -> None:
        """Skip newline tokens"""
        while self.match('NEWLINE'):
            self.advance()
    
    def parse(self) -> Program:
        """Parse full module"""
        module = Program()
        
        while self.current():
            self.skip_newlines()
            if not self.current():
                break
            
            # Parse import
            if self.match('IMPORT'):
                module.imports.append(self.parse_import())
            # Parse function
            elif self.match('DEF'):
                module.declarations.append(self.parse_function())
            # Parse top-level expression
            else:
                expr = self.parse_expr()
                if expr:
                    module.statements.append(expr)
        
        return module
    
    def parse_import(self) -> ImportDecl:
        """Parse import: import "path" as alias"""
        self.expect('IMPORT')
        path_token = self.expect('STRING')
        alias = None
        if self.consume('AS'):
            alias_token = self.expect('IDENT')
            alias = getattr(alias_token, 'value', str(alias_token))
        return ImportDecl(
            path=getattr(path_token, 'value', str(path_token)),
            alias=alias
        )
    
    def parse_function(self) -> FunctionDecl:
        """Parse function declaration"""
        self.expect('DEF')
        name_token = self.expect('IDENT')
        name = getattr(name_token, 'value', str(name_token))
        
        self.expect('LPAREN')
        params = []
        while not self.match('RPAREN'):
            if params:
                self.expect('COMMA')
            param_token = self.expect('IDENT')
            param_name = getattr(param_token, 'value', str(param_token))
            param_type = None
            if self.consume('COLON'):
                param_type = self.parse_type()
            params.append({"name": param_name, "type": param_type})
        self.expect('RPAREN')
        
        return_type = None
        if self.consume('ARROW'):
            return_type = self.parse_type()
        
        effects = []
        if self.consume('EFFECT'):
            effects = self.parse_effects()
        
        body = self.parse_block()
        
        return FunctionDecl(
            name=name,
            params=params,
            return_type=return_type,
            body=body,
            effects=effects
        )
    
    def parse_type(self) -> ASTNode:
        """Parse type annotation"""
        if self.match('IDENT'):
            token = self.advance()
            name = getattr(token, 'value', str(token))
            if name == 'Int':
                return PrimitiveType('Int')
            elif name == 'Float':
                return PrimitiveType('Float')
            elif name == 'Bool':
                return PrimitiveType('Bool')
            elif name == 'String':
                return PrimitiveType('String')
            elif name == 'Unit':
                return PrimitiveType('Unit')
            else:
                return Identifier(name)
        return PrimitiveType('Unit')
    
    def parse_effects(self) -> List[str]:
        """Parse effect list"""
        effects = []
        self.expect('LBRACE')
        while not self.match('RBRACE'):
            if effects:
                self.expect('COMMA')
            token = self.expect('IDENT')
            effects.append(getattr(token, 'value', str(token)))
        self.expect('RBRACE')
        return effects
    
    def parse_block(self) -> List[ASTNode]:
        """Parse block of statements"""
        self.expect('LBRACE')
        statements = []
        while not self.match('RBRACE'):
            self.skip_newlines()
            if self.match('RBRACE'):
                break
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
        self.expect('RBRACE')
        return statements
    
    def parse_statement(self) -> Optional[ASTNode]:
        """Parse statement"""
        self.skip_newlines()
        
        if self.match('LET'):
            return self.parse_let()
        elif self.match('IF'):
            return self.parse_if()
        elif self.match('MATCH'):
            return self.parse_match()
        elif self.match('WHILE'):
            return self.parse_while()
        elif self.match('RETURN'):
            return self.parse_return()
        elif self.match('IDENT'):
            return self.parse_expr_stmt()
        
        return None
    
    def parse_let(self) -> ASTNode:
        """Parse let statement"""
        self.expect('LET')
        name_token = self.expect('IDENT')
        name = getattr(name_token, 'value', str(name_token))
        self.expect('ASSIGN')
        value = self.parse_expr()
        self.consume('SEMICOLON')
        return BinaryOp('=', Identifier(name), value)
    
    def parse_if(self) -> IfStmt:
        """Parse if statement"""
        self.expect('IF')
        condition = self.parse_expr()
        then_block = self.parse_block()
        else_block = None
        if self.consume('ELSE'):
            if self.match('IF'):
                else_block = [self.parse_if()]
            else:
                else_block = self.parse_block()
        return IfStmt(condition, then_block, else_block)
    
    def parse_match(self) -> MatchStmt:
        """Parse match statement"""
        self.expect('MATCH')
        expr = self.parse_expr()
        self.expect('LBRACE')
        cases = []
        while not self.match('RBRACE'):
            if cases:
                self.expect('COMMA')
            pattern = self.parse_pattern()
            self.expect('ARROW')
            body = self.parse_expr() if not self.match('LBRACE') else Block(self.parse_block())
            cases.append(Case(pattern, body))
        self.expect('RBRACE')
        return MatchStmt(expr, cases)
    
    def parse_pattern(self) -> ASTNode:
        """Parse pattern"""
        if self.match('INT'):
            token = self.advance()
            value = int(getattr(token, 'value', str(token)))
            return Literal(value, 'Int')
        elif self.match('STRING'):
            token = self.advance()
            value = getattr(token, 'value', str(token))
            return Literal(value, 'String')
        elif self.match('IDENT'):
            token = self.advance()
            return Identifier(getattr(token, 'value', str(token)))
        return Identifier('_')
    
    def parse_while(self) -> WhileStmt:
        """Parse while loop"""
        self.expect('WHILE')
        condition = self.parse_expr()
        body = self.parse_block()
        return WhileStmt(condition, body)
    
    def parse_return(self) -> ReturnStmt:
        """Parse return statement"""
        self.expect('RETURN')
        value = None
        if not self.match('SEMICOLON') and not self.match('NEWLINE'):
            value = self.parse_expr()
        self.consume('SEMICOLON')
        return ReturnStmt(value)
    
    def parse_expr_stmt(self) -> ASTNode:
        """Parse expression as statement"""
        expr = self.parse_expr()
        self.consume('SEMICOLON')
        return expr
    
    def parse_expr(self) -> ASTNode:
        """Parse expression"""
        return self.parse_or()
    
    def parse_or(self) -> ASTNode:
        """Parse logical OR"""
        left = self.parse_and()
        while self.match('OR'):
            self.advance()
            right = self.parse_and()
            left = BinaryOp('||', left, right)
        return left
    
    def parse_and(self) -> ASTNode:
        """Parse logical AND"""
        left = self.parse_equality()
        while self.match('AND'):
            self.advance()
            right = self.parse_equality()
            left = BinaryOp('&&', left, right)
        return left
    
    def parse_equality(self) -> ASTNode:
        """Parse equality/comparison"""
        left = self.parse_add()
        while self.match('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
            op = self.advance()
            op_str = getattr(op, 'value', str(op))
            right = self.parse_add()
            left = BinaryOp(op_str, left, right)
        return left
    
    def parse_add(self) -> ASTNode:
        """Parse addition/subtraction"""
        left = self.parse_mul()
        while self.match('PLUS', 'MINUS'):
            op = self.advance()
            op_str = '+' if getattr(op, 'type', op) == 'PLUS' else '-'
            right = self.parse_mul()
            left = BinaryOp(op_str, left, right)
        return left
    
    def parse_mul(self) -> ASTNode:
        """Parse multiplication/division"""
        left = self.parse_unary()
        while self.match('STAR', 'SLASH', 'PERCENT'):
            op = self.advance()
            op_map = {'STAR': '*', 'SLASH': '/', 'PERCENT': '%'}
            op_str = op_map.get(getattr(op, 'type', op), '*')
            right = self.parse_unary()
            left = BinaryOp(op_str, left, right)
        return left
    
    def parse_unary(self) -> ASTNode:
        """Parse unary expression"""
        if self.match('MINUS', 'BANG'):
            op = self.advance()
            op_str = '-' if getattr(op, 'type', op) == 'MINUS' else '!'
            operand = self.parse_unary()
            return UnaryOp(op_str, operand)
        return self.parse_call()
    
    def parse_call(self) -> ASTNode:
        """Parse call expression"""
        expr = self.parse_primary()
        
        while True:
            if self.match('LPAREN'):
                args = self.parse_args()
                expr = Call(expr, args)
            elif self.match('DOT'):
                self.advance()
                field = self.expect('IDENT')
                field_name = getattr(field, 'value', str(field))
                expr = BinaryOp('.', expr, Identifier(field_name))
            elif self.match('LBRACKET'):
                self.advance()
                index = self.parse_expr()
                self.expect('RBRACKET')
                expr = BinaryOp('[]', expr, index)
            else:
                break
        
        return expr
    
    def parse_args(self) -> List[ASTNode]:
        """Parse call arguments"""
        self.expect('LPAREN')
        args = []
        while not self.match('RPAREN'):
            if args:
                self.expect('COMMA')
            args.append(self.parse_expr())
        self.expect('RPAREN')
        return args
    
    def parse_primary(self) -> ASTNode:
        """Parse primary expression"""
        if self.match('INT'):
            token = self.advance()
            value = int(getattr(token, 'value', str(token)))
            return Literal(value, 'Int')
        
        elif self.match('FLOAT'):
            token = self.advance()
            value = float(getattr(token, 'value', str(token)))
            return Literal(value, 'Float')
        
        elif self.match('STRING'):
            token = self.advance()
            value = getattr(token, 'value', str(token))
            return Literal(value, 'String')
        
        elif self.match('TRUE'):
            self.advance()
            return Literal(True, 'Bool')
        
        elif self.match('FALSE'):
            self.advance()
            return Literal(False, 'Bool')
        
        elif self.match('UNIT'):
            self.advance()
            return Literal(None, 'Unit')
        
        elif self.match('IDENT'):
            token = self.advance()
            name = getattr(token, 'value', str(token))
            return Identifier(name)
        
        elif self.match('LPAREN'):
            self.advance()
            if self.match('RPAREN'):
                self.advance()
                return Literal(None, 'Unit')
            expr = self.parse_expr()
            self.expect('RPAREN')
            return expr
        
        elif self.match('LBRACKET'):
            return self.parse_list()
        
        raise ParseError(f"Unexpected token: {self.current()}")
    
    def parse_list(self) -> ASTNode:
        """Parse list literal"""
        self.expect('LBRACKET')
        elements = []
        while not self.match('RBRACKET'):
            if elements:
                self.expect('COMMA')
            elements.append(self.parse_expr())
        self.expect('RBRACKET')
        return Call(Identifier('list'), elements)

def parse(source: str) -> Program:
    """Parse HLF source code"""
    from .lexer import Lexer
    lexer = Lexer(source)
    tokens = lexer.tokenize()
    parser = Parser(tokens)
    return parser.parse()
