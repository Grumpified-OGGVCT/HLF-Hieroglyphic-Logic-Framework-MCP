"""
HLF Benchmark — token compression analysis using tiktoken cl100k_base.

Measures HLF token efficiency vs natural language and verbose JSON equivalents.
"""

from __future__ import annotations

from typing import Any

try:
    import tiktoken

    _ENCODER = tiktoken.get_encoding("cl100k_base")

    def _count(text: str) -> int:
        return len(_ENCODER.encode(text))

except ImportError:
    # Fallback: rough word/token estimate
    def _count(text: str) -> int:  # type: ignore[misc]
        import re
        return len(re.findall(r"\S+", text))


# Reference NLP templates for standard HLF intent types
_NLP_TEMPLATES: dict[str, str] = {
    "security_audit": (
        "Please analyze the file at /security/seccomp.json in read-only mode. "
        "I expect you to identify vulnerabilities and return them in shorthand format. "
        "All agents must reach strict consensus before proceeding."
    ),
    "hello_world": (
        "Please say hello to the world and confirm the system is operational. "
        "Return a greeting message with status OK."
    ),
    "db_migration": (
        "Execute a database migration on the production database at /data/prod.db. "
        "Apply schema version 2.1, create the users table if it does not exist, "
        "and run all pending migration scripts. Verify the migration succeeded."
    ),
    "content_delegation": (
        "Delegate a fractal summarization task to the scribe agent. "
        "The source data is at /data/raw_logs/matrix_sync_2026.txt. "
        "Set priority to high. Assert that available VRAM is at least 8GB."
    ),
    "log_analysis": (
        "Analyze the log file at /var/log/system.log using read-only access. "
        "Extract error patterns, count occurrences, and return a summary report "
        "with the top 10 most frequent errors and their timestamps."
    ),
    "stack_deployment": (
        "Deploy the application stack using the auto routing strategy for the current "
        "deployment tier. Set temperature to 0.0 for deterministic output. "
        "Require operator confirmation before proceeding with deployment."
    ),
}


class HLFBenchmark:
    """Measure HLF token compression ratios."""

    def analyze(
        self,
        source: str,
        compare_text: str | None = None,
        domain: str | None = None,
    ) -> dict[str, Any]:
        """Analyze token compression of HLF source.

        Args:
            source: HLF source code
            compare_text: Optional NLP/JSON text to compare against
            domain: Optional domain name to use NLP template (if compare_text not given)

        Returns:
            dict with token counts, compression ratio, and per-line breakdown
        """
        hlf_tokens = _count(source)

        if compare_text:
            nlp_tokens = _count(compare_text)
            compare_source = compare_text
        elif domain and domain in _NLP_TEMPLATES:
            compare_source = _NLP_TEMPLATES[domain]
            nlp_tokens = _count(compare_source)
        else:
            # Estimate NLP equivalent from source
            compare_source = _estimate_nlp(source)
            nlp_tokens = _count(compare_source)

        if nlp_tokens > 0:
            compression_pct = round((1 - hlf_tokens / nlp_tokens) * 100, 1)
        else:
            compression_pct = 0.0

        # Per-line breakdown
        line_analysis = []
        for line in source.splitlines():
            stripped = line.strip()
            if stripped:
                tc = _count(stripped)
                line_analysis.append({"line": stripped[:60], "tokens": tc})

        return {
            "hlf_tokens": hlf_tokens,
            "nlp_tokens": nlp_tokens,
            "compression_pct": compression_pct,
            "savings": nlp_tokens - hlf_tokens,
            "tiktoken_model": "cl100k_base",
            "compare_text_preview": compare_source[:100] + "..." if len(compare_source) > 100 else compare_source,
            "line_analysis": line_analysis,
        }

    def benchmark_suite(self) -> dict[str, Any]:
        """Run the full benchmark suite against all NLP templates."""
        from hlf_mcp.hlf.grammar import GLYPHS

        results = []
        total_hlf = 0
        total_nlp = 0

        for domain, nlp_text in _NLP_TEMPLATES.items():
            nlp_tokens = _count(nlp_text)
            # Use a representative HLF program for each domain
            hlf_source = _DOMAIN_HLF.get(domain, f"[HLF-v3]\nΔ {domain}\nΩ\n")
            hlf_tokens = _count(hlf_source)
            compression = round((1 - hlf_tokens / nlp_tokens) * 100, 1) if nlp_tokens > 0 else 0
            results.append({
                "domain": domain,
                "nlp_tokens": nlp_tokens,
                "hlf_tokens": hlf_tokens,
                "compression_pct": compression,
            })
            total_hlf += hlf_tokens
            total_nlp += nlp_tokens

        overall = round((1 - total_hlf / total_nlp) * 100, 1) if total_nlp > 0 else 0
        return {
            "results": results,
            "totals": {"hlf": total_hlf, "nlp": total_nlp, "compression_pct": overall},
            "tiktoken_model": "cl100k_base",
        }


def _estimate_nlp(source: str) -> str:
    """Generate a rough NLP equivalent from HLF source for comparison."""
    import re
    lines = []
    for raw in source.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[HLF-v"):
            lines.append("Begin HLF program.")
            continue
        if line == "Ω":
            lines.append("End of program.")
            continue
        # Convert glyphs + tags to prose
        line = line.replace("Δ", "Analyze").replace("Ж", "Enforce").replace("⨝", "Vote")
        line = line.replace("⌘", "Command").replace("∇", "Source").replace("⩕", "Priority").replace("⊎", "Branch")
        line = re.sub(r"\[([A-Z_]+)\]", lambda m: m.group(1).replace("_", " ").capitalize(), line)
        lines.append(line.strip() + ".")
    return " ".join(lines)


# Representative HLF programs for each benchmark domain
_DOMAIN_HLF: dict[str, str] = {
    "security_audit": """\
[HLF-v3]
Δ analyze /security/seccomp.json
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] vulnerability_shorthand
  ⨝ [VOTE] consensus="strict"
Ω
""",
    "hello_world": """\
[HLF-v3]
Δ [INTENT] goal="hello_world"
  Ж [ASSERT] status="ok"
  ∇ [RESULT] message="Hello, World!"
Ω
""",
    "db_migration": """\
[HLF-v3]
⌘ [DELEGATE] agent="db_agent" goal="migrate"
  ∇ [SOURCE] /data/prod.db
  ∇ [PARAM] schema_version="2.1"
  Ж [ASSERT] table="users"
  Ж [EXPECT] migration_success
Ω
""",
    "content_delegation": """\
[HLF-v3]
⌘ [DELEGATE] agent="scribe" goal="fractal_summarize"
  ∇ [SOURCE] /data/raw_logs/matrix_sync_2026.txt
  ⩕ [PRIORITY] level="high"
  Ж [ASSERT] vram_limit="8GB"
Ω
""",
    "log_analysis": """\
[HLF-v3]
Δ analyze /var/log/system.log
  Ж [CONSTRAINT] mode="ro"
  Ж [EXPECT] error_patterns
  ∇ [PARAM] top_k=10
  ∇ [PARAM] include_timestamps=true
Ω
""",
    "stack_deployment": """\
[HLF-v3]
⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"
  ∇ [PARAM] temperature=0.0
  Ж [VOTE] confirmation="required"
Ω
""",
}
