"""
OVERWATCH Sentinel Daemon — continuous watchdog loop.

Reads overwatch_config.json, builds targets via OverwatchSentinel,
and runs scan → alert → auto_recover in a loop.

Usage (standalone/Docker):
    python overwatch_daemon.py

Usage (inside hlf_mcp package):
    python hlf_mcp/hlf/overwatch_daemon.py
"""

import importlib.util
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import NoReturn


def _load_overwatch_module():
    """Load the overwatch module, handling both package and standalone modes.

    When running inside hlf_mcp (pip installed), we import normally.
    When running standalone (Docker / direct file copy), we use importlib
    to bypass hlf_mcp/__init__.py which eagerly loads the DSL compiler.
    """
    try:
        from hlf_mcp.hlf.overwatch import OverwatchSentinel, WatchdogTarget  # noqa: F811
        return OverwatchSentinel, WatchdogTarget
    except (ImportError, AttributeError):
        overwatch_path = Path(__file__).resolve().parent / "overwatch.py"
        spec = importlib.util.spec_from_file_location("overwatch", str(overwatch_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["overwatch"] = mod  # register before exec for dataclass slots
        spec.loader.exec_module(mod)
        return mod.OverwatchSentinel, mod.WatchdogTarget


OverwatchSentinel, WatchdogTarget = _load_overwatch_module()


def _resolve_env_vars(text: str) -> str:
    """Replace ${VAR:-default} patterns with env var or default."""
    import re

    def _replace(match):
        var = match.group(1)
        default = match.group(2)
        return os.environ.get(var, default)

    return re.sub(r"\$\{(\w+):-([^}]+)\}", _replace, text)


def _build_sentinel_from_config(config: dict) -> OverwatchSentinel:
    """Build an OverwatchSentinel from a resolved config dict."""
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


def main() -> NoReturn:
    config_path = Path(__file__).resolve().parent / "overwatch_config.json"
    raw = config_path.read_text()
    resolved_text = _resolve_env_vars(raw)
    config = json.loads(resolved_text)

    scan_interval = config.get("scan_interval_sec", 30.0)
    alert_threshold = config.get("alert_threshold", 3)

    sentinel = _build_sentinel_from_config(config)

    print(f"OVERWATCH Sentinel started — {len(sentinel.targets)} target(s), scan every {scan_interval}s")

    running = True

    def _shutdown(signum, frame):
        nonlocal running
        print(f"\nOVERWATCH received signal {signum}, shutting down...")
        running = False

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while running:
        try:
            results = sentinel.scan()
            print(f"\n--- Scan {_now_iso()} ---")
            for tid, status in results.items():
                print(f"  {tid}: {status.value}")

            # Auto-recover any unresponsive/terminated targets
            for tid, target in sentinel.targets.items():
                if target.status.value in ("unresponsive", "terminated"):
                    recovered = sentinel.auto_recover(tid)
                    if recovered.value == "healthy":
                        print(f"  ✅ Auto-recovered: {tid}")
                    else:
                        print(f"  ⚠ Could not recover: {tid} (restart {target.restart_count}/{target.max_restarts})")

            # Count total alerts (consecutive failure counters)
            total_alerts = sum(sentinel._failure_counters.values())
            if total_alerts >= alert_threshold:
                print(f"⚠ Alert threshold reached ({total_alerts} alerts across {len(sentinel.targets)} targets)")

            print(sentinel.status_report())

        except Exception as e:
            print(f"OVERWATCH scan error: {e}", file=sys.stderr)

        time.sleep(scan_interval)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


if __name__ == "__main__":
    main()
