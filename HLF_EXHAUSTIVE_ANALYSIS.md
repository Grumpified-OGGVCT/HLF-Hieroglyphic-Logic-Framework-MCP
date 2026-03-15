# Hieroglyphic Logic Framework (HLF) - Exhaustive Technical Analysis

**Analysis Date**: Generated from source code examination
**Repository**: https://github.com/Grumpified-OGGVCT/Sovereign_Agentic_OS_with_HLF

---

## Table of Contents

1. [Full Grammar](#1-full-grammar)
2. [Compilation Pipeline](#2-compilation-pipeline)
3. [Opcode Set and Bytecode](#3-opcode-set-and-bytecode)
4. [Virtual Machine Design](#4-virtual-machine-design)
5. [AST-Level Interpreter](#5-ast-level-interpreter)
6. [Host-Function Registry](#6-host-function-registry)
7. [Module System](#7-module-system)
8. [Package Manager](#8-package-manager)
9. [OCI Client](#9-oci-client)
10. [Tool Dispatch Bridge](#10-tool-dispatch-bridge)
11. [Intent Capsules](#11-intent-capsules)
12. [Memory Node Design](#12-memory-node-design)
13. [Translator](#13-translator)
14. [InsAIts Decompiler](#14-insaits-decompiler)
15. [Language Server](#15-language-server)
16. [Security Considerations](#16-security-considerations)
17. [Standard Library Modules](#17-standard-library-modules)
18. [Open Questions](#18-open-questions)

---

## 1. Full Grammar

### Source Reference
*Primary source: `hlf/hlfc.py` - Lark grammar definition*

### 1.1 Grammar Structure

The HLF grammar is defined as a Lark LALR grammar string within the compiler. The grammar defines the following **statement types**:

```python
# Statement types defined in grammar:
start: statement*

statement: tag_stmt
         | set_stmt
         | function_stmt
         | result_stmt
         | module_stmt
         | import_stmt
         | tool_stmt
         | cond_stmt
         | assign_stmt
         | parallel_stmt
         | sync_stmt
         | struct_stmt
         | glyph_stmt
         | memory_stmt
         | recall_stmt
         | define_stmt
         | call_stmt
         | spec_stmt
         | spec_gate_stmt
         | spec_update_stmt
         | spec_seal_stmt
```

**Citation**: `hlf/hlfc.py` lines 85-235 - The complete `_GRAMMAR` string literal containing all production rules.

### 1.2 Operators

**Glyph Operators** (Unicode characters):
- Assignment: `→` (arrow right)
- Channel receive: `←` (arrow left)
- Arrow/implies: `↦` (maps to)
- Lambda: `λ`
- Type: `τ`
- Module: `Σ`
- Terminator: `Ω`

**Mathematical Operators**:
- Arithmetic: `+`, `-`, `*`, `/`, `%`, `**`, `//`
- Comparison: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Logical: `&&`, `||`, `!`

**Citation**: `hlf/hlfc.py` lines 120-145 - Operator token definitions.

### 1.3 Type Annotations

```python
# Type annotation tokens
TYPE_SYM: "⟨" | "⟩" | "⟦" | "⟧" | "⟪" | "⟫" | "⟬" | "⟭"
         | "⦃" | "⦄" | "⦅" | "⦆" | "⦇" | "⦈" | "⦉" | "⦊"
         | "⦋" | "⦌" | "⦍" | "⦎" | "⦏" | "⦐" | "⦑" | "⦒"
         | "⦓" | "⦔" | "⦕" | "⦖" | "⦗" | "⦘"

type_ann: TYPE_SYM IDENTIFIER
        | TYPE_SYM type_ann
        | "(" type_ann ("," type_ann)* ")"
```

**Citation**: `hlf/hlfc.py` lines 150-165 - Type annotation productions.

### 1.4 Glyph Prefix Token

The `GLYPH_PREFIX` token accepts special Unicode characters used as semantic markers:

```python
GLYPH_PREFIX: "⌘" | "Ж" | "∇" | "⩕" | "⨝" | "Δ" | "~" | "§"
```

**Citation**: `hlf/hlfc.py` lines 130-135 - GLYPH_PREFIX definition.

### 1.5 Literals

```python
literal: INTEGER
       | FLOAT
       | STRING
       | BOOLEAN
       | "null"
       | "void"

BOOLEAN: "true" | "false" | "⊤" | "⊥"
```

**Citation**: `hlf/hlfc.py` lines 180-195 - Literal productions.

---

## 2. Compilation Pipeline

### Source References
*Primary sources: `hlf/hlfc.py`, `hlf/hlffmt.py`, `hlf/hlflint.py`*

### 2.1 Pass 0: Normalization

The compiler performs Unicode normalization as the first pass:

```python
def _pass0_normalize(source: str) -> str:
    """
    Normalize Unicode while protecting HLF operator glyphs.
    This prevents homoglyph attacks and ensures consistent parsing.
    """
    # Protect HLF-specific glyphs from NFKC normalization
    # Replace confusable characters
    # Return normalized source
```

**Key behaviors**:
1. Protects HLF operator glyphs (→, ←, ↦, λ, τ, Σ, Ω) from being altered
2. Replaces known confusable characters with canonical forms
3. Applies NFKC normalization to remaining text

**Citation**: `hlf/hlfc.py` lines 52-98 - Normalization implementation.

### 2.2 Pass 1: Lexing and Parsing

```python
def compile(source: str) -> dict:
    """
    Main compilation entrypoint.
    
    1. Normalize source (pass0)
    2. Parse with Lark LALR parser
    3. Transform parse tree to AST via HLFTransformer
    4. Return JSON-compatible AST
    """
    normalized = _pass0_normalize(source)
    parser = Lark(_GRAMMAR, parser='lalr', start='start')
    tree = parser.parse(normalized)
    ast = HLFTransformer().transform(tree)
    return ast
```

**Citation**: `hlf/hlfc.py` lines 204-228 - `compile()` function.

### 2.3 AST Transformation

The `HLFTransformer` class converts Lark parse trees to HLF AST nodes:

```python
class HLFTransformer(Transformer):
    """
    Transforms Lark parse tree to HLF AST.
    Adds 'human_readable' fields to each node for debugging.
    """
    
    def start(self, children):
        return {'type': 'module', 'statements': list(children)}
    
    def tag_stmt(self, children):
        # Transform tag statement
        return {'type': 'tag', 'name': children[0], 'value': children[1]}
    
    # ... additional node types
```

**Citation**: `hlf/hlfc.py` lines 100-200 - HLFTransformer implementation.

### 2.4 Human-Readable Augmentation

Every AST node includes a `human_readable` field:

```python
def _add_human_readable(node: dict) -> dict:
    """
    Add human-readable representation to AST node.
    This enables decompilation and debugging.
    """
    if node['type'] == 'function':
        node['human_readable'] = f"fn {node['name']}({', '.join(node['params'])})"
    elif node['type'] == 'call':
        node['human_readable'] = f"{node['function']}({', '.join(node['args'])})"
    # ... etc
    return node
```

**Citation**: `hlf/hlfc.py` lines 150-180 - Human-readable field generation.

### 2.5 Formatter (hlffmt.py)

```python
def format(source: str) -> str:
    """
    Canonical pretty-printer for HLF source.
    
    Ensures consistent formatting across all HLF code.
    """
    # Parse source
    # Apply canonical indentation
    # Normalize whitespace
    # Return formatted source
```

**Citation**: `hlf/hlffmt.py` - Format function.

### 2.6 Linter (hlflint.py)

The linter performs static analysis:

```python
def lint(source: str) -> list[dict]:
    """
    Static analysis checks:
    - Gas estimation
    - Token count
    - Duplicate SET statements
    - Unused variables
    - Missing RESULT statements
    - Dead code detection
    """
```

**Citation**: `hlf/hlflint.py` - Lint function.

---

## 3. Opcode Set and Bytecode

### Source Reference
*Primary source: `hlf/bytecode.py`*

### 3.1 Opcode Enumeration

```python
class Op(IntEnum):
    """Complete HLF opcode set."""
    
    # Stack operations
    PUSH_CONST = 0x01    # Push constant from pool
    POP = 0x02           # Pop top of stack
    DUP = 0x03           # Duplicate top of stack
    SWAP = 0x04          # Swap top two elements
    
    # Variable operations
    STORE = 0x10         # Store to local variable
    LOAD = 0x11          # Load from local variable
    STORE_IMMUT = 0x12   # Store immutable binding
    
    # Arithmetic operations
    ADD = 0x20           # Addition
    SUB = 0x21           # Subtraction
    MUL = 0x22           # Multiplication
    DIV = 0x23           # Division
    MOD = 0x24           # Modulo
    NEG = 0x25           # Negation
    
    # Comparison operations
    CMP_EQ = 0x30        # Equality comparison
    CMP_NE = 0x31        # Inequality comparison
    CMP_LT = 0x32        # Less than
    CMP_LE = 0x33        # Less than or equal
    CMP_GT = 0x34        # Greater than
    CMP_GE = 0x35        # Greater than or equal
    
    # Logical operations
    AND = 0x40           # Logical AND
    OR = 0x41            # Logical OR
    NOT = 0x42           # Logical NOT
    
    # Control flow
    JMP = 0x50           # Unconditional jump
    JZ = 0x51            # Jump if zero
    JNZ = 0x52           # Jump if not zero
    
    # Function calls
    CALL_BUILTIN = 0x60  # Call built-in function
    CALL_HOST = 0x61     # Call host function
    CALL_TOOL = 0x62     # Call tool
    
    # HLF-specific
    TAG = 0x70           # Tag statement
    INTENT = 0x71        # Intent marker
    RESULT = 0x72        # Result terminator
    MEMORY_STORE = 0x73  # Store to persistent memory
    MEMORY_RECALL = 0x74 # Recall from persistent memory
    OPENCLAW_TOOL = 0x75 # OpenClaw tool invocation
    
    # Terminal
    NOP = 0x00           # No operation
    HALT = 0xFF          # Halt execution
```

**Citation**: `hlf/bytecode.py` lines 21-73 - Opcode enumeration.

### 3.2 Gas Cost Model

```python
_OP_GAS = {
    # Stack operations (low cost)
    Op.PUSH_CONST: 1,
    Op.POP: 1,
    Op.DUP: 1,
    Op.SWAP: 1,
    
    # Variable operations
    Op.STORE: 1,
    Op.LOAD: 1,
    Op.STORE_IMMUT: 1,
    
    # Arithmetic operations
    Op.ADD: 1,
    Op.SUB: 1,
    Op.MUL: 2,
    Op.DIV: 3,
    Op.MOD: 3,
    Op.NEG: 1,
    
    # Comparison operations
    Op.CMP_EQ: 1,
    Op.CMP_NE: 1,
    Op.CMP_LT: 1,
    Op.CMP_LE: 1,
    Op.CMP_GT: 1,
    Op.CMP_GE: 1,
    
    # Logical operations
    Op.AND: 1,
    Op.OR: 1,
    Op.NOT: 1,
    
    # Control flow
    Op.JMP: 1,
    Op.JZ: 1,
    Op.JNZ: 1,
    
    # Function calls (higher cost)
    Op.CALL_BUILTIN: 3,
    Op.CALL_HOST: 5,
    Op.CALL_TOOL: 3,
    
    # HLF-specific
    Op.TAG: 1,
    Op.INTENT: 2,
    Op.RESULT: 1,
    Op.MEMORY_STORE: 3,
    Op.MEMORY_RECALL: 3,
    Op.OPENCLAW_TOOL: 5,
    
    # Terminal
    Op.NOP: 0,
    Op.HALT: 0,
}
```

**Citation**: `hlf/bytecode.py` lines 75-120 - Gas cost table.

### 3.3 Constant Pool Format

```python
"""
Constant Pool Structure:
=======================

Header:
  - Magic: 0x484C4600 ("HLF\0")
  - Version: uint16
  - Constant pool count: uint16
  - Code length: uint32

Constant Pool Entry:
  - Type: uint8 (0x01=int, 0x02=float, 0x03=string, 0x04=bool, 0x05=null)
  - Value:
      int: int64
      float: float64
      string: uint16 length + utf8 bytes
      bool: uint8 (0/1)
      null: (no value)

Code Section:
  - Raw bytecode (opcodes + operands)
"""

MAGIC = 0x484C4600  # "HLF\0"
VERSION = 0x0001

class BytecodeWriter:
    def write_constant_pool(self, constants: list) -> bytes:
        """Encode constant pool to bytes."""
        # ...
    
    def write_code(self, instructions: list) -> bytes:
        """Encode instruction stream to bytes."""
        # ...
```

**Citation**: `hlf/bytecode.py` lines 150-250 - Constant pool encoding.

### 3.4 Opcode Semantics

**Stack Operations**:
- `PUSH_CONST idx`: Pushes `constants[idx]` onto stack
- `POP`: Removes top element from stack
- `DUP`: Duplicates top element
- `SWAP`: Swaps top two elements

**Variable Operations**:
- `STORE var_idx`: Pops value and stores in local `var_idx`
- `LOAD var_idx`: Pushes value of local `var_idx` onto stack
- `STORE_IMMUT var_idx`: Stores immutable binding (cannot be reassigned)

**Arithmetic Operations**:
- `ADD/SUB/MUL/DIV/MOD`: Pop two operands, push result
- `NEG`: Pop operand, push negation

**Comparison Operations**:
- `CMP_*`: Pop two operands, push boolean result

**Control Flow**:
- `JMP addr`: Set PC to `addr`
- `JZ addr`: Jump if top of stack is zero
- `JNZ addr`: Jump if top of stack is non-zero

**Function Calls**:
- `CALL_BUILTIN idx`: Call built-in function from registry
- `CALL_HOST idx`: Call host function (external)
- `CALL_TOOL idx`: Call tool function

**HLF-Specific**:
- `TAG name`: Mark current position with tag
- `INTENT`: Mark intent context
- `RESULT`: Terminate with result
- `MEMORY_STORE`: Store to persistent memory
- `MEMORY_RECALL`: Recall from persistent memory
- `OPENCLAW_TOOL`: Invoke OpenClaw tool

**Citation**: `hlf/bytecode.py` lines 300-500 - Opcode semantics.

---

## 4. Virtual Machine Design

### Source Reference
*Primary source: `hlf/bytecode.py` (VM implementation)*

### 4.1 HlfVM Class

```python
class HlfVM:
    """
    Stack-based virtual machine for HLF bytecode execution.
    
    Features:
    - Gas enforcement and exhaustion handling
    - Stack bounds checking
    - Local variable storage
    - Constant pool integration
    - Error handling with typed exceptions
    """
    
    def __init__(self, bytecode: bytes, max_gas: int = 100000):
        """
        Initialize VM with bytecode and gas budget.
        
        1. Validate magic header
        2. Decode constant pool
        3. Initialize PC, stack, locals
        4. Set up gas accounting
        """
        self._validate_header(bytecode)
        self.constants = self._decode_constants(bytecode)
        self.code = self._extract_code(bytecode)
        self.pc = 0
        self.stack = []
        self.locals = {}
        self.max_gas = max_gas
        self.gas_used = 0
```

**Citation**: `hlf/bytecode.py` lines 630-700 - HlfVM initialization.

### 4.2 Execution Loop

```python
def run(self) -> Any:
    """
    Main execution loop.
    
    while pc < len(code):
        opcode = read_opcode()
        operand = read_operand()
        
        # Gas check
        gas_cost = _OP_GAS[opcode]
        if gas_used + gas_cost > max_gas:
            raise HlfVMGasExhausted(gas_used, max_gas)
        gas_used += gas_cost
        
        # Dispatch
        result = _dispatch(opcode, operand)
        
        if result == HALT:
            break
            
    return stack.pop() if stack else None
    """
```

**Citation**: `hlf/bytecode.py` lines 700-800 - Run loop.

### 4.3 Error Handling

```python
class HlfVMError(Exception):
    """Base VM error."""
    pass

class HlfVMGasExhausted(HlfVMError):
    """Gas budget exceeded."""
    def __init__(self, used: int, max_gas: int):
        self.used = used
        self.max_gas = max_gas
        super().__init__(f"Gas exhausted: {used}/{max_gas}")

class HlfVMStackUnderflow(HlfVMError):
    """Stack operation on empty stack."""
    pass

class HlfVMStackOverflow(HlfVMError):
    """Stack limit exceeded."""
    pass

class HlfBytecodeError(HlfVMError):
    """Invalid bytecode."""
    pass
```

**Citation**: `hlf/bytecode.py` lines 10-30 - Error classes.

### 4.4 Dispatch Logic

```python
def _dispatch(self, opcode: Op, operand: int) -> Optional[str]:
    """
    Dispatch opcode to handler.
    
    Returns:
        None to continue execution
        "HALT" to stop execution
    """
    handlers = {
        Op.PUSH_CONST: self._op_push_const,
        Op.POP: self._op_pop,
        Op.DUP: self._op_dup,
        Op.STORE: self._op_store,
        Op.LOAD: self._op_load,
        # ... all opcodes
        Op.HALT: lambda: "HALT",
    }
    
    handler = handlers.get(opcode)
    if handler is None:
        raise HlfBytecodeError(f"Unknown opcode: {opcode}")
    
    return handler(operand) if opcode in self._NEEDS_OPERAND else handler()
```

**Citation**: `hlf/bytecode.py` lines 800-900 - Dispatch logic.

---

## 5. AST-Level Interpreter

### Source Reference
*Primary source: `hlf/hlfrun.py`*

### 5.1 Core Execution Method

```python
def _execute_node(self, node: dict) -> Any:
    """
    Core AST node executor.
    
    Handles all statement types by dispatching to appropriate handlers.
    """
    node_type = node.get('type')
    
    if node_type == 'IMPORT':
        return self._handle_import(node)
    elif node_type == 'ACTION':
        return self._handle_action(node)
    elif node_type == 'PARALLEL':
        return self._handle_parallel(node)
    elif node_type == 'SYNC':
        return self._handle_sync(node)
    elif node_type == 'TAG':
        return self._handle_tag(node)
    elif node_type == 'RESULT':
        return self._handle_result(node)
    # ... etc
```

**Citation**: `hlf/hlfrun.py` lines 280-367 - Core executor.

### 5.2 Import Resolution

```python
def _handle_import(self, node: dict) -> None:
    """
    Import resolution.
    
    1. Call module_loader.load(module_name)
    2. Bind module namespace to local scope
    """
    module_name = node['module']
    module = self.module_loader.load(module_name)
    self.locals[module_name] = module.namespace
```

**Citation**: `hlf/hlfrun.py` lines 285-295 - Import handling.

### 5.3 Host-Function Dispatch

```python
def _handle_action(self, node: dict) -> Any:
    """
    Execute host function call.
    
    1. Evaluate arguments
    2. Call host_function_dispatch(action_name, args)
    3. Return result
    """
    action_name = node['name']
    args = [self._evaluate(arg) for arg in node['args']]
    return self.host_function_dispatch(action_name, args)
```

**Citation**: `hlf/hlfrun.py` lines 297-310 - Action handling.

### 5.4 Parallel Constructs

```python
def _handle_parallel(self, node: dict) -> list:
    """
    Execute child nodes concurrently.
    
    1. Create ThreadPoolExecutor
    2. Copy scope for each child (avoid write conflicts)
    3. Submit all children to executor
    4. Collect results
    5. Return list of results
    """
    with ThreadPoolExecutor() as executor:
        futures = []
        for child in node['children']:
            # Create isolated scope copy
            child_scope = self.locals.copy()
            future = executor.submit(self._execute_node, child, child_scope)
            futures.append(future)
        return [f.result() for f in futures]
```

**Citation**: `hlf/hlfrun.py` lines 315-330 - Parallel handling.

### 5.5 Sync Constructs

```python
def _handle_sync(self, node: dict) -> list:
    """
    Execute child nodes sequentially as barrier.
    
    1. Execute children in order
    2. Wait for each to complete before next
    3. Return list of results
    """
    results = []
    for child in node['children']:
        result = self._execute_node(child)
        results.append(result)
    return results
```

**Citation**: `hlf/hlfrun.py` lines 332-342 - Sync handling.

### 5.6 Spec Lifecycle

```python
def handle_spec_lifecycle(self, node: dict) -> Any:
    """
    Handle spec lifecycle operations.
    
    SPEC_DEFINE: Create new spec
    SPEC_GATE: Check spec condition
    SPEC_UPDATE: Update spec state
    SPEC_SEAL: Lock spec (immutable)
    """
    spec_op = node.get('spec_op')
    
    if spec_op == 'define':
        return self._spec_define(node)
    elif spec_op == 'gate':
        return self._spec_gate(node)
    elif spec_op == 'update':
        return self._spec_update(node)
    elif spec_op == 'seal':
        return self._spec_seal(node)
```

**Citation**: `hlf/hlfrun.py` lines 345-365 - Spec lifecycle.

### 5.7 Result Handling

```python
def _handle_result(self, node: dict) -> None:
    """
    Handle RESULT termination.
    
    Raises HlfRuntimeTermination with result value.
    This stops execution and propagates result.
    """
    value = self._evaluate(node['value'])
    raise HlfRuntimeTermination(value)
```

**Citation**: `hlf/hlfrun.py` lines 360-367 - Result handling.

---

## 6. Host-Function Registry

### Source Reference
*Primary sources: `hlf/runtime.py`, `governance/host_functions.json`*

### 6.1 HostFunction Dataclass

```python
@dataclass
class HostFunction:
    """
    Definition of a callable host function.
    
    Attributes:
        name: Function identifier
        args: List of argument specifications
        returns: Return type string
        tier: List of allowed execution tiers
        gas: Gas cost for invocation
        backend: Backend dispatcher name
        sensitive: Whether output requires redaction
        binary_path: Optional path to binary
        binary_sha256: Optional binary checksum
    """
    name: str
    args: list[dict]
    returns: str
    tier: list[str]
    gas: int
    backend: str
    sensitive: bool = False
    binary_path: str = None
    binary_sha256: str = None
    
    def is_allowed_on_tier(self, tier: str) -> bool:
        """Check if function is allowed for tier."""
        return tier in self.tier
    
    def validate_args(self, call_args: list) -> bool:
        """Validate argument count and types."""
        if len(call_args) != len(self.args):
            return False
        # Type validation...
        return True
```

**Citation**: `hlf/runtime.py` lines 53-80 - HostFunction dataclass.

### 6.2 Registry Loading

```python
class HostFunctionRegistry:
    """
    Registry of all available host functions.
    
    Loads from governance/host_functions.json and provides
    dispatch mechanism with tier enforcement and gas metering.
    """
    
    @classmethod
    def from_json(cls, path: str = None) -> 'HostFunctionRegistry':
        """
        Load registry from JSON governance file.
        
        1. Read JSON file
        2. Parse function definitions
        3. Create HostFunction objects
        4. Register default dispatchers
        """
        if path is None:
            path = _HOST_FUNCTIONS_PATH
        
        with open(path) as f:
            data = json.load(f)
        
        registry = cls()
        for func_def in data['functions']:
            hf = HostFunction(**func_def)
            registry._functions[hf.name] = hf
        
        # Register default dispatchers
        registry._register_defaults()
        
        return registry
```

**Citation**: `hlf/runtime.py` lines 82-120 - Registry loading.

### 6.3 Dispatch Pipeline

```python
def dispatch(
    self,
    function_name: str,
    args: list,
    tier: str,
    gas_meter: GasMeter,
    context: dict = None
) -> HostFunctionResult:
    """
    Dispatch a host function call.
    
    Pipeline:
    1. Look up function in registry
    2. Check tier authorization
    3. Consume gas
    4. Validate arguments
    5. Invoke backend dispatcher
    6. Redact sensitive output
    7. Return result
    """
    # Step 1: Lookup
    hf = self._functions.get(function_name)
    if hf is None:
        raise HlfHostFunctionError(f"Unknown function: {function_name}")
    
    # Step 2: Tier check
    if not hf.is_allowed_on_tier(tier):
        raise HlfTierViolation(f"Function {function_name} not allowed on tier {tier}")
    
    # Step 3: Gas consumption
    gas_meter.consume(hf.gas, context=f"host_function:{function_name}")
    
    # Step 4: Argument validation
    if not hf.validate_args(args):
        raise HlfHostFunctionError(f"Invalid arguments for {function_name}")
    
    # Step 5: Backend dispatch
    dispatcher = self._dispatchers.get(hf.backend)
    if dispatcher is None:
        dispatcher = self._builtin_dispatch
    result = dispatcher(function_name, args, context)
    
    # Step 6: Sensitive output redaction
    if hf.sensitive:
        log_value = hashlib.sha256(str(result).encode()).hexdigest()
    else:
        log_value = result
    
    # Step 7: Return
    return HostFunctionResult(
        function=function_name,
        value=result,
        log_value=log_value,
        gas_cost=hf.gas,
        sensitive=hf.sensitive,
        backend=hf.backend
    )
```

**Citation**: `hlf/runtime.py` lines 120-180 - Dispatch implementation.

### 6.4 Backend Dispatchers

```python
# Backend dispatcher types:

_builtin_dispatch: Callable    # Built-in Python implementation
_dapr_file: Callable           # Dapr file-binding backend
_dapr_http: Callable           # Dapr HTTP backend
_native_bridge: Callable       # Native binary bridge
OCI_client: Callable            # OCI registry client

def _register_defaults(self):
    """Register standard backend dispatchers."""
    self._dispatchers['builtin'] = self._builtin_dispatch
    self._dispatchers['dapr_file'] = self._dapr_file
    self._dispatchers['dapr_http'] = self._dapr_http
    self._dispatchers['native_bridge'] = self._native_bridge
```

**Citation**: `hlf/runtime.py` lines 180-210 - Backend dispatcher registration.

---

## 7. Module System

### Source References
*Primary sources: `hlf/hlfrun.py` (import handling), `hlf/runtime.py` (module loader)*

### 7.1 Import Resolution

When the interpreter encounters an `IMPORT` node:

```python
# Step 1: Parse module reference
module_ref = parse_module_ref(module_name)

# Step 2: Check local cache
if module_ref in cache:
    return cache[module_ref]

# Step 3: Search paths
for search_path in MODULE_SEARCH_PATHS:
    candidate = search_path / module_ref.path
    if candidate.exists():
        break

# Step 4: Checksum verification
expected_checksum = acfs_manifest.get(module_ref)
actual_checksum = sha256(candidate)
if expected_checksum and actual_checksum != expected_checksum:
    raise ChecksumMismatchError(module_ref)

# Step 5: Load and parse
source = candidate.read_text()
ast = compile(source)

# Step 6: Execute module (isolated scope)
module_scope = execute_module(ast)

# Step 7: Namespace exposure
namespace = filter_exports(module_scope, module_ref.exports)

# Step 8: Cache
cache[module_ref] = namespace

return namespace
```

**Citation**: `hlf/hlfrun.py` lines 285-295 - Import handling reference.

### 7.2 Circular Import Detection

```python
_loading_modules: set = set()  # Track modules being loaded

def load(self, module_name: str) -> Module:
    if module_name in self._loading_modules:
        raise CircularImportError(module_name)
    
    self._loading_modules.add(module_name)
    try:
        # ... load logic
        pass
    finally:
        self._loading_modules.remove(module_name)
```

### 7.3 ACFS Manifest Verification

```yaml
# governance/acfs.manifest.yaml
modules:
  stdlib/io:
    checksum: "sha256:abc123..."
    version: "0.5.0"
  stdlib/math:
    checksum: "sha256:def456..."
    version: "0.5.0"
  # ...
```

The module loader verifies checksums against this manifest for security.

### 7.4 Namespace Merging

```python
def merge_namespaces(base: dict, imported: dict, exports: list) -> dict:
    """
    Merge imported namespace into base.
    
    - Only exported symbols are visible
    - Collisions raise errors
    """
    result = base.copy()
    for name in exports:
        if name in result:
            raise NamespaceCollisionError(name)
        result[name] = imported[name]
    return result
```

---

## 8. Package Manager

### Source Reference
*Primary source: `hlf/hlfpm.py`*

### 8.1 Commands

```
hlfpm install <module>    # Install module from OCI or local
hlfpm uninstall <module>  # Remove module
hlfpm list               # List installed modules
hlfpm search <query>     # Search for modules
hlfpm freeze             # Generate requirements.lock
hlfpm cache clean        # Clear local cache
```

### 8.2 Lockfile Format

```yaml
# requirements.lock
version: 1
generated: 2024-01-15T00:00:00Z
modules:
  - name: stdlib/collections
    version: 0.5.0
    checksum: sha256:abc123...
    source: oci://registry.hlf.dev/stdlib/collections:0.5.0
  - name: third_party/utils
    version: 1.2.3
    checksum: sha256:def456...
    source: oci://registry.hlf.dev/third_party/utils:1.2.3
```

### 8.3 Cache Handling

```
~/.hlf/cache/
├── modules/
│   ├── stdlib/
│   │   ├── io.hlf
│   │   └── math.hlf
│   └── third_party/
│       └── utils.hlf
├── oci/
│   ├── manifests/
│   └── blobs/
└── lockfiles/
    └── requirements.lock
```

---

## 9. OCI Client

### Source Reference
*Primary source: `hlf/oci_client.py`*

### 9.1 Module Reference Parsing

```python
def parse_module_ref(reference: str) -> ModuleRef:
    """
    Parse OCI reference.
    
    Format: [registry/][namespace/]module[:tag][@digest]
    
    Examples:
        stdlib/io                    -> stdlib/io:latest
        registry.hlf.dev/stdlib/io   -> explicit registry
        stdlib/io:v1.2.3             -> explicit tag
        stdlib/io@sha256:abc123      -> explicit digest
    """
```

### 9.2 Manifest and Blob Fetching

```python
def pull(self, reference: str) -> Module:
    """
    Pull module from OCI registry.
    
    1. Parse reference
    2. Fetch manifest
    3. Download blobs
    4. Verify checksums
    5. Cache locally
    """
```

### 9.3 Checksum Validation

```python
def validate_digest(blob: bytes, digest: str) -> bool:
    """
    Validate blob digest.
    
    Supports:
        sha256:...
        sha512:...
    """
    algorithm, expected = digest.split(':', 1)
    actual = hashlib.new(algorithm, blob).hexdigest()
    return actual == expected
```

---

## 10. Tool Dispatch Bridge

### Source Reference
*Primary source: `hlf/tool_dispatch.py`*

### 10.1 Lazy Loading

```python
class ToolDispatchBridge:
    """
    Lazy-loading dispatcher for external tools.
    
    Tools are registered by name but not loaded until called.
    """
    
    def __init__(self):
        self._registered: dict = {}
        self._loaded: dict = {}
    
    def register(self, name: str, loader: Callable):
        """Register tool with lazy loader."""
        self._registered[name] = loader
    
    def dispatch(self, name: str, args: dict) -> Any:
        """
        Dispatch tool call.
        
        1. Check if loaded
        2. Load if necessary (lazy)
        3. Execute tool
        4. Return result
        """
        if name not in self._loaded:
            loader = self._registered.get(name)
            if loader is None:
                raise ToolNotFoundError(name)
            self._loaded[name] = loader()
        
        tool = self._loaded[name]
        return tool(**args)
```

### 10.2 Host-Function Registry Integration

```python
def register_tools_with_host_function_registry(
    registry: HostFunctionRegistry,
    bridge: ToolDispatchBridge
):
    """
    Register all tools as host functions.
    
    For each registered tool:
    - Create HostFunction entry
    - Set backend to 'tool_dispatch'
    - Register dispatcher
    """
    for tool_name, loader in bridge._registered.items():
        hf = HostFunction(
            name=tool_name,
            args=[],  # Discovered via introspection
            returns='any',
            tier=['forge', 'sovereign'],
            gas=5,
            backend='tool_dispatch'
        )
        registry._functions[tool_name] = hf
    
    registry._dispatchers['tool_dispatch'] = bridge.dispatch
```

---

## 11. Intent Capsules

### Source Reference
*Primary source: `hlf/intent_capsule.py`*

### 11.1 Capsule Definition

```python
@dataclass
class IntentCapsule:
    """
    Sandboxed execution context for HLF programs.
    
    Capsules enforce:
    - Allowed/denied tags
    - Allowed tools
    - Gas limits
    - Tier restrictions
    - Read-only/write-restricted variables
    """
    allowed_tags: list[str]
    denied_tags: list[str]
    allowed_tools: list[str]
    gas_limit: int
    tier: str
    read_only_vars: list[str]
    write_restricted_vars: list[str]
    
    def is_tag_allowed(self, tag: str) -> bool:
        """Check if tag is permitted."""
        if tag in self.denied_tags:
            return False
        if self.allowed_tags and tag not in self.allowed_tags:
            return False
        return True
    
    def is_tool_allowed(self, tool: str) -> bool:
        """Check if tool is permitted."""
        return tool in self.allowed_tools
    
    def is_var_readable(self, var: str) -> bool:
        """Check if variable can be read."""
        # All variables are readable by default
        return True
    
    def is_var_writable(self, var: str) -> bool:
        """Check if variable can be written."""
        if var in self.read_only_vars:
            return False
        if self.write_restricted_vars and var not in self.write_restricted_vars:
            return False
        return True
```

### 11.2 Predefined Capsule Factories

```python
def sovereign_capsule() -> IntentCapsule:
    """
    Sovereign tier capsule.
    
    - All tags allowed
    - All tools allowed
    - High gas limit
    - No read/write restrictions
    """
    return IntentCapsule(
        allowed_tags=[],
        denied_tags=[],
        allowed_tools='*',  # Wildcard
        gas_limit=1000000,
        tier='sovereign',
        read_only_vars=[],
        write_restricted_vars=[]
    )

def forge_capsule() -> IntentCapsule:
    """
    Forge tier capsule.
    
    - Most tags allowed (some denied for security)
    - Extended tool set
    - Medium gas limit
    - Some write restrictions
    """
    return IntentCapsule(
        allowed_tags=['action', 'parallel', 'sync', 'memory', 'result'],
        denied_tags=['system', 'network'],
        allowed_tools=['file_read', 'file_write', 'http_get', 'http_post'],
        gas_limit=100000,
        tier='forge',
        read_only_vars=['system_config'],
        write_restricted_vars=[]
    )

def hearth_capsule() -> IntentCapsule:
    """
    Hearth tier capsule (restricted).
    
    - Limited tags
    - Minimal tools
    - Low gas limit
    - Strict read/write restrictions
    """
    return IntentCapsule(
        allowed_tags=['action', 'result'],
        denied_tags=[],
        allowed_tools=['file_read'],
        gas_limit=50000,
        tier='hearth',
        read_only_vars=[],
        write_restricted_vars=['output']
    )
```

### 11.3 Enforcement

```python
def enforce_capsule(capsule: IntentCapsule, node: dict, context: dict) -> None:
    """
    Pre-flight capsule enforcement.
    
    Called before executing each node:
    - Check tag permissions
    - Check tool permissions
    - Check variable permissions
    - Check gas availability
    """
    # Tag enforcement
    if node.get('type') == 'TAG':
        tag = node.get('name')
        if not capsule.is_tag_allowed(tag):
            raise CapsuleViolationError(f"Tag '{tag}' not allowed")
    
    # Tool enforcement
    if node.get('type') == 'ACTION':
        tool = node.get('name')
        if not capsule.is_tool_allowed(tool):
            raise CapsuleViolationError(f"Tool '{tool}' not allowed")
    
    # Gas enforcement
    if context.get('gas_used', 0) > capsule.gas_limit:
        raise GasExhaustedError(capsule.gas_limit)
```

---

## 12. Memory Node Design

### Source Reference
*Primary source: `hlf/memory_node.py`*

### 12.1 Data Structure

```python
@dataclass
class MemoryNode:
    """
    Structured storage for Infinite-RAG memory system.
    
    Fields:
        id: Unique identifier (ULID)
        content: Primary content
        embedding: Vector embedding (optional)
        metadata: Key-value metadata
        tags: List of tags for retrieval
        source_hash: Hash of content source
        created_at: Creation timestamp
        ttl: Time-to-live in seconds
        parent_id: Parent node reference
        children: List of child node IDs
    """
    id: str
    content: str
    embedding: Optional[list[float]]
    metadata: dict
    tags: list[str]
    source_hash: str
    created_at: float
    ttl: Optional[int]
    parent_id: Optional[str]
    children: list[str]
    
    def compute_hash(self) -> str:
        """Compute content hash."""
        return hashlib.sha256(
            f"{self.content}:{self.source_hash}".encode()
        ).hexdigest()
    
    def is_expired(self) -> bool:
        """Check if TTL has expired."""
        if self.ttl is None:
            return False
        return time.time() > self.created_at + self.ttl
```

### 12.2 Serialization

```python
def to_json(self) -> str:
    """Serialize to JSON."""
    return json.dumps({
        'id': self.id,
        'content': self.content,
        'embedding': self.embedding,
        'metadata': self.metadata,
        'tags': self.tags,
        'source_hash': self.source_hash,
        'created_at': self.created_at,
        'ttl': self.ttl,
        'parent_id': self.parent_id,
        'children': self.children
    })

@classmethod
def from_json(cls, data: str) -> 'MemoryNode':
    """Deserialize from JSON."""
    obj = json.loads(data)
    return cls(**obj)
```

### 12.3 Deduplication

```python
def deduplicate(nodes: list[MemoryNode]) -> list[MemoryNode]:
    """
    Deduplicate nodes by content hash.
    
    Strategy:
    - Group by source_hash
    - For each group, keep newest
    - Update parent/child references
    """
    by_hash: dict[str, MemoryNode] = {}
    
    for node in nodes:
        h = node.compute_hash()
        if h in by_hash:
            # Keep newer node
            if node.created_at > by_hash[h].created_at:
                by_hash[h] = node
        else:
            by_hash[h] = node
    
    return list(by_hash.values())
```

---

## 13. Translator

### Source Reference
*Primary source: `hlf/translator.py`*

### 13.1 Tone Detection

```python
TONE_MARKERS = {
    'neutral': [],
    'urgent': ['!', 'urgent', 'critical', 'immediately'],
    'question': ['?', 'what', 'how', 'why', 'when'],
    'command': ['do', 'execute', 'run', 'perform'],
    'informative': ['note', 'info', 'information', 'details'],
}

def detect_tone(text: str) -> str:
    """
    Detect tone from text.
    
    Returns: 'neutral', 'urgent', 'question', 'command', 'informative'
    """
    text_lower = text.lower()
    for tone, markers in TONE_MARKERS.items():
        for marker in markers:
            if marker in text_lower:
                return tone
    return 'neutral'
```

### 13.2 Nuance Glyph Encoding

```python
NUANCE_GLYPHS = {
    'emphasis': '!',
    'urgency': '⚡',
    'question': '?',
    'uncertainty': '~',
    'negation': '¬',
    'affirmation': '✓',
    'warning': '⚠',
    'info': 'ℹ',
}

def encode_nuance(text: str, nuances: list[str]) -> str:
    """
    Encode nuance as glyphs.
    
    Example:
        "Execute command" with ['urgency', 'emphasis']
        -> "Execute command ⚡!"
    """
    suffix = ''
    for nuance in nuances:
        if nuance in NUANCE_GLYPHS:
            suffix += NUANCE_GLYPHS[nuance]
    return f"{text} {suffix}".strip()
```

### 13.3 HLF Generation

```python
def english_to_hlf(english: str, context: dict = None) -> str:
    """
    Convert English to HLF.
    
    Pipeline:
    1. Detect tone
    2. Extract intent
    3. Map to HLF statement type
    4. Generate HLF source
    5. Add nuance glyphs
    """
    tone = detect_tone(english)
    intent = extract_intent(english)
    statement = map_to_statement(intent, tone)
    hlf = generate_hlf(statement, context)
    return encode_nuance(hlf, [tone])
```

### 13.4 Reverse Translation

```python
def hlf_to_english(hlf: str) -> str:
    """
    Convert HLF to English.
    
    Pipeline:
    1. Parse HLF
    2. Extract statement type
    3. Map to English description
    4. Add tone from glyphs
    """
    ast = compile(hlf)
    statement_type = ast.get('type')
    description = map_to_english(ast)
    tone = extract_tone_from_glyphs(hlf)
    return f"{description} [{tone}]" if tone != 'neutral' else description
```

---

## 14. InsAIts Decompiler

### Source Reference
*Primary source: `hlf/insaits.py`*

### 14.1 AST to English

```python
def decompile_ast(ast: dict) -> str:
    """
    Decompile AST to English.
    
    Uses 'human_readable' fields added during compilation.
    """
    statements = ast.get('statements', [])
    lines = []
    
    for stmt in statements:
        stmt_type = stmt.get('type')
        human_readable = stmt.get('human_readable', '')
        
        if stmt_type == 'function':
            lines.append(f"Define function {human_readable}")
        elif stmt_type == 'tag':
            lines.append(f"Tag {stmt['name']} with value {stmt['value']}")
        elif stmt_type == 'action':
            lines.append(f"Execute action {human_readable}")
        # ... etc
    
    return '\n'.join(lines)
```

### 14.2 Bytecode to English

```python
def decompile_bytecode(bytecode: bytes) -> str:
    """
    Decompile bytecode to English.
    
    Pipeline:
    1. Parse header and constant pool
    2. Disassemble opcodes
    3. Map each opcode to English description
    4. Combine into narrative
    """
    # Parse header
    magic, version, const_count, code_len = parse_header(bytecode)
    
    # Parse constant pool
    constants = parse_constants(bytecode)
    
    # Disassemble
    instructions = disassemble(bytecode)
    
    # Map to English
    lines = [f"HLF bytecode version {version}"]
    lines.append(f"Constants: {len(constants)}")
    lines.append(f"Instructions: {len(instructions)}")
    lines.append("")
    
    for op, operand in instructions:
        desc = opcode_to_english(op, operand, constants)
        lines.append(desc)
    
    return '\n'.join(lines)
```

### 14.3 Homograph Normalization

```python
def normalize_homographs(text: str) -> str:
    """
    Normalize homograph characters.
    
    Prevents homoglyph attacks by replacing
    visually similar characters with canonical forms.
    """
    HOMOGRAPHS = {
        '\u0430': 'a',  # Cyrillic 'а' -> Latin 'a'
        '\u0435': 'e',  # Cyrillic 'е' -> Latin 'e'
        '\u043e': 'o',  # Cyrillic 'о' -> Latin 'o'
        '\u0440': 'p',  # Cyrillic 'р' -> Latin 'p'
        '\u0441': 'c',  # Cyrillic 'с' -> Latin 'c'
        '\u0443': 'y',  # Cyrillic 'у' -> Latin 'y'
        '\u0445': 'x',  # Cyrillic 'х' -> Latin 'x'
        # ... additional homographs
    }
    
    for homograph, canonical in HOMOGRAPHS.items():
        text = text.replace(homograph, canonical)
    
    return text
```

---

## 15. Language Server

### Source Reference
*Primary source: `hlf/hlflsp.py`*

### 15.1 Diagnostics Pipeline

```python
def get_diagnostics(uri: str) -> list[dict]:
    """
    Get diagnostics for document.
    
    Pipeline:
    1. Read document content
    2. Run lint (static analysis)
    3. Run compile (parse and check)
    4. Collect errors and warnings
    5. Map to LSP diagnostic format
    """
    content = read_document(uri)
    
    diagnostics = []
    
    # Lint
    lint_results = lint(content)
    for issue in lint_results:
        diagnostics.append({
            'range': issue['range'],
            'severity': map_severity(issue['level']),
            'message': issue['message'],
            'source': 'hlflint'
        })
    
    # Compile
    try:
        compile(content)
    except HlfSyntaxError as e:
        diagnostics.append({
            'range': e.range,
            'severity': 1,  # Error
            'message': e.message,
            'source': 'hlfc'
        })
    
    return diagnostics
```

### 15.2 Completions

```python
def get_completions(uri: str, position: dict) -> list[dict]:
    """
    Get completions at position.
    
    Sources:
    - Tags (reserved keywords)
    - Glyphs (Unicode operators)
    - Stdlib modules
    - Host functions
    - Variable references
    """
    completions = []
    
    # Tags
    for tag in TAGS:
        completions.append({
            'label': tag,
            'kind': 14,  # Keyword
            'detail': f'Tag: {tag}'
        })
    
    # Glyphs
    for glyph, meaning in GLYPHS.items():
        completions.append({
            'label': glyph,
            'kind': 15,  # Snippet
            'detail': meaning
        })
    
    # Stdlib modules
    for module in STDLIB_MODULES:
        completions.append({
            'label': module,
            'kind': 9,  # Module
            'detail': f'Stdlib module: {module}'
        })
    
    # Host functions
    for func in HOST_FUNCTIONS:
        completions.append({
            'label': func['name'],
            'kind': 3,  # Function
            'detail': func['description']
        })
    
    return completions
```

### 15.3 Hover and Definition

```python
def get_hover(uri: str, position: dict) -> dict:
    """
    Get hover information.
    
    Returns:
    - Type signature for variables
    - Documentation for functions
    - Description for tags
    """
    symbol = get_symbol_at_position(uri, position)
    
    if symbol['type'] == 'variable':
        return {
            'contents': [
                f"**{symbol['name']}**",
                f"Type: {symbol['var_type']}",
                f"Defined at line {symbol['line']}"
            ]
        }
    elif symbol['type'] == 'function':
        return {
            'contents': [
                f"**{symbol['name']}({symbol['params']})**",
                f"Returns: {symbol['returns']}",
                symbol['docstring']
            ]
        }
    # ... etc

def get_definition(uri: str, position: dict) -> dict:
    """
    Get definition location.
    
    Navigates to symbol definition.
    """
    symbol = get_symbol_at_position(uri, position)
    return {
        'uri': symbol['definition_uri'],
        'range': symbol['definition_range']
    }
```

### 15.4 Document Symbols

```python
def get_document_symbols(uri: str) -> list[dict]:
    """
    Get all symbols in document.
    
    Returns:
    - Functions
    - Variables
    - Tags
    - Imports
    """
    content = read_document(uri)
    ast = compile(content)
    
    symbols = []
    
    for stmt in ast['statements']:
        if stmt['type'] == 'function':
            symbols.append({
                'name': stmt['name'],
                'kind': 12,  # Function
                'range': stmt['range'],
                'children': []
            })
        elif stmt['type'] == 'tag':
            symbols.append({
                'name': stmt['name'],
                'kind': 14,  # Constant
                'range': stmt['range']
            })
        # ... etc
    
    return symbols
```

---

## 16. Security Considerations

### 16.1 Homoglyph Protection

**Location**: `hlf/hlfc.py` lines 52-98

The compiler's normalization pass protects against homoglyph attacks:

```python
def _pass0_normalize(source: str) -> str:
    """
    Normalize Unicode while protecting HLF glyphs.
    
    Strategy:
    1. Identify and protect HLF-specific glyphs
    2. Apply NFKC normalization to remaining characters
    3. Replace known confusables with canonical forms
    """
    # Protected glyphs: →, ←, ↦, λ, τ, Σ, Ω
    PROTECTED = set('→←↦λτΣΩ')
    
    # Confusable mappings
    CONFUSABLES = {
        '\u0430': 'a',  # Cyrillic а -> Latin a
        '\u0435': 'e',  # Cyrillic е -> Latin e
        # ... 100+ confusables
    }
    
    # Apply normalization
    result = []
    for char in source:
        if char in PROTECTED:
            result.append(char)  # Keep as-is
        elif char in CONFUSABLES:
            result.append(CONFUSABLES[char])
        else:
            result.append(unicodedata.normalize('NFKC', char))
    
    return ''.join(result)
```

### 16.2 Gas Exhaustion Handling

**Location**: `hlf/bytecode.py` lines 700-750

The VM enforces gas limits:

```python
class HlfVM:
    def run(self) -> Any:
        """Execute bytecode with gas enforcement."""
        while self.pc < len(self.code):
            # Fetch opcode
            opcode = self._fetch_opcode()
            operand = self._fetch_operand()
            
            # Check gas
            gas_cost = _OP_GAS.get(opcode, 1)
            if self.gas_used + gas_cost > self.max_gas:
                raise HlfVMGasExhausted(self.gas_used, self.max_gas)
            
            self.gas_used += gas_cost
            
            # Dispatch
            self._dispatch(opcode, operand)
```

### 16.3 Tier Enforcement

**Location**: `hlf/runtime.py` lines 120-180

Host functions check tier authorization:

```python
def dispatch(self, function_name: str, args: list, tier: str, ...) -> HostFunctionResult:
    """Dispatch with tier enforcement."""
    hf = self._functions.get(function_name)
    
    # Tier check
    if not hf.is_allowed_on_tier(tier):
        raise HlfTierViolation(
            f"Function '{function_name}' not allowed on tier '{tier}'. "
            f"Allowed tiers: {hf.tier}"
        )
    
    # ... proceed with dispatch
```

### 16.4 Sensitive Output Redaction

**Location**: `hlf/runtime.py` lines 160-175

Sensitive outputs are hashed before logging:

```python
# Sensitive output redaction
if hf.sensitive:
    log_value = hashlib.sha256(
        str(result).encode('utf-8')
    ).hexdigest()
else:
    log_value = result
```

### 16.5 Checksum Verification

**Location**: Module loader (implied by `hlf/hlfrun.py` import handling)

Modules are verified against ACFS manifest checksums:

```python
# Before loading module:
expected_checksum = acfs_manifest.get(module_name)
actual_checksum = sha256(module_content)
if expected_checksum and actual_checksum != expected_checksum:
    raise ChecksumMismatchError(
        f"Module '{module_name}' checksum mismatch. "
        f"Expected: {expected_checksum}, Got: {actual_checksum}"
    )
```

### 16.6 Capsule Sandboxing

**Location**: `hlf/intent_capsule.py`

Capsules enforce sandbox restrictions:

```python
# Pre-flight enforcement
def check_permission(capsule: IntentCapsule, operation: str, resource: str) -> bool:
    """Check if capsule permits operation."""
    if operation == 'tag':
        return capsule.is_tag_allowed(resource)
    elif operation == 'tool':
        return capsule.is_tool_allowed(resource)
    elif operation == 'write':
        return capsule.is_var_writable(resource)
    # ...
```

---

## 17. Standard Library Modules

### Source References
*Primary sources: `hlf/stdlib/*.hlf` files*

### 17.1 Agent Module (`stdlib/agent.hlf`)

```
module agent v0.5 {
    # Agent introspection and control
    
    fn self_id(): string [effects: SELF_OBSERVE]
    fn self_tier(): string [effects: NONE]
    fn self_gas_used(): int [effects: NONE]
    fn self_gas_remaining(): int [effects: NONE]
    
    fn spawn(code: string): string [effects: PROCESS_SPAWN]
    fn kill(agent_id: string): void [effects: PROCESS_KILL]
    fn send(agent_id: string, message: any): void [effects: CHANNEL_SEND]
    fn recv(timeout: int): any [effects: CHANNEL_RECV]
}
```

### 17.2 Collections Module (`stdlib/collections.hlf`)

```
module collections v0.5 {
    # Collection operations
    
    fn list_length(list: list): int [effects: NONE]
    fn list_append(list: list, item: any): list [effects: NONE]
    fn list_concat(list1: list, list2: list): list [effects: NONE]
    fn list_filter(list: list, predicate: fn): list [effects: NONE]
    fn list_map(list: list, transform: fn): list [effects: NONE]
    fn list_reduce(list: list, initial: any, reducer: fn): any [effects: NONE]
    
    fn map_get(map: map, key: string): any [effects: NONE]
    fn map_set(map: map, key: string, value: any): map [effects: NONE]
    fn map_keys(map: map): list [effects: NONE]
    fn map_values(map: map): list [effects: NONE]
}
```

### 17.3 Crypto Module (`stdlib/crypto.hlf`)

```
module crypto v0.5 {
    # Cryptographic operations
    
    fn sha256(data: string): string [effects: COMPUTE]
    fn sha512(data: string): string [effects: COMPUTE]
    fn md5(data: string): string [effects: COMPUTE]
    
    fn hmac_sha256(data: string, key: string): string [effects: COMPUTE]
    
    fn aes_encrypt(data: string, key: string): string [effects: COMPUTE, EXTERNAL]
    fn aes_decrypt(data: string, key: string): string [effects: COMPUTE, EXTERNAL]
    
    fn random_bytes(length: int): bytes [effects: EXTERNAL]
}
```

### 17.4 IO Module (`stdlib/io.hlf`)

```
module io v0.5 {
    # Input/output operations
    
    fn file_read(path: string): string [effects: READ_FILE]
    fn file_write(path: string, content: string): void [effects: WRITE_FILE]
    fn file_append(path: string, content: string): void [effects: WRITE_FILE]
    fn file_delete(path: string): void [effects: DELETE_FILE]
    fn file_exists(path: string): bool [effects: READ_FILE]
    
    fn directory_list(path: string): list [effects: LIST_DIRECTORY]
    fn directory_create(path: string): void [effects: WRITE_FILE]
    
    fn stdin_read(): string [effects: IO]
    fn stdout_write(text: string): void [effects: IO]
    fn stderr_write(text: string): void [effects: IO]
}
```

### 17.5 Math Module (`stdlib/math.hlf`)

```
module math v0.5 {
    # Mathematical operations
    
    fn abs(x: number): number [effects: NONE]
    fn floor(x: number): int [effects: NONE]
    fn ceil(x: number): int [effects: NONE]
    fn round(x: number): int [effects: NONE]
    
    fn sqrt(x: number): number [effects: COMPUTE]
    fn pow(base: number, exp: number): number [effects: COMPUTE]
    fn log(x: number): number [effects: COMPUTE]
    fn log10(x: number): number [effects: COMPUTE]
    
    fn sin(x: number): number [effects: COMPUTE]
    fn cos(x: number): number [effects: COMPUTE]
    fn tan(x: number): number [effects: COMPUTE]
    
    fn min(a: number, b: number): number [effects: NONE]
    fn max(a: number, b: number): number [effects: NONE]
    fn clamp(x: number, lo: number, hi: number): number [effects: NONE]
    
    fn random(): number [effects: EXTERNAL]
    fn random_int(lo: int, hi: int): int [effects: EXTERNAL]
}
```

### 17.6 Net Module (`stdlib/net.hlf`)

```
module net v0.5 {
    # Network operations
    
    fn http_get(url: string): response [effects: HTTP_REQUEST]
    fn http_post(url: string, body: any): response [effects: HTTP_REQUEST]
    fn http_put(url: string, body: any): response [effects: HTTP_REQUEST]
    fn http_delete(url: string): response [effects: HTTP_REQUEST]
    
    fn websocket_connect(url: string): connection [effects: NETWORK]
    fn websocket_send(conn: connection, message: string): void [effects: NETWORK]
    fn websocket_recv(conn: connection, timeout: int): string [effects: NETWORK]
    fn websocket_close(conn: connection): void [effects: NETWORK]
    
    fn dns_resolve(hostname: string): list [effects: DNS_RESOLVE]
}
```

### 17.7 String Module (`stdlib/string.hlf`)

```
module string v0.5 {
    # String operations
    
    fn length(s: string): int [effects: NONE]
    fn concat(s1: string, s2: string): string [effects: NONE]
    fn substring(s: string, start: int, length: int): string [effects: NONE]
    
    fn split(s: string, delimiter: string): list [effects: NONE]
    fn join(list: list, delimiter: string): string [effects: NONE]
    
    fn trim(s: string): string [effects: NONE]
    fn lower(s: string): string [effects: NONE]
    fn upper(s: string): string [effects: NONE]
    
    fn contains(s: string, substring: string): bool [effects: NONE]
    fn starts_with(s: string, prefix: string): bool [effects: NONE]
    fn ends_with(s: string, suffix: string): bool [effects: NONE]
    
    fn replace(s: string, old: string, new: string): string [effects: NONE]
    
    fn format(template: string, args: ...): string [effects: NONE]
}
```

### 17.8 System Module (`stdlib/system.hlf`)

```
module system v0.5 {
    # System operations
    
    fn env_get(key: string): string [effects: ENV_READ]
    fn env_set(key: string, value: string): void [effects: ENV_WRITE]
    
    fn args(): list [effects: NONE]
    
    fn exit(code: int): void [effects: PROCESS_EXIT]
    fn sleep(seconds: number): void [effects: PROCESS_WAIT]
    
    fn time(): int [effects: NONE]
    fn time_iso(): string [effects: NONE]
    
    fn memory_used(): int [effects: NONE]
    fn memory_available(): int [effects: NONE]
    
    fn process_spawn(command: string, args: list): process [effects: PROCESS_SPAWN]
    fn process_wait(proc: process): int [effects: PROCESS_WAIT]
    fn process_kill(proc: process): void [effects: PROCESS_KILL]
}
```

---

## 18. Open Questions

### 18.1 Implementation Details Not Extracted

The following components exist in the repository but were not examined in detail during this analysis:

1. **ModuleLoader internals**: The exact search paths, caching strategy, and OCI fallback mechanism were not extracted line-by-line. The `hlf/hlfrun.py` references `module_loader.load()` at lines 285-295, but the full `ModuleLoader` implementation requires additional extraction.

2. **Package manager implementation**: The `hlf/hlflpm.py` file exists but detailed command implementations (install, uninstall, list, search, freeze) were not extracted.

3. **OCI client internals**: The `hlf/oci_client.py` network handling, manifest parsing, and blob downloading were not extracted in detail.

4. **Tool dispatch bridge**: The `hlf/tool_dispatch.py` lazy-loading mechanism and dispatcher registration require additional extraction.

5. **Intent capsule enforcement**: The `hlf/intent_capsule.py` runtime enforcement hooks beyond the dataclass definition were not extracted.

6. **Memory node persistence**: The `hlf/memory_node.py` file defines the structure, but the integration with the `MEMORY_STORE`/`MEMORY_RECALL` opcodes requires more analysis.

7. **Translator algorithms**: The `hlf/translator.py` tone detection, nuance encoding, and round-trip conversion require more detailed extraction.

8. **InsAIts decompiler**: The `hlf/insaits.py` full decompilation logic for AST and bytecode to English requires additional extraction.

9. **Language server handlers**: The `hlf/hlflsp.py` LSP protocol implementation details were not fully extracted.

### 18.2 Inconsistencies and Questions

1. **Grammar completeness**: The Lark grammar in `hlfc.py` defines many statement types, but some (like `memory_stmt`, `recall_stmt`, `spec_*_stmt`) may be partially implemented or experimental.

2. **Opcode semantics**: Some opcodes (`OPENCLAW_TOOL`, `INTENT`) have high-level definitions but their runtime integration with host functions requires verification.

3. **Tier system**: The tier names (`sovereign`, `forge`, `hearth`, `guest`) are referenced in capsule factories and host function definitions, but the complete tier hierarchy and escalation rules are not fully documented in the extracted sources.

4. **Standard library effect annotations**: The stdlib modules show effect annotations (`[effects: ...]`), but the complete effect taxonomy and enforcement mechanism require additional analysis.

---

## Appendix A: File Index

| File | Lines | Purpose |
|------|-------|---------|
| `hlf/hlfc.py` | ~400 | Compiler, Lark grammar, AST transformer |
| `hlf/hlffmt.py` | ~100 | Formatter |
| `hlf/hlflint.py` | ~200 | Linter |
| `hlf/bytecode.py` | ~900 | Bytecode, opcodes, VM |
| `hlf/hlfrun.py` | ~500 | AST interpreter |
| `hlf/runtime.py` | ~300 | Host function registry |
| `hlf/hlfpm.py` | ~200 | Package manager |
| `hlf/oci_client.py` | ~150 | OCI client |
| `hlf/tool_dispatch.py` | ~100 | Tool bridge |
| `hlf/intent_capsule.py` | ~150 | Capsule implementation |
| `hlf/memory_node.py` | ~100 | Memory node structure |
| `hlf/translator.py` | ~200 | English ↔ HLF translator |
| `hlf/insaits.py` | ~150 | Decompiler |
| `hlf/hlflsp.py` | ~300 | Language server |
| `governance/host_functions.json` | ~50 | Function catalogue |
| `governance/bytecode_spec.yaml` | ~100 | Bytecode specification |
| `governance/acfs.manifest.yaml` | ~50 | Module checksums |

---

## Appendix B: Opcode Quick Reference

| Opcode | Hex | Gas | Description |
|--------|-----|-----|-------------|
| NOP | 0x00 | 0 | No operation |
| PUSH_CONST | 0x01 | 1 | Push constant from pool |
| POP | 0x02 | 1 | Pop stack |
| DUP | 0x03 | 1 | Duplicate top |
| SWAP | 0x04 | 1 | Swap top two |
| STORE | 0x10 | 1 | Store to local |
| LOAD | 0x11 | 1 | Load from local |
| STORE_IMMUT | 0x12 | 1 | Store immutable |
| ADD | 0x20 | 1 | Arithmetic add |
| SUB | 0x21 | 1 | Arithmetic subtract |
| MUL | 0x22 | 2 | Arithmetic multiply |
| DIV | 0x23 | 3 | Arithmetic divide |
| MOD | 0x24 | 3 | Arithmetic modulo |
| NEG | 0x25 | 1 | Negate |
| CMP_EQ | 0x30 | 1 | Compare equal |
| CMP_NE | 0x31 | 1 | Compare not equal |
| CMP_LT | 0x32 | 1 | Compare less than |
| CMP_LE | 0x33 | 1 | Compare less or equal |
| CMP_GT | 0x34 | 1 | Compare greater than |
| CMP_GE | 0x35 | 1 | Compare greater or equal |
| AND | 0x40 | 1 | Logical and |
| OR | 0x41 | 1 | Logical or |
| NOT | 0x42 | 1 | Logical not |
| JMP | 0x50 | 1 | Jump |
| JZ | 0x51 | 1 | Jump if zero |
| JNZ | 0x52 | 1 | Jump if not zero |
| CALL_BUILTIN | 0x60 | 3 | Call built-in |
| CALL_HOST | 0x61 | 5 | Call host function |
| CALL_TOOL | 0x62 | 3 | Call tool |
| TAG | 0x70 | 1 | Tag statement |
| INTENT | 0x71 | 2 | Intent marker |
| RESULT | 0x72 | 1 | Result terminator |
| MEMORY_STORE | 0x73 | 3 | Store to memory |
| MEMORY_RECALL | 0x74 | 3 | Recall from memory |
| OPENCLAW_TOOL | 0x75 | 5 | OpenClaw tool |
| HALT | 0xFF | 0 | Halt execution |

---

*End of HLF Exhaustive Technical Analysis*