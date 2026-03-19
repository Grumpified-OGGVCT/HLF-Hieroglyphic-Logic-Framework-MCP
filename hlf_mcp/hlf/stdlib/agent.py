"""HLF stdlib: agent module — agent identity and goal management."""

from __future__ import annotations

import os


def AGENT_ID() -> str:
    return os.environ.get("HLF_AGENT_ID", "hlf-agent-default")


def AGENT_TIER() -> str:
    return os.environ.get("HLF_TIER", "hearth")


def AGENT_CAPABILITIES() -> list[str]:
    caps = os.environ.get("HLF_CAPABILITIES", "read,write,analyze")
    return [c.strip() for c in caps.split(",") if c.strip()]


_goals: list[str] = []


def SET_GOAL(goal: str) -> bool:
    _goals.append(goal)
    return True


def GET_GOALS() -> list[str]:
    return list(_goals)


def COMPLETE_GOAL(goal_id: str) -> bool:
    global _goals
    _goals = [g for g in _goals if g != goal_id]
    return True
