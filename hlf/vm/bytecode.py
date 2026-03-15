"""
HLF Bytecode Representation
Binary format for compiled HLF programs
"""

from typing import List, Dict, Any, Optional, BinaryIO, Union
from enum import IntEnum
import struct
import io

class OpCode(IntEnum):
    """Bytecode opcodes"""
    # Stack operations (0x00-0x0F)
    NOP = 0x00
    POP = 0x01
    DUP = 0x02
    DUP_N = 0x03
    SWAP = 0x04
    ROT = 0x05
    PICK = 0x06
    DROP_N = 0x07
    
    # Constants (0x10-0x1F)
    LOAD_CONST = 0x10
    LOAD_CONST_FAST = 0x11
    LOAD_TRUE = 0x12
    LOAD_FALSE = 0x13
    LOAD_UNIT = 0x14
    LOAD_INT_SMALL = 0x15
    LOAD_ATOM = 0x16
    
    # Locals (0x20-0x2F)
    LOAD_LOCAL = 0x20
    LOAD_LOCAL_WIDE = 0x21
    STORE_LOCAL = 0x22
    STORE_LOCAL_WIDE = 0x23
    LOAD_ARG = 0x24
    LOAD_ARG_WIDE = 0x25
    LOAD_CLOSURE = 0x26
    STORE_CLOSURE = 0x27
    
    # Arithmetic (0x30-0x4F)
    ADD_INT = 0x30
    SUB_INT = 0x31
    MUL_INT = 0x32
    DIV_INT = 0x33
    MOD_INT = 0x34
    NEG_INT = 0x35
    ADD_FLOAT = 0x36
    SUB_FLOAT = 0x37
    MUL_FLOAT = 0x38
    DIV_FLOAT = 0x39
    NEG_FLOAT = 0x3A
    POW_FLOAT = 0x3B
    
    # Comparisons (0x50-0x6F)
    EQ = 0x50
    NE = 0x51
    LT_INT = 0x52
    LE_INT = 0x53
    GT_INT = 0x54
    GE_INT = 0x55
    LT_FLOAT = 0x56
    LE_FLOAT = 0x57
    GT_FLOAT = 0x58
    GE_FLOAT = 0x59
    NOT = 0x5A
    AND = 0x5B
    OR = 0x5C
    IS_NIL = 0x5D
    
    # Control flow (0x70-0x8F)
    JUMP = 0x70
    JUMP_IF_TRUE = 0x71
    JUMP_IF_FALSE = 0x72
    JUMP_FORWARD = 0x73
    CALL = 0x74
    CALL_LOCAL = 0x75
    TAIL_CALL = 0x76
    RETURN = 0x77
    RETURN_UNIT = 0x78
    MATCH_JUMP = 0x79
    
    # Data structures (0x90-0xAF)
    MAKE_LIST = 0x90
    MAKE_LIST_EMPTY = 0x91
    MAKE_TUPLE = 0x92
    MAKE_RECORD = 0x93
    MAKE_RECORD_NAMED = 0x94
    MAKE_CLOSURE = 0x95
    GET_FIELD = 0x96
    GET_FIELD_BY_NAME = 0x97
    SET_FIELD = 0x98
    GET_INDEX = 0x99
    SET_INDEX = 0x9A
    LIST_LEN = 0x9B
    LIST_APPEND = 0x9C
    LIST_CONS = 0x9D
    LIST_HEAD = 0x9E
    LIST_TAIL = 0x9F
    
    # Host functions & effects (0xB0-0xCF)
    CALL_HOST = 0xB0
    CALL_TOOL = 0xB1
    MEMORY_STORE = 0xB2
    MEMORY_RECALL = 0xB3
    OPENCLAW_TOOL = 0xB4
    SPEC_DEFINE = 0xB5
    SPEC_GATE = 0xB6
    SPEC_UPDATE = 0xB7
    SPEC_SEAL = 0xB8
    
    # Exception handling (0xD0-0xEF)
    PUSH_HANDLER = 0xD0
    POP_HANDLER = 0xD1
    RAISE = 0xD2
    CHECK_EFFECT = 0xD3
    CHECK_TIER = 0xD4
    
    # Special (0xF0-0xFF)
    BREAKPOINT = 0xF0
    TRACE = 0xF1
    ASSERT = 0xF2
    GAS_CHECK = 0xF3
    HALT = 0xFF

class ConstantPoolEntry:
    """Entry in constant pool"""
    
    def __init__(self, type_tag: int, value: Any):
        self.type_tag = type_tag
        self.value = value
    
    def serialize(self) -> bytes:
        """Serialize to bytes"""
        data = bytes([self.type_tag])
        
        if self.type_tag == 0x01:  # INTEGER
            data += struct.pack('<q', self.value)
        elif self.type_tag == 0x02:  # FLOAT
            data += struct.pack('<d', self.value)
        elif self.type_tag == 0x03:  # STRING
            encoded = self.value.encode('utf-8')
            data += struct.pack('<I', len(encoded))
            data += encoded
            # Pad to 4-byte alignment
            padding = (4 - len(encoded) % 4) % 4
            data += b'\x00' * padding
        elif self.type_tag == 0x04:  # ATOM
            encoded = self.value.encode('utf-8')
            data += struct.pack('<I', len(encoded))
            data += encoded
        
        return data

class Function:
    """Compiled function"""
    
    def __init__(self, name: str, arity: int = 0):
        self.name = name
        self.arity = arity
        self.flags = 0
        self.local_count = 0
        self.max_stack = 0
        self.gas_limit = 0
        self.effects: List[int] = []
        self.name_idx = 0
        self.code: List[Union[int, tuple]] = []
        self.doc_idx: Optional[int] = None

class BytecodeModule:
    """Compiled HLF module"""
    
    MAGIC = b'HLFB'
    VERSION = (0, 5, 0)
    
    def __init__(self, name: str = "main"):
        self.name = name
        self.constants: List[ConstantPoolEntry] = []
        self.functions: List[Function] = []
        self.atoms: List[str] = []
        self.field_names: List[str] = []
        self.entry_point = 0
        self.flags = 0
    
    def add_int(self, value: int) -> int:
        """Add integer constant, return index"""
        self.constants.append(ConstantPoolEntry(0x01, value))
        return len(self.constants) - 1
    
    def add_float(self, value: float) -> int:
        """Add float constant, return index"""
        self.constants.append(ConstantPoolEntry(0x02, value))
        return len(self.constants) - 1
    
    def add_string(self, value: str) -> int:
        """Add string constant, return index"""
        self.constants.append(ConstantPoolEntry(0x03, value))
        return len(self.constants) - 1
    
    def add_atom(self, value: str) -> int:
        """Add atom constant, return index"""
        self.constants.append(ConstantPoolEntry(0x04, value))
        return len(self.constants) - 1
    
    def add_function(self, func: Function) -> int:
        """Add function, return index"""
        self.functions.append(func)
        return len(self.functions) - 1
    
    def get_atom_index(self, name: str) -> int:
        """Get or create atom index"""
        try:
            return self.atoms.index(name)
        except ValueError:
            self.atoms.append(name)
            return len(self.atoms) - 1
    
    def get_field_index(self, name: str) -> int:
        """Get or create field name index"""
        try:
            return self.field_names.index(name)
        except ValueError:
            self.field_names.append(name)
            return len(self.field_names) - 1
    
    def serialize(self) -> bytes:
        """Serialize module to bytecode"""
        output = io.BytesIO()
        
        # Header
        output.write(self.MAGIC)
        output.write(struct.pack('<BB', *self.VERSION[:2]))
        output.write(struct.pack('<H', self.flags))
        
        # Calculate section offsets
        header_size = 16
        
        # Constant pool
        const_pool_offset = output.tell()
        output.write(struct.pack('<I', len(self.constants)))
        for entry in self.constants:
            output.write(entry.serialize())
        
        # Atom table
        atom_offset = output.tell()
        output.write(struct.pack('<I', len(self.atoms)))
        for atom in self.atoms:
            encoded = atom.encode('utf-8')
            output.write(struct.pack('<I', len(encoded)))
            output.write(encoded)
        
        # Field name table
        field_offset = output.tell()
        output.write(struct.pack('<I', len(self.field_names)))
        for field in self.field_names:
            encoded = field.encode('utf-8')
            output.write(struct.pack('<I', len(encoded)))
            output.write(encoded)
        
        # Functions
        code_offset = output.tell()
        output.write(struct.pack('<I', len(self.functions)))
        for func in self.functions:
            output.write(struct.pack('<B', func.flags))
            output.write(struct.pack('<B', func.arity))
            output.write(struct.pack('<H', func.local_count))
            output.write(struct.pack('<H', func.max_stack))
            output.write(struct.pack('<I', func.gas_limit))
            output.write(struct.pack('<B', len(func.effects)))
            for effect in func.effects:
                output.write(struct.pack('<H', effect))
            output.write(struct.pack('<H', func.name_idx))
            output.write(struct.pack('<H', func.doc_idx if func.doc_idx is not None else 0xFFFF))
            
            # Serialize code
            code_bytes = self._serialize_code(func.code)
            output.write(struct.pack('<I', len(code_bytes)))
            output.write(code_bytes)
        
        # Entry point
        entry_offset = output.tell()
        output.write(struct.pack('<I', self.entry_point))
        
        # Update header with offsets (go back and patch)
        current_pos = output.tell()
        output.seek(6)
        output.write(struct.pack('<I', const_pool_offset))
        output.write(struct.pack('<I', code_offset))
        output.write(struct.pack('<I', 0))  # debug_info_offset (optional)
        output.write(struct.pack('<I', entry_offset))
        output.seek(current_pos)
        
        return output.getvalue()
    
    def _serialize_code(self, code: List[Union[int, tuple]]) -> bytes:
        """Serialize instruction stream to bytes"""
        output = io.BytesIO()
        
        for instr in code:
            if isinstance(instr, int):
                output.write(bytes([instr]))
            elif isinstance(instr, tuple):
                opcode = instr[0]
                output.write(bytes([opcode]))
                
                # Serialize operands based on opcode
                if opcode in (OpCode.LOAD_CONST, OpCode.LOAD_ATOM, OpCode.GET_FIELD_BY_NAME,
                             OpCode.CALL, OpCode.CALL_TOOL, OpCode.CALL_HOST,
                             OpCode.OPENCLAW_TOOL, OpCode.SPEC_DEFINE):
                    # u16 operand
                    output.write(struct.pack('<H', instr[1]))
                elif opcode in (OpCode.LOAD_CONST_FAST, OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL,
                               OpCode.LOAD_ARG, OpCode.LOAD_CLOSURE, OpCode.STORE_CLOSURE,
                               OpCode.GET_FIELD, OpCode.SET_FIELD, OpCode.DUP_N, OpCode.PICK,
                               OpCode.DROP_N, OpCode.MAKE_LIST, OpCode.MAKE_TUPLE,
                               OpCode.MAKE_RECORD, OpCode.MAKE_CLOSURE, OpCode.CALL_LOCAL,
                               OpCode.TAIL_CALL):
                    # u8 operand
                    output.write(bytes([instr[1]]))
                elif opcode in (OpCode.JUMP, OpCode.JUMP_IF_TRUE, OpCode.JUMP_IF_FALSE,
                               OpCode.CALL_LOCAL, OpCode.PUSH_HANDLER, OpCode.MATCH_JUMP,
                               OpCode.ASSERT):
                    # i16 or u16
                    output.write(struct.pack('<h' if opcode != OpCode.JUMP_FORWARD else '<H', instr[1]))
                elif opcode in (OpCode.LOAD_INT_SMALL, OpCode.CHECK_TIER, OpCode.RAISE,
                               OpCode.TRACE, OpCode.HALT):
                    # Single u8
                    output.write(bytes([instr[1]]))
                elif opcode in (OpCode.CALL, OpCode.TAIL_CALL, OpCode.CALL_HOST):
                    # u16 + u8
                    output.write(struct.pack('<H', instr[1]))
                    output.write(bytes([instr[2]]))
                elif opcode == OpCode.GAS_CHECK:
                    # u32
                    output.write(struct.pack('<I', instr[1]))
        
        return output.getvalue()
    
    def disassemble(self) -> str:
        """Disassemble to readable text"""
        lines = [
            f"; HLF Bytecode Module: {self.name}",
            f"; Version: {self.VERSION[0]}.{self.VERSION[1]}.{self.VERSION[2]}",
            f"; Entry point: function {self.entry_point}",
            "",
            ".const",
        ]
        
        for i, entry in enumerate(self.constants):
            type_name = {0x01: "int", 0x02: "float", 0x03: "string", 0x04: "atom"}.get(
                entry.type_tag, "unknown"
            )
            lines.append(f"  {i}: {type_name} {repr(entry.value)}")
        
        lines.extend(["", ".atom"])
        for i, atom in enumerate(self.atoms):
            lines.append(f"  {i}: :{atom}")
        
        lines.extend(["", ".fields"])
        for i, field in enumerate(self.field_names):
            lines.append(f"  {i}: {field}")
        
        for i, func in enumerate(self.functions):
            lines.extend(["", f".func {func.name}/{func.arity}"])
            lines.append(f"  locals: {func.local_count}")
            lines.append(f"  max_stack: {func.max_stack}")
            lines.append(f"  gas: {func.gas_limit}")
            if func.effects:
                lines.append(f"  effects: {func.effects}")
            
            # Disassemble code
            lines.append("")
            for pc, instr in enumerate(func.code):
                if isinstance(instr, int):
                    opcode_name = OpCode(instr).name if instr in OpCode else f"UNKNOWN_{instr:02X}"
                    lines.append(f"  {pc:4}: {opcode_name}")
                elif isinstance(instr, tuple):
                    opcode_name = OpCode(instr[0]).name if instr[0] in OpCode else f"UNKNOWN_{instr[0]:02X}"
                    operands = " ".join(str(x) for x in instr[1:])
                    lines.append(f"  {pc:4}: {opcode_name} {operands}")
        
        return "\n".join(lines)

# Convenience functions
def load_bytecode(data: bytes) -> BytecodeModule:
    """Load bytecode from bytes"""
    # TODO: Implement bytecode loading
    raise NotImplementedError("Bytecode loading not yet implemented")

# Example/test
def create_hello_world() -> BytecodeModule:
    """Create a simple 'hello world' bytecode module"""
    mod = BytecodeModule("hello")
    
    # Add constants
    hello_idx = mod.add_string("Hello, World!")
    
    # Create main function
    main = Function("main", 0)
    main.local_count = 0
    main.max_stack = 1
    main.gas_limit = 100
    main.code = [
        (OpCode.LOAD_CONST, hello_idx),
        OpCode.RETURN,
    ]
    main.name_idx = mod.add_string("main")
    
    mod.add_function(main)
    mod.entry_point = 0
    
    return mod

if __name__ == "__main__":
    # Test
    mod = create_hello_world()
    print(mod.disassemble())
    print("\n\nSerialized size:", len(mod.serialize()), "bytes")
