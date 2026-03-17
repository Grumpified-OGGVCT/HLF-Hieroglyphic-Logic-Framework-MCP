"""Canonical public HLF surface for the packaged product."""

from hlf_mcp.hlf.benchmark import HLFBenchmark
from hlf_mcp.hlf.bytecode import HLFBytecode
from hlf_mcp.hlf.codegen import HLFCodeGenerator
from hlf_mcp.hlf.compiler import HLFCompiler
from hlf_mcp.hlf.formatter import HLFFormatter
from hlf_mcp.hlf.linter import HLFLinter
from hlf_mcp.hlf.runtime import HLFRuntime
from hlf_mcp.hlf.translator import (
	Tone,
	build_translation_repair_plan,
	canonicalize_translation_text,
	chinese_to_hlf,
	detect_tone,
	detect_input_language,
	detect_system_language,
	english_to_hlf,
	hlf_source_to_language,
	hlf_source_to_english,
	hlf_to_language,
	hlf_to_english,
	language_to_hlf,
	resolve_language,
	TranslationRepairPlan,
	translation_diagnostics,
)

__all__ = [
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
	"hlf_source_to_language",
	"english_to_hlf",
	"hlf_source_to_english",
	"hlf_to_language",
	"hlf_to_english",
	"language_to_hlf",
	"resolve_language",
	"translation_diagnostics",
]
