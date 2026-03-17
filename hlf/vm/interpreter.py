"""
HLF Virtual Machine
Stack-based bytecode interpreter
"""

from typing import List, Dict, Any, Optional, Callable, Union
import time
import sys

from .bytecode import BytecodeModule, Function, OpCode
from .value import Value, ValueType

class VMError(Exception):
    """VM runtime error"""
    pass

class VMTrap(Exception):
    """VM trap (exception)"""
    def __init__(self, code: int, message: str = "", value: Optional[Value] = None):
        self.code = code
        self.message = message
        self.value = value
        super().__init__(message)

class CallFrame:
    """Stack frame for function call"""
    
    __slots__ = ['function', 'pc', 'base', 'locals', 'closure', 'gas_used']
    
    def __init__(self, function: Function, base: int, locals_list: List[Value], closure: Optional[List[Value]] = None):
        self.function = function
        self.pc = 0
        self.base = base  # Stack base for this frame
        self.locals = locals_list
        self.closure = closure
        self.gas_used = 0

class VM:
    """HLF Virtual Machine"""
    
    def __init__(self, module: Optional[BytecodeModule] = None, 
                 stack_size: int = 65536,
                 heap_size: int = 65536,
                 gas_limit: Optional[int] = None):
        self.module = module
        
        # Execution stack
        self.stack: List[Value] = [Value.nil()] * stack_size
        self.sp = 0  # Stack pointer
        
        # Call stack
        self.frames: List[CallFrame] = []
        self.frame_count = 0
        self.max_frames = 1024
        
        # Global gas tracking
        self.gas_limit = gas_limit
        self.total_gas = 0
        
        # Exception handlers
        self.handlers: List[tuple] = []  # (frame_index, pc, effect_mask)
        
        # Host functions registry
        self.host_functions: Dict[int, Callable] = {}
        
        # Effect registry
        self.allowed_effects: set = set()
        self.current_tier = "forge"
        
        # Memory system (Infinite RAG integration)
        self.memory: Dict[str, Value] = {}
        
        # Globals
        self.globals: Dict[str, Value] = {}
        
        # Initialize
        self.reset()
    
    def reset(self) -> None:
        """Reset VM state"""
        self.sp = 0
        self.frames.clear()
        self.frame_count = 0
        self.total_gas = 0
        self.handlers.clear()
    
    def push(self, value: Value) -> None:
        """Push value onto stack"""
        if self.sp >= len(self.stack):
            raise VMTrap(0x09, "Stack overflow")
        self.stack[self.sp] = value
        self.sp += 1
    
    def pop(self) -> Value:
        """Pop value from stack"""
        if self.sp <= 0:
            raise VMTrap(0x09, "Stack underflow")
        self.sp -= 1
        return self.stack[self.sp]
    
    def peek(self, offset: int = 0) -> Value:
        """Peek at stack without popping"""
        if self.sp - offset <= 0:
            raise VMTrap(0x09, "Stack underflow")
        return self.stack[self.sp - 1 - offset]
    
    def consume_gas(self, amount: int) -> None:
        """Consume gas"""
        self.total_gas += amount
        if self.gas_limit is not None and self.total_gas > self.gas_limit:
            raise VMTrap(0x08, f"Out of gas (limit: {self.gas_limit})")
    
    def register_host_function(self, index: int, func: Callable) -> None:
        """Register host function"""
        self.host_functions[index] = func
    
    def get_constant(self, idx: int) -> Value:
        """Get constant from pool"""
        if not self.module or idx >= len(self.module.constants):
            raise VMTrap(0x0C, f"Invalid constant index: {idx}")
        
        entry = self.module.constants[idx]
        
        if entry.type_tag == 0x01:  # INTEGER
            return Value.int(entry.value)
        elif entry.type_tag == 0x02:  # FLOAT
            return Value.float(entry.value)
        elif entry.type_tag == 0x03:  # STRING
            return Value.string(entry.value)
        elif entry.type_tag == 0x04:  # ATOM
            return Value.atom(entry.value)
        
        return Value.nil()
    
    def find_function(self, name: str) -> int:
        """Find function index by name. Raises VMError if not found."""
        if not self.module:
            raise VMError("No module loaded")
        for i, fn in enumerate(self.module.functions):
            if fn.name == name:
                return i
        raise VMError(f"Function not found: {name}")

    def execute(self, function_index: Optional[int] = None, args: Optional[List[Value]] = None) -> Value:
        """Execute bytecode. Args (if given) are placed into the first N locals."""
        if not self.module:
            raise VMError("No module loaded")
        
        # Determine entry point
        if function_index is None:
            function_index = self.module.entry_point
        
        if function_index >= len(self.module.functions):
            raise VMError(f"Invalid function index: {function_index}")
        
        func = self.module.functions[function_index]
        
        # Validate arity if args supplied
        if args is not None and len(args) != func.arity:
            raise VMError(f"Arity mismatch for '{func.name}': expected {func.arity}, got {len(args)}")
        
        # Create initial frame
        locals_list = [Value.nil()] * func.local_count
        if args:
            for i, arg in enumerate(args):
                locals_list[i] = arg
        frame = CallFrame(func, 0, locals_list)
        self.frames.append(frame)
        self.frame_count = 1
        
        # Execute
        return self._run()
    
    def _run(self) -> Value:
        """Main execution loop"""
        while self.frame_count > 0:
            frame = self.frames[-1]
            code = frame.function.code
            
            while frame.pc < len(code):
                instr = code[frame.pc]
                frame.pc += 1
                
                # Decode instruction
                if isinstance(instr, int):
                    opcode = instr
                    operands = []
                else:
                    opcode = instr[0]
                    operands = list(instr[1:])
                
                # Execute
                try:
                    result = self._execute_instruction(opcode, operands, frame)
                    if result is not None:  # RETURN
                        return result
                except VMTrap as trap:
                    if not self._handle_trap(trap, frame):
                        raise
            
            # Frame completed without explicit return
            self._pop_frame()
            self.push(Value.nil())
        
        # Should have returned by now
        return self.pop() if self.sp > 0 else Value.nil()
    
    def _execute_instruction(self, opcode: int, operands: List[int], frame: CallFrame) -> Optional[Value]:
        """Execute single instruction"""
        
        # Stack operations (0x00-0x0F)
        if opcode == OpCode.NOP:
            self.consume_gas(1)
        
        elif opcode == OpCode.POP:
            self.consume_gas(1)
            self.pop()
        
        elif opcode == OpCode.DUP:
            self.consume_gas(1)
            val = self.peek()
            self.push(val.copy())
        
        elif opcode == OpCode.DUP_N:
            self.consume_gas(2)
            n = operands[0]
            val = self.stack[self.sp - 1 - n]
            self.push(val.copy())
        
        elif opcode == OpCode.SWAP:
            self.consume_gas(1)
            a = self.pop()
            b = self.pop()
            self.push(a)
            self.push(b)
        
        elif opcode == OpCode.ROT:
            self.consume_gas(2)
            a = self.pop()
            b = self.pop()
            c = self.pop()
            self.push(b)
            self.push(a)
            self.push(c)
        
        elif opcode == OpCode.PICK:
            self.consume_gas(2)
            n = operands[0]
            val = self.stack[self.sp - 1 - n]
            self.push(val.copy())
        
        elif opcode == OpCode.DROP_N:
            self.consume_gas(operands[0])
            n = operands[0]
            self.sp -= n
            if self.sp < 0:
                raise VMTrap(0x09, "Stack underflow")
        
        # Constants (0x10-0x1F)
        elif opcode == OpCode.LOAD_CONST:
            self.consume_gas(2)
            idx = operands[0]
            self.push(self.get_constant(idx))
        
        elif opcode == OpCode.LOAD_CONST_FAST:
            self.consume_gas(1)
            idx = operands[0]
            self.push(self.get_constant(idx))
        
        elif opcode == OpCode.LOAD_TRUE:
            self.consume_gas(1)
            self.push(Value.bool(True))
        
        elif opcode == OpCode.LOAD_FALSE:
            self.consume_gas(1)
            self.push(Value.bool(False))
        
        elif opcode == OpCode.LOAD_UNIT:
            self.consume_gas(1)
            self.push(Value.unit())
        
        elif opcode == OpCode.LOAD_INT_SMALL:
            self.consume_gas(1)
            val = operands[0]
            # Handle signed byte
            if val > 127:
                val -= 256
            self.push(Value.int(val))
        
        elif opcode == OpCode.LOAD_ATOM:
            self.consume_gas(2)
            idx = operands[0]
            if not self.module or idx >= len(self.module.atoms):
                raise VMTrap(0x0C, f"Invalid atom index: {idx}")
            self.push(Value.atom(self.module.atoms[idx]))
        
        # Locals (0x20-0x2F)
        elif opcode == OpCode.LOAD_LOCAL:
            self.consume_gas(2)
            idx = operands[0]
            if idx >= len(frame.locals):
                raise VMTrap(0x0C, f"Invalid local index: {idx}")
            self.push(frame.locals[idx].copy())
        
        elif opcode == OpCode.LOAD_LOCAL_WIDE:
            self.consume_gas(3)
            idx = operands[0]
            if idx >= len(frame.locals):
                raise VMTrap(0x0C, f"Invalid local index: {idx}")
            self.push(frame.locals[idx].copy())
        
        elif opcode == OpCode.STORE_LOCAL:
            self.consume_gas(2)
            idx = operands[0]
            if idx >= len(frame.locals):
                raise VMTrap(0x0C, f"Invalid local index: {idx}")
            frame.locals[idx] = self.pop()
        
        elif opcode == OpCode.STORE_LOCAL_WIDE:
            self.consume_gas(3)
            idx = operands[0]
            if idx >= len(frame.locals):
                raise VMTrap(0x0C, f"Invalid local index: {idx}")
            frame.locals[idx] = self.pop()
        
        elif opcode == OpCode.LOAD_ARG:
            self.consume_gas(1)
            idx = operands[0]
            # Arguments are at base of stack
            arg_idx = frame.base + idx
            if arg_idx >= self.sp:
                raise VMTrap(0x0C, f"Invalid argument index: {idx}")
            self.push(self.stack[arg_idx].copy())
        
        elif opcode == OpCode.LOAD_CLOSURE:
            self.consume_gas(3)
            idx = operands[0]
            if frame.closure is None or idx >= len(frame.closure):
                raise VMTrap(0x0C, f"Invalid closure index: {idx}")
            self.push(frame.closure[idx].copy())
        
        elif opcode == OpCode.STORE_CLOSURE:
            self.consume_gas(3)
            idx = operands[0]
            if frame.closure is None or idx >= len(frame.closure):
                raise VMTrap(0x0C, f"Invalid closure index: {idx}")
            frame.closure[idx] = self.pop()
        
        # Arithmetic (0x30-0x4F)
        elif opcode == OpCode.ADD_INT:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, f"Type mismatch in ADD_INT: {a.type}, {b.type}")
            self.push(Value.int(a.as_int() + b.as_int()))
        
        elif opcode == OpCode.SUB_INT:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in SUB_INT")
            self.push(Value.int(a.as_int() - b.as_int()))
        
        elif opcode == OpCode.MUL_INT:
            self.consume_gas(3)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in MUL_INT")
            self.push(Value.int(a.as_int() * b.as_int()))
        
        elif opcode == OpCode.DIV_INT:
            self.consume_gas(5)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in DIV_INT")
            if b.as_int() == 0:
                raise VMTrap(0x01, "Division by zero")
            self.push(Value.int(a.as_int() // b.as_int()))
        
        elif opcode == OpCode.MOD_INT:
            self.consume_gas(5)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in MOD_INT")
            if b.as_int() == 0:
                raise VMTrap(0x01, "Division by zero")
            self.push(Value.int(a.as_int() % b.as_int()))
        
        elif opcode == OpCode.NEG_INT:
            self.consume_gas(2)
            a = self.pop()
            if not a.is_int():
                raise VMTrap(0x05, "Type mismatch in NEG_INT")
            self.push(Value.int(-a.as_int()))
        
        elif opcode == OpCode.ADD_FLOAT:
            self.consume_gas(3)
            b = self.pop()
            a = self.pop()
            if not (a.is_number() and b.is_number()):
                raise VMTrap(0x05, "Type mismatch in ADD_FLOAT")
            self.push(Value.float(a.as_float() + b.as_float()))
        
        elif opcode == OpCode.SUB_FLOAT:
            self.consume_gas(3)
            b = self.pop()
            a = self.pop()
            if not (a.is_number() and b.is_number()):
                raise VMTrap(0x05, "Type mismatch in SUB_FLOAT")
            self.push(Value.float(a.as_float() - b.as_float()))
        
        elif opcode == OpCode.MUL_FLOAT:
            self.consume_gas(4)
            b = self.pop()
            a = self.pop()
            if not (a.is_number() and b.is_number()):
                raise VMTrap(0x05, "Type mismatch in MUL_FLOAT")
            self.push(Value.float(a.as_float() * b.as_float()))
        
        elif opcode == OpCode.DIV_FLOAT:
            self.consume_gas(5)
            b = self.pop()
            a = self.pop()
            if not (a.is_number() and b.is_number()):
                raise VMTrap(0x05, "Type mismatch in DIV_FLOAT")
            if b.as_float() == 0.0:
                raise VMTrap(0x01, "Division by zero")
            self.push(Value.float(a.as_float() / b.as_float()))
        
        # Comparisons (0x50-0x6F)
        elif opcode == OpCode.EQ:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            self.push(Value.bool(a == b))
        
        elif opcode == OpCode.NE:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            self.push(Value.bool(a != b))
        
        elif opcode == OpCode.LT_INT:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in LT_INT")
            self.push(Value.bool(a.as_int() < b.as_int()))
        
        elif opcode == OpCode.LE_INT:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in LE_INT")
            self.push(Value.bool(a.as_int() <= b.as_int()))
        
        elif opcode == OpCode.GT_INT:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in GT_INT")
            self.push(Value.bool(a.as_int() > b.as_int()))
        
        elif opcode == OpCode.GE_INT:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            if not (a.is_int() and b.is_int()):
                raise VMTrap(0x05, "Type mismatch in GE_INT")
            self.push(Value.bool(a.as_int() >= b.as_int()))
        
        elif opcode == OpCode.NOT:
            self.consume_gas(1)
            a = self.pop()
            self.push(Value.bool(not a.as_bool()))
        
        elif opcode == OpCode.AND:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            self.push(Value.bool(a.as_bool() and b.as_bool()))
        
        elif opcode == OpCode.OR:
            self.consume_gas(2)
            b = self.pop()
            a = self.pop()
            self.push(Value.bool(a.as_bool() or b.as_bool()))
        
        # Control flow (0x70-0x8F)
        elif opcode == OpCode.JUMP:
            self.consume_gas(2)
            offset = operands[0]
            frame.pc += offset
        
        elif opcode == OpCode.JUMP_IF_TRUE:
            self.consume_gas(3)
            cond = self.pop()
            offset = operands[0]
            if cond.as_bool():
                frame.pc += offset
        
        elif opcode == OpCode.JUMP_IF_FALSE:
            self.consume_gas(3)
            cond = self.pop()
            offset = operands[0]
            if not cond.as_bool():
                frame.pc += offset
        
        elif opcode == OpCode.JUMP_FORWARD:
            self.consume_gas(2)
            offset = operands[0]
            frame.pc += offset
        
        elif opcode == OpCode.CALL:
            self.consume_gas(10)
            func_idx = operands[0]
            argc = operands[1]
            self._call_function(func_idx, argc)
            # Execution continues in new frame
            return None
        
        elif opcode == OpCode.RETURN:
            self.consume_gas(3)
            result = self.pop()
            self._pop_frame()
            return result
        
        elif opcode == OpCode.RETURN_UNIT:
            self.consume_gas(2)
            self._pop_frame()
            return Value.unit()
        
        # Data structures (0x90-0xAF)
        elif opcode == OpCode.MAKE_LIST:
            self.consume_gas(2 + operands[0])
            count = operands[0]
            elements = []
            for _ in range(count):
                elements.append(self.pop())
            elements.reverse()
            self.push(Value.list_(elements))
        
        elif opcode == OpCode.MAKE_LIST_EMPTY:
            self.consume_gas(2)
            self.push(Value.list_([]))
        
        elif opcode == OpCode.MAKE_TUPLE:
            self.consume_gas(2 + operands[0])
            count = operands[0]
            elements = []
            for _ in range(count):
                elements.append(self.pop())
            elements.reverse()
            self.push(Value.tuple_(elements))
        
        elif opcode == OpCode.MAKE_RECORD:
            self.consume_gas(3 + operands[0])
            count = operands[0]
            fields = {}
            for _ in range(count):
                val = self.pop()
                key = self.pop().as_string()
                fields[key] = val
            self.push(Value.record(fields))
        
        elif opcode == OpCode.GET_FIELD:
            self.consume_gas(3)
            idx = operands[0]
            if not self.module or idx >= len(self.module.field_names):
                raise VMTrap(0x0C, f"Invalid field index: {idx}")
            field_name = self.module.field_names[idx]
            record = self.pop()
            self.push(record.get_field(field_name))
        
        elif opcode == OpCode.GET_FIELD_BY_NAME:
            self.consume_gas(4)
            idx = operands[0]
            if not self.module or idx >= len(self.module.field_names):
                raise VMTrap(0x0C, f"Invalid field index: {idx}")
            field_name = self.module.field_names[idx]
            record = self.pop()
            self.push(record.get_field(field_name))
        
        elif opcode == OpCode.GET_INDEX:
            self.consume_gas(4)
            idx = self.pop()
            obj = self.pop()
            self.push(obj.get_index(idx.as_int()))
        
        elif opcode == OpCode.LIST_LEN:
            self.consume_gas(2)
            lst = self.pop()
            self.push(Value.int(len(lst)))
        
        elif opcode == OpCode.LIST_HEAD:
            self.consume_gas(2)
            lst = self.pop()
            self.push(lst.head())
        
        elif opcode == OpCode.LIST_TAIL:
            self.consume_gas(2)
            lst = self.pop()
            self.push(lst.tail())
        
        # Host functions & effects (0xB0-0xCF)
        elif opcode == OpCode.CALL_HOST:
            self.consume_gas(50)
            func_idx = operands[0]
            argc = operands[1]
            
            if func_idx not in self.host_functions:
                raise VMTrap(0x0B, f"Host function not found: {func_idx}")
            
            # Pop arguments
            args = [self.pop() for _ in range(argc)]
            args.reverse()
            
            # Call host function
            result = self.host_functions[func_idx](*args)
            self.push(result)
        
        elif opcode == OpCode.MEMORY_STORE:
            self.consume_gas(20)
            value = self.pop()
            key = self.pop().as_string()
            self.memory[key] = value
            self.push(Value.unit())
        
        elif opcode == OpCode.MEMORY_RECALL:
            self.consume_gas(15)
            key = self.pop().as_string()
            if key in self.memory:
                self.push(self.memory[key].copy())
            else:
                self.push(Value.nil())
        
        # Exception handling (0xD0-0xEF)
        elif opcode == OpCode.PUSH_HANDLER:
            self.consume_gas(5)
            offset = operands[0]
            effect_mask = operands[1]
            self.handlers.append((self.frame_count - 1, frame.pc + offset, effect_mask))
        
        elif opcode == OpCode.POP_HANDLER:
            self.consume_gas(2)
            if self.handlers:
                self.handlers.pop()
        
        elif opcode == OpCode.RAISE:
            self.consume_gas(10)
            code = operands[0]
            val = self.pop()
            raise VMTrap(code, value=val)
        
        elif opcode == OpCode.CHECK_EFFECT:
            self.consume_gas(3)
            effect_idx = operands[0]
            self.push(Value.bool(effect_idx in self.allowed_effects))
        
        elif opcode == OpCode.CHECK_TIER:
            self.consume_gas(2)
            tier_idx = operands[0]
            # Simplified tier checking
            self.push(Value.bool(True))
        
        # Special (0xF0-0xFF)
        elif opcode == OpCode.HALT:
            self.consume_gas(0)
            exit_code = operands[0]
            sys.exit(exit_code)
        
        elif opcode == OpCode.TRACE:
            self.consume_gas(5)
            level = operands[0]
            val = self.pop()
            print(f"[TRACE:{level}] {val}")
            self.push(val)
        
        elif opcode == OpCode.ASSERT:
            self.consume_gas(3)
            cond = self.pop()
            if not cond.as_bool():
                raise VMTrap(0x0A, "Assertion failed")
        
        else:
            raise VMTrap(0x0C, f"Unknown opcode: {opcode:02X}")
        
        return None
    
    def _call_function(self, func_idx: int, argc: int) -> None:
        """Call function by index"""
        if not self.module or func_idx >= len(self.module.functions):
            raise VMTrap(0x0C, f"Invalid function index: {func_idx}")
        
        func = self.module.functions[func_idx]
        
        if argc != func.arity:
            raise VMTrap(0x0C, f"Arity mismatch: expected {func.arity}, got {argc}")
        
        # Pop arguments (they're on stack)
        # Note: they're already on stack, we just set up the frame
        base = self.sp - argc
        
        # Set up locals
        locals_list = [Value.nil()] * func.local_count
        
        # Create frame
        frame = CallFrame(func, base, locals_list)
        self.frames.append(frame)
        self.frame_count += 1
        
        if self.frame_count > self.max_frames:
            raise VMTrap(0x09, "Stack overflow (max frames)")
    
    def _pop_frame(self) -> None:
        """Pop current frame"""
        if self.frames:
            self.frames.pop()
            self.frame_count -= 1
    
    def _handle_trap(self, trap: VMTrap, frame: CallFrame) -> bool:
        """Handle VM trap, returns True if handled"""
        # Find matching handler
        while self.handlers:
            handler_frame, handler_pc, effect_mask = self.handlers[-1]
            
            # Check if handler is still valid
            if handler_frame < self.frame_count:
                # Pop to handler frame
                while self.frame_count > handler_frame + 1:
                    self._pop_frame()
                
                # Set PC to handler
                if self.frames:
                    self.frames[-1].pc = handler_pc
                
                # Push trap value onto stack
                self.push(trap.value if trap.value else Value.nil())
                
                return True
            
            # Handler no longer valid
            self.handlers.pop()
        
        return False

# Convenience function
def run_bytecode(module: BytecodeModule, gas_limit: Optional[int] = None) -> Value:
    """Run bytecode module"""
    vm = VM(module, gas_limit=gas_limit)
    return vm.execute()
