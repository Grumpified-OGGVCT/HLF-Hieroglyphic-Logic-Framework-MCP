"""
HLF Parser - LALR(1) parser for HLF grammar
Converts tokens to AST
"""

from typing import List, Optional, Callable, Dict, Any
from .lexer import Token, TokenType, Lexer, LexerError
from .ast_nodes import *

class ParseError(Exception):
    def __init__(self, message: str, token: Optional[Token] = None):
        self.message = message
        self.token = token
        if token and token.loc:
            super().__init__(f"{message} at line {token.loc.start.line}, column {token.loc.start.column}")
        else:
            super().__init__(message)

class Parser:
    """LALR(1) Parser for HLF"""
    
    def __init__(self, tokens: List[Token], filename: str = "<input>"):
        self.tokens = tokens
        self.pos = 0
        self.filename = filename
        
    def error(self, message: str) -> ParseError:
        token = self.current() if self.pos < len(self.tokens) else None
        return ParseError(message, token)
    
    def current(self) -> Token:
        if self.pos >= len(self.tokens):
            return self.tokens[-1]  # EOF
        return self.tokens[self.pos]
    
    def peek(self, offset: int = 0) -> Token:
        idx = self.pos + offset
        if idx >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[idx]
    
    def advance(self) -> Token:
        token = self.current()
        if self.pos < len(self.tokens):
            self.pos += 1
        return token
    
    def match(self, *types: TokenType) -> bool:
        return self.current().type in types
    
    def consume(self, type: TokenType, message: Optional[str] = None) -> Token:
        if self.current().type != type:
            expected = message or type.name
            raise self.error(f"Expected {expected}, got {self.current().type.name}")
        return self.advance()
    
    def skip_newlines(self) -> None:
        while self.match(TokenType.NEWLINE):
            self.advance()

    def _skip_separators(self) -> None:
        while self.match(TokenType.NEWLINE, TokenType.SEMICOLON):
            self.advance()

    def parse(self) -> Module:
        """Parse module"""
        self.skip_newlines()
        
        # Module doc comment
        doc = None
        # TODO: Parse doc comments
        
        imports = []
        declarations = []
        
        while not self.match(TokenType.EOF):
            self._skip_separators()
            
            if self.match(TokenType.EOF):
                break
            elif self.match(TokenType.IMPORT):
                imports.append(self.parse_import())
            elif self.match(TokenType.FN):
                declarations.append(self.parse_function())
            elif self.match(TokenType.SPEC):
                declarations.append(self.parse_spec())
            elif self.match(TokenType.TYPE):
                declarations.append(self.parse_type_decl())
            elif self.match(TokenType.CONST):
                declarations.append(self.parse_const())
            else:
                raise self.error(f"Unexpected token: {self.current().type.name}")
            
            self._skip_separators()
        
        loc = Location(
            Position(1, 1, 0),
            self.current().loc.end if self.current().loc else Position(1, 1, 0),
            self.filename
        )
        
        return Module(
            name=self.filename,
            doc=doc,
            imports=imports,
            declarations=declarations,
            loc=loc
        )
    
    def parse_import(self) -> Import:
        """Parse import statement"""
        start = self.current()
        self.consume(TokenType.IMPORT)
        
        # import path
        if self.match(TokenType.STRING):
            path = self.advance().value
        elif self.match(TokenType.IDENT):
            path = self.advance().value
        else:
            raise self.error("Expected import path")
        
        alias = None
        items = None
        
        # import path as alias
        if self.match(TokenType.AS):
            self.advance()
            alias = self.consume(TokenType.IDENT).value
        
        # import { items } from path
        # or: import items from path
        elif self.match(TokenType.IDENT, TokenType.LBRACE):
            if self.match(TokenType.LBRACE):
                items = self.parse_import_items()
            else:
                items = [self.advance().value]
            
            if self.match(TokenType.FROM):
                self.advance()
                if self.match(TokenType.STRING):
                    path = self.advance().value
                elif self.match(TokenType.IDENT):
                    path = self.advance().value
        
        return Import(path=path, alias=alias, items=items)
    
    def parse_import_items(self) -> List[str]:
        """Parse import items { a, b, c }"""
        self.consume(TokenType.LBRACE)
        items = []
        
        while not self.match(TokenType.RBRACE):
            item = self.consume(TokenType.IDENT).value
            items.append(item)
            
            if self.match(TokenType.COMMA):
                self.advance()
                self.skip_newlines()
            else:
                break
        
        self.consume(TokenType.RBRACE)
        return items
    
    def parse_function(self) -> FunctionDecl:
        """Parse function declaration"""
        start = self.current()
        self.consume(TokenType.FN)
        
        name = Identifier(self.consume(TokenType.IDENT).value)
        
        # Parse parameters
        self.consume(TokenType.LPAREN)
        params = []
        
        while not self.match(TokenType.RPAREN):
            param = self.parse_parameter()
            params.append(param)
            
            if self.match(TokenType.COMMA):
                self.advance()
                self.skip_newlines()
            else:
                break
        
        self.consume(TokenType.RPAREN)
        
        # Return type annotation
        return_type = None
        if self.match(TokenType.COLON):
            self.advance()
            return_type = self.parse_type()
        
        # Effect annotation
        effects = []
        if self.match(TokenType.EFFECT):
            effects = self.parse_effects()
        
        # Tier annotation
        tiers = []
        if self.match(TokenType.TIER):
            tiers = self.parse_tiers()
        
        # Gas annotation
        gas = None
        if self.match(TokenType.GAS):
            self.advance()
            gas = int(self.consume(TokenType.INT).value)
        
        # Function body
        body = self.parse_block()
        
        loc = Location(start.loc.start, body.loc.end if body.loc else start.loc.end, self.filename)
        
        return FunctionDecl(
            name=name,
            params=params,
            return_type=return_type,
            effects=effects,
            tiers=tiers,
            gas=gas,
            body=body,
            loc=loc
        )
    
    def parse_parameter(self) -> Parameter:
        """Parse function parameter"""
        name = self.consume(TokenType.IDENT).value
        
        param_type = None
        if self.match(TokenType.COLON):
            self.advance()
            param_type = self.parse_type()
        
        default = None
        if self.match(TokenType.ASSIGN):
            self.advance()
            default = self.parse_expression()
        
        return Parameter(name=name, param_type=param_type, default=default)
    
    def parse_effects(self) -> List[Effect]:
        """Parse effect annotation"""
        self.consume(TokenType.EFFECT)
        self.consume(TokenType.LBRACKET)
        
        effects = []
        while not self.match(TokenType.RBRACKET):
            name = self.consume(TokenType.IDENT).value
            args = []
            
            if self.match(TokenType.LPAREN):
                self.advance()
                while not self.match(TokenType.RPAREN):
                    args.append(self.parse_expression())
                    if self.match(TokenType.COMMA):
                        self.advance()
                self.consume(TokenType.RPAREN)
            
            effects.append(Effect(name=name, args=args))
            
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break
        
        self.consume(TokenType.RBRACKET)
        return effects
    
    def parse_tiers(self) -> List[str]:
        """Parse tier annotation"""
        self.consume(TokenType.TIER)
        self.consume(TokenType.LBRACKET)
        
        tiers = []
        while not self.match(TokenType.RBRACKET):
            tier = self.consume(TokenType.IDENT).value
            tiers.append(tier)
            
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break
        
        self.consume(TokenType.RBRACKET)
        return tiers
    
    def parse_block(self) -> Block:
        """Parse block { stmts }"""
        start = self.current()
        self.consume(TokenType.LBRACE)
        self._skip_separators()
        
        statements = []
        while not self.match(TokenType.RBRACE):
            stmt = self.parse_statement()
            statements.append(stmt)
            self._skip_separators()
        
        end = self.current()
        self.consume(TokenType.RBRACE)
        
        loc = Location(start.loc.start, end.loc.end if end.loc else start.loc.end, self.filename)
        return Block(statements=statements)
    
    def parse_statement(self) -> Statement:
        """Parse statement"""
        self.skip_newlines()
        
        if self.match(TokenType.LET):
            return self.parse_let()
        elif self.match(TokenType.CONST):
            return self.parse_const_stmt()
        elif self.match(TokenType.RETURN):
            return self.parse_return()
        elif self.match(TokenType.IF):
            return self.parse_if_stmt()
        elif self.match(TokenType.FOR):
            return self.parse_for()
        elif self.match(TokenType.MATCH):
            return self.parse_match_stmt()
        elif self.match(TokenType.BREAK):
            self.advance()
            return BreakStmt()
        elif self.match(TokenType.CONTINUE):
            self.advance()
            return ContinueStmt()
        else:
            # Expression statement
            expr = self.parse_expression()
            return ExprStmt(expression=expr)
    
    def parse_let(self) -> LetStmt:
        """Parse let statement"""
        self.consume(TokenType.LET)
        
        mutable = False
        if self.match(TokenType.MUT):
            self.advance()
            mutable = True
        
        name = Identifier(self.consume(TokenType.IDENT).value)
        
        # Type annotation
        if self.match(TokenType.COLON):
            self.advance()
            self.parse_type()  # TODO: store type annotation
        
        self.consume(TokenType.ASSIGN)
        value = self.parse_expression()
        
        return LetStmt(name=name, value=value, mutable=mutable)
    
    def parse_const_stmt(self) -> ConstStmt:
        """Parse const statement"""
        self.consume(TokenType.CONST)
        name = Identifier(self.consume(TokenType.IDENT).value)
        self.consume(TokenType.ASSIGN)
        value = self.parse_expression()
        return ConstStmt(name=name, value=value)
    
    def parse_return(self) -> ReturnStmt:
        """Parse return statement"""
        self.consume(TokenType.RETURN)
        value = None
        if not self.match(TokenType.NEWLINE, TokenType.RBRACE, TokenType.SEMICOLON):
            value = self.parse_expression()
        return ReturnStmt(value=value)
    
    def parse_if_stmt(self) -> IfStmt:
        """Parse if statement"""
        self.consume(TokenType.IF)
        condition = self.parse_expression()
        self.consume(TokenType.THEN)
        then_block = self.parse_block()
        
        else_block = None
        if self.match(TokenType.ELSE):
            self.advance()
            if self.match(TokenType.IF):
                # else if
                else_stmt = self.parse_if_stmt()
                else_block = Block(statements=[else_stmt])
            else:
                else_block = self.parse_block()
        
        return IfStmt(condition=condition, then_block=then_block, else_block=else_block)
    
    def parse_for(self) -> ForStmt:
        """Parse for statement"""
        self.consume(TokenType.FOR)
        var = Identifier(self.consume(TokenType.IDENT).value)
        self.consume(TokenType.IN)
        iterable = self.parse_expression()
        body = self.parse_block()
        return ForStmt(variable=var, iterable=iterable, body=body)
    
    def parse_match_stmt(self) -> MatchStmt:
        """Parse match statement"""
        self.consume(TokenType.MATCH)
        subject = self.parse_expression()
        self.consume(TokenType.WITH)
        
        self.consume(TokenType.LBRACE)
        self.skip_newlines()
        
        arms = []
        while not self.match(TokenType.RBRACE):
            arm = self.parse_match_stmt_arm()
            arms.append(arm)
            self.skip_newlines()
        
        self.consume(TokenType.RBRACE)
        return MatchStmt(subject=subject, arms=arms)
    
    def parse_match_stmt_arm(self) -> MatchStmtArm:
        """Parse match statement arm"""
        pattern = self.parse_pattern()
        
        guard = None
        if self.match(TokenType.IF):
            self.advance()
            guard = self.parse_expression()
        
        self.skip_newlines()
        body = self.parse_block()
        
        return MatchStmtArm(pattern=pattern, body=body, guard=guard)
    
    def parse_pattern(self) -> Pattern:
        """Parse pattern"""
        if self.match(TokenType.UNDERSCORE):  # TODO: add UNDERSCORE token
            self.advance()
            return WildcardPattern()
        elif self.match(TokenType.CAPITAL_IDENT):
            # Constructor pattern
            ctor = Identifier(self.advance().value)
            fields = []
            if self.match(TokenType.LBRACE):
                self.advance()
                while not self.match(TokenType.RBRACE):
                    name = self.consume(TokenType.IDENT).value
                    self.consume(TokenType.ASSIGN)
                    pattern = self.parse_pattern()
                    fields.append({"name": name, "pattern": pattern})
                    if self.match(TokenType.COMMA):
                        self.advance()
                self.consume(TokenType.RBRACE)
            return ConstructorPattern(constructor=ctor, fields=fields)
        elif self.match(TokenType.IDENT):
            # Identifier pattern
            name = self.advance().value
            return IdentPattern(name=name)
        elif self.match(TokenType.INT, TokenType.FLOAT, TokenType.STRING, TokenType.BOOL, TokenType.ATOM):
            # Literal pattern
            lit = self.parse_literal()
            return LiteralPattern(value=lit)
        else:
            raise self.error(f"Expected pattern, got {self.current().type.name}")
    
    def parse_spec(self) -> SpecDecl:
        """Parse spec declaration"""
        self.consume(TokenType.SPEC)
        name = Identifier(self.consume(TokenType.IDENT).value)
        
        self.consume(TokenType.LBRACE)
        self.skip_newlines()
        
        constraints = []
        while not self.match(TokenType.RBRACE):
            # Parse constraint (invariant, ensures, requires)
            # TODO: implement full constraint parsing
            self.advance()  # Placeholder
        
        self.consume(TokenType.RBRACE)
        return SpecDecl(name=name, constraints=constraints)
    
    def parse_type_decl(self) -> TypeDecl:
        """Parse type declaration"""
        self.consume(TokenType.TYPE)
        name = Identifier(self.consume(TokenType.IDENT).value)
        self.consume(TokenType.ASSIGN)
        definition = self.parse_type()
        return TypeDecl(name=name, definition=definition)
    
    def parse_const(self) -> ConstDecl:
        """Parse const declaration"""
        self.consume(TokenType.CONST)
        name = Identifier(self.consume(TokenType.IDENT).value)
        self.consume(TokenType.ASSIGN)
        value = self.parse_expression()
        return ConstDecl(name=name, value=value)
    
    def parse_type(self) -> Type:
        """Parse type expression"""
        if self.match(TokenType.CAPITAL_IDENT):
            name = self.advance().value
            # Generic type: Name[T, U]
            if self.match(TokenType.LBRACKET):
                self.advance()
                params = [self.parse_type()]
                while self.match(TokenType.COMMA):
                    self.advance()
                    params.append(self.parse_type())
                self.consume(TokenType.RBRACKET)
                return GenericType(name=name, params=params)
            return NamedType(name=name)
        elif self.match(TokenType.IDENT):
            name = self.advance().value
            return PrimitiveType(name=name)
        elif self.match(TokenType.LPAREN):
            # Function type: (A, B) -> C
            self.advance()
            params = []
            while not self.match(TokenType.RPAREN):
                params.append(self.parse_type())
                if self.match(TokenType.COMMA):
                    self.advance()
            self.consume(TokenType.RPAREN)
            if self.match(TokenType.ARROW):
                self.advance()
                ret = self.parse_type()
                return FunctionType(params=params, return_type=ret)
            return PrimitiveType(name="unit")
        return PrimitiveType(name="unit")
    
    def parse_expression(self) -> Expression:
        """Parse expression (using precedence climbing)"""
        return self.parse_pipeline()
    
    def parse_pipeline(self) -> Expression:
        """Parse pipeline expression (lowest precedence)"""
        left = self.parse_or()
        
        while self.match(TokenType.PIPELINE):
            self.advance()
            right = self.parse_or()
            left = PipelineExpr(left=left, right=right)
        
        return left
    
    def parse_or(self) -> Expression:
        """Parse logical or"""
        left = self.parse_and()
        
        while self.match(TokenType.DOUBLE_PIPE):
            op = self.advance().value
            right = self.parse_and()
            left = BinaryExpr(operator=op, left=left, right=right)
        
        return left
    
    def parse_and(self) -> Expression:
        """Parse logical and"""
        left = self.parse_equality()
        
        while self.match(TokenType.DOUBLE_AMPERSAND):
            op = self.advance().value
            right = self.parse_equality()
            left = BinaryExpr(operator=op, left=left, right=right)
        
        return left
    
    def parse_equality(self) -> Expression:
        """Parse equality comparisons"""
        left = self.parse_comparison()
        
        while self.match(TokenType.EQ, TokenType.NE):
            op = self.advance().value
            right = self.parse_comparison()
            left = BinaryExpr(operator=op, left=left, right=right)
        
        return left
    
    def parse_comparison(self) -> Expression:
        """Parse comparison operators"""
        left = self.parse_additive()
        
        while self.match(TokenType.LT, TokenType.LE, TokenType.GT, TokenType.GE):
            op = self.advance().value
            right = self.parse_additive()
            left = BinaryExpr(operator=op, left=left, right=right)
        
        return left
    
    def parse_additive(self) -> Expression:
        """Parse addition/subtraction"""
        left = self.parse_multiplicative()
        
        while self.match(TokenType.PLUS, TokenType.MINUS):
            op = self.advance().value
            right = self.parse_multiplicative()
            left = BinaryExpr(operator=op, left=left, right=right)
        
        return left
    
    def parse_multiplicative(self) -> Expression:
        """Parse multiplication/division/modulo"""
        left = self.parse_unary()
        
        while self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self.advance().value
            right = self.parse_unary()
            left = BinaryExpr(operator=op, left=left, right=right)
        
        return left
    
    def parse_unary(self) -> Expression:
        """Parse unary operators"""
        if self.match(TokenType.MINUS, TokenType.BANG, TokenType.TILDE):
            op = self.advance().value
            operand = self.parse_unary()
            return UnaryExpr(operator=op, operand=operand)
        
        return self.parse_postfix()
    
    def parse_postfix(self) -> Expression:
        """Parse postfix expressions (calls, field access, indexing)"""
        expr = self.parse_primary()
        
        while True:
            if self.match(TokenType.LPAREN):
                # Function call
                self.advance()
                args = []
                kwargs = {}
                
                while not self.match(TokenType.RPAREN):
                    if self.match(TokenType.IDENT) and self.peek(1).type == TokenType.ASSIGN:
                        # Keyword argument
                        key = self.advance().value
                        self.advance()  # =
                        val = self.parse_expression()
                        kwargs[key] = val
                    else:
                        # Positional argument
                        args.append(self.parse_expression())
                    
                    if self.match(TokenType.COMMA):
                        self.advance()
                    else:
                        break
                
                self.consume(TokenType.RPAREN)
                expr = CallExpr(callee=expr, arguments=args, keyword_args=kwargs)
            
            elif self.match(TokenType.DOT):
                # Field access
                self.advance()
                field = Identifier(self.consume(TokenType.IDENT).value)
                expr = FieldExpr(obj=expr, field=field)
            
            elif self.match(TokenType.LBRACKET):
                # Index access
                self.advance()
                index = self.parse_expression()
                self.consume(TokenType.RBRACKET)
                expr = IndexExpr(obj=expr, index=index)
            
            else:
                break
        
        return expr
    
    def parse_primary(self) -> Expression:
        """Parse primary expressions"""
        if self.match(TokenType.INT, TokenType.FLOAT, TokenType.STRING, TokenType.BOOL, TokenType.ATOM):
            return self.parse_literal()
        
        elif self.match(TokenType.IDENT):
            return Identifier(self.advance().value)
        
        elif self.match(TokenType.LPAREN):
            self.advance()
            if self.match(TokenType.RPAREN):
                self.advance()
                return Literal.unit()
            
            expr = self.parse_expression()
            
            # Check for tuple
            if self.match(TokenType.COMMA):
                elements = [expr]
                while self.match(TokenType.COMMA):
                    self.advance()
                    elements.append(self.parse_expression())
                self.consume(TokenType.RPAREN)
                return TupleExpr(elements=elements)
            
            self.consume(TokenType.RPAREN)
            return expr
        
        elif self.match(TokenType.LBRACKET):
            return self.parse_list()
        
        elif self.match(TokenType.LBRACE):
            return self.parse_record()
        
        elif self.match(TokenType.FN):
            return self.parse_lambda()
        
        elif self.match(TokenType.IF):
            return self.parse_if_expr()
        
        elif self.match(TokenType.MATCH):
            return self.parse_match_expr()
        
        else:
            raise self.error(f"Unexpected token: {self.current().type.name}")
    
    def parse_literal(self) -> Literal:
        """Parse literal value"""
        token = self.advance()
        
        if token.type == TokenType.INT:
            return Literal.int(int(token.value))
        elif token.type == TokenType.FLOAT:
            return Literal.float(float(token.value))
        elif token.type == TokenType.STRING:
            return Literal.string(token.value)
        elif token.type == TokenType.BOOL:
            return Literal.bool(token.value == 'true')
        elif token.type == TokenType.ATOM:
            return Literal.atom(token.value)
        elif token.type == TokenType.UNIT:
            return Literal.unit()
        else:
            raise self.error(f"Expected literal, got {token.type.name}")
    
    def parse_list(self) -> ListExpr:
        """Parse list literal [a, b, c]"""
        self.consume(TokenType.LBRACKET)
        elements = []
        
        while not self.match(TokenType.RBRACKET):
            elements.append(self.parse_expression())
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break
        
        self.consume(TokenType.RBRACKET)
        return ListExpr(elements=elements)
    
    def parse_record(self) -> RecordExpr:
        """Parse record literal {field: value, ...}"""
        self.consume(TokenType.LBRACE)
        fields = []
        
        while not self.match(TokenType.RBRACE):
            name = self.consume(TokenType.IDENT).value
            self.consume(TokenType.COLON)
            value = self.parse_expression()
            fields.append(RecordField(name=name, value=value))
            
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break
        
        self.consume(TokenType.RBRACE)
        return RecordExpr(fields=fields)
    
    def parse_lambda(self) -> LambdaExpr:
        """Parse lambda expression fn (params) => body"""
        self.consume(TokenType.FN)
        
        self.consume(TokenType.LPAREN)
        params = []
        
        while not self.match(TokenType.RPAREN):
            params.append(self.parse_parameter())
            if self.match(TokenType.COMMA):
                self.advance()
            else:
                break
        
        self.consume(TokenType.RPAREN)
        
        # Optional return type
        return_type = None
        if self.match(TokenType.COLON):
            self.advance()
            return_type = self.parse_type()
        
        self.consume(TokenType.ARROW)
        body = self.parse_expression()
        
        return LambdaExpr(params=params, body=body, return_type=return_type)
    
    def parse_if_expr(self) -> IfExpr:
        """Parse if-then-else expression"""
        self.consume(TokenType.IF)
        condition = self.parse_expression()
        self.consume(TokenType.THEN)
        then_branch = self.parse_expression()
        self.consume(TokenType.ELSE)
        else_branch = self.parse_expression()
        return IfExpr(condition=condition, then_branch=then_branch, else_branch=else_branch)
    
    def parse_match_expr(self) -> MatchExpr:
        """Parse match expression"""
        self.consume(TokenType.MATCH)
        subject = self.parse_expression()
        self.consume(TokenType.WITH)
        
        self.consume(TokenType.LBRACE)
        self.skip_newlines()
        
        arms = []
        while not self.match(TokenType.RBRACE):
            arm = self.parse_match_arm()
            arms.append(arm)
            self.skip_newlines()
        
        self.consume(TokenType.RBRACE)
        return MatchExpr(subject=subject, arms=arms)
    
    def parse_match_arm(self) -> MatchArm:
        """Parse match expression arm"""
        pattern = self.parse_pattern()
        
        guard = None
        if self.match(TokenType.IF):
            self.advance()
            guard = self.parse_expression()
        
        self.consume(TokenType.ARROW)
        body = self.parse_expression()
        
        return MatchArm(pattern=pattern, body=body, guard=guard)

# Convenience function
def parse(source: str, filename: str = "<input>") -> Module:
    """Parse HLF source code into AST"""
    from .lexer import tokenize
    tokens = tokenize(source, filename)
    return Parser(tokens, filename).parse()
