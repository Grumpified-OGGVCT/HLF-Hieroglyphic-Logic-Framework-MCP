"""
HLF Virtual Machine
"""

from .bytecode import (
    BytecodeModule, Function, OpCode,
    ConstantPoolEntry
)
from .value import Value, ValueType
from .interpreter import VM, VMError, VMTrap, CallFrame

# Aliases for backward compatibility
Bytecode = BytecodeModule

__all__ = [
    # Bytecode
    'BytecodeModule', 'Bytecode', 'Function', 'OpCode',
    'ConstantPoolEntry',
    # Values
    'Value', 'ValueType',
    # VM
    'VM', 'VMError', 'VMTrap', 'CallFrame',
]
