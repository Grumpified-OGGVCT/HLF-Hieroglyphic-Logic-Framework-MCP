"""
HLF Virtual Machine
Stack-based bytecode interpreter
"""

from typing import List, Dict, Any, Optional, Callable
from enum import Enum
import time
import sys

from .bytecode import Bytecode, Function, Instruction, OpCode, ConstantPool
from .value import Value, ValueType

class VMError(Exception):
    """Base VM error"""
    pass

class Trap(Exception):
    """Runtime trap/exception"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message
        super().__init__(message)

class OutOfGas(Trap):
    """Out of gas"""
    def __init__(self):
        super().__init__(0x08, "Out of gas")

class DivisionByZero(Trap):
    """Division by zero"""
    def __init__(self):
        super().__init__(0x01, "Division by zero")

class StackOverflow(Trap):
    """Stack overflow"""
    def __init__(self):
        super().__init__(0x09, "Stack overflow")

class CallFrame:
    """Stack frame for function call"""
    __slots__ = ['function', 'locals', 'ip', 'stack_base']
    
    def __init__(self, function: Function, stack_base: int):
        self.function = function
        self.locals: List[Value] = [Value.nil()] * function.local_count
        self.ip = 0  # Instruction pointer
        self.stack_base = stack_base

class VM:
    """HLF Virtual Machine"""
    
    def __init__(self, 
                 bytecode: Bytecode,
                 gas_limit: int = 10_000_000,
                 stack_size: int = 65536,
                 enable_gas: bool = True):
        self.bytecode = bytecode
        self.gas_limit = gas_limit
        self.gas_used = 0
        self.enable_gas = enable_gas
        
        # Execution state
        self.stack: List[Value] = []
        self.call_stack: List[CallFrame] = []
        self.globals: Dict[str, Value] = {}
        
        # Host function registry
        self.host_functions: Dict[str, Callable] = {}
        
        # Effect tracking
        self.allowed_effects: set = set()
        self.allowed_tiers: set = {'slag', 'obsidian'}
        
        # Handler stack for exceptions
        self.handlers: List[Dict[str, Any]] = []
        
        # Debug mode
        self.debug = False
        self.trace = False
        
        # Setup
        self._setup_host_functions()
    
    def _setup_host_functions(self):
        """Register built-in host functions"""
        # I/O
        self.host_functions['print'] = self._hf_print
        self.host_functions['println'] = self._hf_println
        self.host_functions['read_line'] = self._hf_read_line
        
        # Math
        self.host_functions['abs'] = self._hf_abs
        self.host_functions['sqrt'] = self._hf_sqrt
        self.host_functions['pow'] = self._hf_pow
        self.host_functions['floor'] = self._hf_floor
        self.host_functions['ceil'] = self._hf_ceil
        
        # String
        self.host_functions['strlen'] = self._hf_strlen
        self.host_functions['substr'] = self._hf_substr
        self.host_functions['concat'] = self._hf_concat
        
        # List
        self.host_functions['length'] = self._hf_length
        self.host_functions['map'] = self._hf_map
        self.host_functions['filter'] = self._hf_filter
        self.host_functions['reduce'] = self._hf_reduce
        
        # Debug
        self.host_functions['typeof'] = self._hf_typeof
        self.host_functions['inspect'] = self._hf_inspect
    
    def use_gas(self, amount: int):
        """Consume gas"""
        if not self.enable_gas:
            return
        self.gas_used += amount
        if self.gas_used > self.gas_limit:
            raise OutOfGas()
    
    def push(self, value: Value):
        """Push value onto stack"""
        if len(self.stack) >= 65536:
            raise StackOverflow()
        self.stack.append(value)
    
    def pop(self) -> Value:
        """Pop value from stack"""
        if not self.stack:
            raise VMError("Stack underflow")
        return self.stack.pop()
    
    def peek(self, n: int = 0) -> Value:
        """Peek at stack value"""
        if n >= len(self.stack):
            raise VMError("Stack access out of bounds")
        return self.stack[-(n+1)]
    
    def get_local(self, index: int) -> Value:
        """Get local variable from current frame"""
        if not self.call_stack:
            raise VMError("No active call frame")
        frame = self.call_stack[-1]
        if index >= len(frame.locals):
            raise VMError(f"Local index {index} out of range")
        return frame.locals[index]
    
    def set_local(self, index: int, value: Value):
        """Set local variable in current frame"""
        if not self.call_stack:
            raise VMError("No active call frame")
        frame = self.call_stack[-1]
        if index >= len(frame.locals):
            raise VMError(f"Local index {index} out of range")
        frame.locals[index] = value
    
    def get_arg(self, index: int) -> Value:
        """Get argument from current frame"""
        frame = self.call_stack[-1]
        stack_base = frame.stack_base
        return self.stack[stack_base + index]
    
    def current_frame(self) -> CallFrame:
        """Get current call frame"""
        if not self.call_stack:
            raise VMError("No active call frame")
        return self.call_stack[-1]
    
    def current_function(self) -> Function:
        """Get current function"""
        return self.current_frame().function
    
    def current_instruction(self) -> Instruction:
        """Get current instruction"""
        frame = self.current_frame()
        if frame.ip >= len(frame.function.code):
            return Instruction(OpCode.NOP)
        return frame.function.code[frame.ip]
    
    def step(self):
        """Execute one instruction"""
        frame = self.current_frame()
        instr = self.current_instruction()
        
        if self.trace:
            print(f"  [{frame.ip:04x}] {instr} | Stack: {len(self.stack)}", file=sys.stderr)
        
        frame.ip += 1
        
        # Execute instruction
        self.execute_instruction(instr)
    
    def execute_instruction(self, instr: Instruction):
        """Execute a single instruction"""
        op = instr.opcode
        ops = instr.operands
        
        # Stack operations (gas: 1-2)
        if op == OpCode.NOP:
            self.use_gas(1)
        
        elif op == OpCode.POP:
            self.use_gas(1)
            self.pop()
        
        elif op == OpCode.DUP:
            self.use_gas(1)
            val = self.peek()
            self.push(val.copy())
        
        elif op == OpCode.DUP_N:
            self.use_gas(2)
            n = ops[0]
            val = self.peek(n)
            self.push(val.copy())
        
        elif op == OpCode.SWAP:
            self.use_gas(1)
            a, b = self.pop(), self.pop()
            self.push(a)
            self.push(b)
        
        elif op == OpCode.ROT:
            self.use_gas(2)
            a, b, c = self.pop(), self.pop(), self.pop()
            self.push(b)
            self.push(a)
            self.push(c)
        
        elif op == OpCode.PICK:
            self.use_gas(2)
            n = ops[0]
            val = self.peek(n)
            self.push(val.copy())
        
        elif op == OpCode.DROP_N:
            self.use_gas(ops[0])
            n = ops[0]
            for _ in range(n):
                self.pop()
        
        # Constant loading
        elif op == OpCode.LOAD_CONST:
            self.use_gas(2)
            idx = ops[0]
            const = self.bytecode.constant_pool.get(idx)
            val = self._const_to_value(const)
            self.push(val)
        
        elif op == OpCode.LOAD_CONST_FAST:
            self.use_gas(1)
            idx = ops[0]
            const = self.bytecode.constant_pool.get(idx)
            val = self._const_to_value(const)
            self.push(val)
        
        elif op == OpCode.LOAD_TRUE:
            self.use_gas(1)
            self.push(Value.bool(True))
        
        elif op == OpCode.LOAD_FALSE:
            self.use_gas(1)
            self.push(Value.bool(False))
        
        elif op == OpCode.LOAD_UNIT:
            self.use_gas(1)
            self.push(Value.nil())
        
        elif op == OpCode.LOAD_INT_SMALL:
            self.use_gas(1)
            self.push(Value.int(ops[0] if ops[0] < 128 else ops[0] - 256))
        
        elif op == OpCode.LOAD_ATOM:
            self.use_gas(2)
            idx = ops[0]
            const = self.bytecode.constant_pool.get(idx)
            self.push(Value.atom(const['value']))
        
        # Local variables
        elif op == OpCode.LOAD_LOCAL:
            self.use_gas(2)
            idx = ops[0]
            self.push(self.get_local(idx))
        
        elif op == OpCode.LOAD_LOCAL_WIDE:
            self.use_gas(3)
            idx = ops[0]
            self.push(self.get_local(idx))
        
        elif op == OpCode.STORE_LOCAL:
            self.use_gas(2)
            idx = ops[0]
            val = self.pop()
            self.set_local(idx, val)
        
        elif op == OpCode.LOAD_ARG:
            self.use_gas(1)
            idx = ops[0]
            self.push(self.get_arg(idx))
        
        # Arithmetic
        elif op == OpCode.ADD_INT:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.int(a.as_int() + b.as_int()))
        
        elif op == OpCode.SUB_INT:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.int(a.as_int() - b.as_int()))
        
        elif op == OpCode.MUL_INT:
            self.use_gas(3)
            b, a = self.pop(), self.pop()
            self.push(Value.int(a.as_int() * b.as_int()))
        
        elif op == OpCode.DIV_INT:
            self.use_gas(5)
            b, a = self.pop(), self.pop()
            if b.as_int() == 0:
                raise DivisionByZero()
            self.push(Value.int(a.as_int() // b.as_int()))
        
        elif op == OpCode.MOD_INT:
            self.use_gas(5)
            b, a = self.pop(), self.pop()
            if b.as_int() == 0:
                raise DivisionByZero()
            self.push(Value.int(a.as_int() % b.as_int()))
        
        elif op == OpCode.NEG_INT:
            self.use_gas(2)
            a = self.pop()
            self.push(Value.int(-a.as_int()))
        
        elif op == OpCode.ADD_FLOAT:
            self.use_gas(3)
            b, a = self.pop(), self.pop()
            self.push(Value.float(a.as_float() + b.as_float()))
        
        elif op == OpCode.SUB_FLOAT:
            self.use_gas(3)
            b, a = self.pop(), self.pop()
            self.push(Value.float(a.as_float() - b.as_float()))
        
        elif op == OpCode.MUL_FLOAT:
            self.use_gas(4)
            b, a = self.pop(), self.pop()
            self.push(Value.float(a.as_float() * b.as_float()))
        
        elif op == OpCode.DIV_FLOAT:
            self.use_gas(5)
            b, a = self.pop(), self.pop()
            self.push(Value.float(a.as_float() / b.as_float()))
        
        elif op == OpCode.NEG_FLOAT:
            self.use_gas(2)
            a = self.pop()
            self.push(Value.float(-a.as_float()))
        
        # Comparisons
        elif op == OpCode.EQ:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a == b))
        
        elif op == OpCode.NE:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a != b))
        
        elif op == OpCode.LT_INT:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a.as_int() < b.as_int()))
        
        elif op == OpCode.LE_INT:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a.as_int() <= b.as_int()))
        
        elif op == OpCode.GT_INT:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a.as_int() > b.as_int()))
        
        elif op == OpCode.GE_INT:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a.as_int() >= b.as_int()))
        
        elif op == OpCode.NOT:
            self.use_gas(1)
            a = self.pop()
            self.push(Value.bool(not a.as_bool()))
        
        elif op == OpCode.AND:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a.as_bool() and b.as_bool()))
        
        elif op == OpCode.OR:
            self.use_gas(2)
            b, a = self.pop(), self.pop()
            self.push(Value.bool(a.as_bool() or b.as_bool()))
        
        # Control flow
        elif op == OpCode.JUMP:
            self.use_gas(2)
            offset = ops[0]
            frame = self.current_frame()
            frame.ip += offset
        
        elif op == OpCode.JUMP_IF_TRUE:
            self.use_gas(3)
            offset = ops[0]
            cond = self.pop()
            if cond.as_bool():
                frame = self.current_frame()
                frame.ip += offset
        
        elif op == OpCode.JUMP_IF_FALSE:
            self.use_gas(3)
            offset = ops[0]
            cond = self.pop()
            if not cond.as_bool():
                frame = self.current_frame()
                frame.ip += offset
        
        elif op == OpCode.RETURN:
            self.use_gas(3)
            val = self.pop()
            self.call_stack.pop()
            self.push(val)
        
        elif op == OpCode.RETURN_UNIT:
            self.use_gas(2)
            self.call_stack.pop()
            self.push(Value.nil())
        
        # Data structures
        elif op == OpCode.MAKE_LIST:
            self.use_gas(2 + ops[0])
            n = ops[0]
            elements = [self.pop() for _ in range(n)]
            elements.reverse()
            self.push(Value.list_(elements))
        
        elif op == OpCode.MAKE_LIST_EMPTY:
            self.use_gas(2)
            self.push(Value.list_([]))
        
        elif op == OpCode.MAKE_TUPLE:
            self.use_gas(2 + ops[0])
            n = ops[0]
            elements = [self.pop() for _ in range(n)]
            elements.reverse()
            self.push(Value.tuple_(elements))
        
        elif op == OpCode.MAKE_RECORD:
            self.use_gas(3 + ops[0])
            n = ops[0]
            fields = {}
            for _ in range(n):
                val = self.pop()
                name = self.pop().as_string()
                fields[name] = val
            self.push(Value.record(fields))
        
        elif op == OpCode.GET_FIELD:
            self.use_gas(3)
            idx = ops[0]
            record = self.pop()
            # TODO: Use field index
            self.push(Value.nil())
        
        elif op == OpCode.GET_INDEX:
            self.use_gas(4)
            idx = self.pop()
            obj = self.pop()
            if obj.is_list():
                self.push(obj.get_index(idx.as_int()))
            elif obj.is_tuple():
                self.push(obj.get_index(idx.as_int()))
            else:
                raise Trap(0x05, f"Cannot index {obj.type}")
        
        elif op == OpCode.LIST_LEN:
            self.use_gas(2)
            lst = self.pop()
            self.push(Value.int(len(lst)))
        
        # Host functions
        elif op == OpCode.CALL_HOST:
            self.use_gas(50)  # Base cost
            func_idx = ops[0]
            argc = ops[1]
            
            # Get function name from constant pool
            const = self.bytecode.constant_pool.get(func_idx)
            func_name = const['name']
            
            # Pop arguments
            args = [self.pop() for _ in range(argc)]
            args.reverse()
            
            # Call host function
            if func_name not in self.host_functions:
                raise Trap(0x0B, f"Host function {func_name} not found")
            
            result = self.host_functions[func_name](*args)
            self.push(result)
        
        elif op == OpCode.MEMORY_STORE:
            self.use_gas(20)
            val = self.pop()
            key = self.pop()
            # TODO: Implement infinite RAG storage
            self.globals[key.as_string()] = val
        
        elif op == OpCode.MEMORY_RECALL:
            self.use_gas(15)
            key = self.pop()
            val = self.globals.get(key.as_string(), Value.nil())
            self.push(val)
        
        # Special
        elif op == OpCode.HALT:
            self.use_gas(0)
            raise VMError("Halted")
        
        else:
            raise VMError(f"Unknown opcode: {op}")
    
    def _const_to_value(self, const: Dict[str, Any]) -> Value:
        """Convert constant to Value"""
        t = const['type']
        if t == 0x01:  # INTEGER
            return Value.int(const['value'])
        elif t == 0x02:  # FLOAT
            return Value.float(const['value'])
        elif t == 0x03:  # STRING
            return Value.string(const['value'])
        elif t == 0x04:  # ATOM
            return Value.atom(const['value'])
        else:
            raise VMError(f"Unknown constant type: {t}")
    
    # Host function implementations
    def _hf_print(self, *args) -> Value:
        """Print values"""
        print(' '.join(str(a) for a in args), end='')
        return Value.nil()
    
    def _hf_println(self, *args) -> Value:
        """Print values with newline"""
        print(' '.join(str(a) for a in args))
        return Value.nil()
    
    def _hf_read_line(self) -> Value:
        """Read line from stdin"""
        return Value.string(input())
    
    def _hf_abs(self, x: Value) -> Value:
        if x.is_int():
            return Value.int(abs(x.as_int()))
        return Value.float(abs(x.as_float()))
    
    def _hf_sqrt(self, x: Value) -> Value:
        import math
        return Value.float(math.sqrt(x.as_float()))
    
    def _hf_pow(self, base: Value, exp: Value) -> Value:
        import math
        return Value.float(math.pow(base.as_float(), exp.as_float()))
    
    def _hf_floor(self, x: Value) -> Value:
        import math
        return Value.int(math.floor(x.as_float()))
    
    def _hf_ceil(self, x: Value) -> Value:
        import math
        return Value.int(math.ceil(x.as_float()))
    
    def _hf_strlen(self, s: Value) -> Value:
        return Value.int(len(s.as_string()))
    
    def _hf_substr(self, s: Value, start: Value, length: Value) -> Value:
        return Value.string(s.as_string()[start.as_int():start.as_int()+length.as_int()])
    
    def _hf_concat(self, *args) -> Value:
        return Value.string(''.join(a.as_string() for a in args))
    
    def _hf_length(self, x: Value) -> Value:
        return Value.int(len(x))
    
    def _hf_map(self, f: Value, xs: Value) -> Value:
        # TODO: Implement properly
        return xs
    
    def _hf_filter(self, f: Value, xs: Value) -> Value:
        # TODO: Implement properly
        return xs
    
    def _hf_reduce(self, f: Value, init: Value, xs: Value) -> Value:
        # TODO: Implement properly
        return init
    
    def _hf_typeof(self, x: Value) -> Value:
        return Value.atom(x.type.name.lower())
    
    def _hf_inspect(self, x: Value) -> Value:
        return Value.string(repr(x))
    
    def run(self, function_name: Optional[str] = None, args: List[Value] = None) -> Value:
        """Run the VM"""
        if args is None:
            args = []
        
        # Get entry function
        if function_name is None:
            function_name = self.bytecode.entry_point
        
        if function_name not in self.bytecode.functions:
            raise VMError(f"Function {function_name} not found")
        
        func = self.bytecode.functions[function_name]
        
        # Push arguments
        for arg in args:
            self.push(arg)
        
        # Create initial frame
        frame = CallFrame(func, len(self.stack) - len(args))
        self.call_stack.append(frame)
        
        # Execute
        try:
            while self.call_stack:
                self.step()
        except IndexError:
            pass  # Program ended normally
        
        # Return result
        if self.stack:
            return self.pop()
        return Value.nil()
    
    def dump_state(self):
        """Dump current VM state for debugging"""
        print("=== VM State ===", file=sys.stderr)
        print(f"Gas: {self.gas_used}/{self.gas_limit}", file=sys.stderr)
        print(f"Stack ({len(self.stack)}):", file=sys.stderr)
        for i, val in enumerate(self.stack):
            print(f"  [{i}] {val}", file=sys.stderr)
        print(f"Call stack ({len(self.call_stack)}):", file=sys.stderr)
        for i, frame in enumerate(self.call_stack):
            print(f"  [{i}] {frame.function.name} @ {frame.ip}", file=sys.stderr)
