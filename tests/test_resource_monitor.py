"""Tests for ResourceMonitor — GPU VRAM and latent inference tracking."""

from __future__ import annotations

import pytest

from hlf_mcp.hlf.resource_monitor import (
    LatentSessionRecord,
    ResourceMonitor,
    ResourceSnapshot,
    estimate_model_vram,
)


class TestResourceSnapshot:
    def test_defaults(self):
        snap = ResourceSnapshot()
        assert snap.active_sessions == 0
        assert snap.total_models_loaded == 0
        assert snap.gpu_available is False

    def test_to_dict(self):
        snap = ResourceSnapshot(
            active_sessions=1,
            total_models_loaded=3,
            total_vram_allocated_mb=4500.0,
        )
        d = snap.to_dict()
        assert d["active_sessions"] == 1
        assert d["total_models_loaded"] == 3
        assert d["total_vram_allocated_mb"] == 4500.0


class TestLatentSessionRecord:
    def test_defaults(self):
        rec = LatentSessionRecord(session_type="latent_recursive")
        assert rec.session_type == "latent_recursive"
        assert rec.active is True
        assert rec.record_id

    def test_to_dict(self):
        rec = LatentSessionRecord(
            session_type="governed_latent",
            agent_models=["Qwen/Qwen2.5-1.5B-Instruct"],
            model_count=1,
            adapter_count=3,
            recursion_rounds=2,
            vram_allocated_mb=1500.0,
            device="cuda",
        )
        d = rec.to_dict()
        assert d["session_type"] == "governed_latent"
        assert d["vram_allocated_mb"] == 1500.0


class TestResourceMonitor:
    def setup_method(self):
        self.monitor = ResourceMonitor()

    def test_register_session_load(self):
        rec = self.monitor.register_session_load(
            "latent_recursive",
            ["Qwen/Qwen2.5-1.5B-Instruct", "meta-llama/Llama-3.2-1B-Instruct"],
            adapter_count=3,
            recursion_rounds=2,
            vram_allocated_mb=2700.0,
            device="cuda",
        )
        assert rec.model_count == 2
        assert rec.vram_allocated_mb == 2700.0
        assert rec.active is True

        active = self.monitor.get_active_sessions()
        assert len(active) == 1
        assert active[0]["model_count"] == 2

    def test_register_multiple_sessions(self):
        r1 = self.monitor.register_session_load(
            "latent_recursive", ["model-a"], vram_allocated_mb=1000.0
        )
        r2 = self.monitor.register_session_load(
            "governed_latent", ["model-b"], vram_allocated_mb=2000.0
        )

        active = self.monitor.get_active_sessions()
        assert len(active) == 2

        snap = self.monitor.get_latest_snapshot()
        assert snap.active_sessions == 2
        assert snap.total_vram_allocated_mb == 3000.0

    def test_register_session_unload_by_record_id(self):
        rec = self.monitor.register_session_load(
            "latent_recursive", ["model-a"], vram_allocated_mb=1000.0
        )
        assert len(self.monitor.get_active_sessions()) == 1

        self.monitor.register_session_unload(record_id=rec.record_id)
        assert len(self.monitor.get_active_sessions()) == 0

        snap = self.monitor.get_latest_snapshot()
        assert snap.active_sessions == 0
        assert snap.total_vram_allocated_mb == 0.0

    def test_register_session_unload_by_model_match(self):
        self.monitor.register_session_load(
            "latent_recursive",
            ["model-a", "model-b"],
            vram_allocated_mb=2500.0,
        )
        self.monitor.register_session_unload(
            agent_models=["model-a", "model-b"]
        )
        assert len(self.monitor.get_active_sessions()) == 0

    def test_unload_nonexistent_does_not_crash(self):
        self.monitor.register_session_unload(record_id="nonexistent")
        self.monitor.register_session_unload(agent_models=["nonexistent"])

    def test_session_history(self):
        for i in range(5):
            self.monitor.register_session_load(
                "latent_recursive",
                [f"model-{i}"],
                vram_allocated_mb=100.0,
            )
        history = self.monitor.get_session_history(limit=3)
        assert len(history) == 3

    def test_empty_monitor(self):
        active = self.monitor.get_active_sessions()
        assert active == []

        snap = self.monitor.get_latest_snapshot()
        assert snap.active_sessions == 0

        report = self.monitor.get_resource_report()
        assert report["active_session_count"] == 0
        assert report["total_session_records"] == 0

    def test_resource_report(self):
        self.monitor.register_session_load(
            "latent_recursive",
            ["Qwen/Qwen2.5-1.5B-Instruct"],
            adapter_count=3,
            vram_allocated_mb=1500.0,
        )
        report = self.monitor.get_resource_report()
        assert "snapshot" in report
        assert "active_sessions" in report
        assert report["active_session_count"] == 1
        assert report["total_session_records"] == 1

    def test_singleton(self):
        m1 = ResourceMonitor.get_instance()
        m2 = ResourceMonitor.get_instance()
        assert m1 is m2


class TestEstimateModelVRAM:
    def test_known_model(self):
        mb = estimate_model_vram("Qwen/Qwen2.5-1.5B-Instruct", fp16=True)
        assert mb == 1500.0

    def test_known_model_fp32(self):
        mb = estimate_model_vram("Qwen/Qwen2.5-1.5B-Instruct", fp16=False)
        assert mb == pytest.approx(2850.0, rel=0.01)

    def test_unknown_model_default(self):
        mb = estimate_model_vram("some/unknown-model", fp16=True)
        assert mb == 1500.0  # default fallback

    def test_parse_size_from_name(self):
        mb = estimate_model_vram("org/TestModel-3B-v2", fp16=True)
        assert mb == 3000.0

    def test_llama_model(self):
        mb = estimate_model_vram("meta-llama/Llama-3.2-1B-Instruct", fp16=True)
        assert mb == 1200.0
