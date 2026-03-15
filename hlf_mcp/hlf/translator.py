"""
HLF Translator — bidirectional English ↔ HLF translation with tone detection.

Tone detection uses keyword heuristics to identify emotional/urgency context.
english_to_hlf() converts natural language to HLF source programs.
hlf_to_english() converts HLF AST to prose (using InsAIts human_readable fields).
"""

from __future__ import annotations
import re
from enum import Enum
from typing import Any

class Tone(Enum):
    NEUTRAL    = "neutral"
    FRUSTRATED = "frustrated"
    URGENT     = "urgent"
    CURIOUS    = "curious"
    CONFIDENT  = "confident"
    UNCERTAIN  = "uncertain"
    DECISIVE   = "decisive"

_TONE_CUE_WORDS: dict[Tone, list[str]] = {
    Tone.FRUSTRATED: ["stuck", "frustrated", "annoyed", "blocked", "cannot", "impossible", "broken"],
    Tone.URGENT:     ["urgent", "critical", "asap", "immediately", "deadline", "emergency", "now"],
    Tone.CURIOUS:    ["wonder", "curious", "explore", "investigate", "understand", "what if"],
    Tone.CONFIDENT:  ["will", "definitely", "certainly", "sure", "completed", "done", "ready"],
    Tone.UNCERTAIN:  ["maybe", "might", "perhaps", "unclear", "unsure", "think", "possibly"],
    Tone.DECISIVE:   ["must", "shall", "required", "executing", "enforce", "mandate"],
}

_NUANCE_GLYPHS: dict[str, str] = {
    "frustrated": "⚠", "urgent": "⚡", "curious": "🔍",
    "confident":  "✓", "uncertain": "?", "decisive": "!",
}

def detect_tone(text: str) -> Tone:
    text_lower = text.lower()
    for tone, cues in _TONE_CUE_WORDS.items():
        for cue in cues:
            if cue in text_lower:
                return tone
    return Tone.NEUTRAL

def english_to_hlf(english: str, tone: Tone | None = None, version: str = "3") -> str:
    """Convert English instructions to HLF program source."""
    if tone is None:
        tone = detect_tone(english)
    lines = [f"[HLF-v{version}]"]
    lines.append(f"# Generated from English (tone: {tone.value})")
    # Extract key actions
    actions = _extract_actions(english)
    for action in actions:
        lines.append(action)
    lines.append("Ω")
    return "\n".join(lines) + "\n"

def _extract_actions(text: str) -> list[str]:
    """Heuristically extract HLF statements from English text."""
    actions = []
    sentences = re.split(r'[.;!?\n]', text)
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        s_lower = s.lower()
        # Analyze/read
        if any(w in s_lower for w in ("analyze", "read", "check", "inspect", "audit")):
            path = _extract_path(s) or "/data/target"
            actions.append(f'Δ [INTENT] goal="analyze" target="{path}"')
            if "read-only" in s_lower or "ro" in s_lower:
                actions.append('  Ж [CONSTRAINT] mode="ro"')
        # Delegate
        elif any(w in s_lower for w in ("delegate", "assign", "send to", "task")):
            agent = _extract_quoted(s) or "sub_agent"
            actions.append(f'⌘ [DELEGATE] agent="{agent}" goal="execute"')
        # Route
        elif any(w in s_lower for w in ("route", "select model", "choose")):
            actions.append('⌘ [ROUTE] strategy="auto" tier="$DEPLOYMENT_TIER"')
        # Memory store
        elif any(w in s_lower for w in ("remember", "store", "save", "memorize")):
            actions.append('MEMORY [context] value="' + s[:40].replace('"', "'") + '"')
        # Memory recall
        elif any(w in s_lower for w in ("recall", "retrieve", "look up")):
            actions.append('RECALL [context]')
        # Vote/consensus
        elif any(w in s_lower for w in ("consensus", "vote", "agree")):
            actions.append('⨝ [VOTE] consensus="strict"')
        # Assert/enforce
        elif any(w in s_lower for w in ("assert", "enforce", "require", "must")):
            constraint = _extract_quoted(s) or "constraint"
            actions.append(f'Ж [ASSERT] rule="{constraint}"')
        else:
            # Generic intent
            goal = s[:40].strip().replace('"', "'")
            actions.append(f'Δ [INTENT] goal="{goal}"')
    return actions or ['Δ [INTENT] goal="execute"']

def _extract_path(text: str) -> str | None:
    m = re.search(r'/[\w/._-]+', text)
    return m.group(0) if m else None

def _extract_quoted(text: str) -> str | None:
    m = re.search(r'"([^"]+)"', text)
    return m.group(1) if m else None

def hlf_to_english(ast: dict[str, Any]) -> str:
    """Convert HLF AST to natural language summary using human_readable fields."""
    statements = ast.get("statements", [])
    if not statements:
        return "Empty HLF program."
    summaries = []
    for node in statements:
        if isinstance(node, dict):
            hr = node.get("human_readable", "")
            if hr:
                summaries.append(hr)
    program_hr = ast.get("human_readable", "")
    prefix = program_hr + ": " if program_hr else ""
    return prefix + "; ".join(summaries) + "." if summaries else "HLF program with no readable statements."

def hlf_source_to_english(source: str) -> str:
    """Convenience: parse source and return English summary."""
    from hlf_mcp.hlf.compiler import HLFCompiler
    try:
        result = HLFCompiler().compile(source)
        return hlf_to_english(result["ast"])
    except Exception as exc:
        return f"Translation failed: {exc}"
