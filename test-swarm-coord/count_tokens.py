import os
import tiktoken

ENCODING_NAME = "cl100k_base"
enc = tiktoken.get_encoding(ENCODING_NAME)

def count_tokens(filepath):
    with open(filepath, "rb") as f:
        content = f.read()
    text = content.decode("utf-8", errors="replace")
    tokens = enc.encode(text)
    return len(tokens), len(content)

files = [
    # Main benchmark coordination files
    "test-2-nl/PLAN.md",
    "test-2-hlf/swarm.hlf",
    "test-3-nl/PLAN.md",
    "test-3-hlf/swarm.hlf",
    # Trial PLAN.md files (Test 1)
    "trial-1/PLAN.md",
    "trial-2/PLAN.md",
    "trial-3/PLAN.md",
    "trial-4/PLAN.md",
    "trial-5/PLAN.md",
    # Source code files
    "src/index.js",
    "src/queue.js",
    "src/worker.js",
    # Test files
    "tests/queue.test.js",
    "tests/worker.test.js",
]

results = []
for rel in files:
    abs_path = os.path.join(os.path.dirname(__file__), rel)
    if os.path.exists(abs_path):
        tokens, byte_size = count_tokens(abs_path)
        results.append({
            "file": rel,
            "bytes": byte_size,
            "tokens": tokens,
        })
    else:
        print(f"MISSING: {abs_path}")

# Print as JSON-like for easy parsing
for r in results:
    print(f"{r['file']}|{r['bytes']}|{r['tokens']}")
