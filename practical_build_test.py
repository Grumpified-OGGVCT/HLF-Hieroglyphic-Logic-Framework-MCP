"""MicroSquad Practical Build Benchmark - Ollama API direct.
Calls Ollama (cloud or local) to generate code, executes it, verifies correct output.
Pass/fail is objective: does the code run and produce correct output?

RecursiveMAS citation: Yang et al., 2026, arXiv:2604.25917
"""

import json, time, sys, os, subprocess, requests

OLLAMA = "http://localhost:11434"
MODEL = sys.argv[1] if len(sys.argv) > 1 else "deepseek-v4-flash:cloud"
OUTDIR = r"C:\Users\gerry\generic_workspace\HLF_MCP\_microsquad_builds"

BUILD_TASKS = {
    "Level 1 - Single Function": [
        {
            "name": "fizzbuzz",
            "prompt": "Write a complete, runnable Python function fizzbuzz(n) that returns a list of strings: numbers 1 to n, multiples of 3 -> \"Fizz\", multiples of 5 -> \"Buzz\", multiples of both -> \"FizzBuzz\". Include `if __name__ == \"__main__\"` block that prints result for n=30. Output ONLY valid Python code, no markdown, no explanations.",
            "verify": lambda code: run_and_check(code, "fizzbuzz", 30, lambda out: "FizzBuzz" in out and "Fizz" in out and "Buzz" in out and "1" in out),
        },
        {
            "name": "binary_search",
            "prompt": "Write a complete, runnable Python function binary_search(arr, target) that returns the index of target in a sorted list, or -1 if not found. Use iterative binary search. Include `if __name__ == \"__main__\"` block with test cases: search for 7 in [1,3,5,7,9,11] (should return 3), search for 4 (should return -1). Output ONLY valid Python code, no markdown.",
            "verify": lambda code: run_and_check(code, "binary_search", None, lambda out: "3" in out and "-1" in out),
        },
    ],
    "Level 2 - Multi-Function Module": [
        {
            "name": "calculator",
            "prompt": "Write a complete Python calculator module. Functions: add(a,b), subtract(a,b), multiply(a,b), divide(a,b) with ZeroDivisionError handling. Include `if __name__ == \"__main__\"` block that runs: add(10,5), subtract(10,5), multiply(10,5), divide(10,5), divide(10,0). Output ONLY valid Python code.",
            "verify": lambda code: run_and_check(code, "calculator", None, lambda out: "15" in out and "5" in out and "50" in out and "2.0" in out and ("error" in out.lower() or "cannot" in out.lower() or "division by zero" in out.lower())),
        },
        {
            "name": "todo_cli",
            "prompt": "Write a complete Python CLI todo list manager. Functions: add_task(tasks, task_name), remove_task(tasks, index), list_tasks(tasks). Store tasks as list of dicts with \"name\" and \"done\" keys. Include `if __name__ == \"__main__\"` block demonstrating: add 3 tasks, list, mark one done, remove one, list again. Print clear labeled output. Output ONLY valid Python code.",
            "verify": lambda code: run_and_check(code, "todo_cli", None, lambda out: len(out.strip()) > 50),
        },
    ],
    "Level 3 - Network/File I/O": [
        {
            "name": "file_stats",
            "prompt": "Write a complete Python script that reads a text file given as command-line argument, counts: total lines, total words, total characters, and the 5 most frequent words (case-insensitive). Include error handling for missing file. Include `if __name__ == \"__main__\"` block. Output ONLY valid Python code.",
            "verify": lambda code: test_file_stats(code),
        },
        {
            "name": "simple_server",
            "prompt": "Write a complete Python HTTP server using only stdlib (http.server) that serves static files from a \"public\" directory. On GET /api/health, return JSON {\"status\": \"ok\"}. Include `if __name__ == \"__main__\"` block starting server on port 8999. Output ONLY valid Python code.",
            "verify": lambda code: test_server(code),
        },
    ],
}


def call_ollama(prompt, model=MODEL):
    """Send prompt to Ollama, return generated text."""
    resp = requests.post(
        f"{OLLAMA}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False,
              "options": {"temperature": 0.1, "num_predict": 2048}},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["response"]


def run_and_check(code, name, arg, check_fn):
    """Write code to temp file, run it, check output."""
    filepath = os.path.join(OUTDIR, name + ".py")
    os.makedirs(OUTDIR, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        result = subprocess.run(
            [sys.executable, filepath],
            capture_output=True, text=True, timeout=15,
            cwd=OUTDIR,
        )
        output = result.stdout + result.stderr
        ok = check_fn(output)
        return ok, output[:500]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)[:200]


def test_file_stats(code):
    """Create a test file, run the stats script, verify output."""
    testfile = os.path.join(OUTDIR, "_test_input.txt")
    with open(testfile, "w", encoding="utf-8") as f:
        f.write("hello world\nhello python\nworld of code\npython is great\nhello again world\n")
    filepath = os.path.join(OUTDIR, "file_stats.py")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        result = subprocess.run(
            [sys.executable, filepath, testfile],
            capture_output=True, text=True, timeout=15,
            cwd=OUTDIR,
        )
        output = result.stdout + result.stderr
        has_lines = "5" in output or "lines" in output.lower()
        has_words = "hello" in output.lower()
        ok = has_lines and has_words and result.returncode == 0
        return ok, output[:500]
    except subprocess.TimeoutExpired:
        return False, "TIMEOUT"
    except Exception as e:
        return False, str(e)[:200]


def test_server(code):
    """Start server briefly, curl it, check response, then kill it."""
    filepath = os.path.join(OUTDIR, "simple_server.py")
    os.makedirs(os.path.join(OUTDIR, "public"), exist_ok=True)
    with open(os.path.join(OUTDIR, "public", "index.html"), "w") as f:
        f.write("<h1>Hello</h1>")
    with open(filepath, "w") as f:
        f.write(code)
    proc = subprocess.Popen(
        [sys.executable, filepath],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        cwd=OUTDIR,
    )
    time.sleep(2)
    try:
        resp = requests.get("http://localhost:8999/api/health", timeout=5)
        data = resp.text
        ok = "ok" in data.lower()
        return ok, f"Health response: {data[:200]}"
    except Exception as e:
        return False, f"Connection failed: {e}"
    finally:
        proc.terminate()
        proc.wait(timeout=5)


if __name__ == "__main__":
    print(f"MicroSquad Build Benchmark - Model: {MODEL}")
    print("=" * 70)

    RESULTS = {"model": MODEL, "results": {}, "summary": {}}
    total_start = time.time()

    for level_name, tasks in BUILD_TASKS.items():
        print(f"\n>>> {level_name}")
        print("-" * 50)
        RESULTS["results"][level_name] = []

        for task in tasks:
            print(f"\n  [{task['name']}] ", end="", flush=True)
            t0 = time.time()

            try:
                answer = call_ollama(task["prompt"])
                elapsed = time.time() - t0

                # Extract code from response
                code = answer
                if "```python" in code:
                    code = code.split("```python", 1)[1]
                    if "```" in code:
                        code = code.split("```", 1)[0]
                elif "```" in code:
                    code = code.split("```", 1)[1]
                    if "```" in code:
                        code = code.split("```", 1)[0]

                # Verify
                verify_fn = task["verify"]
                passed, verify_output = verify_fn(code)
                status = "PASS" if passed else "FAIL"
                print(f"{status} ({elapsed:.1f}s) — {verify_output[:100]}")

                RESULTS["results"][level_name].append({
                    "name": task["name"],
                    "generated_chars": len(code),
                    "executable": passed,
                    "verify_output": verify_output,
                    "time_s": elapsed,
                })

                # Save generated code
                filepath = os.path.join(OUTDIR, f"{task['name']}.py")
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(code)

            except Exception as e:
                elapsed = time.time() - t0
                print(f"ERROR ({elapsed:.1f}s): {e}")
                RESULTS["results"][level_name].append({
                    "name": task["name"],
                    "error": str(e),
                    "time_s": elapsed,
                })

    total_time = time.time() - total_start
    passed = sum(1 for level in RESULTS["results"].values() for r in level if r.get("executable"))
    total = sum(len(v) for v in BUILD_TASKS.values())
    RESULTS["summary"] = {"passed": passed, "total": total, "rate": f"{passed}/{total}"}
    RESULTS["total_time_s"] = total_time

    outpath = r"C:\Users\gerry\generic_workspace\HLF_MCP\microsquad_build_results.json"
    with open(outpath, "w") as f:
        json.dump(RESULTS, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"BUILD BENCHMARK: {passed}/{total} executables passed ({total_time:.0f}s)")
    print(f"Model: {MODEL}")
    print(f"Results: {outpath}")
    print(f"{'=' * 70}")
