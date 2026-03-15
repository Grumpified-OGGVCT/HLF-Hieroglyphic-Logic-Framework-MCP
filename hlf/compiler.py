"""
HLF Compiler
Compiles AST to VM bytecode per spec/vm/bytecode_spec.yaml
"""

from typing import Dict, List, Any, Optional
from .ast_nodes import *
from .vm import Bytecode, Function, Instruction, OpCode, ConstantPool

class CompileError(Exception):
    """Compilation error"""
    pass

class Compiler:
    """HLF AST to bytecode compiler"""
    
    def __init__(self, profile: str = "P0"):
        self.profile = profile
        self.cp = ConstantPool()
        self.functions: Dict[str, Function] = {}
        self.current_func: Optional[Function] = None
        self.local_vars: Dict[str, int] = {}
        self.locals_count = 0
        self.label_counter = 0
    
    def compile(self, module: Module) -> Bytecode:
        """Compile module to bytecode"""
        # Compile all functions
        for decl in module.declarations:
            if isinstance(decl, FunctionDecl):
                self.compile_function(decl)
        
        # Compile main if there are top-level statements
        if module.statements:
            main_func = FunctionDecl(
                name="__main__",
                params=[],
                body=module.statements,
                effects=[]
            )
            self.compile_function(main_func)
        
        return Bytecode(
            version=(1, 0, 0),
            constant_pool=self.cp,
            functions=self.functions,
            entry_point="__main__" if "__main__" in self.functions else (
                self.functions[list(self.functions.keys())[0]].name if self.functions else ""
            )
        )
    
    def compile_function(self, decl: FunctionDecl) -> Function:
        """Compile function declaration"""
        # Reset locals for new function
        self.local_vars = {}
        self.locals_count = 0
        
        # Add parameters as locals
        for param in decl.params:
            self.local_vars[param["name"]] = self.locals_count
            self.locals_count += 1
        
        # Compile body
        code: List[Instruction] = []
        for stmt in decl.body:
            self.compile_statement(stmt, code)
        
        # Ensure return
        if not code or code[-1].opcode not in (OpCode.RETURN, OpCode.RETURN_UNIT):
            code.append(Instruction(OpCode.RETURN_UNIT))
        
        func = Function(
            name=decl.name,
            code=code,
            local_count=self.locals_count,
            entry_point=0,
            effect_indices=self.compile_effects(decl.effects)
        )
        
        self.functions[decl.name] = func
        return func
    
    def compile_effects(self, effects: List[str]) -> List[int]:
        """Compile effect annotations"""
        indices = []
        for effect in effects:
            idx = self.cp.add_host_func_ref(effect)
            indices.append(idx)
        return indices
    
    def compile_statement(self, stmt: ASTNode, code: List[Instruction]) -> None:
        """Compile statement"""
        if isinstance(stmt, BinaryOp) and stmt.op == '=':
            # Assignment
            self.compile_assignment(stmt, code)
        elif isinstance(stmt, IfStmt):
            self.compile_if(stmt, code)
        elif isinstance(stmt, WhileStmt):
            self.compile_while(stmt, code)
        elif isinstance(stmt, MatchStmt):
            self.compile_match(stmt, code)
        elif isinstance(stmt, ReturnStmt):
            self.compile_return(stmt, code)
        else:
            # Expression statement
            self.compile_expr(stmt, code)
            code.append(Instruction(OpCode.POP))
    
    def compile_assignment(self, stmt: BinaryOp, code: List[Instruction]) -> None:
        """Compile assignment"""
        if isinstance(stmt.right, Identifier):
            var_name = stmt.right.name
            if var_name not in self.local_vars:
                self.local_vars[var_name] = self.locals_count
                self.locals_count += 1
        
        self.compile_expr(stmt.left, code)
        
        if isinstance(stmt.right, Identifier):
            code.append(Instruction(OpCode.STORE_LOCAL, [self.local_vars[stmt.right.name]]))
        else:
            raise CompileError(f"Invalid assignment target: {stmt.right}")
    
    def compile_if(self, stmt: IfStmt, code: List[Instruction]) -> None:
        """Compile if statement"""
        # Compile condition
        self.compile_expr(stmt.condition, code)
        
        # Jump if false to else
        else_label = self.new_label()
        end_label = self.new_label()
        
        code.append(Instruction(OpCode.JUMP_IF_FALSE, [else_label]))
        
        # Then branch
        for s in stmt.then_block:
            self.compile_statement(s, code)
        
        # Jump to end
        code.append(Instruction(OpCode.JUMP, [end_label]))
        
        # Else branch
        code[else_label] = Instruction(OpCode.NOP)  # Patch later
        if stmt.else_block:
            for s in stmt.else_block:
                self.compile_statement(s, code)
        
        # End
        code[end_label] = Instruction(OpCode.NOP)
    
    def compile_while(self, stmt: WhileStmt, code: List[Instruction]) -> None:
        """Compile while loop"""
        start_label = len(code)
        
        # Condition
        self.compile_expr(stmt.condition, code)
        end_label = self.new_label()
        code.append(Instruction(OpCode.JUMP_IF_FALSE, [end_label]))
        
        # Body
        for s in stmt.body:
            self.compile_statement(s, code)
        
        # Jump back
        code.append(Instruction(OpCode.JUMP, [start_label - len(code) - 1]))
        
        # End
        code.append(Instruction(OpCode.NOP))
    
    def compile_match(self, stmt: MatchStmt, code: List[Instruction]) -> None:
        """Compile match statement"""
        self.compile_expr(stmt.expr, code)
        
        # Simple matching - only supports int literals
        for case in stmt.cases:
            if isinstance(case.pattern, Literal):
                idx = self.cp.add_int(case.pattern.value)
                code.append(Instruction(OpCode.DUP))
                code.append(Instruction(OpCode.LOAD_CONST, [idx]))
                code.append(Instruction(OpCode.EQ))
                
                next_label = self.new_label()
                code.append(Instruction(OpCode.JUMP_IF_FALSE, [next_label]))
                
                # Match body
                if isinstance(case.body, Block):
                    for s in case.body.statements:
                        self.compile_statement(s, code)
                else:
                    self.compile_expr(case.body, code)
                
                code.append(Instruction(OpCode.NOP))  # Next case
        
        # Default case
        code.append(Instruction(OpCode.POP))  # Remove match value
    
    def compile_return(self, stmt: ReturnStmt, code: List[Instruction]) -> None:
        """Compile return statement"""
        if stmt.value:
            self.compile_expr(stmt.value, code)
            code.append(Instruction(OpCode.RETURN))
        else:
            code.append(Instruction(OpCode.RETURN_UNIT))
    
    def compile_expr(self, expr: ASTNode, code: List[Instruction]) -> None:
        """Compile expression"""
        if isinstance(expr, Literal):
            self.compile_literal(expr, code)
        elif isinstance(expr, Identifier):
            self.compile_identifier(expr, code)
        elif isinstance(expr, BinaryOp):
            self.compile_binary(expr, code)
        elif isinstance(expr, UnaryOp):
            self.compile_unary(expr, code)
        elif isinstance(expr, Call):
            self.compile_call(expr, code)
        elif isinstance(expr, IfStmt):
            # Ternary conditional
            self.compile_conditional(expr, code)
        else:
            raise CompileError(f"Cannot compile expression: {type(expr)}")
    
    def compile_literal(self, expr: Literal, code: List[Instruction]) -> None:
        """Compile literal"""
        if expr.literal_type == 'Int':
            if -128 <= expr.value <= 127:
                code.append(Instruction(OpCode.LOAD_INT_SMALL, [expr.value & 0xFF]))
            else:
                idx = self.cp.add_int(expr.value)
                code.append(Instruction(OpCode.LOAD_CONST, [idx]))
        elif expr.literal_type == 'Float':
            idx = self.cp.add_float(expr.value)
            code.append(Instruction(OpCode.LOAD_CONST, [idx]))
        elif expr.literal_type == 'String':
            idx = self.cp.add_string(expr.value)
            code.append(Instruction(OpCode.LOAD_CONST, [idx]))
        elif expr.literal_type == 'Bool':
            if expr.value:
                code.append(Instruction(OpCode.LOAD_TRUE))
            else:
                code.append(Instruction(OpCode.LOAD_FALSE))
        elif expr.literal_type == 'Unit':
            code.append(Instruction(OpCode.LOAD_UNIT))
    
    def compile_identifier(self, expr: Identifier, code: List[Instruction]) -> None:
        """Compile identifier reference"""
        if expr.name in self.local_vars:
            code.append(Instruction(OpCode.LOAD_LOCAL, [self.local_vars[expr.name]]))
        else:
            # Global or external reference - treat as host function
            idx = self.cp.add_host_func_ref(expr.name)
            code.append(Instruction(OpCode.LOAD_CONST, [idx]))
    
    def compile_binary(self, expr: BinaryOp, code: List[Instruction]) -> None:
        """Compile binary operation"""
        self.compile_expr(expr.left, code)
        self.compile_expr(expr.right, code)
        
        op_map = {
            '+': OpCode.ADD_INT,
            '-': OpCode.SUB_INT,
            '*': OpCode.MUL_INT,
            '/': OpCode.DIV_INT,
            '%': OpCode.MOD_INT,
            '>': OpCode.GT_INT,
            '<': OpCode.LT_INT,
            '>=': OpCode.GE_INT,
            '<=': OpCode.LE_INT,
            '==': OpCode.EQ,
            '!=': OpCode.NE,
            '&&': OpCode.AND,
            '||': OpCode.OR,
        }
        
        if expr.op in op_map:
            code.append(Instruction(op_map[expr.op]))
        else:
            raise CompileError(f"Unknown binary operator: {expr.op}")
    
    def compile_unary(self, expr: UnaryOp, code: List[Instruction]) -> None:
        """Compile unary operation"""
        self.compile_expr(expr.operand, code)
        
        if expr.op == '-':
            code.append(Instruction(OpCode.NEG_INT))
        elif expr.op == '!':
            code.append(Instruction(OpCode.NOT))
        else:
            raise CompileError(f"Unknown unary operator: {expr.op}")
    
    def compile_call(self, expr: Call, code: List[Instruction]) -> None:
        """Compile function call"""
        # Compile arguments
        for arg in expr.args:
            self.compile_expr(arg, code)
        
        # Get function
        if isinstance(expr.func, Identifier):
            func_name = expr.func.name
            if func_name in self.functions:
                # Direct call to known function
                # For now, emit as host call
                idx = self.cp.add_host_func_ref(func_name)
                code.append(Instruction(OpCode.CALL_HOST, [idx, len(expr.args)]))
            else:
                # Host function call
                idx = self.cp.add_host_func_ref(func_name)
                code.append(Instruction(OpCode.CALL_HOST, [idx, len(expr.args)]))
        else:
            # Dynamic call
            self.compile_expr(expr.func, code)
            # TODO: Support dynamic calls
    
    def compile_conditional(self, expr: IfStmt, code: List[Instruction]) -> None:
        """Compile conditional expression"""
        self.compile_expr(expr.condition, code)
        
        else_label = self.new_label()
        end_label = self.new_label()
        
        code.append(Instruction(OpCode.JUMP_IF_FALSE, [else_label]))
        
        # Then
        for s in expr.then_block:
            self.compile_statement(s, code)
        code.append(Instruction(OpCode.JUMP, [end_label]))
        
        # Else
        code.append(Instruction(OpCode.NOP))
        if expr.else_block:
            for s in expr.else_block:
                self.compile_statement(s, code)
        
        code.append(Instruction(OpCode.NOP))
    
    def new_label(self) -> int:
        """Create new label index"""
        label = self.label_counter
        self.label_counter += 1
        return label
