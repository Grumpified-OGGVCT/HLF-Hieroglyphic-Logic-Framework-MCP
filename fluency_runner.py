"""Diagnose HLF translation quality — the real fluency gap."""
import json
from hlf_mcp.server import _ctx, mcp

intents = [
    ("memory_store", "Store a memory record: key=session_state, value=active_and_verified"),
    ("function_def", "Define a function add that takes a and b and returns a plus b, then call add with a=3 and b=4"),
    ("conditional",  "If the gas estimate is above 50 then log warning else log normal"),
    ("memory_recall", "Recall the memory record with key session_state"),
    ("aggregate",    "Summarize the build health: all tests passing, compiler operational, 93 tools active"),
]

print("=== HLF TRANSLATION QUALITY AUDIT ===\n")
print("Goal: see what HLF the NLP pipeline actually produces for each intent type\n")

for label, intent in intents:
    r = mcp._tool_manager._tools["hlf_translate_to_hlf"].fn(text=intent, language="en")
    hlf_source = r.get("source", "").strip()
    fidelity = r.get("translation", {}).get("roundtrip_fidelity_score", 0)
    fallback = r.get("translation", {}).get("fallback_used", False)
    statements = r.get("translation", {}).get("extracted_statement_count", 0)
    
    print("=" * 70)
    print("[%s] %s" % (label.upper(), intent))
    print("  fidelity=%.2f  fallback=%s  statements=%s" % (fidelity, fallback, statements))
    print("  HLF produced:")
    for line in hlf_source.split("\n"):
        print("    | %s" % line)
    print()

print("=" * 70)
print("DIAGNOSIS: The NLP engine produces generic 'analyze [INTENT]' for most inputs.")
print("FUNCTION, IF/ELSE, MEMORY, RECALL, and SIGMA statements are NOT being generated.")
print("This is the fluency gap — the compiler supports these constructs,")
print("but the NLP bridge doesn't produce them.")
