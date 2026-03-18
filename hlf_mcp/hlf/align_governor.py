from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


AlignAction = Literal["ALLOW", "WARN", "DROP", "DROP_AND_QUARANTINE", "ROUTE_TO_HUMAN_APPROVAL"]
AlignStatus = Literal["ok", "warning", "blocked"]

_DEFAULT_ALIGN_RULES_PATH = Path(__file__).resolve().parents[2] / "governance" / "align_rules.json"


@dataclass(slots=True, frozen=True)
class AlignRule:
    id: str
    name: str
    pattern: str
    action: AlignAction
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern,
            "action": self.action,
            "description": self.description,
        }


@dataclass(slots=True, frozen=True)
class AlignMatch:
    rule_id: str
    rule_name: str
    action: AlignAction
    description: str

    def to_dict(self) -> dict[str, str]:
        return {
            "rule_id": self.rule_id,
            "rule_name": self.rule_name,
            "action": self.action,
            "description": self.description,
        }


@dataclass(slots=True)
class AlignVerdict:
    allowed: bool
    status: AlignStatus
    action: str
    subject_hash: str
    decisive_rule_id: str = ""
    decisive_rule_name: str = ""
    decisive_rule_action: str = ""
    matches: list[AlignMatch] = field(default_factory=list)
    loaded_rule_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "status": self.status,
            "action": self.action,
            "subject_hash": self.subject_hash,
            "decisive_rule_id": self.decisive_rule_id,
            "decisive_rule_name": self.decisive_rule_name,
            "decisive_rule_action": self.decisive_rule_action,
            "matches": [match.to_dict() for match in self.matches],
            "loaded_rule_count": self.loaded_rule_count,
        }


class AlignGovernor:
    def __init__(self, rules_path: Path | None = None) -> None:
        self.rules_path = rules_path or _DEFAULT_ALIGN_RULES_PATH
        self._compiled_rules: list[tuple[AlignRule, re.Pattern[str]]] = []
        self.reload_rules()

    def reload_rules(self) -> int:
        if not self.rules_path.exists():
            self._compiled_rules = []
            return 0

        payload = json.loads(self.rules_path.read_text(encoding="utf-8"))
        rules = payload.get("rules", []) if isinstance(payload, dict) else []
        compiled_rules: list[tuple[AlignRule, re.Pattern[str]]] = []
        for raw_rule in rules:
            rule = AlignRule(
                id=str(raw_rule.get("id", "")),
                name=str(raw_rule.get("name", "")),
                pattern=str(raw_rule.get("pattern", "")),
                action=self._normalize_action(raw_rule.get("action")),
                description=str(raw_rule.get("description", "")),
            )
            if not rule.id or not rule.pattern:
                continue
            try:
                compiled_rules.append((rule, re.compile(rule.pattern, re.IGNORECASE)))
            except re.error:
                continue
        self._compiled_rules = compiled_rules
        return len(self._compiled_rules)

    def loaded_rules(self) -> list[dict[str, Any]]:
        return [rule.to_dict() for rule, _ in self._compiled_rules]

    def status_snapshot(self) -> dict[str, Any]:
        return {
            "rules_path": str(self.rules_path),
            "loaded_rule_count": len(self._compiled_rules),
            "rules": self.loaded_rules(),
            "normalized_actions": [
                "ALLOW",
                "WARN",
                "DROP",
                "DROP_AND_QUARANTINE",
                "ROUTE_TO_HUMAN_APPROVAL",
            ],
        }

    def evaluate(self, payload: str | dict[str, Any]) -> AlignVerdict:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True) if isinstance(payload, dict) else str(payload)
        subject_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        matches: list[AlignMatch] = []
        decisive_match: AlignMatch | None = None
        for rule, pattern in self._compiled_rules:
            if not pattern.search(text):
                continue
            match = AlignMatch(
                rule_id=rule.id,
                rule_name=rule.name,
                action=rule.action,
                description=rule.description,
            )
            matches.append(match)
            if decisive_match is None:
                decisive_match = match
            if rule.action in {"DROP", "DROP_AND_QUARANTINE"}:
                decisive_match = match
                break

        if decisive_match and decisive_match.action in {"DROP", "DROP_AND_QUARANTINE"}:
            return AlignVerdict(
                allowed=False,
                status="blocked",
                action=decisive_match.action,
                subject_hash=subject_hash,
                decisive_rule_id=decisive_match.rule_id,
                decisive_rule_name=decisive_match.rule_name,
                decisive_rule_action=decisive_match.action,
                matches=matches,
                loaded_rule_count=len(self._compiled_rules),
            )
        if decisive_match and decisive_match.action in {"WARN", "ROUTE_TO_HUMAN_APPROVAL"}:
            return AlignVerdict(
                allowed=True,
                status="warning",
                action=decisive_match.action,
                subject_hash=subject_hash,
                decisive_rule_id=decisive_match.rule_id,
                decisive_rule_name=decisive_match.rule_name,
                decisive_rule_action=decisive_match.action,
                matches=matches,
                loaded_rule_count=len(self._compiled_rules),
            )
        return AlignVerdict(
            allowed=True,
            status="ok",
            action="ALLOW",
            subject_hash=subject_hash,
            matches=matches,
            loaded_rule_count=len(self._compiled_rules),
        )

    @staticmethod
    def _normalize_action(raw_action: Any) -> AlignAction:
        normalized = str(raw_action or "allow").strip().lower()
        mapping = {
            "allow": "ALLOW",
            "ok": "ALLOW",
            "pass": "ALLOW",
            "warn": "WARN",
            "review": "ROUTE_TO_HUMAN_APPROVAL",
            "human_review": "ROUTE_TO_HUMAN_APPROVAL",
            "route_to_human_approval": "ROUTE_TO_HUMAN_APPROVAL",
            "block": "DROP",
            "deny": "DROP",
            "drop": "DROP",
            "drop_and_quarantine": "DROP_AND_QUARANTINE",
            "quarantine": "DROP_AND_QUARANTINE",
        }
        return mapping.get(normalized, "ALLOW")







