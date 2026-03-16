"""
HLF Complete Compiler
AST -> Bytecode with optimizations
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

from .ast_nodes import *
from ..vm.bytecode import BytecodeModule, Function, OpCode
from ..vm.value import Value

class CompileError(Exception):
    """Compilation error"""
    pass

@dataclass
class LocalVar:
    """Local variable info"""
    name: str
    index: int
    is_captured: bool = False

@dataclass
class CompileContext:
    """Compilation context"""
    module: BytecodeModule
    function: Function
    locals: List[LocalVar] = field(default_factory=list)
    globals: Set[str] = field(default_factory=set)
    loop_stack: List[tuple] = field(default_factory=list)  # (start_label, end_label)
    label_counter: int = 0
    
    def add_local(self, name: str) -> int:
        """Add local variable, return index"""
        idx = len(self.locals)
        self.locals.append(LocalVar(name, idx))
        return idx
    
    def resolve_local(self, name: str) -> Optional[int]:
        """Resolve local variable, return index or None"""
        for i, local in enumerate(reversed(self.locals)):
            if local.name == name:
                return len(self.locals) - 1 - i
        return None
    
    def new_label(self) -> int:
        """Generate new label"""
        self.label_counter += 1
        return self.label_counter

def _resolve_name(obj) -> str:
    """Extract string name from an Identifier, string, or dict."""
    if isinstance(obj, str):
        return obj
    if hasattr(obj, 'name'):
        return _resolve_name(obj.name)
    if isinstance(obj, dict):
        return obj.get('name', str(obj))
    return str(obj)

class Compiler:
    """HLF to Bytecode compiler"""
    
    def __init__(self):
        self.module: Optional[BytecodeModule] = None
        self.ctx: Optional[CompileContext] = None
        self.optimization_level = 1
    
    def compile(self, ast, optimization_level: int = 1) -> BytecodeModule:
        """Compile AST (Module or Program) to bytecode module"""
        self.optimization_level = optimization_level
        name = getattr(ast, 'surface', None) or getattr(ast, 'name', 'module')
        self.module = BytecodeModule(name)
        
        # Compile all declarations
        for decl in ast.declarations:
            self._compile_declaration(decl)
        
        # Compile main body (root-level statements if present)
        body = getattr(ast, 'body', None)
        if body:
            main = Function("main", 0)
            main.local_count = 0
            main.max_stack = 4
            main.gas_limit = 10000
            
            ctx = CompileContext(self.module, main)
            self.ctx = ctx
            
            for stmt in body:
                self._compile_statement(stmt)
            
            main.code.append(OpCode.RETURN_UNIT)
            
            main_idx = self.module.add_function(main)
            self.module.entry_point = main_idx
        
        # Optimize if requested
        if optimization_level >= 1:
            self._optimize()
        
        return self.module
    
    def _compile_declaration(self, decl: ASTNode) -> None:
        """Compile top-level declaration"""
        if isinstance(decl, FunctionDecl):
            self._compile_function_decl(decl)
        elif isinstance(decl, SpecDecl):
            self._compile_spec_decl(decl)
        elif isinstance(decl, EffectDecl):
            self._compile_effect_decl(decl)
        elif isinstance(decl, AgentDecl):
            self._compile_agent_decl(decl)
        elif isinstance(decl, ProcDecl):
            self._compile_proc_decl(decl)
        elif isinstance(decl, Binding):
            self._compile_global_binding(decl)
    
    def _compile_function_decl(self, decl: FunctionDecl) -> int:
        """Compile function declaration, return function index"""
        func = Function(_resolve_name(decl.name), len(decl.params))
        func.local_count = len(decl.params)  # Params become locals
        func.max_stack = 4
        func.gas_limit = 10000
        
        # Convert effects to indices
        func.effects = [self.module.get_atom_index(_resolve_name(eff)) for eff in getattr(decl, 'effects', [])]
        
        ctx = CompileContext(self.module, func)
        self.ctx = ctx
        
        # Add parameters as locals
        for param in decl.params:
            pname = _resolve_name(param) if isinstance(param, str) else _resolve_name(getattr(param, 'name', param))
            ctx.add_local(pname)
        
        # Compile body
        self._compile_block(decl.body)
        
        # Implicit return: if last instruction is POP (from an ExprStmt),
        # replace it with RETURN so the expression value is returned.
        if func.code and self._opcode_of(func.code[-1]) == OpCode.POP:
            func.code[-1] = OpCode.RETURN
        elif not func.code or self._opcode_of(func.code[-1]) != OpCode.RETURN:
            func.code.append(OpCode.RETURN_UNIT)
        
        # Update local_count to include locals created during body compilation
        func.local_count = len(ctx.locals)
        func.name_idx = self.module.add_string(_resolve_name(decl.name))
        
        return self.module.add_function(func)
    
    def _compile_spec_decl(self, decl: SpecDecl) -> None:
        """Compile spec declaration"""
        func = Function(f"spec:{_resolve_name(decl.name)}", 0)
        func.code = [OpCode.RETURN_UNIT]
        self.module.add_function(func)
    
    def _compile_effect_decl(self, decl: EffectDecl) -> None:
        """Compile effect declaration"""
        params = getattr(decl, 'params', getattr(decl, 'operations', []))
        func = Function(f"effect:{_resolve_name(decl.name)}", len(params))
        func.code = [OpCode.RETURN_UNIT]
        self.module.add_function(func)
    
    def _compile_agent_decl(self, decl: AgentDecl) -> None:
        """Compile agent declaration"""
        func = Function(f"agent:{_resolve_name(decl.name)}", 0)
        
        ctx = CompileContext(self.module, func)
        self.ctx = ctx
        
        # Compile agent clauses
        for clause in decl.clauses:
            self._compile_agent_clause(clause)
        
        self.module.add_function(func)
    
    def _compile_agent_clause(self, clause: AgentClause) -> None:
        """Compile agent clause"""
        # WHEN condition
        if clause.when:
            self._compile_expression(clause.when)
            end_label = self.ctx.new_label()
            self._emit(OpCode.JUMP_IF_FALSE, 0)  # Will patch later
            jump_idx = len(self.ctx.function.code) - 1
        
        # ON condition
        if clause.on:
            self._compile_expression(clause.on)
            self._emit(OpCode.JUMP_IF_FALSE, 0)
        
        # DO actions
        for stmt in clause.do:
            self._compile_statement(stmt)
    
    def _compile_proc_decl(self, decl: ProcDecl) -> int:
        """Compile procedure"""
        func = Function(_resolve_name(decl.name), len(decl.params))
        func.local_count = len(decl.params)
        func.max_stack = 4
        func.gas_limit = 10000
        
        ctx = CompileContext(self.module, func)
        self.ctx = ctx
        
        for param in decl.params:
            ctx.add_local(_resolve_name(param))
        
        self._compile_block(decl.body)
        
        if not func.code or func.code[-1] != OpCode.RETURN:
            func.code.append(OpCode.RETURN_UNIT)
        
        return self.module.add_function(func)
    
    def _compile_global_binding(self, binding: Binding) -> None:
        """Compile global binding"""
        self.ctx.globals.add(binding.name)
    
    def _compile_statement(self, stmt: Statement) -> None:
        """Compile statement"""
        if isinstance(stmt, LetStmt):
            self._compile_let(stmt)
        elif isinstance(stmt, IfStmt):
            self._compile_if(stmt)
        elif isinstance(stmt, GuardStmt):
            self._compile_guard(stmt)
        elif isinstance(stmt, ReturnStmt):
            self._compile_return(stmt)
        elif isinstance(stmt, ExprStmt):
            self._compile_expression(stmt.expression)
            self._emit(OpCode.POP)  # Discard result
        elif isinstance(stmt, LoopStmt):
            self._compile_loop(stmt)
        elif isinstance(stmt, MatchStmt):
            self._compile_match(stmt)
        elif isinstance(stmt, BlockStmt):
            self._compile_block(stmt.statements)
    
    def _compile_let(self, stmt: LetStmt) -> None:
        """Compile let statement"""
        self._compile_expression(stmt.value)
        idx = self.ctx.add_local(_resolve_name(stmt.name))
        self._emit(OpCode.STORE_LOCAL, idx)
    
    def _compile_if(self, stmt: IfStmt) -> None:
        """Compile if statement"""
        # Condition
        self._compile_expression(stmt.condition)
        
        else_label = self.ctx.new_label()
        self._emit(OpCode.JUMP_IF_FALSE, 0)  # Placeholder
        cond_jump_idx = len(self.ctx.function.code) - 1
        
        # Then block
        then_body = getattr(stmt, 'then_body', None) or getattr(stmt, 'then_block', None)
        self._compile_block(then_body)
        
        # Jump over else
        end_label = self.ctx.new_label()
        self._emit(OpCode.JUMP, 0)
        end_jump_idx = len(self.ctx.function.code) - 1
        
        # Else block
        else_target = len(self.ctx.function.code)
        self._patch_jump(cond_jump_idx, else_target - cond_jump_idx - 1)
        
        else_body = getattr(stmt, 'else_body', None) or getattr(stmt, 'else_block', None)
        if else_body:
            self._compile_block(else_body)
        
        # End
        end_target = len(self.ctx.function.code)
        self._patch_jump(end_jump_idx, end_target - end_jump_idx - 1)
    
    def _compile_guard(self, stmt: GuardStmt) -> None:
        """Compile guard statement"""
        self._compile_expression(stmt.condition)
        
        else_label = self.ctx.new_label()
        self._emit(OpCode.JUMP_IF_TRUE, 0)
        cond_jump_idx = len(self.ctx.function.code) - 1
        
        # Otherwise block
        self._compile_block(stmt.otherwise_body)
        self._emit(OpCode.RETURN_UNIT)
        
        # Continue after guard
        target = len(self.ctx.function.code)
        self._patch_jump(cond_jump_idx, target - cond_jump_idx - 1)
    
    def _compile_return(self, stmt: ReturnStmt) -> None:
        """Compile return statement"""
        if stmt.value:
            self._compile_expression(stmt.value)
            self._emit(OpCode.RETURN)
        else:
            self._emit(OpCode.RETURN_UNIT)
    
    def _compile_loop(self, stmt: LoopStmt) -> None:
        """Compile loop statement"""
        if stmt.loop_type == "infinite":
            start_label = len(self.ctx.function.code)
            self._compile_block(stmt.body)
            # Jump back
            offset = start_label - len(self.ctx.function.code)
            self._emit(OpCode.JUMP, offset)
        
        elif stmt.loop_type == "while":
            start_label = len(self.ctx.function.code)
            
            # Condition
            self._compile_expression(stmt.condition)
            self._emit(OpCode.JUMP_IF_FALSE, 0)
            exit_jump_idx = len(self.ctx.function.code) - 1
            
            # Body
            self._compile_block(stmt.body)
            
            # Jump back
            offset = start_label - len(self.ctx.function.code)
            self._emit(OpCode.JUMP, offset)
            
            # Exit
            exit_target = len(self.ctx.function.code)
            self._patch_jump(exit_jump_idx, exit_target - exit_jump_idx - 1)
        
        elif stmt.loop_type == "for":
            # FOR x IN iterable
            # Desugar to: iterator = iterable; while (not done) { x = next(iterator); body }
            
            # Add iterator variable
            iter_idx = self.ctx.add_local(f"__iter_{self.ctx.new_label()}")
            
            # Compile iterable
            self._compile_expression(stmt.iterable)
            self._emit(OpCode.STORE_LOCAL, iter_idx)
            
            # Loop
            start_label = len(self.ctx.function.code)
            
            # Check if more elements
            self._emit(OpCode.LOAD_LOCAL, iter_idx)
            # Simplified: just check if non-empty
            self._emit(OpCode.JUMP_IF_FALSE, 0)
            exit_jump_idx = len(self.ctx.function.code) - 1
            
            # Get next element
            self._emit(OpCode.LOAD_LOCAL, iter_idx)
            self._emit(OpCode.LIST_HEAD)
            loop_var_idx = self.ctx.add_local(stmt.iterator)
            self._emit(OpCode.STORE_LOCAL, loop_var_idx)
            
            # Update iterator
            self._emit(OpCode.LOAD_LOCAL, iter_idx)
            self._emit(OpCode.LIST_TAIL)
            self._emit(OpCode.STORE_LOCAL, iter_idx)
            
            # Body
            self._compile_block(stmt.body)
            
            # Jump back
            offset = start_label - len(self.ctx.function.code)
            self._emit(OpCode.JUMP, offset)
            
            # Exit
            exit_target = len(self.ctx.function.code)
            self._patch_jump(exit_jump_idx, exit_target - exit_jump_idx - 1)
    
    def _compile_match(self, stmt: MatchStmt) -> None:
        """Compile match statement"""
        # Simplified match compilation
        # Compile subject
        self._compile_expression(stmt.value)
        
        # For each case
        end_jumps = []
        
        for i, case in enumerate(stmt.cases):
            # Duplicate subject for comparison
            self._emit(OpCode.DUP)
            
            # Compile pattern matching
            self._compile_pattern_match(case.pattern)
            
            self._emit(OpCode.JUMP_IF_FALSE, 0)
            skip_jump_idx = len(self.ctx.function.code) - 1
            
            # Pop subject (matched)
            self._emit(OpCode.POP)
            
            # Guard?
            if case.guard:
                self._compile_expression(case.guard)
                self._emit(OpCode.JUMP_IF_FALSE, 0)
                guard_skip_idx = len(self.ctx.function.code) - 1
            
            # Body
            self._compile_block(case.body)
            
            # Jump to end
            self._emit(OpCode.JUMP, 0)
            end_jumps.append(len(self.ctx.function.code) - 1)
            
            # Patch skip
            skip_target = len(self.ctx.function.code)
            self._patch_jump(skip_jump_idx, skip_target - skip_jump_idx - 1)
            
            if case.guard:
                guard_skip_target = len(self.ctx.function.code)
                self._patch_jump(guard_skip_idx, guard_skip_target - guard_skip_idx - 1)
        
        # Default: error
        self._emit(OpCode.POP)
        self._emit(OpCode.RETURN_UNIT)
        
        # Patch end jumps
        end_target = len(self.ctx.function.code)
        for jump_idx in end_jumps:
            self._patch_jump(jump_idx, end_target - jump_idx - 1)
    
    def _compile_pattern_match(self, pattern: Pattern) -> None:
        """Compile pattern match, leaves boolean on stack"""
        if isinstance(pattern, LiteralPattern):
            # Compare with literal
            if pattern.value is None:
                self._emit(OpCode.LOAD_UNIT)
            elif isinstance(pattern.value, int):
                self._emit(OpCode.LOAD_INT_SMALL, pattern.value)
            elif isinstance(pattern.value, str):
                idx = self.module.add_string(pattern.value)
                self._emit(OpCode.LOAD_CONST, idx)
            elif isinstance(pattern.value, bool):
                self._emit(OpCode.LOAD_TRUE if pattern.value else OpCode.LOAD_FALSE)
            
            self._emit(OpCode.EQ)
        
        elif isinstance(pattern, IdentifierPattern):
            # Bind and always match
            idx = self.ctx.add_local(pattern.name)
            self._emit(OpCode.STORE_LOCAL, idx)
            self._emit(OpCode.LOAD_TRUE)
        
        elif isinstance(pattern, WildcardPattern):
            # Always match
            self._emit(OpCode.POP)  # Remove subject
            self._emit(OpCode.LOAD_TRUE)
        
        else:
            # Fallback: always true
            self._emit(OpCode.POP)
            self._emit(OpCode.LOAD_TRUE)
    
    def _compile_block(self, block) -> None:
        """Compile block of statements (accepts Block object or list)"""
        statements = getattr(block, 'statements', block) if not isinstance(block, list) else block
        for stmt in statements:
            self._compile_statement(stmt)
    
    def _compile_expression(self, expr: Expression) -> None:
        """Compile expression"""
        if isinstance(expr, LiteralExpr):
            self._compile_literal(expr)
        elif isinstance(expr, IdentifierExpr):
            self._compile_identifier(expr)
        elif isinstance(expr, BinaryExpr):
            self._compile_binary(expr)
        elif isinstance(expr, UnaryExpr):
            self._compile_unary(expr)
        elif isinstance(expr, CallExpr):
            self._compile_call(expr)
        elif isinstance(expr, AccessExpr):
            self._compile_access(expr)
        elif isinstance(expr, IndexExpr):
            self._compile_index(expr)
        elif isinstance(expr, ConditionalExpr):
            self._compile_conditional(expr)
        elif isinstance(expr, LambdaExpr):
            self._compile_lambda(expr)
        elif isinstance(expr, ListExpr):
            self._compile_list(expr)
        elif isinstance(expr, DictExpr):
            self._compile_dict(expr)
        elif isinstance(expr, HostCallExpr):
            self._compile_host_call(expr)
    
    def _compile_literal(self, expr: LiteralExpr) -> None:
        """Compile literal"""
        val = expr.value
        
        if val is None:
            self._emit(OpCode.LOAD_UNIT)
        elif val is True:
            self._emit(OpCode.LOAD_TRUE)
        elif val is False:
            self._emit(OpCode.LOAD_FALSE)
        elif isinstance(val, int) and -128 <= val <= 127:
            self._emit(OpCode.LOAD_INT_SMALL, val & 0xFF)
        elif isinstance(val, int):
            idx = self.module.add_int(val)
            self._emit(OpCode.LOAD_CONST, idx)
        elif isinstance(val, float):
            idx = self.module.add_float(val)
            self._emit(OpCode.LOAD_CONST, idx)
        elif isinstance(val, str):
            idx = self.module.add_string(val)
            self._emit(OpCode.LOAD_CONST, idx)
    
    def _compile_identifier(self, expr: IdentifierExpr) -> None:
        """Compile identifier reference"""
        name = expr.name
        
        # Check locals
        idx = self.ctx.resolve_local(name)
        if idx is not None:
            self._emit(OpCode.LOAD_LOCAL, idx)
            return
        
        # Check globals
        if name in self.ctx.globals:
            # Global access - simplified
            self._emit(OpCode.LOAD_UNIT)
            return
        
        # Undefined - load nil
        self._emit(OpCode.LOAD_UNIT)
    
    def _compile_binary(self, expr: BinaryExpr) -> None:
        """Compile binary expression"""
        # Short-circuit for && and ||
        if expr.operator == "&&":
            self._compile_expression(expr.left)
            self._emit(OpCode.DUP)
            end_label = self.ctx.new_label()
            self._emit(OpCode.JUMP_IF_FALSE, 0)
            short_jump = len(self.ctx.function.code) - 1
            self._emit(OpCode.POP)
            self._compile_expression(expr.right)
            target = len(self.ctx.function.code)
            self._patch_jump(short_jump, target - short_jump - 1)
            return
        
        if expr.operator == "||":
            self._compile_expression(expr.left)
            self._emit(OpCode.DUP)
            end_label = self.ctx.new_label()
            self._emit(OpCode.JUMP_IF_TRUE, 0)
            short_jump = len(self.ctx.function.code) - 1
            self._emit(OpCode.POP)
            self._compile_expression(expr.right)
            target = len(self.ctx.function.code)
            self._patch_jump(short_jump, target - short_jump - 1)
            return
        
        # Compile operands
        self._compile_expression(expr.left)
        self._compile_expression(expr.right)
        
        # Apply operator
        op_map = {
            "+": (OpCode.ADD_INT, OpCode.ADD_FLOAT),
            "-": (OpCode.SUB_INT, OpCode.SUB_FLOAT),
            "*": (OpCode.MUL_INT, OpCode.MUL_FLOAT),
            "/": (OpCode.DIV_INT, OpCode.DIV_FLOAT),
            "%": (OpCode.MOD_INT, None),
            "==": (OpCode.EQ, OpCode.EQ),
            "!=": (OpCode.NE, OpCode.NE),
            "<": (OpCode.LT_INT, OpCode.LT_FLOAT),
            "<=": (OpCode.LE_INT, OpCode.LE_FLOAT),
            ">": (OpCode.GT_INT, OpCode.GT_FLOAT),
            ">=": (OpCode.GE_INT, OpCode.GE_FLOAT),
        }
        
        if expr.operator in op_map:
            int_op, float_op = op_map[expr.operator]
            # Simplified: just use int ops
            self._emit(int_op)
        elif expr.operator == "&&":
            self._emit(OpCode.AND)
        elif expr.operator == "||":
            self._emit(OpCode.OR)
    
    def _compile_unary(self, expr: UnaryExpr) -> None:
        """Compile unary expression"""
        self._compile_expression(expr.operand)
        
        if expr.operator == "-":
            self._emit(OpCode.NEG_INT)
        elif expr.operator == "!":
            self._emit(OpCode.NOT)
    
    def _compile_call(self, expr: CallExpr) -> None:
        """Compile function call"""
        # Compile arguments
        for arg in expr.args:
            self._compile_expression(arg)
        
        # Compile callee
        if isinstance(expr.callee, IdentifierExpr):
            # Direct call
            func_name = expr.callee.name
            func_idx = self._find_function(func_name)
            
            if func_idx >= 0:
                self._emit(OpCode.CALL, func_idx, len(expr.args))
            else:
                # Undefined function
                self._emit(OpCode.LOAD_UNIT)
        else:
            # Dynamic call - simplified
            self._compile_expression(expr.callee)
            self._emit(OpCode.LOAD_UNIT)
    
    def _compile_access(self, expr: AccessExpr) -> None:
        """Compile field access"""
        obj = getattr(expr, 'object', None) or getattr(expr, 'obj', expr)
        self._compile_expression(obj)
        field_name = _resolve_name(getattr(expr, 'field', ''))
        idx = self.module.get_field_index(field_name)
        self._emit(OpCode.GET_FIELD, idx)
    
    def _compile_index(self, expr: IndexExpr) -> None:
        """Compile index access"""
        obj = getattr(expr, 'object', None) or getattr(expr, 'obj', expr)
        self._compile_expression(obj)
        self._compile_expression(expr.index)
        self._emit(OpCode.GET_INDEX)
    
    def _compile_conditional(self, expr: ConditionalExpr) -> None:
        """Compile ternary conditional"""
        self._compile_expression(expr.condition)
        
        self._emit(OpCode.JUMP_IF_FALSE, 0)
        else_jump = len(self.ctx.function.code) - 1
        
        then_expr = getattr(expr, 'then_expr', None) or getattr(expr, 'then_branch', None)
        self._compile_expression(then_expr)
        self._emit(OpCode.JUMP, 0)
        end_jump = len(self.ctx.function.code) - 1
        
        else_target = len(self.ctx.function.code)
        self._patch_jump(else_jump, else_target - else_jump - 1)
        
        else_expr = getattr(expr, 'else_expr', None) or getattr(expr, 'else_branch', None)
        self._compile_expression(else_expr)
        
        end_target = len(self.ctx.function.code)
        self._patch_jump(end_jump, end_target - end_jump - 1)
    
    def _compile_lambda(self, expr: LambdaExpr) -> None:
        """Compile lambda"""
        # Create inner function
        inner = Function(f"lambda_{self.ctx.new_label()}", len(expr.params))
        inner.local_count = len(expr.params)
        inner.max_stack = 4
        
        saved_ctx = self.ctx
        inner_ctx = CompileContext(self.module, inner)
        self.ctx = inner_ctx
        
        for param in expr.params:
            inner_ctx.add_local(_resolve_name(param))
        
        self._compile_expression(expr.body)
        inner.code.append(OpCode.RETURN)
        
        self.ctx = saved_ctx
        
        func_idx = self.module.add_function(inner)
        self._emit(OpCode.MAKE_CLOSURE, func_idx, 0)
    
    def _compile_list(self, expr: ListExpr) -> None:
        """Compile list literal"""
        for elem in expr.elements:
            self._compile_expression(elem)
        
        if expr.elements:
            self._emit(OpCode.MAKE_LIST, len(expr.elements))
        else:
            self._emit(OpCode.MAKE_LIST_EMPTY)
    
    def _compile_dict(self, expr: DictExpr) -> None:
        """Compile dict literal"""
        # Simplified: create record
        for key, value in expr.pairs:
            self._compile_expression(value)
            self._compile_expression(key)  # Push key
        
        self._emit(OpCode.MAKE_RECORD, len(expr.pairs))
    
    def _compile_host_call(self, expr: HostCallExpr) -> None:
        """Compile host function call"""
        # Push arguments
        for key, arg in expr.args.items():
            self._compile_expression(arg)
        
        # Get host function index
        func_idx = self._find_host_function(expr.function)
        self._emit(OpCode.CALL_HOST, func_idx, len(expr.args))
    
    def _emit(self, opcode: int, *operands: int) -> None:
        """Emit instruction"""
        if operands:
            self.ctx.function.code.append((opcode, *operands))
        else:
            self.ctx.function.code.append(opcode)

    @staticmethod
    def _opcode_of(instr) -> int:
        """Extract opcode from an instruction (plain int or tuple)."""
        return instr[0] if isinstance(instr, tuple) else instr

    def _patch_jump(self, jump_idx: int, offset: int) -> None:
        """Patch jump instruction with target offset"""
        instr = self.ctx.function.code[jump_idx]
        if isinstance(instr, tuple):
            self.ctx.function.code[jump_idx] = (instr[0], offset)
    
    def _find_function(self, name: str) -> int:
        """Find function by name, return index or -1"""
        for i, func in enumerate(self.module.functions):
            if func.name == name:
                return i
        return -1
    
    def _find_host_function(self, name: str) -> int:
        """Find host function, return index or 0"""
        # Simplified: return hash of name
        return abs(hash(name)) % 65536
    
    def _optimize(self) -> None:
        """Optimize bytecode"""
        for func in self.module.functions:
            self._optimize_function(func)
    
    def _optimize_function(self, func: Function) -> None:
        """Optimize single function"""
        # Simple constant folding
        new_code = []
        i = 0
        while i < len(func.code):
            instr = func.code[i]
            
            # LOAD_CONST, LOAD_CONST, ADD_INT -> LOAD_CONST (result)
            if (i + 2 < len(func.code) and
                isinstance(instr, tuple) and instr[0] == OpCode.LOAD_CONST_FAST and
                isinstance(func.code[i+1], tuple) and func.code[i+1][0] == OpCode.LOAD_CONST_FAST and
                func.code[i+2] == OpCode.ADD_INT):
                
                a = self.module.constants[func.code[i][1]].value
                b = self.module.constants[func.code[i+1][1]].value
                if isinstance(a, int) and isinstance(b, int):
                    result_idx = self.module.add_int(a + b)
                    new_code.append((OpCode.LOAD_CONST, result_idx))
                    i += 3
                    continue
            
            new_code.append(instr)
            i += 1
        
        func.code = new_code
