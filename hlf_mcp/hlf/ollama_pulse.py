"""
Ollama Pulse — Ollama model auto-scanner and CLOUD_CATALOG updater.

Scans the local Ollama API (http://localhost:11434) for available models,
extracts model metadata (size, family, quantization, parameter count), and
keeps the CLOUD_CATALOG in sync with TTL-based staleness detection.

Architecture:
    ModelScanner   → polls Ollama API, extracts model details
    CatalogUpdater → diffs against current catalog, TTL-based staleness
    PulseMonitor   → periodic orchestrator (configurable interval)

Thread-safe with lock. Graceful when Ollama is not running.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Default scan interval (seconds)
DEFAULT_SCAN_INTERVAL = 300.0  # 5 minutes
# Default catalog TTL (seconds) — after this, catalog is considered stale
DEFAULT_CATALOG_TTL = 600.0  # 10 minutes
# Default Ollama API endpoint
DEFAULT_OLLAMA_ENDPOINT = "http://localhost:11434"

# Path to CLOUD_CATALOG (stored alongside model_catalog's cache)
_CLOUD_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "state" / "cloud_catalog.json"
)


# ── ModelRecord Dataclass ──────────────────────────────────────────────────────


@dataclass
class ModelRecord:
    """A scanned model record with metadata from Ollama."""

    name: str
    size_bytes: int = 0
    family: str = ""
    quantization: str = ""
    parameters: str = ""
    last_seen: float = 0.0
    first_seen: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "size_bytes": self.size_bytes,
            "family": self.family,
            "quantization": self.quantization,
            "parameters": self.parameters,
            "last_seen": self.last_seen,
            "first_seen": self.first_seen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelRecord:
        return cls(
            name=data.get("name", ""),
            size_bytes=data.get("size_bytes", 0),
            family=data.get("family", ""),
            quantization=data.get("quantization", ""),
            parameters=data.get("parameters", ""),
            last_seen=data.get("last_seen", 0.0),
            first_seen=data.get("first_seen", 0.0),
        )


# ── ModelScanner ───────────────────────────────────────────────────────────────


class ModelScanner:
    """Scans the Ollama API for available models and their metadata.

    Handles the Ollama /api/tags endpoint to get model listings, then
    queries /api/show for each model to get detailed metadata (size,
    family, quantization, parameter count).

    Graceful when Ollama is not running: returns empty results rather
    than raising exceptions.
    """

    def __init__(self, endpoint: str = DEFAULT_OLLAMA_ENDPOINT) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._lock = threading.Lock()
        self._last_scan_time: float = 0.0
        self._last_scan_models: dict[str, ModelRecord] = {}
        self._scan_error: str | None = None

    @property
    def endpoint(self) -> str:
        return self._endpoint

    @property
    def last_scan_time(self) -> float:
        return self._last_scan_time

    @property
    def last_scan_models(self) -> dict[str, ModelRecord]:
        with self._lock:
            return dict(self._last_scan_models)

    @property
    def scan_error(self) -> str | None:
        return self._scan_error

    def scan(self) -> dict[str, ModelRecord]:
        """Scan Ollama for all available models.

        Returns:
            Dict mapping model name → ModelRecord.
            Empty dict if Ollama is unreachable.
        """
        now = time.time()
        models: dict[str, ModelRecord] = {}
        self._scan_error = None

        try:
            # Step 1: List all models via /api/tags
            list_url = f"{self._endpoint}/api/tags"
            resp = httpx.get(list_url, timeout=10.0)
            resp.raise_for_status()
            tag_data = resp.json()
            raw_models = tag_data.get("models", [])

            if not raw_models:
                logger.info("Ollama Pulse scan: no models found at %s", self._endpoint)
                with self._lock:
                    self._last_scan_time = now
                    self._last_scan_models = {}
                return {}

            # Step 2: For each model, get detailed info via /api/show
            for raw in raw_models:
                model_name = raw.get("name", "")
                if not model_name:
                    continue

                # Extract available info from tags response
                size_bytes = raw.get("size", 0)
                details = raw.get("details", {})
                family = details.get("family", "")
                quant = details.get("quantization_level", "")
                params = details.get("parameter_size", "")

                # Try to get richer details from /api/show
                try:
                    show_url = f"{self._endpoint}/api/show"
                    show_resp = httpx.post(
                        show_url,
                        json={"name": model_name},
                        timeout=15.0,
                    )
                    if show_resp.status_code == 200:
                        show_data = show_resp.json()
                        if not size_bytes:
                            size_bytes = show_data.get("size", 0)
                        show_details = show_data.get("details", {})
                        family = family or show_details.get("family", "")
                        quant = quant or show_details.get("quantization_level", "")
                        params = params or show_details.get("parameter_size", "")
                        # Model info from show response
                        model_info = show_data.get("model_info", {})
                        if model_info:
                            for k, v in model_info.items():
                                if "family" in k.lower() and not family:
                                    family = str(v)
                                if "param" in k.lower() and not params:
                                    params = str(v)
                                if "quant" in k.lower() and not quant:
                                    quant = str(v)
                except (httpx.RequestError, httpx.HTTPStatusError, json.JSONDecodeError):
                    # /api/show failed for this model; use whatever we have
                    pass

                # Check if we've seen this model before
                existing = self._last_scan_models.get(model_name)
                first_seen = existing.first_seen if existing else now

                record = ModelRecord(
                    name=model_name,
                    size_bytes=size_bytes,
                    family=family,
                    quantization=quant,
                    parameters=params,
                    last_seen=now,
                    first_seen=first_seen,
                )
                models[model_name] = record

            logger.info(
                "Ollama Pulse scan complete: %d models found at %s",
                len(models),
                self._endpoint,
            )

        except httpx.ConnectError:
            msg = f"Ollama not running at {self._endpoint} — skipping scan"
            logger.warning(msg)
            self._scan_error = msg
            models = {}
        except httpx.RequestError as exc:
            msg = f"Ollama Pulse scan failed: {exc}"
            logger.warning(msg)
            self._scan_error = msg
            models = {}
        except (json.JSONDecodeError, httpx.HTTPStatusError) as exc:
            msg = f"Ollama Pulse scan parse error: {exc}"
            logger.warning(msg)
            self._scan_error = msg
            models = {}

        with self._lock:
            self._last_scan_time = now
            self._last_scan_models = dict(models)

        return models

    def is_ollama_available(self) -> bool:
        """Quick check whether Ollama is reachable."""
        try:
            resp = httpx.get(f"{self._endpoint}/api/tags", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            return False


# ── DiffResult ─────────────────────────────────────────────────────────────────


@dataclass
class DiffResult:
    """Result of diffing two model snapshots."""

    added: list[ModelRecord] = field(default_factory=list)
    removed: list[ModelRecord] = field(default_factory=list)
    changed: list[tuple[ModelRecord, ModelRecord]] = field(
        default_factory=list
    )  # (old, new)
    unchanged: list[ModelRecord] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)

    @property
    def summary(self) -> dict[str, Any]:
        return {
            "added_count": len(self.added),
            "removed_count": len(self.removed),
            "changed_count": len(self.changed),
            "unchanged_count": len(self.unchanged),
            "has_changes": self.has_changes,
            "added_names": [r.name for r in self.added],
            "removed_names": [r.name for r in self.removed],
            "changed_names": [new.name for _, new in self.changed],
        }


# ── CatalogUpdater ─────────────────────────────────────────────────────────────


class CatalogUpdater:
    """Updates CLOUD_CATALOG with scanned models.

    Manages TTL-based staleness detection, diff computation between scans,
    and persistence of the catalog to disk.

    Thread-safe via internal lock.
    """

    def __init__(
        self,
        catalog_path: Path | str | None = None,
        ttl: float = DEFAULT_CATALOG_TTL,
    ) -> None:
        self._catalog_path = Path(catalog_path) if catalog_path else _CLOUD_CATALOG_PATH
        self._ttl = ttl
        self._lock = threading.Lock()
        self._catalog: dict[str, ModelRecord] = {}
        self._last_updated: float = 0.0
        self._last_diff: DiffResult | None = None

        # Ensure parent directory exists
        self._catalog_path.parent.mkdir(parents=True, exist_ok=True)

        # Load existing catalog from disk
        self._load_from_disk()

    @property
    def ttl(self) -> float:
        return self._ttl

    @property
    def last_updated(self) -> float:
        with self._lock:
            return self._last_updated

    @property
    def is_stale(self) -> bool:
        """Check if catalog is stale (older than TTL)."""
        with self._lock:
            if self._last_updated == 0.0:
                return True
            return (time.time() - self._last_updated) > self._ttl

    @property
    def catalog(self) -> dict[str, ModelRecord]:
        with self._lock:
            return dict(self._catalog)

    @property
    def last_diff(self) -> DiffResult | None:
        with self._lock:
            return self._last_diff

    def _load_from_disk(self) -> None:
        """Load persisted catalog from disk."""
        try:
            if self._catalog_path.exists():
                data = json.loads(self._catalog_path.read_text(encoding="utf-8"))
                records = data.get("models", {})
                self._catalog = {
                    name: ModelRecord.from_dict(rec)
                    for name, rec in records.items()
                }
                self._last_updated = data.get("last_updated", 0.0)
                logger.debug(
                    "Loaded %d models from cloud catalog at %s",
                    len(self._catalog),
                    self._catalog_path,
                )
        except (json.JSONDecodeError, OSError, KeyError) as exc:
            logger.warning("Failed to load cloud catalog from disk: %s", exc)
            self._catalog = {}
            self._last_updated = 0.0

    def _save_to_disk(self) -> None:
        """Persist catalog to disk."""
        try:
            data = {
                "models": {
                    name: rec.to_dict() for name, rec in self._catalog.items()
                },
                "last_updated": self._last_updated,
                "ttl": self._ttl,
            }
            self._catalog_path.write_text(
                json.dumps(data, indent=2), encoding="utf-8"
            )
            logger.debug(
                "Saved %d models to cloud catalog at %s",
                len(self._catalog),
                self._catalog_path,
            )
        except OSError as exc:
            logger.error("Failed to save cloud catalog to disk: %s", exc)

    def compute_diff(
        self,
        old_models: dict[str, ModelRecord],
        new_models: dict[str, ModelRecord],
    ) -> DiffResult:
        """Compute the difference between two model snapshots.

        Args:
            old_models: Previous snapshot (name → ModelRecord).
            new_models: Current snapshot (name → ModelRecord).

        Returns:
            DiffResult with added, removed, changed, and unchanged models.
        """
        old_names = set(old_models.keys())
        new_names = set(new_models.keys())

        added_names = new_names - old_names
        removed_names = old_names - new_names
        common_names = old_names & new_names

        added = [new_models[n] for n in sorted(added_names)]
        removed = [old_models[n] for n in sorted(removed_names)]

        changed: list[tuple[ModelRecord, ModelRecord]] = []
        unchanged: list[ModelRecord] = []

        for name in sorted(common_names):
            old = old_models[name]
            new = new_models[name]
            # Check for meaningful changes
            if (
                old.size_bytes != new.size_bytes
                or old.family != new.family
                or old.quantization != new.quantization
                or old.parameters != new.parameters
            ):
                changed.append((old, new))
            else:
                unchanged.append(new)

        return DiffResult(
            added=added,
            removed=removed,
            changed=changed,
            unchanged=unchanged,
        )

    def update(
        self, scanned_models: dict[str, ModelRecord], force: bool = False
    ) -> DiffResult:
        """Update the catalog with freshly scanned models.

        Args:
            scanned_models: Latest scan results (name → ModelRecord).
            force: If True, update even if within TTL.

        Returns:
            DiffResult showing what changed.
        """
        with self._lock:
            # Compute diff against current catalog
            diff = self.compute_diff(self._catalog, scanned_models)

            # Update catalog
            now = time.time()
            self._catalog = dict(scanned_models)
            self._last_updated = now
            self._last_diff = diff

            if diff.has_changes:
                logger.info(
                    "Cloud catalog updated: +%d added, -%d removed, ~%d changed, =%d unchanged",
                    len(diff.added),
                    len(diff.removed),
                    len(diff.changed),
                    len(diff.unchanged),
                )
            else:
                logger.debug(
                    "Cloud catalog updated: no changes (%d models)", len(diff.unchanged)
                )

            # Persist to disk
            self._save_to_disk()

            return diff

    def get_model(self, name: str) -> ModelRecord | None:
        """Get a single model from the catalog."""
        with self._lock:
            return self._catalog.get(name)

    def list_models(self) -> list[ModelRecord]:
        """List all models in the catalog."""
        with self._lock:
            return sorted(self._catalog.values(), key=lambda r: r.name)

    def summary(self) -> dict[str, Any]:
        """Return a summary of the catalog state."""
        with self._lock:
            stale = (time.time() - self._last_updated) > self._ttl if self._last_updated > 0 else True
            return {
                "model_count": len(self._catalog),
                "last_updated": self._last_updated,
                "ttl": self._ttl,
                "is_stale": stale,
                "catalog_path": str(self._catalog_path),
                "last_diff": self._last_diff.summary if self._last_diff else None,
            }


# ── PulseMonitor ───────────────────────────────────────────────────────────────


class PulseMonitor:
    """Main orchestrator for periodic Ollama model scanning and catalog sync.

    Combines ModelScanner and CatalogUpdater into a periodic monitor that:
      - Scans Ollama at configurable intervals
      - Detects diffs (new/removed/changed models)
      - Syncs the CLOUD_CATALOG automatically
      - Is thread-safe and runs in a background thread

    Usage:
        monitor = PulseMonitor()
        monitor.start()  # begins periodic scanning
        # ... later ...
        monitor.stop()   # stops background thread
    """

    def __init__(
        self,
        endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
        scan_interval: float = DEFAULT_SCAN_INTERVAL,
        catalog_ttl: float = DEFAULT_CATALOG_TTL,
        catalog_path: Path | str | None = None,
        auto_start: bool = False,
    ) -> None:
        self._scanner = ModelScanner(endpoint=endpoint)
        self._updater = CatalogUpdater(catalog_path=catalog_path, ttl=catalog_ttl)
        self._scan_interval = scan_interval
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._last_diff: DiffResult | None = None
        self._scan_count: int = 0
        self._error_count: int = 0

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._running

    @property
    def scanner(self) -> ModelScanner:
        return self._scanner

    @property
    def updater(self) -> CatalogUpdater:
        return self._updater

    @property
    def scan_count(self) -> int:
        with self._lock:
            return self._scan_count

    @property
    def error_count(self) -> int:
        with self._lock:
            return self._error_count

    @property
    def last_diff(self) -> DiffResult | None:
        with self._lock:
            return self._last_diff

    # ── Core Operations ───────────────────────────────────────────────────

    def scan(self) -> dict[str, ModelRecord]:
        """Perform a single scan of the Ollama API.

        Returns:
            Dict mapping model name → ModelRecord.
        """
        models = self._scanner.scan()
        with self._lock:
            self._scan_count += 1
            if self._scanner.scan_error:
                self._error_count += 1
        return models

    def update_catalog(self, force: bool = False) -> DiffResult:
        """Scan Ollama and update the catalog atomically.

        Args:
            force: If True, update even if within TTL.

        Returns:
            DiffResult showing what changed.
        """
        models = self.scan()
        diff = self._updater.update(models, force=force)
        with self._lock:
            self._last_diff = diff
        return diff

    def ensure_fresh(self) -> DiffResult | None:
        """Ensure the catalog is fresh. Scans if stale.

        Returns:
            DiffResult if a scan was performed, None if catalog was still fresh.
        """
        if self._updater.is_stale:
            return self.update_catalog()
        return None

    # ── Background Thread ─────────────────────────────────────────────────

    def _run_loop(self) -> None:
        """Background scan loop."""
        logger.info(
            "PulseMonitor started: endpoint=%s interval=%.0fs",
            self._scanner.endpoint,
            self._scan_interval,
        )
        while True:
            with self._lock:
                if not self._running:
                    break

            try:
                self.update_catalog()
            except Exception as exc:
                logger.error("PulseMonitor scan error: %s", exc)
                with self._lock:
                    self._error_count += 1

            # Sleep in chunks so we can respond to stop() quickly
            remaining = self._scan_interval
            while remaining > 0:
                with self._lock:
                    if not self._running:
                        break
                chunk = min(remaining, 5.0)
                time.sleep(chunk)
                remaining -= chunk

        logger.info("PulseMonitor stopped.")

    def start(self) -> None:
        """Start periodic scanning in a background thread."""
        with self._lock:
            if self._running:
                logger.warning("PulseMonitor already running")
                return
            self._running = True
            self._thread = threading.Thread(
                target=self._run_loop, name="pulse-monitor", daemon=True
            )
            self._thread.start()

    def stop(self, timeout: float = 10.0) -> None:
        """Stop the background scanning thread.

        Args:
            timeout: Maximum seconds to wait for thread to finish.
        """
        with self._lock:
            self._running = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("PulseMonitor thread did not stop within timeout")

    # ── Status ────────────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        """Return monitor status and stats."""
        with self._lock:
            return {
                "running": self._running,
                "endpoint": self._scanner.endpoint,
                "scan_interval": self._scan_interval,
                "scan_count": self._scan_count,
                "error_count": self._error_count,
                "catalog": self._updater.summary(),
                "last_scan_time": self._scanner.last_scan_time,
                "last_scan_models_count": len(self._scanner.last_scan_models),
                "last_diff": self._last_diff.summary if self._last_diff else None,
            }


# Module-level global instance (lazily initialized, used by model_gateway)
_global_pulse_monitor: PulseMonitor | None = None
_global_pulse_lock = threading.Lock()


def get_pulse_monitor(
    endpoint: str = DEFAULT_OLLAMA_ENDPOINT,
    scan_interval: float = DEFAULT_SCAN_INTERVAL,
    catalog_ttl: float = DEFAULT_CATALOG_TTL,
    auto_start: bool = False,
) -> PulseMonitor:
    """Get or create the global PulseMonitor singleton.

    Args:
        endpoint: Ollama API endpoint.
        scan_interval: Seconds between periodic scans.
        catalog_ttl: Seconds before catalog is considered stale.
        auto_start: If True, start background scanning immediately.

    Returns:
        The global PulseMonitor instance.
    """
    global _global_pulse_monitor
    if _global_pulse_monitor is None:
        with _global_pulse_lock:
            if _global_pulse_monitor is None:
                _global_pulse_monitor = PulseMonitor(
                    endpoint=endpoint,
                    scan_interval=scan_interval,
                    catalog_ttl=catalog_ttl,
                    auto_start=auto_start,
                )
    return _global_pulse_monitor
