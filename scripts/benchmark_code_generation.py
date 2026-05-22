#!/usr/bin/env python3
"""HLF Code Benchmark: Sieve of Eratosthenes — Solo vs RecursiveMAS.

Tests whether latent recursion improves code generation quality for a 
classic algorithm implementation. The sieve requires:
1. Algorithm selection (Eratosthenes specifically, not trial division)
2. Correct initialization (boolean array)
3. Correct loop bounds (p*p <= n, not p <= sqrt(n))
4. Edge cases (n < 2, n = 2)
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

PROMPT_SIEVE = (
    "Write a Python function `sieve_of_eratosthenes(n: int) -> list[int]` "
    "that returns all prime numbers up to n using the Sieve of Eratosthenes algorithm. "
    "Include proper edge case handling (n < 2). "
    "Return only the function code, no explanation."
)

PROMPT_BST = (
    "Write a Python class `BinarySearchTree` with methods `insert(value)`, "
    "`search(value) -> bool`, and `inorder_traversal() -> list`. "
    "Handle duplicate insertions gracefully (no duplicate nodes). "
    "Return only the class code, no explanation."
)

PROMPT_FIB = (
    "Write a Python function `fibonacci_memoized(n: int) -> int` "
    "that computes the nth Fibonacci number using memoization. "
    "Handle n=0 (return 0) and n=1 (return 1). Use O(n) time and O(n) space. "
    "Return only the function code, no explanation."
)


def extract_code(text: str) -> str:
    """Extract Python code from model output."""
    if "```python" in text:
        parts = text.split("```python", 1)
        if len(parts) > 1:
            code = parts[1].split("```", 1)[0]
            return code.strip()
    if "```" in text:
        parts = text.split("```", 1)
        if len(parts) > 1:
            code = parts[1].split("```", 1)[0]
            return code.strip()
    return text.strip()


def test_execution(code: str, test_name: str) -> dict:
    """Try to compile and run the generated code with test cases."""
    result = {"compiles": False, "test_results": {}, "errors": []}

    if not code or len(code) < 10:
        result["errors"].append("empty_or_too_short")
        return result

    # Test compile
    try:
        compile(code, f"<{test_name}>", "exec")
        result["compiles"] = True
    except SyntaxError as e:
        result["errors"].append(f"syntax_error: {e}")
        return result
    
    # Test execution
    namespace = {}
    try:
        exec(code, namespace)
    except Exception as e:
        result["errors"].append(f"exec_error: {e}")
        return result

    # Sieve-specific tests
    if test_name == "sieve":
        fn = namespace.get("sieve_of_eratosthenes")
        if not fn:
            result["errors"].append("function_not_found")
            return result
        
        test_cases = [
            ("n=0", 0, []),
            ("n=1", 1, []),
            ("n=2", 2, [2]),
            ("n=10", 10, [2, 3, 5, 7]),
            ("n=20", 20, [2, 3, 5, 7, 11, 13, 17, 19]),
            ("n=30", 30, [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]),
        ]
        for name, n, expected in test_cases:
            try:
                output = fn(n)
                if output == expected:
                    result["test_results"][name] = "pass"
                else:
                    result["test_results"][name] = f"fail: got {output}"
            except Exception as e:
                result["test_results"][name] = f"error: {e}"

    # BST-specific tests
    elif test_name == "bst":
        BST = namespace.get("BinarySearchTree")
        if not BST:
            result["errors"].append("class_not_found")
            return result
        
        tests = []
        try:
            tree = BST()
            tree.insert(5)
            tree.insert(3)
            tree.insert(7)
            tree.insert(2)
            tree.insert(4)
            tree.insert(3)  # duplicate — should not crash
            
            tests.append(("search_5", tree.search(5), True))
            tests.append(("search_3", tree.search(3), True))
            tests.append(("search_10", tree.search(10), False))
            
            inorder = tree.inorder_traversal()
            tests.append(("inorder", inorder, [2, 3, 4, 5, 7]))
        except Exception as e:
            result["errors"].append(f"bst_error: {e}")
            return result
        
        for name, got, expected in tests:
            if got == expected:
                result["test_results"][name] = "pass"
            else:
                result["test_results"][name] = f"fail: got {got}, expected {expected}"

    # Fibonacci-specific tests
    elif test_name == "fib":
        fn = namespace.get("fibonacci_memoized")
        if not fn:
            result["errors"].append("function_not_found")
            return result
        
        test_cases = [
            ("n=0", 0, 0),
            ("n=1", 1, 1),
            ("n=2", 2, 1),
            ("n=5", 5, 5),
            ("n=10", 10, 55),
            ("n=20", 20, 6765),
        ]
        for name, n, expected in test_cases:
            try:
                output = fn(n)
                if output == expected:
                    result["test_results"][name] = "pass"
                else:
                    result["test_results"][name] = f"fail: got {output}"
            except Exception as e:
                result["test_results"][name] = f"error: {e}"

    result["all_pass"] = all(
        v == "pass" for v in result["test_results"].values()
    )
    return result


def run_solo_code(prompt: str, test_name: str) -> dict:
    """Solo solver code generation."""
    print(f"\n  [Solo] Running {test_name}...")
    try:
        from hlf_mcp.hlf.latent_model_interface import (
            LatentRecursiveSession, RecursiveSessionConfig,
        )
        from hlf_mcp.hlf.model_orchestrator import _resolve_checkpoint_base

        cache_root = str(Path.home() / ".cache" / "huggingface" / "recursivemas")
        solver_path = _resolve_checkpoint_base(
            cache_root, "Sequential-Light-Solver-Qwen2.5-Math-1.5B",
            fallback_hf_id="RecursiveMAS/Sequential-Light-Solver-Qwen2.5-Math-1.5B"
        )

        config = RecursiveSessionConfig(
            agent_models={"solver": str(solver_path)},
            recursion_rounds=1,
            adapter_task="math",
        )
        session = LatentRecursiveSession(config)
        session.load_all()
        
        t0 = time.time()
        result = session.recursive_infer(prompt)
        elapsed = time.time() - t0
        
        output = result.output_text if hasattr(result, 'output_text') else str(result)
        code = extract_code(output)
        session.unload()
        
        import torch, gc
        torch.cuda.empty_cache()
        torch.cuda.synchronize()
        gc.collect()
        
        return {
            "path": "solo",
            "elapsed_s": round(elapsed, 2),
            "raw_output": output[:300],
            "extracted_code": code[:500],
            "code_len": len(code),
        }
    except Exception as e:
        return {"path": "solo", "error": str(e)}


def run_recursive_code(prompt: str, test_name: str) -> dict:
    """RecursiveMAS governed code generation."""
    print(f"  [RecursiveMAS] Running {test_name}...")
    try:
        from hlf_mcp.hlf.latent_capsule import governed_latent_infer
        
        t0 = time.time()
        result = governed_latent_infer(prompt, agent_id=f"code-{test_name}", max_rounds=2)
        elapsed = time.time() - t0
        
        result_dict = result if isinstance(result, dict) else result.to_dict()
        output = result_dict.get("final_text", "")
        code = extract_code(output)
        
        return {
            "path": "recursive_mas",
            "elapsed_s": round(elapsed, 2),
            "raw_output": output[:300],
            "extracted_code": code[:500],
            "code_len": len(code),
            "rounds": result_dict.get("rounds_completed", 0),
            "gas": result_dict.get("total_gas", 0),
            "capsule_id": result_dict.get("capsule_id", "N/A"),
            "status": result_dict.get("status", "unknown"),
        }
    except Exception as e:
        return {"path": "recursive_mas", "error": str(e)}


def clear_gpu():
    try:
        import torch, gc
        torch.cuda.synchronize()
        gc.collect()
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def main():
    tests = [
        ("sieve", PROMPT_SIEVE),
        ("bst", PROMPT_BST),
        ("fib", PROMPT_FIB),
    ]

    print("=" * 70)
    print("HLF Code Generation Benchmark — Solo vs RecursiveMAS")
    print("=" * 70)

    all_results = {}

    for test_name, prompt in tests:
        print(f"\n{'=' * 70}")
        print(f"TEST: {test_name}")
        print(f"{'=' * 70}")
        print(f"  Prompt: {prompt[:100]}...")

        clear_gpu()
        solo = run_solo_code(prompt, test_name)
        clear_gpu()
        rec = run_recursive_code(prompt, test_name)

        # Test each output
        solo_code = solo.get("extracted_code", "")
        rec_code = rec.get("extracted_code", "")
        
        solo_test = test_execution(solo_code, test_name) if solo_code else {"errors": ["no_code"]}
        rec_test = test_execution(rec_code, test_name) if rec_code else {"errors": ["no_code"]}

        solo["test"] = solo_test
        rec["test"] = rec_test

        # Display results
        print(f"\n  {'='*50}")
        print(f"  RESULTS — {test_name}")
        print(f"  {'='*50}")
        
        for label, result in [("Solo Solver", solo), ("RecursiveMAS", rec)]:
            if "error" in result:
                print(f"\n  {label}: ERROR — {result['error']}")
                continue
            
            test = result.get("test", {})
            compiles = "✅" if test.get("compiles") else "❌"
            all_pass = "✅" if test.get("all_pass") else "❌"
            
            print(f"\n  {label}:")
            print(f"    Time: {result.get('elapsed_s')}s")
            print(f"    Code length: {result.get('code_len')} chars")
            print(f"    Compiles: {compiles}")
            print(f"    All tests pass: {all_pass}")
            
            if test.get("test_results"):
                for tc, status in test["test_results"].items():
                    icon = "✅" if status == "pass" else "❌"
                    print(f"      {icon} {tc}: {status}")
            
            if test.get("errors"):
                for err in test["errors"]:
                    print(f"      ⚠️ {err}")
            
            if result.get("rounds"):
                print(f"    Rounds: {result['rounds']} | Gas: {result.get('gas')} | Capsule: {result.get('capsule_id')}")
        
        all_results[test_name] = {"solo": solo, "recursive_mas": rec}

    # Summary table
    print(f"\n{'=' * 70}")
    print("FINAL SUMMARY")
    print(f"{'=' * 70}")
    print(f"\n{'Test':<15} {'Solo Compile':<15} {'Solo Pass':<15} {'RecMAS Compile':<15} {'RecMAS Pass':<15}")
    print("-" * 75)
    
    for test_name in all_results:
        solo = all_results[test_name]["solo"]
        rec = all_results[test_name]["recursive_mas"]
        
        s_compile = "✅" if solo.get("test", {}).get("compiles") else "❌"
        s_pass = "✅" if solo.get("test", {}).get("all_pass") else "❌"
        r_compile = "✅" if rec.get("test", {}).get("compiles") else "❌"
        r_pass = "✅" if rec.get("test", {}).get("all_pass") else "❌"
        
        if "error" in solo:
            s_compile = s_pass = "ERR"
        if "error" in rec:
            r_compile = r_pass = "ERR"
        
        print(f"{test_name:<15} {s_compile:<15} {s_pass:<15} {r_compile:<15} {r_pass:<15}")

    # Save
    out_path = REPO_ROOT / "benchmark_code_results.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\n  Results saved to: {out_path}")
    print("\n✅ Code benchmark complete.")


if __name__ == "__main__":
    main()
