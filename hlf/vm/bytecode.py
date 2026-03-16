"""
HLF Bytecode Representation
Binary format for compiled HLF programs
"""

from typing import List, Dict, Any, Optional, BinaryIO, Union
from enum import IntEnum
import struct
import hashlib
import io
import zlib

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
    
    MAGIC = b'HLB\x00'
    FORMAT_VERSION = 0x0005  # v0.5
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
        """Serialize module to .hlb binary format per README spec.
        
                Layout:
                    0..31   SHA-256 hash of everything after it
                    32..35  Magic: HLB\\x00
                    36..37  Format version (LE uint16)
                    38..41  Code section length (LE uint32)
                    42..45  CRC32 of code section (LE uint32)
                    46..47  Flags (LE uint16)
                    48..n   Constant pool (typed entries)
                    n+1..   Code section (variable-width instructions per function)
        """
        body = io.BytesIO()
        
        # Magic + version + placeholders for code_len/crc/flags
        body.write(self.MAGIC)                            # 4 bytes  (offset 0 in body)
        body.write(struct.pack('<H', self.FORMAT_VERSION)) # 2 bytes
        code_len_pos = body.tell()
        body.write(struct.pack('<I', 0))                  # code section length placeholder
        crc_pos = body.tell()
        body.write(struct.pack('<I', 0))                  # CRC32 placeholder
        body.write(struct.pack('<H', self.flags))         # 2 bytes flags
        # body offset 16 = start of constant pool
        
        # Constant pool
        body.write(struct.pack('<I', len(self.constants)))
        for entry in self.constants:
            body.write(entry.serialize())
        
        # Atom table
        body.write(struct.pack('<I', len(self.atoms)))
        for atom in self.atoms:
            encoded = atom.encode('utf-8')
            body.write(struct.pack('<I', len(encoded)))
            body.write(encoded)
        
        # Field name table
        body.write(struct.pack('<I', len(self.field_names)))
        for field in self.field_names:
            encoded = field.encode('utf-8')
            body.write(struct.pack('<I', len(encoded)))
            body.write(encoded)
        
        # Functions metadata + code
        code_section_start = body.tell()
        body.write(struct.pack('<I', len(self.functions)))
        body.write(struct.pack('<I', self.entry_point))
        
        for func in self.functions:
            # Function header
            name_encoded = func.name.encode('utf-8')
            body.write(struct.pack('<I', len(name_encoded)))
            body.write(name_encoded)
            body.write(struct.pack('<B', func.flags))
            body.write(struct.pack('<B', func.arity))
            body.write(struct.pack('<H', func.local_count))
            body.write(struct.pack('<H', func.max_stack))
            body.write(struct.pack('<I', func.gas_limit))
            body.write(struct.pack('<B', len(func.effects)))
            for effect in func.effects:
                body.write(struct.pack('<H', effect))
            
            code_bytes = self._serialize_code(func.code)
            body.write(struct.pack('<I', len(code_bytes)))
            body.write(code_bytes)
        
        # Patch code section length and CRC32
        code_section_bytes = body.getvalue()[code_section_start:]
        code_len = len(code_section_bytes)
        crc = zlib.crc32(code_section_bytes) & 0xFFFFFFFF
        
        body.seek(code_len_pos)
        body.write(struct.pack('<I', code_len))
        body.seek(crc_pos)
        body.write(struct.pack('<I', crc))
        
        # Prepend SHA-256 of the body
        body_bytes = body.getvalue()
        sha = hashlib.sha256(body_bytes).digest()
        return sha + body_bytes
    
    @classmethod
    def deserialize(cls, data: bytes) -> "BytecodeModule":
        """Deserialize .hlb binary back into a BytecodeModule."""
        if len(data) < 48:
            raise ValueError("Data too short for .hlb format")
        
        # Verify SHA-256
        sha_expected = data[:32]
        body = data[32:]
        sha_actual = hashlib.sha256(body).digest()
        if sha_expected != sha_actual:
            raise ValueError("SHA-256 integrity check failed")
        
        r = io.BytesIO(body)
        
        # Magic
        magic = r.read(4)
        if magic != cls.MAGIC:
            raise ValueError(f"Bad magic: {magic!r}, expected {cls.MAGIC!r}")
        
        fmt_version = struct.unpack('<H', r.read(2))[0]
        code_section_len = struct.unpack('<I', r.read(4))[0]
        crc_expected = struct.unpack('<I', r.read(4))[0]
        flags = struct.unpack('<H', r.read(2))[0]
        
        mod = cls()
        mod.flags = flags
        
        # Constant pool
        const_count = struct.unpack('<I', r.read(4))[0]
        for _ in range(const_count):
            tag = r.read(1)[0]
            if tag == 0x01:  # INT
                val = struct.unpack('<q', r.read(8))[0]
            elif tag == 0x02:  # FLOAT
                val = struct.unpack('<d', r.read(8))[0]
            elif tag == 0x03:  # STRING
                slen = struct.unpack('<I', r.read(4))[0]
                val = r.read(slen).decode('utf-8')
                padding = (4 - slen % 4) % 4
                r.read(padding)
            elif tag == 0x04:  # ATOM
                slen = struct.unpack('<I', r.read(4))[0]
                val = r.read(slen).decode('utf-8')
            else:
                raise ValueError(f"Unknown constant tag: {tag:#x}")
            mod.constants.append(ConstantPoolEntry(tag, val))
        
        # Atom table
        atom_count = struct.unpack('<I', r.read(4))[0]
        for _ in range(atom_count):
            slen = struct.unpack('<I', r.read(4))[0]
            mod.atoms.append(r.read(slen).decode('utf-8'))
        
        # Field name table
        field_count = struct.unpack('<I', r.read(4))[0]
        for _ in range(field_count):
            slen = struct.unpack('<I', r.read(4))[0]
            mod.field_names.append(r.read(slen).decode('utf-8'))
        
        # Functions
        code_section_start = r.tell()
        func_count = struct.unpack('<I', r.read(4))[0]
        mod.entry_point = struct.unpack('<I', r.read(4))[0]
        
        for _ in range(func_count):
            name_len = struct.unpack('<I', r.read(4))[0]
            name = r.read(name_len).decode('utf-8')
            func = Function(name)
            func.flags = r.read(1)[0]
            func.arity = r.read(1)[0]
            func.local_count = struct.unpack('<H', r.read(2))[0]
            func.max_stack = struct.unpack('<H', r.read(2))[0]
            func.gas_limit = struct.unpack('<I', r.read(4))[0]
            effect_count = r.read(1)[0]
            func.effects = [struct.unpack('<H', r.read(2))[0] for _ in range(effect_count)]
            
            code_len = struct.unpack('<I', r.read(4))[0]
            code_raw = r.read(code_len)
            func.code = cls._deserialize_code(code_raw)
            mod.functions.append(func)
        
        # Verify CRC32 of code section
        code_section_bytes = body[code_section_start:]
        crc_actual = zlib.crc32(code_section_bytes) & 0xFFFFFFFF
        if crc_actual != crc_expected:
            raise ValueError(f"CRC32 mismatch: expected {crc_expected:#x}, got {crc_actual:#x}")
        
        return mod
    
    # Opcodes that take no operand (bare int in internal repr)
    _NO_OPERAND_OPCODES = frozenset({
        OpCode.NOP, OpCode.POP, OpCode.DUP, OpCode.SWAP, OpCode.ROT,
        OpCode.LOAD_TRUE, OpCode.LOAD_FALSE, OpCode.LOAD_UNIT,
        OpCode.ADD_INT, OpCode.SUB_INT, OpCode.MUL_INT, OpCode.DIV_INT,
        OpCode.MOD_INT, OpCode.NEG_INT,
        OpCode.ADD_FLOAT, OpCode.SUB_FLOAT, OpCode.MUL_FLOAT, OpCode.DIV_FLOAT,
        OpCode.NEG_FLOAT, OpCode.POW_FLOAT,
        OpCode.EQ, OpCode.NE, OpCode.LT_INT, OpCode.LE_INT, OpCode.GT_INT,
        OpCode.GE_INT, OpCode.LT_FLOAT, OpCode.LE_FLOAT, OpCode.GT_FLOAT,
        OpCode.GE_FLOAT, OpCode.NOT, OpCode.AND, OpCode.OR, OpCode.IS_NIL,
        OpCode.RETURN, OpCode.RETURN_UNIT,
        OpCode.MAKE_LIST_EMPTY,
        OpCode.GET_INDEX, OpCode.SET_INDEX, OpCode.LIST_LEN,
        OpCode.LIST_APPEND, OpCode.LIST_CONS, OpCode.LIST_HEAD, OpCode.LIST_TAIL,
        OpCode.POP_HANDLER, OpCode.RAISE,
        OpCode.BREAKPOINT, OpCode.HALT,
    })

    @staticmethod
    def _deserialize_code(data: bytes) -> List[Union[int, tuple]]:
        """Deserialize variable-width instructions back to internal representation."""
        no_op = BytecodeModule._NO_OPERAND_OPCODES
        u16_ops = frozenset({
            OpCode.LOAD_CONST, OpCode.LOAD_ATOM, OpCode.GET_FIELD_BY_NAME,
            OpCode.CALL_TOOL, OpCode.OPENCLAW_TOOL, OpCode.SPEC_DEFINE,
        })
        u8_ops = frozenset({
            OpCode.LOAD_CONST_FAST, OpCode.LOAD_LOCAL, OpCode.STORE_LOCAL,
            OpCode.LOAD_ARG, OpCode.LOAD_CLOSURE, OpCode.STORE_CLOSURE,
            OpCode.GET_FIELD, OpCode.SET_FIELD, OpCode.DUP_N, OpCode.PICK,
            OpCode.DROP_N, OpCode.MAKE_LIST, OpCode.MAKE_TUPLE,
            OpCode.MAKE_RECORD, OpCode.MAKE_CLOSURE, OpCode.CALL_LOCAL,
            OpCode.TAIL_CALL,
        })
        jump_ops = frozenset({
            OpCode.JUMP, OpCode.JUMP_IF_TRUE, OpCode.JUMP_IF_FALSE,
            OpCode.JUMP_FORWARD, OpCode.PUSH_HANDLER, OpCode.MATCH_JUMP,
            OpCode.ASSERT,
        })
        single_byte_ops = frozenset({
            OpCode.LOAD_INT_SMALL, OpCode.CHECK_TIER, OpCode.RAISE,
            OpCode.TRACE, OpCode.HALT,
        })
        multi_operand_ops = frozenset({OpCode.CALL, OpCode.CALL_HOST})

        code = []
        i = 0
        while i < len(data):
            opcode = data[i]
            i += 1

            if opcode in no_op:
                code.append(opcode)
            elif opcode in u16_ops:
                code.append((opcode, struct.unpack('<H', data[i:i+2])[0]))
                i += 2
            elif opcode in u8_ops:
                code.append((opcode, data[i]))
                i += 1
            elif opcode in jump_ops:
                fmt = '<H' if opcode == OpCode.JUMP_FORWARD else '<h'
                code.append((opcode, struct.unpack(fmt, data[i:i+2])[0]))
                i += 2
            elif opcode in single_byte_ops:
                code.append((opcode, data[i]))
                i += 1
            elif opcode in multi_operand_ops:
                operand = struct.unpack('<H', data[i:i+2])[0]
                argc = data[i+2]
                code.append((opcode, operand, argc))
                i += 3
            elif opcode == OpCode.GAS_CHECK:
                code.append((opcode, struct.unpack('<I', data[i:i+4])[0]))
                i += 4
            else:
                code.append((opcode, operand))

        return code
    
    def _serialize_code(self, code: List[Union[int, tuple]]) -> bytes:
        """Serialize instruction stream to variable-width bytes (internal use)."""
        output = io.BytesIO()
        
        for instr in code:
            if isinstance(instr, int):
                output.write(bytes([instr]))
            elif isinstance(instr, tuple):
                opcode = instr[0]
                output.write(bytes([opcode]))
                
                # Serialize operands based on opcode
                if opcode in (
                    OpCode.LOAD_CONST,
                    OpCode.LOAD_ATOM,
                    OpCode.GET_FIELD_BY_NAME,
                    OpCode.CALL_TOOL,
                    OpCode.OPENCLAW_TOOL,
                    OpCode.SPEC_DEFINE,
                ):
                    # u16 operand
                    output.write(struct.pack('<H', instr[1]))
                elif opcode in (
                    OpCode.LOAD_CONST_FAST,
                    OpCode.LOAD_LOCAL,
                    OpCode.STORE_LOCAL,
                    OpCode.LOAD_ARG,
                    OpCode.LOAD_CLOSURE,
                    OpCode.STORE_CLOSURE,
                    OpCode.GET_FIELD,
                    OpCode.SET_FIELD,
                    OpCode.DUP_N,
                    OpCode.PICK,
                    OpCode.DROP_N,
                    OpCode.MAKE_LIST,
                    OpCode.MAKE_TUPLE,
                    OpCode.MAKE_RECORD,
                    OpCode.MAKE_CLOSURE,
                    OpCode.CALL_LOCAL,
                ):
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
    """Load bytecode from .hlb bytes"""
    return BytecodeModule.deserialize(data)

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
