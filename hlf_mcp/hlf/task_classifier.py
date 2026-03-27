"""
Task Classifier — Sizes, Routes, and Fast-Paths Agent Tasks.

Faithful port from hlf_source/agents/core/task_classifier.py.
Extended with an HLF Workload bridge (task_envelope_to_workload) that
maps TaskCategory/TaskEnvelope to the Workload strings used by
governed_routing.py and server_profiles.py.

Provides the routing layer with the intelligence to distinguish between
micro-tasks (one-liner fixes, hotpatches, quick config edits) and full
orchestration tasks (multi-file refactors, feature builds, deployments).

The classifier produces a TaskEnvelope that carries:
  - size: MICRO | SMALL | MEDIUM | LARGE | EPIC
  - category: CODE | BUILD | DEPLOY | BROWSER | RESEARCH | DOCS | SHELL | API
  - estimated_gas: predicted gas cost for the intent
  - fast_path: whether to skip DAG orchestration

Size definitions:
  MICRO  — single-line edit, config change, env var, hotpatch (< 5 lines)
  SMALL  — single-file change with clear scope (5–50 lines)
  MEDIUM — multi-file change, moderate complexity (50–300 lines)
  LARGE  — multi-component change, new feature (300–1000 lines)
  EPIC   — architectural change, cross-cutting concern (1000+ lines)

Usage::

    from hlf_mcp.hlf.task_classifier import classify_intent, task_envelope_to_workload

    envelope = classify_intent("write unit tests for the parser module")
    workload  = task_envelope_to_workload(envelope)   # → "verification_task"
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)

# Ordinal ordering for TaskSize (StrEnum comparison is lexicographic, not ordinal)
_SIZE_ORDER: dict[str, int] = {
    "micro": 0, "small": 1, "medium": 2, "large": 3, "epic": 4,
}


def _size_max(a: "TaskSize", b: "TaskSize") -> "TaskSize":
    """Return the larger of two TaskSize values by ordinal rank."""
    return a if _SIZE_ORDER[a] >= _SIZE_ORDER[b] else b


def _size_min(a: "TaskSize", b: "TaskSize") -> "TaskSize":
    """Return the smaller of two TaskSize values by ordinal rank."""
    return a if _SIZE_ORDER[a] <= _SIZE_ORDER[b] else b


# --------------------------------------------------------------------------- #
# Enumerations
# --------------------------------------------------------------------------- #


class TaskSize(StrEnum):
    """Task sizing for effort estimation and routing."""
    MICRO = "micro"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    EPIC = "epic"


class TaskCategory(StrEnum):
    """Broad task categories for agent routing."""
    CODE = "code"               # File create/modify/refactor/delete
    BUILD = "build"             # Tests, lint, syntax, validation
    DEPLOY = "deploy"           # Deployment, CI/CD, release
    BROWSER = "browser"         # BrowserOS navigation, search, workflow
    RESEARCH = "research"       # Web search, knowledge retrieval, analysis
    DOCS = "docs"               # Documentation generation/update
    SHELL = "shell"             # Shell command execution
    API = "api"                 # External API calls
    ORCHESTRATE = "orchestrate" # Multi-step plans, DAGs
    GOVERNANCE = "governance"   # ALIGN checks, security scans, audits


class TaskLauncher(StrEnum):
    """Who/what dispatched this task.

    CRITICAL DESIGN RULE: The launcher is PROVENANCE ONLY.
    All agents follow identical ALIGN governance, gas metering,
    ALS audit logging, and sandbox constraints regardless of launcher.
    No agent may alter behavior based on launcher identity.
    """
    GATEWAY = "gateway"           # Sovereign Gateway Bus (HLF dispatch)
    OPENCLAW = "openclaw"         # OpenClaw summarization/analysis
    LOLLMS = "lollms"             # LoLLMs chatbot interface
    BROWSEROS = "browseros"       # BrowserOS MCP server
    JULES = "jules"               # Jules autonomous agent
    CLI = "cli"                   # CLI direct invocation
    HLF_RUNTIME = "hlf_runtime"   # HLF bytecode VM host functions
    MCP_CLIENT = "mcp_client"     # External MCP client
    MANUAL = "manual"             # Manual/interactive user action
    SCHEDULER = "scheduler"       # Scheduled/cron tasks
    CANARY = "canary"             # Canary agent health probes


# --------------------------------------------------------------------------- #
# Extended Task Types (Superset of PlanExecutor vocabulary)
# --------------------------------------------------------------------------- #


# Maps every recognized task type to its category and typical size
TASK_TYPE_REGISTRY: dict[str, dict[str, Any]] = {
    # ── CODE (CodeAgent) ──────────────────────────────────────────────
    "create_file":      {"category": TaskCategory.CODE,       "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "code-agent"},
    "modify_file":      {"category": TaskCategory.CODE,       "default_size": TaskSize.SMALL,  "gas": 4,  "agent": "code-agent"},
    "refactor":         {"category": TaskCategory.CODE,       "default_size": TaskSize.MEDIUM, "gas": 8,  "agent": "code-agent"},
    "delete_file":      {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "code-agent"},

    # ── MICRO CODE (CodeAgent — fast path) ────────────────────────────
    "micro_edit":       {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "hotpatch":         {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "quick_fix":        {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "config_edit":      {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "env_var":          {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "add_import":       {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},
    "rename_symbol":    {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "code-agent"},
    "toggle_flag":      {"category": TaskCategory.CODE,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "code-agent"},

    # ── BUILD (BuildAgent) ────────────────────────────────────────────
    "run_tests":        {"category": TaskCategory.BUILD,      "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "build-agent"},
    "run_lint":         {"category": TaskCategory.BUILD,      "default_size": TaskSize.SMALL,  "gas": 3,  "agent": "build-agent"},
    "validate_imports": {"category": TaskCategory.BUILD,      "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "build-agent"},
    "check_syntax":     {"category": TaskCategory.BUILD,      "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "build-agent"},
    "check_forbidden_calls": {"category": TaskCategory.BUILD, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "build-agent"},
    "check_import_rules":    {"category": TaskCategory.BUILD, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "build-agent"},
    "preflight":        {"category": TaskCategory.BUILD,      "default_size": TaskSize.MEDIUM, "gas": 10, "agent": "build-agent"},
    "security_scan":    {"category": TaskCategory.BUILD,      "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "build-agent"},

    # ── DEPLOY ────────────────────────────────────────────────────────
    "deploy_staging":   {"category": TaskCategory.DEPLOY,     "default_size": TaskSize.MEDIUM, "gas": 15, "agent": "deploy-agent"},
    "deploy_prod":      {"category": TaskCategory.DEPLOY,     "default_size": TaskSize.LARGE,  "gas": 25, "agent": "deploy-agent"},
    "git_commit":       {"category": TaskCategory.DEPLOY,     "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "deploy-agent"},
    "git_push":         {"category": TaskCategory.DEPLOY,     "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "deploy-agent"},
    "create_pr":        {"category": TaskCategory.DEPLOY,     "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "deploy-agent"},
    "release":          {"category": TaskCategory.DEPLOY,     "default_size": TaskSize.MEDIUM, "gas": 12, "agent": "deploy-agent"},

    # ── BROWSER (BrowserOS) ───────────────────────────────────────────
    "browser_navigate": {"category": TaskCategory.BROWSER,    "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "browser-agent"},
    "browser_search":   {"category": TaskCategory.BROWSER,    "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "browser-agent"},
    "browser_workflow": {"category": TaskCategory.BROWSER,    "default_size": TaskSize.MEDIUM, "gas": 8,  "agent": "browser-agent"},
    "browser_cowork":   {"category": TaskCategory.BROWSER,    "default_size": TaskSize.MEDIUM, "gas": 10, "agent": "browser-agent"},
    "browser_extract":  {"category": TaskCategory.BROWSER,    "default_size": TaskSize.SMALL,  "gas": 3,  "agent": "browser-agent"},

    # ── RESEARCH ──────────────────────────────────────────────────────
    "web_search":       {"category": TaskCategory.RESEARCH,   "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "research-agent"},
    "knowledge_query":  {"category": TaskCategory.RESEARCH,   "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "research-agent"},
    "summarize":        {"category": TaskCategory.RESEARCH,   "default_size": TaskSize.SMALL,  "gas": 4,  "agent": "research-agent"},
    "analyze":          {"category": TaskCategory.RESEARCH,   "default_size": TaskSize.MEDIUM, "gas": 6,  "agent": "research-agent"},
    "deep_research":    {"category": TaskCategory.RESEARCH,   "default_size": TaskSize.LARGE,  "gas": 20, "agent": "research-agent"},
    "convergence_analysis": {"category": TaskCategory.RESEARCH, "default_size": TaskSize.MEDIUM, "gas": 12, "agent": "research-agent"},

    # ── DOCS ──────────────────────────────────────────────────────────
    "update_readme":    {"category": TaskCategory.DOCS,       "default_size": TaskSize.SMALL,  "gas": 3,  "agent": "docs-agent"},
    "generate_docs":    {"category": TaskCategory.DOCS,       "default_size": TaskSize.MEDIUM, "gas": 8,  "agent": "docs-agent"},
    "update_changelog": {"category": TaskCategory.DOCS,       "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "docs-agent"},
    "write_docstring":  {"category": TaskCategory.DOCS,       "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "docs-agent"},

    # ── SHELL ─────────────────────────────────────────────────────────
    "run_command":      {"category": TaskCategory.SHELL,      "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "shell-agent"},
    "install_package":  {"category": TaskCategory.SHELL,      "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "shell-agent"},
    "run_script":       {"category": TaskCategory.SHELL,      "default_size": TaskSize.SMALL,  "gas": 5,  "agent": "shell-agent"},

    # ── API ───────────────────────────────────────────────────────────
    "api_call":         {"category": TaskCategory.API,        "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "api-agent"},
    "mcp_invoke":       {"category": TaskCategory.API,        "default_size": TaskSize.MICRO,  "gas": 3,  "agent": "api-agent"},

    # ── GOVERNANCE ────────────────────────────────────────────────────
    "align_check":      {"category": TaskCategory.GOVERNANCE, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "governance-agent"},
    "audit_log":        {"category": TaskCategory.GOVERNANCE, "default_size": TaskSize.MICRO,  "gas": 1,  "agent": "governance-agent"},
    "policy_check":     {"category": TaskCategory.GOVERNANCE, "default_size": TaskSize.MICRO,  "gas": 2,  "agent": "governance-agent"},

    # ── ORCHESTRATE ───────────────────────────────────────────────────
    "execute_plan":     {"category": TaskCategory.ORCHESTRATE, "default_size": TaskSize.LARGE,  "gas": 20, "agent": "plan-executor"},
}

# Task types that qualify for the micro fast-path (skip DAG overhead)
FAST_PATH_TYPES: set[str] = {
    k for k, v in TASK_TYPE_REGISTRY.items()
    if v["default_size"] == TaskSize.MICRO
}


# --------------------------------------------------------------------------- #
# Task Envelope (Classification Result)
# --------------------------------------------------------------------------- #


@dataclass
class TaskEnvelope:
    """Result of task classification — wraps a task dict with routing metadata.

    INVARIANT: The launcher field is provenance-only. All agents follow
    identical ALIGN governance, gas metering, ALS audit logging, and
    sandbox constraints regardless of launcher identity.

    Attributes:
        task: The original task specification.
        task_type: Resolved task type string.
        category: Broad category for agent routing.
        size: Estimated effort level.
        estimated_gas: Predicted gas cost.
        agent_target: Which agent should handle this.
        launcher: Who/what dispatched this task (provenance only).
        fast_path: Whether to skip DAG orchestration.
        confidence: 0.0-1.0 confidence in the classification.
        reasoning: Human-readable explanation of classification.
    """
    task: dict[str, Any]
    task_type: str
    category: TaskCategory
    size: TaskSize
    estimated_gas: int
    agent_target: str
    launcher: TaskLauncher = field(default=TaskLauncher.MANUAL)
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
# Classification Logic
# --------------------------------------------------------------------------- #


def classify_task(
    task: dict[str, Any],
    launcher: TaskLauncher = TaskLauncher.MANUAL,
) -> TaskEnvelope:
    """Classify a task dict into a TaskEnvelope with size, category, and routing.

    The classifier resolves the task type, estimates size from content heuristics,
    determines the target agent, and decides whether the micro fast-path applies.

    The launcher parameter is PROVENANCE ONLY — it records who dispatched the
    task but does NOT alter how the task is processed. All tasks receive
    identical ALIGN governance, gas metering, and sandbox constraints.

    Args:
        task: Task specification with at minimum a 'type' field.
        launcher: Who/what dispatched this task (default: MANUAL).

    Returns:
        TaskEnvelope with full classification metadata.
    """
    task_type = task.get("type", "")

    # ── Known type ────────────────────────────────────────────────────
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

    # ── Heuristic classification for unknown types ────────────────────
    return _heuristic_classify(task, task_type, launcher)


def classify_intent(
    intent_text: str,
    launcher: TaskLauncher = TaskLauncher.MANUAL,
) -> TaskEnvelope:
    """Classify a natural-language intent into a TaskEnvelope.

    Uses keyword matching and pattern detection to determine the most
    likely task type, category, and size from a free-text description.

    Args:
        intent_text: Natural-language description of the task.
        launcher: Who/what dispatched this task (default: MANUAL).

    Returns:
        TaskEnvelope with heuristic classification.
    """
    text = intent_text.lower().strip()

    # ── Pattern matching (ordered by specificity) ─────────────────────
    patterns: list[tuple[str, str]] = [
        # Micro-code patterns
        (r"\b(fix|patch|hotfix|one-?liner)\b", "quick_fix"),
        (r"\b(rename|rename\s+\w+\s+to)\b", "rename_symbol"),
        (r"\b(add\s+import|import\s+\w+)\b", "add_import"),
        (r"\b(toggle|enable|disable)\s+(flag|feature|setting)\b", "toggle_flag"),
        (r"\b(set|change|update)\s+(env|environment)\s*(var|variable)?\b", "env_var"),
        (r"\b(edit|change|update)\s*(config|conf|settings|yaml|json|toml)\b", "config_edit"),

        # Code patterns
        (r"\b(create|new|add)\s+(file|module|class|component)\b", "create_file"),
        (r"\b(modify|edit|change|update)\s+(file|code|function|method)\b", "modify_file"),
        (r"\b(refactor|restructure|reorganize|extract)\b", "refactor"),
        (r"\b(delete|remove)\s+(file|module)\b", "delete_file"),

        # Build/verify patterns
        (r"\b(run|execute)\s+(?:\w+\s+)*(test|tests|pytest|unittest)\b", "run_tests"),
        (r"\b(lint|ruff|flake8|pylint)\b", "run_lint"),
        (r"\b(check\s+syntax|syntax\s+check|parse)\b", "check_syntax"),
        (r"\b(preflight|pre-?flight|full\s+check)\b", "preflight"),
        (r"\b(security|vuln|vulnerability)\s*(scan|check|audit)\b", "security_scan"),

        # Deploy patterns
        (r"\b(deploy|deployment)\s*(?:\w+\s+)*(staging|stage)\b", "deploy_staging"),
        (r"\b(deploy|deployment)\s*(?:\w+\s+)*(prod|production)\b", "deploy_prod"),
        (r"\b(commit|git\s+commit)\b", "git_commit"),
        (r"\b(push|git\s+push)\b", "git_push"),
        (r"\b(create|open)\s*(?:\w+\s+)*(pr|pull\s*request)\b", "create_pr"),
        (r"\b(release|tag|version\s+bump)\b", "release"),

        # Browser patterns
        (r"\b(navigate|go\s+to|open)\s+(?:\w+\s+)*(url|page|site|website)\b", "browser_navigate"),
        (r"\b(search|look\s+up|find)\s+(?:\w+\s+)*(web|online|google)\b", "browser_search"),
        (r"\b(workflow|automate)\s+(?:\w+\s+)*(browser|browseros)\b", "browser_workflow"),
        (r"\b(cowork|filesystem)\s+(?:\w+\s+)*(browser|browseros)\b", "browser_cowork"),
        (r"\b(extract|scrape|get\s+content)\s+(?:\w+\s+)*(page|web)\b", "browser_extract"),

        # Research patterns
        (r"\b(research|investigate|explore)\b", "analyze"),
        (r"\b(summarize|summary|tldr)\b", "summarize"),
        (r"\b(search|query)\s+(?:\w+\s+)*(knowledge|memory|docs)\b", "knowledge_query"),

        # Docs patterns
        (r"\b(update|write|edit)\s+(?:\w+\s+)*(readme|documentation|docs)\b", "update_readme"),
        (r"\b(generate|create)\s+(?:\w+\s+)*(docs|documentation|api\s+docs)\b", "generate_docs"),
        (r"\b(changelog|release\s+notes)\b", "update_changelog"),
        (r"\b(docstring|docstrings|jsdoc)\b", "write_docstring"),

        # Shell patterns
        (r"\b(run|execute)\s+(?:\w+\s+)*(command|cmd|script|bash|shell|powershell)\b", "run_command"),
        (r"\b(install|pip\s+install|npm\s+install)\b", "install_package"),

        # API patterns
        (r"\b(call|invoke|request)\s+(api|endpoint|service)\b", "api_call"),
        (r"\b(mcp|tool)\s+(call|invoke)\b", "mcp_invoke"),

        # Governance patterns
        (r"\b(align|governance|compliance)\s*(check|audit|verify)\b", "align_check"),
        (r"\b(policy|rule)\s*(check|enforce|verify)\b", "policy_check"),
    ]

    for pattern, task_type in patterns:
        if re.search(pattern, text):
            entry = TASK_TYPE_REGISTRY[task_type]
            task_dict = {"type": task_type, "description": intent_text}
            size = entry["default_size"]

            return TaskEnvelope(
                task=task_dict,
                task_type=task_type,
                category=entry["category"],
                size=size,
                estimated_gas=entry["gas"],
                agent_target=entry["agent"],
                launcher=launcher,
                fast_path=(size == TaskSize.MICRO),
                confidence=0.7,
                reasoning=f"Pattern matched '{pattern}' → '{task_type}'",
            )

    # ── Fallback: unknown intent ──────────────────────────────────────
    # Estimate size from word count
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


def get_task_types_for_category(category: TaskCategory) -> list[str]:
    """Return all registered task types for a given category."""
    return [
        k for k, v in TASK_TYPE_REGISTRY.items()
        if v["category"] == category
    ]


def get_all_categories() -> list[str]:
    """Return all task categories."""
    return [c.value for c in TaskCategory]


def get_vocabulary_summary() -> dict[str, Any]:
    """Return a structured summary of the full task vocabulary.

    Useful for introspection, help text, and agent self-documentation.
    """
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


# --------------------------------------------------------------------------- #
# Internal Helpers
# --------------------------------------------------------------------------- #


def _estimate_size(task: dict[str, Any], default: TaskSize) -> TaskSize:
    """Refine the default size based on task content heuristics."""
    # Explicit override
    explicit = task.get("size", "")
    if explicit:
        try:
            return TaskSize(explicit)
        except ValueError:
            pass

    # Content-length heuristic
    content = task.get("content", "")
    if content:
        lines = len(content.splitlines())
        if lines <= 3:
            return TaskSize.MICRO
        elif lines <= 50:
            return _size_min(default, TaskSize.SMALL)
        elif lines <= 300:
            return _size_max(default, TaskSize.MEDIUM)
        elif lines <= 1000:
            return _size_max(default, TaskSize.LARGE)
        else:
            return TaskSize.EPIC

    # Changes-count heuristic (for modify_file)
    changes = task.get("changes", [])
    if changes:
        if len(changes) == 1:
            return TaskSize.MICRO
        elif len(changes) <= 3:
            return _size_min(default, TaskSize.SMALL)
        elif len(changes) > 5:
            return _size_max(default, TaskSize.MEDIUM)

    # File-count heuristic (for refactors)
    files = task.get("files", [])
    if len(files) > 5:
        return _size_max(default, TaskSize.LARGE)

    return default


def _heuristic_classify(
    task: dict[str, Any],
    task_type: str,
    launcher: TaskLauncher = TaskLauncher.MANUAL,
) -> TaskEnvelope:
    """Classify an unknown task type using content heuristics."""
    has_path = bool(task.get("path", ""))
    has_content = bool(task.get("content", ""))
    has_changes = bool(task.get("changes", []))
    has_command = bool(task.get("command", ""))
    has_url = bool(task.get("url", ""))

    if has_path and (has_content or has_changes):
        category = TaskCategory.CODE
        agent = "code-agent"
    elif has_path and not has_content:
        category = TaskCategory.BUILD
        agent = "build-agent"
    elif has_command:
        category = TaskCategory.SHELL
        agent = "shell-agent"
    elif has_url:
        category = TaskCategory.BROWSER
        agent = "browser-agent"
    else:
        category = TaskCategory.CODE
        agent = "code-agent"

    size = _estimate_size(task, TaskSize.SMALL)

    return TaskEnvelope(
        task=task,
        task_type=task_type or "unknown",
        category=category,
        size=size,
        estimated_gas=5,
        agent_target=agent,
        launcher=launcher,
        fast_path=(size == TaskSize.MICRO),
        confidence=0.5,
        reasoning=f"Heuristic: path={has_path}, content={has_content}, "
                  f"cmd={has_command}, url={has_url}",
    )


# --------------------------------------------------------------------------- #
# HLF Workload Bridge
# --------------------------------------------------------------------------- #

# Maps TaskCategory → HLF Workload string (used by governed_routing.py and
# server_profiles.py).  The mapping is category-level; fine-grained override
# by task_type happens in task_envelope_to_workload().
_CATEGORY_TO_WORKLOAD: dict[TaskCategory, str] = {
    TaskCategory.CODE:       "code_completion",
    TaskCategory.BUILD:      "verification_task",
    TaskCategory.DEPLOY:     "doer_task",
    TaskCategory.BROWSER:    "universal_query",
    TaskCategory.RESEARCH:   "analysis_task",
    TaskCategory.DOCS:       "universal_query",
    TaskCategory.SHELL:      "doer_task",
    TaskCategory.API:        "reasoning_query",
    TaskCategory.ORCHESTRATE: "planning_task",
    TaskCategory.GOVERNANCE: "ethics_review",
}

# Task-type-level overrides that are more precise than category allows
_TASK_TYPE_TO_WORKLOAD: dict[str, str] = {
    # Planning tasks → planning lane
    "execute_plan": "planning_task",
    "create_pr":    "planning_task",
    "release":      "planning_task",

    # Analysis tasks → analysis lane
    "analyze":             "analysis_task",
    "deep_research":       "analysis_task",
    "convergence_analysis": "analysis_task",
    "summarize":           "analysis_task",

    # Security / governance → ethics lane
    "align_check":   "ethics_review",
    "policy_check":  "ethics_review",
    "security_scan": "ethics_review",

    # Doer tasks (execution-heavy)
    "deploy_staging": "doer_task",
    "deploy_prod":    "doer_task",
    "run_command":    "doer_task",
    "run_script":     "doer_task",
    "install_package": "doer_task",

    # Reasoning-heavy
    "api_call":    "reasoning_query",
    "mcp_invoke":  "reasoning_query",

    # Verification
    "run_tests":         "verification_task",
    "run_lint":          "verification_task",
    "preflight":         "verification_task",
    "validate_imports":  "verification_task",
    "check_syntax":      "verification_task",
    "check_forbidden_calls": "verification_task",
    "check_import_rules":    "verification_task",
}


def task_envelope_to_workload(envelope: TaskEnvelope) -> str:
    """Map a TaskEnvelope to an HLF Workload string.

    Resolution order:
      1. task_type-level override (_TASK_TYPE_TO_WORKLOAD)
      2. category-level default (_CATEGORY_TO_WORKLOAD)
      3. "universal_query" fallback

    Returns:
        One of the Workload string literals used by governed_routing.py
        and server_profiles.py.
    """
    if envelope.task_type in _TASK_TYPE_TO_WORKLOAD:
        return _TASK_TYPE_TO_WORKLOAD[envelope.task_type]
    return _CATEGORY_TO_WORKLOAD.get(envelope.category, "universal_query")
