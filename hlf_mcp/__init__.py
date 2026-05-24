"""HLF MCP package."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("hlf-mcp")
except PackageNotFoundError:
    __version__ = "0.5.0"


def __getattr__(name: str):
    """Lazy-load all hlf exports to avoid pulling in DSL at import time."""
    if name == "__version__":
        return __version__
    import hlf_mcp.hlf as _hlf
    return getattr(_hlf, name)


__all__ = [
    "__version__",
    "HLFBenchmark",
    "HLFBytecode",
    "HLFCodeGenerator",
    "HLFCompiler",
    "HLFFormatter",
    "HLFLinter",
    "HLFRuntime",
    "Tone",
    "TranslationRepairPlan",
    "build_translation_repair_plan",
    "canonicalize_translation_text",
    "chinese_to_hlf",
    "detect_input_language",
    "detect_system_language",
    "detect_tone",
    "english_to_hlf",
    "hlf_source_to_language",
    "hlf_source_to_english",
    "hlf_to_language",
    "hlf_to_english",
    "language_to_hlf",
    "resolve_language",
    "translation_diagnostics",
]
