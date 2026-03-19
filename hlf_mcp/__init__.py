"""HLF MCP package."""

from importlib.metadata import PackageNotFoundError, version

from hlf_mcp.hlf import (
    HLFBenchmark,
    HLFBytecode,
    HLFCodeGenerator,
    HLFCompiler,
    HLFFormatter,
    HLFLinter,
    HLFRuntime,
    Tone,
    TranslationRepairPlan,
    build_translation_repair_plan,
    canonicalize_translation_text,
    chinese_to_hlf,
    detect_input_language,
    detect_system_language,
    detect_tone,
    english_to_hlf,
    hlf_source_to_language,
    hlf_source_to_english,
    hlf_to_language,
    hlf_to_english,
    language_to_hlf,
    resolve_language,
    translation_diagnostics,
)

try:
    __version__ = version("hlf-mcp")
except PackageNotFoundError:
    __version__ = "0.5.0"

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
