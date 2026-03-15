"""
HLF Virtual Machine
"""

from .bytecode import (
    Bytecode, Function, Instruction, OpCode,
    ConstantPool, encode_u16, encode_u32, decode_u16, decode_u32
)
from .value import Value, ValueType
from .vm import VM, VMError, Trap, OutOfGas, DivisionByZero, CallFrame

__all__ = [
    # Bytecode
    'Bytecode', 'Function', 'Instruction', 'OpCode',
    'ConstantPool', 'encode_u16', 'encode_u32', 'decode_u16', 'decode_u32',
    # Values
    'Value', 'ValueType',
    # VM
    'VM', 'VMError', 'Trap', 'OutOfGas', 'DivisionByZero', 'CallFrame',
]
