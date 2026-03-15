#!/usr/bin/env python3
"""
HLF CLI
Command-line interface for the Hierarchical Language Framework
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from hlf.parser import parse
from hlf.compiler.full_compiler import Compiler
from hlf.vm.interpreter import VM, run_bytecode
from hlf.vm.bytecode import BytecodeModule

def cmd_compile(args):
    """Compile HLF source to bytecode"""
    # Read source
    with open(args.input, 'r') as f:
        source = f.read()
    
    # Parse
    print(f"Parsing {args.input}...")
    ast = parse(source)
    
    # Compile
    print("Compiling...")
    compiler = Compiler()
    module = compiler.compile(ast, optimization_level=args.optimize)
    
    # Output
    if args.output:
        with open(args.output, 'wb') as f:
            f.write(module.serialize())
        print(f"Compiled to {args.output}")
    else:
        # Print disassembly
        print("\n" + module.disassemble())
    
    return 0

def cmd_run(args):
    """Run HLF source directly"""
    # Read source
    with open(args.input, 'r') as f:
        source = f.read()
    
    # Parse
    ast = parse(source)
    
    # Compile
    compiler = Compiler()
    module = compiler.compile(ast)
    
    # Execute
    print(f"Running {args.input}...")
    
    vm = VM(module, gas_limit=args.gas_limit)
    
    # Register host functions
    def print_fn(*args):
        print(" ".join(str(a) for a in args))
        return None
    
    def add_fn(a, b):
        return a.as_int() + b.as_int()
    
    vm.register_host_function(0, print_fn)
    vm.register_host_function(1, add_fn)
    
    result = vm.execute()
    
    print(f"Result: {result}")
    print(f"Gas used: {vm.total_gas}")
    
    return 0

def cmd_disassemble(args):
    """Disassemble bytecode file"""
    with open(args.input, 'rb') as f:
        data = f.read()
    
    # TODO: Implement bytecode loading
    print("Disassembly not yet implemented")
    return 1

def cmd_repl(args):
    """Interactive REPL"""
    print("="*60)
    print("HLF Interactive REPL v0.5.0")
    print("Type 'exit' or Ctrl+D to quit")
    print("="*60)
    print()
    
    # Create module
    module = BytecodeModule("repl")
    
    while True:
        try:
            line = input("hlf> ")
        except EOFError:
            print()
            break
        
        if line.strip() == 'exit':
            break
        
        if not line.strip():
            continue
        
        try:
            # Parse
            ast = parse(line)
            
            # Compile
            compiler = Compiler()
            mod = compiler.compile(ast)
            
            # Execute
            vm = VM(mod)
            result = vm.execute()
            
            print(f"=> {result}")
            print(f"   [gas: {vm.total_gas}]")
            
        except Exception as e:
            print(f"Error: {e}")
    
    print("Goodbye!")
    return 0

def cmd_test(args):
    """Run test suite"""
    import subprocess
    
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "hlf/tests/", "-v"],
        cwd=Path(__file__).parent.parent.parent
    )
    
    return result.returncode

def cmd_verify(args):
    """Verify HLF installation"""
    print("="*60)
    print("HLF Installation Verification")
    print("="*60)
    print()
    
    checks = []
    
    # Check Python version
    import platform
    py_version = platform.python_version()
    checks.append(("Python version", py_version, True))
    
    # Check imports
    try:
        from hlf.parser import parse
        checks.append(("Parser module", "OK", True))
    except Exception as e:
        checks.append(("Parser module", str(e), False))
    
    try:
        from hlf.compiler.full_compiler import Compiler
        checks.append(("Compiler module", "OK", True))
    except Exception as e:
        checks.append(("Compiler module", str(e), False))
    
    try:
        from hlf.vm.interpreter import VM
        checks.append(("VM module", "OK", True))
    except Exception as e:
        checks.append(("VM module", str(e), False))
    
    # Run basic test
    try:
        source = "def main() { return 42 }"
        ast = parse(source)
        compiler = Compiler()
        module = compiler.compile(ast)
        vm = VM(module)
        result = vm.execute()
        
        if result.as_int() == 42:
            checks.append(("End-to-end test", "PASS", True))
        else:
            checks.append(("End-to-end test", f"Expected 42, got {result}", False))
    except Exception as e:
        checks.append(("End-to-end test", str(e), False))
    
    # Print results
    for name, status, ok in checks:
        symbol = "✓" if ok else "✗"
        color = "\033[92m" if ok else "\033[91m"
        reset = "\033[0m"
        print(f"{color}{symbol}{reset} {name}: {status}")
    
    print()
    
    passed = sum(1 for _, _, ok in checks if ok)
    total = len(checks)
    
    if passed == total:
        print(f"All {total} checks passed!")
        return 0
    else:
        print(f"{passed}/{total} checks passed")
        return 1

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        prog='hlf',
        description='Hierarchical Language Framework'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Compile
    compile_parser = subparsers.add_parser('compile', help='Compile HLF source')
    compile_parser.add_argument('input', help='Input HLF file')
    compile_parser.add_argument('-o', '--output', help='Output bytecode file')
    compile_parser.add_argument('-O', '--optimize', type=int, default=1, 
                               help='Optimization level (0-3)')
    
    # Run
    run_parser = subparsers.add_parser('run', help='Run HLF source')
    run_parser.add_argument('input', help='Input HLF file')
    run_parser.add_argument('--gas-limit', type=int, help='Gas limit')
    
    # Disassemble
    dis_parser = subparsers.add_parser('dis', help='Disassemble bytecode')
    dis_parser.add_argument('input', help='Input bytecode file')
    
    # REPL
    repl_parser = subparsers.add_parser('repl', help='Interactive REPL')
    
    # Test
    test_parser = subparsers.add_parser('test', help='Run tests')
    
    # Verify
    verify_parser = subparsers.add_parser('verify', help='Verify installation')
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    commands = {
        'compile': cmd_compile,
        'run': cmd_run,
        'dis': cmd_disassemble,
        'repl': cmd_repl,
        'test': cmd_test,
        'verify': cmd_verify,
    }
    
    return commands[args.command](args)

if __name__ == '__main__':
    sys.exit(main())
