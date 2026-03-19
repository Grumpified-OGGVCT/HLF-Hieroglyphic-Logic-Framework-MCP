"""
HLF Translator — bidirectional English ↔ HLF translation with tone detection.

Tone detection uses keyword heuristics to identify emotional/urgency context.
english_to_hlf() converts natural language to HLF source programs.
hlf_to_english() converts HLF AST to prose (using InsAIts human_readable fields).
"""

from __future__ import annotations
from dataclasses import dataclass
import locale
import os
import re
from enum import Enum
from typing import Any

SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"en", "fr", "es", "ar", "zh"})

_SYSTEM_LANGUAGE_HINTS: dict[str, str] = {
    "en": "en",
    "english": "en",
    "fr": "fr",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "es": "es",
    "spanish": "es",
    "espanol": "es",
    "español": "es",
    "ar": "ar",
    "arabic": "ar",
    "zh": "zh",
    "chinese": "zh",
    "mandarin": "zh",
    "zhongwen": "zh",
    "中文": "zh",
}

_LANGUAGE_CUE_WORDS: dict[str, tuple[str, ...]] = {
    "en": ("analyze", "read", "check", "inspect", "audit", "delegate", "remember", "recall"),
    "fr": ("analyser", "lire", "verifier", "vérifier", "inspecter", "audit", "deleguer", "déléguer", "memoire", "mémoire", "rappeler"),
    "es": ("analizar", "leer", "verificar", "inspeccionar", "auditar", "delegar", "recordar", "recuperar"),
    "ar": ("تحليل", "اقرأ", "قراءة", "تحقق", "تفقد", "راجع", "فوض", "تذكر", "استرجع"),
    "zh": ("分析", "读取", "检查", "审计", "查看", "委托", "记住", "召回", "检索"),
}

_ARABIC_SCRIPT_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
_CJK_SCRIPT_RE = re.compile(r"[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF]")


@dataclass(frozen=True)
class LanguageProfile:
    name: str
    generated_from_label: str
    empty_program: str
    no_readable_statements: str
    translation_failed_prefix: str
    summary_prefix_suffix: str
    joiner: str
    analyze_words: tuple[str, ...]
    read_only_words: tuple[str, ...]
    delegate_words: tuple[str, ...]
    route_words: tuple[str, ...]
    memory_store_words: tuple[str, ...]
    memory_recall_words: tuple[str, ...]
    vote_words: tuple[str, ...]
    assert_words: tuple[str, ...]
    analyze_goal: str
    delegate_goal: str
    route_strategy: str
    memory_label: str
    recall_label: str
    vote_label: str
    generic_execute_goal: str
    generic_fallback_prefix: str
    localized_human_readable_prefix: str


@dataclass(frozen=True)
class TranslationDiagnostics:
    resolved_language: str
    extracted_statement_count: int
    fallback_count: int
    fallback_used: bool
    roundtrip_fidelity_score: float
    semantic_loss_flags: tuple[str, ...]
    roundtrip_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved_language": self.resolved_language,
            "extracted_statement_count": self.extracted_statement_count,
            "fallback_count": self.fallback_count,
            "fallback_used": self.fallback_used,
            "roundtrip_fidelity_score": self.roundtrip_fidelity_score,
            "semantic_loss_flags": list(self.semantic_loss_flags),
            "roundtrip_summary": self.roundtrip_summary,
        }


@dataclass(frozen=True)
class TranslationRepairPlan:
    retryable: bool
    terminal_reason: str | None
    resolved_language: str
    original_text: str
    repaired_text: str
    recommended_tool: str
    next_request: dict[str, Any]
    diagnostics: TranslationDiagnostics

    def to_dict(self) -> dict[str, Any]:
        return {
            "retryable": self.retryable,
            "terminal_reason": self.terminal_reason,
            "resolved_language": self.resolved_language,
            "original_text": self.original_text,
            "repaired_text": self.repaired_text,
            "recommended_tool": self.recommended_tool,
            "next_request": self.next_request,
            "diagnostics": self.diagnostics.to_dict(),
        }


_LANGUAGE_PROFILES: dict[str, LanguageProfile] = {
    "en": LanguageProfile(
        name="English",
        generated_from_label="Generated from English",
        empty_program="Empty HLF program.",
        no_readable_statements="HLF program with no readable statements.",
        translation_failed_prefix="Translation failed:",
        summary_prefix_suffix=": ",
        joiner="; ",
        analyze_words=("analyze", "read", "check", "inspect", "audit"),
        read_only_words=("read-only", "readonly", "ro"),
        delegate_words=("delegate", "assign", "send to", "task"),
        route_words=("route", "select model", "choose"),
        memory_store_words=("remember", "store", "save", "memorize"),
        memory_recall_words=("recall", "retrieve", "look up"),
        vote_words=("consensus", "vote", "agree"),
        assert_words=("assert", "enforce", "require", "must"),
        analyze_goal="analyze",
        delegate_goal="execute",
        route_strategy="auto",
        memory_label="context",
        recall_label="context",
        vote_label="strict",
        generic_execute_goal="execute",
        generic_fallback_prefix="goal",
        localized_human_readable_prefix="Program summary",
    ),
    "fr": LanguageProfile(
        name="français",
        generated_from_label="Généré à partir du français",
        empty_program="Programme HLF vide.",
        no_readable_statements="Programme HLF sans instructions lisibles.",
        translation_failed_prefix="Échec de traduction :",
        summary_prefix_suffix=" : ",
        joiner=" ; ",
        analyze_words=("analyser", "lire", "verifier", "vérifier", "inspecter", "auditer", "audit"),
        read_only_words=("lecture seule", "lecture-seule", "mode ro", "ro"),
        delegate_words=("deleguer", "déléguer", "confier", "assigner", "transmettre"),
        route_words=("acheminer", "router", "routage", "choisir", "selectionner", "sélectionner"),
        memory_store_words=("memoriser", "mémoriser", "retenir", "sauvegarder", "stocker"),
        memory_recall_words=("rappeler", "recuperer", "récupérer", "chercher", "retrouver"),
        vote_words=("consensus", "voter", "accord"),
        assert_words=("affirmer", "imposer", "exiger", "doit", "contraindre"),
        analyze_goal="analyser",
        delegate_goal="executer",
        route_strategy="auto",
        memory_label="contexte",
        recall_label="contexte",
        vote_label="strict",
        generic_execute_goal="executer",
        generic_fallback_prefix="objectif",
        localized_human_readable_prefix="Résumé du programme",
    ),
    "es": LanguageProfile(
        name="español",
        generated_from_label="Generado desde español",
        empty_program="Programa HLF vacío.",
        no_readable_statements="Programa HLF sin instrucciones legibles.",
        translation_failed_prefix="Traducción fallida:",
        summary_prefix_suffix=": ",
        joiner="; ",
        analyze_words=("analizar", "leer", "verificar", "inspeccionar", "auditar", "revisar"),
        read_only_words=("solo lectura", "sólo lectura", "lectura sola", "modo ro", "ro"),
        delegate_words=("delegar", "asignar", "enviar a", "encargar"),
        route_words=("enrutar", "encaminar", "elegir", "seleccionar", "despachar"),
        memory_store_words=("recordar", "guardar", "almacenar", "memorizar"),
        memory_recall_words=("recuperar", "consultar", "buscar", "recordar"),
        vote_words=("consenso", "votar", "acuerdo"),
        assert_words=("afirmar", "imponer", "requerir", "debe", "exigir"),
        analyze_goal="analizar",
        delegate_goal="ejecutar",
        route_strategy="auto",
        memory_label="contexto",
        recall_label="contexto",
        vote_label="estricto",
        generic_execute_goal="ejecutar",
        generic_fallback_prefix="objetivo",
        localized_human_readable_prefix="Resumen del programa",
    ),
    "ar": LanguageProfile(
        name="العربية",
        generated_from_label="تم الإنشاء من العربية",
        empty_program="برنامج HLF فارغ.",
        no_readable_statements="برنامج HLF بدون تعليمات قابلة للقراءة.",
        translation_failed_prefix="فشل الترجمة:",
        summary_prefix_suffix=": ",
        joiner="؛ ",
        analyze_words=("تحليل", "اقرأ", "قراءة", "تحقق", "تفقد", "راجع", "دقق"),
        read_only_words=("للقراءة فقط", "قراءة فقط", "وضع القراءة فقط", "ro"),
        delegate_words=("فوض", "تفويض", "اسند", "حوّل"),
        route_words=("وجه", "توجيه", "اختر", "مرر", "أرسل"),
        memory_store_words=("تذكر", "احفظ", "خزن", "تخزين"),
        memory_recall_words=("استرجع", "ابحث", "استعلم", "تذكر"),
        vote_words=("تصويت", "توافق", "اتفاق"),
        assert_words=("أكد", "افرض", "الزم", "يجب", "تطلب"),
        analyze_goal="تحليل",
        delegate_goal="تنفيذ",
        route_strategy="تلقائي",
        memory_label="سياق",
        recall_label="سياق",
        vote_label="صارم",
        generic_execute_goal="تنفيذ",
        generic_fallback_prefix="هدف",
        localized_human_readable_prefix="ملخص البرنامج",
    ),
    "zh": LanguageProfile(
        name="中文",
        generated_from_label="由中文生成",
        empty_program="空的 HLF 程序。",
        no_readable_statements="HLF 程序没有可读语句。",
        translation_failed_prefix="翻译失败：",
        summary_prefix_suffix="：",
        joiner="；",
        analyze_words=("分析", "读取", "检查", "审计", "查看", "检视"),
        read_only_words=("只读", "唯读", "只读取", "ro"),
        delegate_words=("委托", "代理", "交给", "分派", "指派"),
        route_words=("路由", "选择模型", "选择", "分发", "转发"),
        memory_store_words=("记住", "存储", "保存", "记忆"),
        memory_recall_words=("召回", "检索", "取回", "查询"),
        vote_words=("共识", "投票", "同意"),
        assert_words=("断言", "强制", "要求", "必须", "约束"),
        analyze_goal="分析",
        delegate_goal="执行",
        route_strategy="自动",
        memory_label="上下文",
        recall_label="上下文",
        vote_label="严格",
        generic_execute_goal="执行",
        generic_fallback_prefix="目标",
        localized_human_readable_prefix="程序摘要",
    ),
}

_PATH_PATTERNS: dict[str, re.Pattern[str]] = {
    "en": re.compile(r"(?:[A-Za-z]:[\\/][^\s\"']+|/[\w/._-]+)"),
    "fr": re.compile(r"(?:[A-Za-z]:[\\/][^\s\"']+|/[\w/._-]+)"),
    "es": re.compile(r"(?:[A-Za-z]:[\\/][^\s\"']+|/[\w/._-]+)"),
    "ar": re.compile(r"(?:[A-Za-z]:[\\/][^\s\"']+|/[\w/._-]+)"),
    "zh": re.compile(r"(?:[A-Za-z]:[\\/][^\s\"']+|/[\w/._-]+)"),
}

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


def detect_system_language(preferred_language: str | None = None) -> str:
    """Return the best supported language from explicit preference or host locale."""
    candidates: list[str] = []
    if preferred_language:
        candidates.append(preferred_language)
    env_override = os.environ.get("HLF_LANGUAGE")
    if env_override:
        candidates.append(env_override)
    for env_name in ("LANGUAGE", "LC_ALL", "LANG"):
        env_value = os.environ.get(env_name)
        if env_value:
            candidates.append(env_value)
    try:
        current_locale = locale.getlocale()
        if current_locale and current_locale[0]:
            candidates.append(current_locale[0])
    except Exception:
        pass

    for candidate in candidates:
        normalized = _normalize_language_hint(candidate)
        if normalized in SUPPORTED_LANGUAGES:
            return normalized
    return "en"


def detect_input_language(text: str, default_language: str = "en") -> str:
    """Infer language from text, falling back to the caller's default language."""
    if not text.strip():
        return default_language
    if _ARABIC_SCRIPT_RE.search(text):
        return "ar"
    if _CJK_SCRIPT_RE.search(text):
        return "zh"

    lowered = text.casefold()
    scores = {
        language: sum(1 for cue in cues if cue in lowered)
        for language, cues in _LANGUAGE_CUE_WORDS.items()
    }
    best_language = max(scores, key=scores.get)
    if scores[best_language] > 0:
        return best_language
    return default_language


def resolve_language(
    language: str = "auto",
    *,
    text: str = "",
    preferred_language: str | None = None,
) -> str:
    """Resolve explicit or automatic language selection to a supported code."""
    normalized = language.lower().strip()
    if normalized != "auto":
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        return normalized

    system_language = detect_system_language(preferred_language=preferred_language)
    return detect_input_language(text, default_language=system_language)


def language_to_hlf(
    text: str,
    language: str = "auto",
    tone: Tone | None = None,
    version: str = "3",
    *,
    preferred_language: str | None = None,
) -> str:
    """Convert natural language instructions to HLF program source, supporting i18n gates."""
    lang = resolve_language(language, text=text, preferred_language=preferred_language)
    if lang == "en":
        return english_to_hlf(text, tone=tone, version=version)
    elif lang == "fr":
        return french_to_hlf(text, tone=tone, version=version)
    elif lang == "es":
        return spanish_to_hlf(text, tone=tone, version=version)
    elif lang == "ar":
        return arabic_to_hlf(text, tone=tone, version=version)
    elif lang == "zh":
        return chinese_to_hlf(text, tone=tone, version=version)
    raise ValueError(f"Unsupported language: {lang}")


def _normalize_language_hint(value: str) -> str:
    cleaned = value.strip().casefold().replace("-", "_")
    if "." in cleaned:
        cleaned = cleaned.split(".", 1)[0]
    if ":" in cleaned:
        cleaned = cleaned.split(":", 1)[0]
    if "_" in cleaned:
        cleaned = cleaned.split("_", 1)[0]
    return _SYSTEM_LANGUAGE_HINTS.get(cleaned, cleaned)


def _semantic_expectations(text: str, *, language: str) -> dict[str, bool]:
    profile = _LANGUAGE_PROFILES[language]
    lowered = text.casefold()
    return {
        "path": _extract_path(text, language=language) is not None,
        "read_only": any(word in lowered for word in profile.read_only_words),
        "delegate": any(word in lowered for word in profile.delegate_words),
        "route": any(word in lowered for word in profile.route_words),
        "memory_store": any(word in lowered for word in profile.memory_store_words),
        "memory_recall": any(word in lowered for word in profile.memory_recall_words),
        "vote": any(word in lowered for word in profile.vote_words),
        "assert": any(word in lowered for word in profile.assert_words),
    }


def _semantic_actuals(source: str) -> dict[str, bool]:
    return {
        "path": 'target="' in source,
        "read_only": 'mode="ro"' in source,
        "delegate": "[DELEGATE]" in source,
        "route": "[ROUTE]" in source,
        "memory_store": "MEMORY [" in source,
        "memory_recall": "RECALL [" in source,
        "vote": "[VOTE]" in source,
        "assert": "[ASSERT]" in source,
    }


def translation_diagnostics(
    text: str,
    *,
    language: str = "auto",
    preferred_language: str | None = None,
    source: str | None = None,
) -> TranslationDiagnostics:
    resolved_language = resolve_language(language, text=text, preferred_language=preferred_language)
    effective_source = source or language_to_hlf(
        text,
        language=resolved_language,
        preferred_language=preferred_language,
    )
    profile = _LANGUAGE_PROFILES[resolved_language]
    fallback_marker = f'goal="{profile.generic_fallback_prefix}:'
    recognized_goals = {
        profile.analyze_goal,
        profile.delegate_goal,
        profile.generic_execute_goal,
    }
    extracted_statement_count = 0
    fallback_count = 0
    for line in effective_source.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("[HLF-v") or stripped.startswith("#") or stripped == "Ω":
            continue
        extracted_statement_count += 1
        if fallback_marker in stripped:
            fallback_count += 1
            continue
        if stripped.startswith('Δ [INTENT] goal="'):
            try:
                goal_value = stripped.split('goal="', 1)[1].split('"', 1)[0]
            except Exception:
                goal_value = ""
            if not any(flag for flag in _semantic_expectations(text, language=resolved_language).values()) and goal_value not in recognized_goals:
                fallback_count += 1

    expected = _semantic_expectations(text, language=resolved_language)
    actual = _semantic_actuals(effective_source)
    missing = tuple(key for key, expected_present in expected.items() if expected_present and not actual[key])
    expected_count = sum(1 for present in expected.values() if present)
    matched_count = expected_count - len(missing)
    fidelity_score = round((matched_count / expected_count), 3) if expected_count else 1.0
    roundtrip_summary = hlf_source_to_language(effective_source, language=resolved_language)
    return TranslationDiagnostics(
        resolved_language=resolved_language,
        extracted_statement_count=extracted_statement_count,
        fallback_count=fallback_count,
        fallback_used=fallback_count > 0,
        roundtrip_fidelity_score=fidelity_score,
        semantic_loss_flags=missing,
        roundtrip_summary=roundtrip_summary,
    )


def canonicalize_translation_text(
    text: str,
    *,
    language: str = "auto",
    preferred_language: str | None = None,
) -> str:
    """Reduce intent text to a more deterministic retry form for translator repair."""
    resolved_language = resolve_language(language, text=text, preferred_language=preferred_language)
    profile = _LANGUAGE_PROFILES[resolved_language]
    lowered = text.casefold()
    path = _extract_path(text, language=resolved_language)
    clauses: list[str] = []

    if any(word in lowered for word in profile.analyze_words) or path is not None:
        clause = f"{profile.analyze_words[0]} {path or '/data/target'}"
        if any(word in lowered for word in profile.read_only_words):
            clause += f" {profile.read_only_words[0]}"
        clauses.append(clause)

    if any(word in lowered for word in profile.delegate_words):
        agent = _extract_quoted(text) or "sub_agent"
        clauses.append(f'{profile.delegate_words[0]} "{agent}"')

    if any(word in lowered for word in profile.route_words):
        clauses.append(profile.route_words[0])

    if any(word in lowered for word in profile.memory_store_words):
        clauses.append(profile.memory_store_words[0])

    if any(word in lowered for word in profile.memory_recall_words):
        clauses.append(profile.memory_recall_words[0])

    if any(word in lowered for word in profile.vote_words):
        clauses.append(profile.vote_words[0])

    if any(word in lowered for word in profile.assert_words):
        constraint = _extract_quoted(text) or "constraint"
        clauses.append(f'{profile.assert_words[0]} "{constraint}"')

    if clauses:
        return "; ".join(dict.fromkeys(clauses))
    return " ".join(text.split())


def build_translation_repair_plan(
    text: str,
    *,
    language: str = "auto",
    preferred_language: str | None = None,
    failure_status: str = "",
    failure_error: str = "",
) -> TranslationRepairPlan:
    """Build a deterministic machine-readable retry plan for failed HLF translation flows."""
    resolved_language = resolve_language(language, text=text, preferred_language=preferred_language)
    lowered_error = failure_error.casefold()
    lowered_status = failure_status.casefold()

    retryable = True
    terminal_reason: str | None = None
    if "ethics governor" in lowered_error or "governor_blocked" in lowered_status:
        retryable = False
        terminal_reason = "policy_block"
    elif "align ledger violation" in lowered_error:
        retryable = False
        terminal_reason = "align_block"
    elif "unsupported language" in lowered_error:
        retryable = True
        resolved_language = "en"

    repaired_text = canonicalize_translation_text(
        text,
        language=resolved_language,
        preferred_language=preferred_language,
    )
    diagnostics = translation_diagnostics(
        repaired_text,
        language=resolved_language,
        preferred_language=preferred_language,
    )
    next_request = {
        "text": repaired_text,
        "language": resolved_language,
        "version": "3",
    }
    return TranslationRepairPlan(
        retryable=retryable,
        terminal_reason=terminal_reason,
        resolved_language=resolved_language,
        original_text=text,
        repaired_text=repaired_text,
        recommended_tool="hlf_translate_to_hlf",
        next_request=next_request,
        diagnostics=diagnostics,
    )

def english_to_hlf(english: str, tone: Tone | None = None, version: str = "3") -> str:
    """Convert English instructions to HLF program source."""
    return _language_profile_to_hlf(english, language="en", tone=tone, version=version)

def french_to_hlf(french: str, tone: Tone | None = None, version: str = "3") -> str:
    """Convert French instructions to HLF program source."""
    return _language_profile_to_hlf(french, language="fr", tone=tone, version=version)

def spanish_to_hlf(spanish: str, tone: Tone | None = None, version: str = "3") -> str:
    """Convert Spanish instructions to HLF program source."""
    return _language_profile_to_hlf(spanish, language="es", tone=tone, version=version)

def arabic_to_hlf(arabic: str, tone: Tone | None = None, version: str = "3") -> str:
    """Convert Arabic instructions to HLF program source."""
    return _language_profile_to_hlf(arabic, language="ar", tone=tone, version=version)


def chinese_to_hlf(chinese: str, tone: Tone | None = None, version: str = "3") -> str:
    """Convert Chinese instructions to HLF program source."""
    return _language_profile_to_hlf(chinese, language="zh", tone=tone, version=version)


def _language_profile_to_hlf(text: str, language: str, tone: Tone | None, version: str) -> str:
    profile = _LANGUAGE_PROFILES[language]
    resolved_tone = tone or detect_tone(text)
    lines = [f"[HLF-v{version}]"]
    lines.append(f"# {profile.generated_from_label} (tone: {resolved_tone.value})")
    actions = _extract_actions(text, language=language)
    for action in actions:
        lines.append(action)
    lines.append("Ω")
    return "\n".join(lines) + "\n"

def _extract_actions(text: str, *, language: str = "en") -> list[str]:
    """Heuristically extract HLF statements from supported language text."""
    profile = _LANGUAGE_PROFILES[language]
    actions = []
    # Split sentence boundaries without breaking dotted file paths like /var/log/app.log.
    sentences = re.split(r'[;!?\n]|\.(?!\w)', text)
    for sentence in sentences:
        s = sentence.strip()
        if not s:
            continue
        s_lower = s.casefold()
        if any(w in s_lower for w in profile.analyze_words):
            path = _extract_path(s, language=language) or "/data/target"
            actions.append(f'Δ [INTENT] goal="{profile.analyze_goal}" target="{path}"')
            if any(w in s_lower for w in profile.read_only_words):
                actions.append('  Ж [CONSTRAINT] mode="ro"')
        elif any(w in s_lower for w in profile.delegate_words):
            agent = _extract_quoted(s) or "sub_agent"
            actions.append(f'⌘ [DELEGATE] agent="{agent}" goal="{profile.delegate_goal}"')
        elif any(w in s_lower for w in profile.route_words):
            actions.append(f'⌘ [ROUTE] strategy="{profile.route_strategy}" tier="$DEPLOYMENT_TIER"')
        elif any(w in s_lower for w in profile.memory_store_words):
            actions.append(f'MEMORY [{profile.memory_label}] value="' + s[:40].replace('"', "'") + '"')
        elif any(w in s_lower for w in profile.memory_recall_words):
            actions.append(f'RECALL [{profile.recall_label}]')
        elif any(w in s_lower for w in profile.vote_words):
            actions.append(f'⨝ [VOTE] consensus="{profile.vote_label}"')
        elif any(w in s_lower for w in profile.assert_words):
            constraint = _extract_quoted(s) or "constraint"
            actions.append(f'Ж [ASSERT] rule="{constraint}"')
        else:
            goal = s[:40].strip().replace('"', "'")
            if language != "en" and goal:
                goal = f"{profile.generic_fallback_prefix}: {goal}"
            actions.append(f'Δ [INTENT] goal="{goal}"')
    return actions or [f'Δ [INTENT] goal="{profile.generic_execute_goal}"']

def _extract_path(text: str, *, language: str = "en") -> str | None:
    m = _PATH_PATTERNS[language].search(text)
    return m.group(0) if m else None

def _extract_quoted(text: str) -> str | None:
    m = re.search(r'"([^"]+)"', text)
    return m.group(1) if m else None

def hlf_to_english(ast: dict[str, Any]) -> str:
    """Convert HLF AST to natural language summary using human_readable fields."""
    return hlf_to_language(ast, language="en")


def hlf_to_language(ast: dict[str, Any], language: str = "en") -> str:
    """Convert HLF AST to a supported natural-language summary."""
    profile = _LANGUAGE_PROFILES[resolve_language(language)]
    statements = ast.get("statements", [])
    if not statements:
        return profile.empty_program
    summaries = []
    for node in statements:
        if isinstance(node, dict):
            hr = node.get("human_readable", "")
            if hr:
                summaries.append(hr)
    program_hr = ast.get("human_readable", "")
    if program_hr:
        prefix = program_hr + profile.summary_prefix_suffix
        return prefix + profile.joiner.join(summaries) + "." if summaries else profile.no_readable_statements
    if summaries:
        return f"{profile.localized_human_readable_prefix}{profile.summary_prefix_suffix}{profile.joiner.join(summaries)}."
    return profile.no_readable_statements

def hlf_source_to_english(source: str) -> str:
    """Convenience: parse source and return English summary."""
    return hlf_source_to_language(source, language="en")


def hlf_source_to_language(source: str, language: str = "en") -> str:
    """Convenience: parse source and return a supported-language summary."""
    resolved_language = resolve_language(language)
    profile = _LANGUAGE_PROFILES[resolved_language]
    from hlf_mcp.hlf.compiler import HLFCompiler
    try:
        result = HLFCompiler().compile(source)
        return hlf_to_language(result["ast"], language=resolved_language)
    except Exception as exc:
        return f"{profile.translation_failed_prefix} {exc}"
