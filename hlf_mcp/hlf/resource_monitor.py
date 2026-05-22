"""
Resource Monitor — tracks GPU VRAM and latent inference resource usage.

Extends the EGL monitor's behavioral tracking with hardware-resource
awareness.  The monitor detects when RecursiveMAS latent inference
sessions allocate GPU memory (PyTorch models loaded into CUDA) and
tracks model count, adapter count, recursion rounds, and approximate
VRAM consumption.

Usage:
    from hlf_mcp.hlf.resource_monitor import ResourceMonitor

    monitor = ResourceMonitor()
    monitor.register_session_load("planner", vram_mb=1200)
    monitor.register_session_unload("planner")
    report = monitor.get_resource_report()
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


# ─── Data Types ─────────────────────────────────────────────────────────────

@dataclass
class LatentSessionRecord:
    """A record of one latent inference session's resource usage."""
    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_type: str = ""              # "latent_recursive" | "governed_latent"
    agent_models: list[str] = field(default_factory=list)
    model_count: int = 0
    adapter_count: int = 0
    recursion_rounds: int = 0
    vram_allocated_mb: float = 0.0      # Estimated VRAM allocated
    device: str = "cpu"
    loaded_at: float = field(default_factory=time.time)
    unloaded_at: float | None = None
    active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "session_type": self.session_type,
            "agent_models": self.agent_models,
            "model_count": self.model_count,
            "adapter_count": self.adapter_count,
            "recursion_rounds": self.recursion_rounds,
            "vram_allocated_mb": round(self.vram_allocated_mb, 1),
            "device": self.device,
            "loaded_at": self.loaded_at,
            "unloaded_at": self.unloaded_at,
            "active": self.active,
        }


@dataclass
class ResourceSnapshot:
    """Point-in-time snapshot of GPU/resource state."""
    timestamp: float = field(default_factory=time.time)
    active_sessions: int = 0
    total_models_loaded: int = 0
    total_adapters: int = 0
    total_vram_allocated_mb: float = 0.0
    total_vram_free_mb: float = 0.0
    total_vram_total_mb: float = 0.0
    gpu_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "active_sessions": self.active_sessions,
            "total_models_loaded": self.total_models_loaded,
            "total_adapters": self.total_adapters,
            "total_vram_allocated_mb": round(self.total_vram_allocated_mb, 1),
            "total_vram_free_mb": round(self.total_vram_free_mb, 1),
            "total_vram_total_mb": round(self.total_vram_total_mb, 1),
            "gpu_available": self.gpu_available,
        }


# ─── Resource Monitor ──────────────────────────────────────────────────────

class ResourceMonitor:
    """Tracks GPU/VRAM resource usage for latent inference sessions.

    Thread-safe.  Lightweight hooks that the latent_model_interface
    and latent_capsule modules call during model load/unload.
    """

    # Singleton pattern — all modules share one monitor
    _instance: ResourceMonitor | None = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self) -> None:
        self._sessions: list[LatentSessionRecord] = []
        self._snapshots: list[ResourceSnapshot] = []
        self._mutex = threading.Lock()

    @classmethod
    def get_instance(cls) -> ResourceMonitor:
        """Return the global singleton ResourceMonitor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── GPU detection ───────────────────────────────────────────────────

    @staticmethod
    def _detect_gpu_vram() -> tuple[bool, float, float]:
        """Detect GPU VRAM info via PyTorch. Returns (available, free_mb, total_mb)."""
        try:
            import torch
            if torch.cuda.is_available():
                free, total = torch.cuda.mem_get_info()
                free_mb = free / (1024 * 1024)
                total_mb = total / (1024 * 1024)
                return True, free_mb, total_mb
        except ImportError:
            pass
        return False, 0.0, 0.0

    # ── Session tracking ─────────────────────────────────────────────────

    def register_session_load(
        self,
        session_type: str,
        agent_models: list[str],
        *,
        adapter_count: int = 0,
        recursion_rounds: int = 0,
        vram_allocated_mb: float = 0.0,
        device: str = "cpu",
    ) -> LatentSessionRecord:
        """Called when a latent session loads models into GPU.

        Args:
            session_type: "latent_recursive" or "governed_latent"
            agent_models: List of model IDs loaded
            adapter_count: Number of RecursiveLink adapters active
            recursion_rounds: Planned recursion rounds
            vram_allocated_mb: Estimated VRAM allocated in MB
            device: "cuda" or "cpu"
        """
        record = LatentSessionRecord(
            session_type=session_type,
            agent_models=list(agent_models),
            model_count=len(agent_models),
            adapter_count=adapter_count,
            recursion_rounds=recursion_rounds,
            vram_allocated_mb=vram_allocated_mb,
            device=device,
        )
        with self._mutex:
            self._sessions.append(record)
        logger.info(
            "ResourceMonitor: registered session load — %d models, %.1f MB VRAM, device=%s",
            record.model_count, record.vram_allocated_mb, device,
        )
        self._take_snapshot()
        return record

    def register_session_unload(
        self,
        record_id: str | None = None,
        *,
        agent_models: list[str] | None = None,
    ) -> None:
        """Called when a latent session unloads models.

        Args:
            record_id: Specific record to mark unloaded (preferred).
            agent_models: If record_id not given, unload the most recent
                active session matching these models.
        """
        with self._mutex:
            if record_id:
                for rec in self._sessions:
                    if rec.record_id == record_id and rec.active:
                        rec.active = False
                        rec.unloaded_at = time.time()
                        logger.info(
                            "ResourceMonitor: unloaded session %s (%.1f MB freed)",
                            record_id, rec.vram_allocated_mb,
                        )
                        self._take_snapshot()
                        return

            # Fallback: find most recent active session by model match
            if agent_models:
                for rec in reversed(self._sessions):
                    if rec.active and set(rec.agent_models) == set(agent_models):
                        rec.active = False
                        rec.unloaded_at = time.time()
                        logger.info(
                            "ResourceMonitor: unloaded session %s (%.1f MB freed)",
                            rec.record_id, rec.vram_allocated_mb,
                        )
                        self._take_snapshot()
                        return

    def _take_snapshot(self) -> ResourceSnapshot:
        """Capture current GPU/resource state."""
        gpu_available, free_mb, total_mb = self._detect_gpu_vram()
        active = [s for s in self._sessions if s.active]
        allocated = sum(s.vram_allocated_mb for s in active)
        snapshot = ResourceSnapshot(
            active_sessions=len(active),
            total_models_loaded=sum(s.model_count for s in active),
            total_adapters=sum(s.adapter_count for s in active),
            total_vram_allocated_mb=allocated,
            total_vram_free_mb=free_mb,
            total_vram_total_mb=total_mb,
            gpu_available=gpu_available,
        )
        self._snapshots.append(snapshot)
        return snapshot

    # ── Reporting ────────────────────────────────────────────────────────

    def get_active_sessions(self) -> list[dict[str, Any]]:
        """Return all currently active latent sessions."""
        with self._mutex:
            return [s.to_dict() for s in self._sessions if s.active]

    def get_session_history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent session records (active + completed)."""
        with self._mutex:
            return [s.to_dict() for s in self._sessions[-limit:]]

    def get_latest_snapshot(self) -> ResourceSnapshot:
        """Get the most recent resource snapshot."""
        with self._mutex:
            if self._snapshots:
                return self._snapshots[-1]
            return self._take_snapshot()

    def get_resource_report(self) -> dict[str, Any]:
        """Get a comprehensive resource report (suitable for JSON endpoints)."""
        snap = self.get_latest_snapshot()
        active = self.get_active_sessions()
        return {
            "snapshot": snap.to_dict(),
            "active_sessions": active,
            "active_session_count": len(active),
            "total_session_records": len(self._sessions),
            "total_snapshots": len(self._snapshots),
        }


# ─── Convenience: estimate VRAM for a model ─────────────────────────────────

def estimate_model_vram(model_id: str, *, fp16: bool = True) -> float:
    """Rough heuristic to estimate VRAM for common HuggingFace models.

    Returns estimated MB.  Falls back to 1500 MB for unknown models.
    """
    # Known model sizes (approximate, fp16)
    _KNOWN: dict[str, float] = {
        "Qwen/Qwen2.5-1.5B-Instruct": 1500,
        "Qwen/Qwen2.5-Math-1.5B": 1500,
        "meta-llama/Llama-3.2-1B-Instruct": 1200,
        "meta-llama/Llama-3.2-3B-Instruct": 3000,
        "Qwen/Qwen2.5-0.5B-Instruct": 600,
        "google/gemma-2-2b-it": 2500,
        "microsoft/Phi-3-mini-4k-instruct": 2200,
    }
    if model_id in _KNOWN:
        mb = _KNOWN[model_id]
        return mb if fp16 else mb * 1.9
    # Heuristic: 1B params ≈ 1 GB fp16 VRAM
    # Try to parse size from model name
    import re
    match = re.search(r'(\d+\.?\d*)\s*B', model_id)
    if match:
        size_b = float(match.group(1))
        return size_b * 1000 * (1.0 if fp16 else 1.9)
    return 1500.0  # sensible default
