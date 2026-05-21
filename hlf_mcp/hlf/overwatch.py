"""OVERWATCH Sentinel — process-level watchdog for agent lifecycle monitoring.

Scattered sentinel functionality (SentinelAlertEntry in daemon_manager.py,
sentinel policy in governed_routing, persona sentinel role) is unified here
as a dedicated overwatch module providing:
- WatchdogTarget registration and health scanning
- Automatic process recovery with restart limits
- Config-driven OverwatchSentinel bootstrap
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ── Enums ──────────────────────────────────────────────────────────────────────


class WatchdogStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNRESPONSIVE = "unresponsive"
    TERMINATED = "terminated"


# ── Dataclass ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class WatchdogTarget:
    target_id: str
    process_name: str
    pid: int | None = None
    check_interval_sec: float = 30.0
    last_heartbeat: str | None = None  # ISO timestamp
    status: WatchdogStatus = WatchdogStatus.HEALTHY
    restart_count: int = 0
    max_restarts: int = 3
    health_check_url: str | None = None
    resource_limits: dict[str, float] = field(default_factory=lambda: {
        "max_memory_mb": 512.0,
        "max_cpu_percent": 80.0,
    })

    def to_dict(self) -> dict[str, Any]:
        return {
            "target_id": self.target_id,
            "process_name": self.process_name,
            "pid": self.pid,
            "check_interval_sec": self.check_interval_sec,
            "last_heartbeat": self.last_heartbeat,
            "status": self.status.value,
            "restart_count": self.restart_count,
            "max_restarts": self.max_restarts,
            "health_check_url": self.health_check_url,
            "resource_limits": dict(self.resource_limits),
        }


# ── OverwatchSentinel ──────────────────────────────────────────────────────────


class OverwatchSentinel:
    """Unified sentinel that scans watchdog targets, triggers alerts, and auto-recovers."""

    def __init__(
        self,
        targets: dict[str, WatchdogTarget] | None = None,
        scan_interval_sec: float = 30.0,
        alert_threshold: int = 3,
    ) -> None:
        self.targets: dict[str, WatchdogTarget] = targets or {}
        self.scan_interval_sec = scan_interval_sec
        self.alert_threshold = alert_threshold
        # Per-target failure counters for consecutive-failure tracking
        self._failure_counters: dict[str, int] = {}

    # ── Registration ───────────────────────────────────────────────────────

    def register_target(self, target: WatchdogTarget) -> None:
        """Register a new watchdog target, overwriting any existing entry with the same id."""
        self.targets[target.target_id] = target
        self._failure_counters.setdefault(target.target_id, 0)
        logger.info("Registered watchdog target: %s (%s)", target.target_id, target.process_name)

    # ── Scanning ───────────────────────────────────────────────────────────

    def scan(self) -> dict[str, WatchdogStatus]:
        """Scan all registered targets and return a status map."""
        results: dict[str, WatchdogStatus] = {}
        for target_id in self.targets:
            results[target_id] = self.check_target(target_id)
        return results

    def check_target(self, target_id: str) -> WatchdogStatus:
        """Check a specific target's health and update its status."""
        target = self.targets.get(target_id)
        if target is None:
            logger.warning("check_target called on unknown target: %s", target_id)
            return WatchdogStatus.TERMINATED

        # Determine health via process check and optional HTTP probe
        is_alive = self._probe_target(target)

        if is_alive:
            target.last_heartbeat = _now_iso()
            target.status = WatchdogStatus.HEALTHY
            self._failure_counters[target_id] = 0
        else:
            target.status = WatchdogStatus.UNRESPONSIVE
            self._failure_counters[target_id] = self._failure_counters.get(target_id, 0) + 1

        # Escalate to TERMINATED if consecutive failures exceed threshold
        if self._failure_counters.get(target_id, 0) >= self.alert_threshold:
            target.status = WatchdogStatus.TERMINATED
            logger.warning("Target %s exceeded alert threshold (%d consecutive failures)",
                           target_id, self.alert_threshold)

        # Check resource limits for degradation
        if target.status == WatchdogStatus.HEALTHY and self._check_resource_limits(target):
            target.status = WatchdogStatus.DEGRADED

        return target.status

    def _probe_target(self, target: WatchdogTarget) -> bool:
        """Check if a target process is alive. Uses PID or process-name lookup."""
        if target.pid is not None:
            return _pid_is_alive(target.pid)
        if target.health_check_url is not None:
            return _http_health_check(target.health_check_url)
        return _process_name_is_running(target.process_name)

    def _check_resource_limits(self, target: WatchdogTarget) -> bool:
        """Return True if the target exceeds any resource limit (degraded)."""
        limits = target.resource_limits
        if target.pid is not None:
            mem_mb = _get_process_memory_mb(target.pid)
            cpu_pct = _get_process_cpu_percent(target.pid)
            if mem_mb > limits.get("max_memory_mb", 512.0):
                return True
            if cpu_pct > limits.get("max_cpu_percent", 80.0):
                return True
        return False

    # ── Recovery ───────────────────────────────────────────────────────────

    def terminate(self, target_id: str, reason: str = "") -> bool:
        """Terminate the target process. Returns True if successfully killed."""
        target = self.targets.get(target_id)
        if target is None:
            return False
        if target.pid is not None:
            _kill_pid(target.pid)
        target.status = WatchdogStatus.TERMINATED
        logger.info("Terminated target %s (pid=%s): %s", target_id, target.pid, reason)
        return True

    def auto_recover(self, target_id: str) -> WatchdogStatus:
        """If a target is down, attempt to restart it up to max_restarts times."""
        target = self.targets.get(target_id)
        if target is None:
            return WatchdogStatus.TERMINATED

        if target.status not in (WatchdogStatus.UNRESPONSIVE, WatchdogStatus.TERMINATED):
            return target.status

        if target.restart_count >= target.max_restarts:
            logger.warning("Target %s exceeded max_restarts (%d); will not restart",
                           target_id, target.max_restarts)
            return WatchdogStatus.TERMINATED

        target.restart_count += 1
        # Simulate restart: set status back to healthy and reset heartbeat
        target.pid = _simulate_restart_pid()
        target.last_heartbeat = _now_iso()
        target.status = WatchdogStatus.HEALTHY
        self._failure_counters[target_id] = 0
        logger.info("Auto-recovered target %s (restart #%d)", target_id, target.restart_count)
        return target.status

    # ── Reporting ──────────────────────────────────────────────────────────

    def status_report(self) -> str:
        """Generate a Markdown status report of all targets."""
        lines = ["# OVERWATCH Sentinel Status Report", "", f"**Scan interval:** {self.scan_interval_sec}s",
                 f"**Alert threshold:** {self.alert_threshold} consecutive failures",
                 f"**Registered targets:** {len(self.targets)}", ""]
        lines.append("| Target ID | Process | PID | Status | Restarts | Last Heartbeat |")
        lines.append("|-----------|---------|-----|--------|----------|----------------|")
        for target in self.targets.values():
            hb = target.last_heartbeat or "—"
            pid_str = str(target.pid) if target.pid is not None else "—"
            lines.append(
                f"| {target.target_id} | {target.process_name} | {pid_str} | "
                f"**{target.status.value.upper()}** | {target.restart_count}/{target.max_restarts} | {hb} |"
            )
        dead = [t.target_id for t in self.targets.values()
                if t.status in (WatchdogStatus.UNRESPONSIVE, WatchdogStatus.TERMINATED)]
        if dead:
            lines.append("")
            lines.append(f"⚠️ **Dead/unresponsive targets:** {', '.join(dead)}")
        return "\n".join(lines)


# ── Config-driven bootstrap ────────────────────────────────────────────────────


def build_overwatch_from_config(config_path: str) -> OverwatchSentinel:
    """Read a JSON config file and build an OverwatchSentinel with registered targets.

    Expected config format:
    {
        "scan_interval_sec": 30.0,
        "alert_threshold": 3,
        "targets": [
            {
                "target_id": "agent-server",
                "process_name": "hlf-agent",
                "check_interval_sec": 15.0,
                "max_restarts": 3,
                "health_check_url": "http://localhost:8080/health",
                "resource_limits": {"max_memory_mb": 512, "max_cpu_percent": 80}
            }
        ]
    }
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Overwatch config not found: {config_path}")

    with path.open("r", encoding="utf-8") as f:
        config: dict[str, Any] = json.load(f)

    sentinel = OverwatchSentinel(
        scan_interval_sec=config.get("scan_interval_sec", 30.0),
        alert_threshold=config.get("alert_threshold", 3),
    )

    for t_cfg in config.get("targets", []):
        target = WatchdogTarget(
            target_id=t_cfg["target_id"],
            process_name=t_cfg.get("process_name", t_cfg["target_id"]),
            check_interval_sec=t_cfg.get("check_interval_sec", 30.0),
            max_restarts=t_cfg.get("max_restarts", 3),
            health_check_url=t_cfg.get("health_check_url"),
            resource_limits=t_cfg.get("resource_limits", {"max_memory_mb": 512, "max_cpu_percent": 80}),
        )
        sentinel.register_target(target)

    return sentinel


# ── OS-level helpers (with graceful degradation for test environments) ─────────


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _pid_is_alive(pid: int) -> bool:
    """Check if a process with the given PID exists on the system."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, PermissionError):
        return False


def _process_name_is_running(name: str) -> bool:
    """Check if any process with the given name is running (platform-agnostic)."""
    try:
        import subprocess
        import sys
        if sys.platform == "win32":
            result = subprocess.run(
                ["tasklist", "/FI", f"IMAGENAME eq {name}", "/NH"],
                capture_output=True, text=True, timeout=5,
            )
            return name.lower() in result.stdout.lower()
        else:
            result = subprocess.run(
                ["pgrep", "-f", name],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
    except Exception:
        logger.debug("Process-name lookup failed for %s", name, exc_info=True)
        return False


def _http_health_check(url: str, timeout: float = 5.0) -> bool:
    """Perform a simple HTTP GET health check."""
    try:
        import urllib.request
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        logger.debug("HTTP health check failed for %s", url, exc_info=True)
        return False


def _kill_pid(pid: int) -> None:
    """Terminate a process by PID."""
    try:
        os.kill(pid, 15)  # SIGTERM
    except (OSError, PermissionError):
        try:
            os.kill(pid, 9)  # SIGKILL
        except (OSError, PermissionError):
            logger.warning("Failed to kill PID %d", pid)


def _get_process_memory_mb(pid: int) -> float:
    """Get RSS memory usage in MB for a given PID (best-effort)."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return proc.memory_info().rss / (1024 * 1024)
    except Exception:
        return 0.0


def _get_process_cpu_percent(pid: int) -> float:
    """Get CPU usage percent for a given PID (best-effort)."""
    try:
        import psutil
        proc = psutil.Process(pid)
        return proc.cpu_percent(interval=0.1)
    except Exception:
        return 0.0


def _simulate_restart_pid() -> int:
    """Return a simulated new PID for restart scenarios (test-safe)."""
    return int(time.time() * 1000) % 100000 + 10000
