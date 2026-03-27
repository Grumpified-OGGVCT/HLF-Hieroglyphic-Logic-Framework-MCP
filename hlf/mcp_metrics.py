"""
Legacy MCP metrics for HLF.

Tracks usage statistics, test results, and improvement suggestions for the
older MCP/provider stack.

Keep this module for compatibility and historical reporting, but prefer the
packaged `hlf_mcp` line when defining current product metrics behavior.
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime
import threading

@dataclass
class UsageMetric:
    """Single usage event."""
    timestamp: float
    tool_name: str
    success: bool
    gas_used: int = 0
    duration_ms: float = 0.0
    error: str = ""
    tier: str = "unknown"
    profile: str = "unknown"

@dataclass
class TestResult:
    """Test execution result."""
    test_name: str
    timestamp: float
    passed: bool
    duration_ms: float
    error: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ImprovementSuggestion:
    """User/agent submitted improvement suggestion."""
    id: str
    timestamp: float
    source: str  # "user" or "agent"
    category: str  # "grammar", "tool", "performance", "docs"
    title: str
    description: str
    priority: int  # 1-5, 5 highest
    status: str  # "open", "in_progress", "resolved", "rejected"
    votes: int = 0
    submitter_tier: str = "unknown"

@dataclass
class EvidenceFact:
    """Governed evidence fact linking routing decision → execution → outcome.
    
    Used for:
    1. Proving the path from intent classification to final result
    2. Tracking whether execution matched routing predictions
    3. Supporting governed evidence facts with full audit trail
    4. Enabling promotion/demotion of HKS exemplars based on fidelity
    """
    fact_id: str
    timestamp: float
    task_type: str
    task_category: str
    task_size: str
    workload_string: str
    selected_lane: str
    routing_decision: str  # "allow", "deny", "advisory", etc.
    routing_allowed: bool
    predicted_primary_model: str
    actual_model_used: str
    actual_provider_used: str
    predicted_primary_matched: bool
    escalation_depth: int
    escalation_attempts: int
    advisory_mode: bool
    governance_mode: str
    deployment_tier: str
    latency_s: float = 0.0
    rationale: str = ""
    policy_constraints: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

class HLFMetrics:
    """
    Metrics collection and reporting for the legacy HLF MCP stack.
    
    Usage:
        metrics = HLFMetrics(metrics_dir=Path.home() / '.sovereign' / 'metrics')
        
        # Record tool usage
        metrics.record_usage("hlf_compile", success=True, gas_used=100, duration_ms=50)
        
        # Record test result
        metrics.record_test("compile_basic", passed=True, duration_ms=10)
        
        # Submit improvement
        metrics.suggest_improvement(
            source="user",
            category="grammar",
            title="Add async effect type",
            description="Need effect type for async operations",
            priority=4
        )
        
        # Get stats
        stats = metrics.get_stats()
    """
    
    def __init__(self, metrics_dir: Path = None):
        self.metrics_dir = metrics_dir or (Path.home() / '.sovereign' / 'metrics')
        self.metrics_dir.mkdir(parents=True, exist_ok=True)
        
        self.usage_file = self.metrics_dir / 'usage.jsonl'
        self.tests_file = self.metrics_dir / 'tests.jsonl'
        self.suggestions_file = self.metrics_dir / 'suggestions.jsonl'
        self.stats_file = self.metrics_dir / 'stats.json'
        self.evidence_facts_file = self.metrics_dir / 'evidence_facts.jsonl'
        
        self._lock = threading.Lock()
        
        # In-memory stats
        self._stats = {
            "total_uses": 0,
            "successful_uses": 0,
            "failed_uses": 0,
            "total_gas_used": 0,
            "total_duration_ms": 0.0,
            "tools_used": {},
            "errors_seen": {},
            "tests_passed": 0,
            "tests_failed": 0,
            "suggestions_open": 0,
            "suggestions_resolved": 0,
            "sessions": 0,
            "first_use": None,
            "last_use": None,
            "evidence_facts_recorded": 0,
            "evidence_facts_predictions_matched": 0,
            "evidence_facts_escalated": 0,
            "evidence_facts_advisory": 0,
        }
        
        self._load_stats()
    
    def _load_stats(self):
        """Load existing stats from file."""
        if self.stats_file.exists():
            try:
                data = json.loads(self.stats_file.read_text())
                self._stats.update(data)
            except:
                pass
    
    def _save_stats(self):
        """Save stats to file."""
        with self._lock:
            self.stats_file.write_text(json.dumps(self._stats, indent=2))
    
    def record_usage(
        self,
        tool_name: str,
        success: bool,
        gas_used: int = 0,
        duration_ms: float = 0.0,
        error: str = "",
        tier: str = "unknown",
        profile: str = "unknown"
    ) -> str:
        """Record a tool usage event."""
        
        metric = UsageMetric(
            timestamp=time.time(),
            tool_name=tool_name,
            success=success,
            gas_used=gas_used,
            duration_ms=duration_ms,
            error=error,
            tier=tier,
            profile=profile
        )
        
        # Append to usage log
        with self.usage_file.open('a') as f:
            f.write(json.dumps(asdict(metric)) + '\n')
        
        # Update stats
        with self._lock:
            self._stats["total_uses"] += 1
            if success:
                self._stats["successful_uses"] += 1
            else:
                self._stats["failed_uses"] += 1
            
            self._stats["total_gas_used"] += gas_used
            self._stats["total_duration_ms"] += duration_ms
            
            if tool_name not in self._stats["tools_used"]:
                self._stats["tools_used"][tool_name] = 0
            self._stats["tools_used"][tool_name] += 1
            
            if error:
                if error not in self._stats["errors_seen"]:
                    self._stats["errors_seen"][error] = 0
                self._stats["errors_seen"][error] += 1
            
            if self._stats["first_use"] is None:
                self._stats["first_use"] = metric.timestamp
            self._stats["last_use"] = metric.timestamp
        
        self._save_stats()
        
        return f"usage_{int(metric.timestamp)}"
    
    def record_test(
        self,
        test_name: str,
        passed: bool,
        duration_ms: float,
        error: str = "",
        details: Dict[str, Any] = None
    ) -> str:
        """Record a test result."""
        
        result = TestResult(
            test_name=test_name,
            timestamp=time.time(),
            passed=passed,
            duration_ms=duration_ms,
            error=error,
            details=details or {}
        )
        
        # Append to tests log
        with self.tests_file.open('a') as f:
            f.write(json.dumps(asdict(result)) + '\n')
        
        # Update stats
        with self._lock:
            if passed:
                self._stats["tests_passed"] += 1
            else:
                self._stats["tests_failed"] += 1
        
        self._save_stats()
        
        return f"test_{int(result.timestamp)}"
    
    def suggest_improvement(
        self,
        source: str,
        category: str,
        title: str,
        description: str,
        priority: int = 3,
        submitter_tier: str = "unknown"
    ) -> str:
        """Submit an improvement suggestion."""
        
        import hashlib
        
        suggestion_id = hashlib.sha256(
            f"{title}:{time.time()}".encode()
        ).hexdigest()[:8]
        
        suggestion = ImprovementSuggestion(
            id=suggestion_id,
            timestamp=time.time(),
            source=source,
            category=category,
            title=title,
            description=description,
            priority=max(1, min(5, priority)),
            status="open",
            votes=0,
            submitter_tier=submitter_tier
        )
        
        # Append to suggestions log
        with self.suggestions_file.open('a') as f:
            f.write(json.dumps(asdict(suggestion)) + '\n')
        
        # Update stats
        with self._lock:
            self._stats["suggestions_open"] += 1
        
        self._save_stats()
        
        return suggestion_id
    
    def vote_improvement(self, suggestion_id: str, vote: int = 1) -> bool:
        """Vote for an improvement suggestion."""
        
        if not self.suggestions_file.exists():
            return False
        
        suggestions = []
        found = False
        
        with self.suggestions_file.open('r') as f:
            for line in f:
                sugg = json.loads(line.strip())
                if sugg["id"] == suggestion_id:
                    sugg["votes"] += vote
                    found = True
                suggestions.append(sugg)
        
        if found:
            with self.suggestions_file.open('w') as f:
                for sugg in suggestions:
                    f.write(json.dumps(sugg) + '\n')
        
        return found

    def record_evidence_fact(
        self,
        task_type: str,
        task_category: str,
        task_size: str,
        workload_string: str,
        selected_lane: str,
        routing_decision: str,
        routing_allowed: bool,
        predicted_primary_model: str,
        actual_model_used: str,
        actual_provider_used: str,
        predicted_primary_matched: bool,
        escalation_depth: int,
        escalation_attempts: int,
        advisory_mode: bool,
        governance_mode: str,
        deployment_tier: str,
        latency_s: float = 0.0,
        rationale: str = "",
        policy_constraints: str = "",
        details: Dict[str, Any] = None,
    ) -> str:
        """Record a governed evidence fact linking routing → execution → outcome.
        
        Parameters
        ----------
        task_type : str
            The task type (e.g. "code_completion", "reasoning_query")
        task_category : str
            Task category (e.g. "generation", "analysis")
        task_size : str
            Task size estimate ("small", "medium", "large")
        workload_string : str
            Classified workload type
        selected_lane : str
            The execution lane decided by routing
        routing_decision : str
            The routing verdict decision ("allow", "deny", "advisory", etc.)
        routing_allowed : bool
            Whether routing authorized execution
        predicted_primary_model : str
            Model predicted by routing
        actual_model_used : str
            Model actually used for execution
        actual_provider_used : str
            Provider actually used ("ollama" | "openrouter")
        predicted_primary_matched : bool
            Whether prediction matched actual execution
        escalation_depth : int
            How many fallbacks were needed (0 = primary succeeded)
        escalation_attempts : int
            Total number of execution attempts
        advisory_mode : bool
            Whether execution proceeded in advisory mode despite denial
        governance_mode : str
            Governance posture used
        deployment_tier : str
            Execution tier used
        latency_s : float
            Wall-clock execution time
        rationale : str
            Routing rationale explanation
        policy_constraints : str
            Policy constraints that applied
        details : dict | None
            Additional contextual details

        Returns
        -------
        str
            Fact ID for tracking
        """
        import hashlib

        fact_id = hashlib.sha256(
            f"{task_type}:{workload_string}:{time.time()}".encode()
        ).hexdigest()[:12]

        fact = EvidenceFact(
            fact_id=fact_id,
            timestamp=time.time(),
            task_type=task_type,
            task_category=task_category,
            task_size=task_size,
            workload_string=workload_string,
            selected_lane=selected_lane,
            routing_decision=routing_decision,
            routing_allowed=routing_allowed,
            predicted_primary_model=predicted_primary_model,
            actual_model_used=actual_model_used,
            actual_provider_used=actual_provider_used,
            predicted_primary_matched=predicted_primary_matched,
            escalation_depth=escalation_depth,
            escalation_attempts=escalation_attempts,
            advisory_mode=advisory_mode,
            governance_mode=governance_mode,
            deployment_tier=deployment_tier,
            latency_s=latency_s,
            rationale=rationale,
            policy_constraints=policy_constraints,
            details=details or {},
        )

        # Append to evidence facts log
        with self.evidence_facts_file.open('a') as f:
            f.write(json.dumps(asdict(fact)) + '\n')

        # Update stats
        with self._lock:
            self._stats["evidence_facts_recorded"] += 1
            if predicted_primary_matched:
                self._stats["evidence_facts_predictions_matched"] += 1
            if escalation_depth > 0:
                self._stats["evidence_facts_escalated"] += 1
            if advisory_mode:
                self._stats["evidence_facts_advisory"] += 1

        self._save_stats()

        return fact_id
    
    
    def resolve_improvement(self, suggestion_id: str, status: str = "resolved") -> bool:
        """Mark an improvement as resolved or rejected."""
        
        if not self.suggestions_file.exists():
            return False
        
        suggestions = []
        found = False
        
        with self.suggestions_file.open('r') as f:
            for line in f:
                sugg = json.loads(line.strip())
                if sugg["id"] == suggestion_id:
                    sugg["status"] = status
                    found = True
                suggestions.append(sugg)
        
        if found:
            with self.suggestions_file.open('w') as f:
                for sugg in suggestions:
                    f.write(json.dumps(sugg) + '\n')
            
            with self._lock:
                self._stats["suggestions_open"] -= 1
                if status in ("resolved", "rejected"):
                    self._stats["suggestions_resolved"] += 1
            
            self._save_stats()
        
        return found
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return dict(self._stats)
    
    def get_recent_usage(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent usage events."""
        
        if not self.usage_file.exists():
            return []
        
        events = []
        with self.usage_file.open('r') as f:
            for line in f:
                events.append(json.loads(line.strip()))
        
        return events[-limit:]
    
    def get_open_suggestions(self) -> List[Dict[str, Any]]:
        """Get open improvement suggestions."""
        
        if not self.suggestions_file.exists():
            return []
        
        suggestions = []
        with self.suggestions_file.open('r') as f:
            for line in f:
                sugg = json.loads(line.strip())
                if sugg["status"] == "open":
                    suggestions.append(sugg)
        
        return sorted(suggestions, key=lambda x: (-x["priority"], -x["votes"]))
    
    def get_test_results(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent test results."""
        
        if not self.tests_file.exists():
            return []
        
        results = []
        with self.tests_file.open('r') as f:
            for line in f:
                results.append(json.loads(line.strip()))
        
        return results[-limit:]
    
    def record_session(self):
        """Record a new session."""
        with self._lock:
            self._stats["sessions"] += 1
        self._save_stats()
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get a health report."""
        
        stats = self.get_stats()
        
        # Calculate health score
        total = stats["total_uses"]
        success_rate = stats["successful_uses"] / total if total > 0 else 1.0
        test_pass_rate = (
            stats["tests_passed"] / (stats["tests_passed"] + stats["tests_failed"])
            if (stats["tests_passed"] + stats["tests_failed"]) > 0
            else 1.0
        )
        
        health_score = (success_rate * 0.5 + test_pass_rate * 0.5) * 100
        
        return {
            "health_score": round(health_score, 1),
            "success_rate": round(success_rate * 100, 1),
            "test_pass_rate": round(test_pass_rate * 100, 1),
            "total_uses": total,
            "total_gas_used": stats["total_gas_used"],
            "avg_duration_ms": round(stats["total_duration_ms"] / total, 2) if total > 0 else 0,
            "open_suggestions": stats["suggestions_open"],
            "errors_count": len(stats["errors_seen"]),
            "top_tools": sorted(
                stats["tools_used"].items(),
                key=lambda x: -x[1]
            )[:5]
        }
    
    def export_metrics(self, output_path: Path = None) -> Path:
        """Export all metrics to a JSON file."""
        
        output = output_path or (self.metrics_dir / 'metrics_export.json')
        
        data = {
            "exported_at": time.time(),
            "stats": self.get_stats(),
            "health": self.get_health_report(),
            "recent_usage": self.get_recent_usage(limit=1000),
            "recent_tests": self.get_test_results(limit=1000),
            "open_suggestions": self.get_open_suggestions()
        }
        
        output.write_text(json.dumps(data, indent=2))
        return output


# Singleton instance
_metrics_instance = None
_metrics_lock = threading.Lock()

def get_metrics(metrics_dir: Path = None) -> HLFMetrics:
    """Get or create the singleton metrics instance."""
    global _metrics_instance
    
    with _metrics_lock:
        if _metrics_instance is None:
            _metrics_instance = HLFMetrics(metrics_dir)
    
    return _metrics_instance


# Convenience functions that delegate to the singleton
def record_tool_call(tool_name: str, success: bool = True, duration_ms: float = 0, 
                     gas_used: int = 0, error: str = None, metadata: dict = None):
    """Record a tool call (convenience function)."""
    metrics = get_metrics()
    metrics.record_usage(
        tool_name=tool_name,
        success=success,
        gas_used=gas_used,
        duration_ms=duration_ms,
        error=error or ""
    )


def record_friction(failure_type: str, source_snippet: str, context: Dict = None):
    """Record a friction event (convenience function)."""
    metrics = get_metrics()
    metrics.record_usage(
        tool_name="friction_log",
        success=True,
        error=f"{failure_type}: {source_snippet[:100]}",
    )


def suggest_improvement(category: str, description: str, priority: int = 1,
                        source: str = "toolkit", title: str = "") -> str:
    """Suggest an improvement (convenience function)."""
    metrics = get_metrics()
    return metrics.suggest_improvement(
        source=source,
        category=category,
        title=title or description[:60],
        description=description,
        priority=priority,
    )


def record_test_result(test_name: str, success: bool, duration_ms: float = 0, error: str = None):
    """Record a test result (convenience function)."""
    metrics = get_metrics()
    metrics.record_test(test_name, success, duration_ms, error)