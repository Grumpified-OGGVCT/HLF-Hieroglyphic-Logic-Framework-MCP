"""
Task Classification — Faithful port of hlf_source/agents/core/task_classifier.py.

Produces TaskEnvelope wrappers that carry task type, category, size, estimated gas,
and agent routing target.  Supports both registered-type lookup and heuristic
intent classification.

Usage::

    from hlf_mcp.instinct.classification import classify_task, classify_intent, TaskSize, TaskCategory

    envelope = classify_task({"type": "modify_file", "path": "src/app.py"})
    if envelope.fast_path:
        result = execute_directly(envelope)
    else:
        result = plan_executor.execute_plan([envelope.task], sandbox)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Ordinal helpers
# --------------------------------------------------------------------------- #

_SIZE_ORDER: dict[str, int] = {
    "micro": 0, "small": 1, "medium": 2, "large": 3, "epic": 4,
}


def _size_max(a: TaskSize, b: TaskSize) -> TaskSize:
    return a if _SIZE_ORDER[a] >= _SIZE_ORDER[b] else b


def _size_min(a: TaskSize, b: TaskSize) -> TaskSize:
    return a if _SIZE_ORDER[a] <= _SIZE_ORDER[b] else b


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class TaskSize(StrEnum):
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EPIC = "epic"


class TaskCategory(StrEnum):
    CODE = "code"
    BUILD = "build"
    DEPLOY = "deploy"
    BROWSER = "browser"
    RESEARCH = "research"
    DOCS = "docs"
    SHELL = "shell"
    API = "api"
    ORCHESTRATE = "orchestrate"
    GOVERNANCE = "governance"


class TaskLauncher(StrEnum):
    """Provenance-only launcher identity.  Does NOT alter governance treatment."""
    GATEWAY = "gateway"
    CLI = "cli"
    HLF_RUNTIME = "hlf_runtime"
    MCP_CLIENT = "mcp_client"
    MANUAL = "manual"
    SCHEDULER = "scheduler"


# --------------------------------------------------------------------------- #
# Task Type Registry
# --------------------------------------------------------------------------- #

TASK_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    # ── CODE ───────────────────────────────────────────────────────────
    "create_file":    {"category": TaskCategory.CODE,  "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "code-agent"},
    "modify_file":    {"category": TaskCategory.CODE,  "default_size": TaskSize.SMALL,  "gas": 4,  "agent": "code-agent"},
    "refactor":       {"category": TaskCategory.CODE,  "default_size": TaskSize.MEDIUM, "gas": 8,  "agent": "code-agent"},
    "delete_file":    {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "code-agent"},
    # ── MICRO CODE ─────────────────────────────────────────────────────
    "micro_edit":     {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "hotpatch":       {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "quick_fix":      {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "config_edit":    {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "env_var":        {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "add_import":     {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "rename_symbol":  {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "code-agent"},
    "toggle_flag":    {"category": TaskCategory.CODE,  "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    # ── BUILD ──────────────────────────────────────────────────────────
    "run_tests":      {"category": TaskCategory.BUILD, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "build-agent"},
    "run_lint":       {"category": TaskCategory.BUILD, "default_size": TaskSize.SMALL,  "gas": 3,  "agent": "build-agent"},
    "validate_imports": {"category": TaskCategory.BUILD, "default_size": TaskSize.MICRO, "gas": 2,  "agent": "build-agent"},
    "check_syntax":   {"category": TaskCategory.BUILD, "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "build-agent"},
    "preflight":      {"category": TaskCategory.BUILD, "default_size": TaskSize.MEDIUM, "gas": 10, "agent": "build-agent"},
    "security_scan":  {"category": TaskCategory.BUILD, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "build-agent"},
    # ── DEPLOY ─────────────────────────────────────────────────────────
    "deploy_staging": {"category": TaskCategory.DEPLOY, "default_size": TaskSize.MEDIUM, "gas": 15, "agent": "deploy-agent"},
    "deploy_prod":    {"category": TaskCategory.DEPLOY, "default_size": TaskSize.LARGE,  "gas": 25, "agent": "deploy-agent"},
    "git_commit":     {"category": TaskCategory.DEPLOY, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "deploy-agent"},
    "git_push":       {"category": TaskCategory.DEPLOY, "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "deploy-agent"},
    "create_pr":      {"category": TaskCategory.DEPLOY, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "deploy-agent"},
    "release":        {"category": TaskCategory.DEPLOY, "default_size": TaskSize.MEDIUM, "gas": 12, "agent": "deploy-agent"},
    # ── BROWSER ────────────────────────────────────────────────────────
    "browser_navigate": {"category": TaskCategory.BROWSER, "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "browser-agent"},
    "browser_search":   {"category": TaskCategory.BROWSER, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "browser-agent"},
    "browser_workflow": {"category": TaskCategory.BROWSER, "default_size": TaskSize.MEDIUM, "gas": 8,  "agent": "browser-agent"},
    # ── RESEARCH ───────────────────────────────────────────────────────
    "web_search":     {"category": TaskCategory.RESEARCH, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "research-agent"},
    "knowledge_query": {"category": TaskCategory.RESEARCH, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "research-agent"},
    "summarize":      {"category": TaskCategory.RESEARCH, "default_size": TaskSize.SMALL,  "gas": 4,  "agent": "research-agent"},
    "analyze":        {"category": TaskCategory.RESEARCH, "default_size": TaskSize.MEDIUM, "gas": 6,  "agent": "research-agent"},
    "deep_research":  {"category": TaskCategory.RESEARCH, "default_size": TaskSize.LARGE,  "gas": 20, "agent": "research-agent"},
    # ── DOCS ───────────────────────────────────────────────────────────
    "update_readme":  {"category": TaskCategory.DOCS, "default_size": TaskSize.SMALL,  "gas": 3,  "agent": "docs-agent"},
    "generate_docs":  {"category": TaskCategory.DOCS, "default_size": TaskSize.MEDIUM, "gas": 8,  "agent": "docs-agent"},
    "update_changelog": {"category": TaskCategory.DOCS, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "docs-agent"},
    # ── SHELL ──────────────────────────────────────────────────────────
    "run_command":    {"category": TaskCategory.SHELL, "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "shell-agent"},
    "install_package": {"category": TaskCategory.SHELL, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "shell-agent"},
    "run_script":     {"category": TaskCategory.SHELL, "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "shell-agent"},
    # ── API ────────────────────────────────────────────────────────────
    "api_call":       {"category": TaskCategory.API, "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "api-agent"},
    "mcp_invoke":     {"category": TaskCategory.API, "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "api-agent"},
    # ── GOVERNANCE ─────────────────────────────────────────────────────
    "align_check":    {"category": TaskCategory.GOVERNANCE, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "governance-agent"},
    "audit_log":      {"category": TaskCategory.GOVERNANCE, "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "governance-agent"},
    "policy_check":   {"category": TaskCategory.GOVERNANCE, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "governance-agent"},
    # ── ORCHESTRATE ────────────────────────────────────────────────────
    "execute_plan":   {"category": TaskCategory.ORCHESTRATE, "default_size": TaskSize.LARGE, "gas": 20, "agent": "plan-executor"},
}

FAST_PATH_TYPES: set[str] = {
    k for k, v in TASK_TYPE_REGISTRY.items()
    if v["default_size"] == TaskSize.MICRO
}


# --------------------------------------------------------------------------- #
# Task Envelope
# --------------------------------------------------------------------------- #


@dataclass
class TaskEnvelope:
    """Classification result wrapping a task with routing metadata.

    INVARIANT: The launcher field is provenance-only.  All tasks receive
    identical ALIGN governance, gas metering, and sandbox constraints.
    """

    task: dict[str, Any]
    task_type: str
    category: TaskCategory
    size: TaskSize
    estimated_gas: int
    agent_target: str
    launcher: TaskLauncher = TaskLauncher.MANUAL
    fast_path: bool = False
    confidence: float = 1.0
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_type": self.task_type,
            "category": self.category.value,
            "size": self.size.value,
            "estimated_gas": self.estimated_gas,
            "agent_target": self.agent_target,
            "launcher": self.launcher.value,
            "fast_path": self.fast_path,
            "confidence": round(self.confidence, 3),
        }


# --------------------------------------------------------------------------- #
# Classification logic
# --------------------------------------------------------------------------- #


def _estimate_size(task: dict[str, Any], default: TaskSize) -> TaskSize:
    """Refine size estimate from content heuristics."""
    content = task.get("content", task.get("description", task.get("body", "")))
    if isinstance(content, str) and content:
        lines = len(content.splitlines())
        if lines < 5:
            return _size_min(TaskSize.MICRO, default)
        if lines > 1000:
            return _size_max(TaskSize.EPIC, default)
        if lines > 300:
            return _size_max(TaskSize.LARGE, default)
        if lines > 50:
            return _size_max(TaskSize.MEDIUM, default)
        return default

    files = task.get("files", task.get("paths", task.get("affected_files", [])))
    if isinstance(files, list) and files:
        if len(files) > 10:
            return _size_max(TaskSize.LARGE, default)
        if len(files) > 3:
            return _size_max(TaskSize.MEDIUM, default)

    return default


def classify_task(
    task: dict[str, Any],
    launcher: TaskLauncher = TaskLauncher.MANUAL,
) -> TaskEnvelope:
    """Classify a task dict into a TaskEnvelope.

    Args:
        task: Task spec with at minimum a 'type' field.
        launcher: Provenance-only dispatch identity.
    """
    task_type = task.get("type", "")

    if task_type in TASK_TYPE_REGISTRY:
        entry = TASK_TYPE_REGISTRY[task_type]
        size = _estimate_size(task, entry["default_size"])
        fast_path = (size == TaskSize.MICRO) and task_type in FAST_PATH_TYPES
        return TaskEnvelope(
            task=task,
            task_type=task_type,
            category=entry["category"],
            size=size,
            estimated_gas=entry["gas"],
            agent_target=entry["agent"],
            launcher=launcher,
            fast_path=fast_path,
            confidence=1.0,
            reasoning=f"Matched registered type '{task_type}'",
        )

    return _heuristic_classify(task, task_type, launcher)


def classify_intent(
    intent_text: str,
    launcher: TaskLauncher = TaskLauncher.MANUAL,
) -> TaskEnvelope:
    """Classify a natural-language intent string into a TaskEnvelope."""
    text = intent_text.lower().strip()

    patterns: list[tuple[str, str]] = [
        # Micro-code
        (r"\b(fix|patch|hotfix|one-?liner)\b", "quick_fix"),
        (r"\b(rename|rename\s+\w+\s+to)\b", "rename_symbol"),
        (r"\b(add\s+import|import\s+\w+)\b", "add_import"),
        (r"\b(toggle|enable|disable)\s+(flag|feature|setting)\b", "toggle_flag"),
        (r"\b(set|change|update)\s+(env|environment)\s*(var|variable)?\b", "env_var"),
        (r"\b(edit|change|update)\s*(config|conf|settings|yaml|json|toml)\b", "config_edit"),
        # Code
        (r"\b(create|new|add)\s+(file|module|class|component)\b", "create_file"),
        (r"\b(modify|edit|change|update)\s+(file|code|function|method)\b", "modify_file"),
        (r"\b(refactor|restructure|reorganize|extract)\b", "refactor"),
        (r"\b(delete|remove)\s+(file|module)\b", "delete_file"),
        # Build/verify
        (r"\b(run|execute)\s+(?:\w+\s+)*(test|tests|pytest|unittest)\b", "run_tests"),
        (r"\b(lint|ruff|flake8|pylint)\b", "run_lint"),
        (r"\b(check\s+syntax|syntax\s+check|parse)\b", "check_syntax"),
        (r"\b(preflight|pre-?flight|full\s+check)\b", "preflight"),
        (r"\b(security|vuln|vulnerability)\s*(scan|check|audit)\b", "security_scan"),
        # Deploy
        (r"\b(deploy|deployment)\s*(?:\w+\s+)*(staging|stage)\b", "deploy_staging"),
        (r"\b(deploy|deployment)\s*(?:\w+\s+)*(prod|production)\b", "deploy_prod"),
        (r"\b(commit|git\s+commit)\b", "git_commit"),
        (r"\b(push|git\s+push)\b", "git_push"),
        (r"\b(create|open)\s*(?:\w+\s+)*(pr|pull\s*request)\b", "create_pr"),
        (r"\b(release|tag|version\s+bump)\b", "release"),
        # Browser
        (r"\b(navigate|go\s+to|open)\s+(?:\w+\s+)*(url|page|site|website)\b", "browser_navigate"),
        (r"\b(search|look\s+up|find)\s+(?:\w+\s+)*(web|online|google)\b", "browser_search"),
        # Research
        (r"\b(research|investigate|explore)\b", "analyze"),
        (r"\b(summarize|summary|tldr)\b", "summarize"),
        (r"\b(search|query)\s+(?:\w+\s+)*(knowledge|memory|docs)\b", "knowledge_query"),
        # Docs
        (r"\b(update|write|edit)\s+(?:\w+\s+)*(readme|documentation|docs)\b", "update_readme"),
        (r"\b(generate|create)\s+(?:\w+\s+)*(docs|documentation|api\s+docs)\b", "generate_docs"),
        (r"\b(changelog|release\s+notes)\b", "update_changelog"),
        # Shell
        (r"\b(run|execute)\s+(?:\w+\s+)*(command|cmd|script|bash|shell|powershell)\b", "run_command"),
        (r"\b(install|pip\s+install|npm\s+install)\b", "install_package"),
        # API
        (r"\b(call|invoke|request)\s+(api|endpoint|service)\b", "api_call"),
        (r"\b(mcp|tool)\s+(call|invoke)\b", "mcp_invoke"),
        # Governance
        (r"\b(align|governance|compliance)\s*(check|audit|verify)\b", "align_check"),
        (r"\b(policy|rule)\s*(check|enforce|verify)\b", "policy_check"),
    ]

    for pattern, task_type in patterns:
        if re.search(pattern, text):
            entry = TASK_TYPE_REGISTRY[task_type]
            task_dict = {"type": task_type, "description": intent_text}
            return TaskEnvelope(
                task=task_dict,
                task_type=task_type,
                category=entry["category"],
                size=entry["default_size"],
                estimated_gas=entry["gas"],
                agent_target=entry["agent"],
                launcher=launcher,
                fast_path=(entry["default_size"] == TaskSize.MICRO),
                confidence=0.7,
                reasoning=f"Pattern matched '{pattern}' → '{task_type}'",
            )

    # Fallback
    words = len(intent_text.split())
    if words < 10:
        size = TaskSize.MICRO
    elif words < 30:
        size = TaskSize.SMALL
    elif words < 100:
        size = TaskSize.MEDIUM
    else:
        size = TaskSize.LARGE

    return TaskEnvelope(
        task={"type": "unknown", "description": intent_text},
        task_type="unknown",
        category=TaskCategory.CODE,
        size=size,
        estimated_gas=5,
        agent_target="code-agent",
        launcher=launcher,
        fast_path=False,
        confidence=0.3,
        reasoning="No pattern match; defaulting to code-agent",
    )


def _heuristic_classify(
    task: dict[str, Any],
    task_type: str,
    launcher: TaskLauncher,
) -> TaskEnvelope:
    """Heuristic classification for unknown task types."""
    text_lower = task_type.lower()
    description = str(task.get("description", task.get("content", ""))).lower()

    # Try to infer from type name
    heuristic_matches = [
        ({"fix", "patch", "hotfix", "quick"}, "quick_fix"),
        ({"test", "tests", "pytest", "unittest"}, "run_tests"),
        ({"lint", "ruff", "flake8"}, "run_lint"),
        ({"deploy", "deployment"}, "deploy_staging"),
        ({"doc", "docs", "readme", "documentation"}, "update_readme"),
        ({"shell", "bash", "command", "cmd"}, "run_command"),
        ({"refactor", "restructure"}, "refactor"),
        ({"scan", "audit", "security"}, "security_scan"),
        ({"search", "query", "lookup", "find"}, "web_search"),
    ]

    for keywords, target_type in heuristic_matches:
        if any(kw in text_lower or kw in description for kw in keywords):
            entry = TASK_TYPE_REGISTRY[target_type]
            size = _estimate_size(task, entry["default_size"])
            return TaskEnvelope(
                task=task,
                task_type=target_type,
                category=entry["category"],
                size=size,
                estimated_gas=entry["gas"],
                agent_target=entry["agent"],
                launcher=launcher,
                fast_path=(size == TaskSize.MICRO),
                confidence=0.6,
                reasoning=f"Heuristic match '{task_type}' → '{target_type}'",
            )

    size = _estimate_size(task, TaskSize.SMALL)
    return TaskEnvelope(
        task=task,
        task_type=task_type or "unknown",
        category=TaskCategory.CODE,
        size=size,
        estimated_gas=5,
        agent_target="code-agent",
        launcher=launcher,
        fast_path=False,
        confidence=0.3,
        reasoning=f"Unknown type '{task_type}'; defaulting to code-agent",
    )


# --------------------------------------------------------------------------- #
# Utility
# --------------------------------------------------------------------------- #


def get_task_types_for_category(category: TaskCategory) -> list[str]:
    return [k for k, v in TASK_TYPE_REGISTRY.items() if v["category"] == category]


def get_all_categories() -> list[str]:
    return [c.value for c in TaskCategory]


def get_vocabulary_summary() -> dict[str, Any]:
    by_category: dict[str, list[dict[str, Any]]] = {}
    for task_type, entry in TASK_TYPE_REGISTRY.items():
        cat = entry["category"].value
        by_category.setdefault(cat, []).append({
            "type": task_type,
            "size": entry["default_size"].value,
            "gas": entry["gas"],
            "agent": entry["agent"],
            "fast_path": task_type in FAST_PATH_TYPES,
        })
    return {
        "total_types": len(TASK_TYPE_REGISTRY),
        "categories": len(TaskCategory),
        "fast_path_types": len(FAST_PATH_TYPES),
        "by_category": by_category,
    }
