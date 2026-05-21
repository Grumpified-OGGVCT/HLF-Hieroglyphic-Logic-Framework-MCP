"""
Tests for ollama_pulse — model scanning, catalog updates, TTL, diff detection,
and graceful offline handling.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from hlf_mcp.hlf.ollama_pulse import (
    ModelRecord,
    ModelScanner,
    CatalogUpdater,
    PulseMonitor,
    DiffResult,
    DEFAULT_CATALOG_TTL,
    DEFAULT_SCAN_INTERVAL,
    get_pulse_monitor,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_models() -> dict[str, ModelRecord]:
    """Sample model records for testing."""
    now = time.time()
    return {
        "kimi-k2.6:cloud": ModelRecord(
            name="kimi-k2.6:cloud",
            size_bytes=10000000000,
            family="kimi",
            quantization="Q4_K_M",
            parameters="200B",
            last_seen=now,
            first_seen=now - 1000,
        ),
        "qwen3-coder:480b-cloud": ModelRecord(
            name="qwen3-coder:480b-cloud",
            size_bytes=50000000000,
            family="qwen",
            quantization="Q5_K_M",
            parameters="480B",
            last_seen=now,
            first_seen=now - 500,
        ),
        "deepseek-v3.2:cloud": ModelRecord(
            name="deepseek-v3.2:cloud",
            size_bytes=30000000000,
            family="deepseek",
            quantization="Q4_K_M",
            parameters="685B",
            last_seen=now,
            first_seen=now - 2000,
        ),
    }


@pytest.fixture
def temp_catalog_path(tmp_path: Path) -> Path:
    """Temporary catalog path for testing."""
    return tmp_path / "cloud_catalog.json"


# ── ModelRecord Tests ─────────────────────────────────────────────────────────


class TestModelRecord:
    """Test ModelRecord dataclass serialization."""

    def test_to_dict(self) -> None:
        now = time.time()
        record = ModelRecord(
            name="test-model:cloud",
            size_bytes=12345,
            family="test-family",
            quantization="Q4_K_M",
            parameters="7B",
            last_seen=now,
            first_seen=now - 100,
        )
        d = record.to_dict()
        assert d["name"] == "test-model:cloud"
        assert d["size_bytes"] == 12345
        assert d["family"] == "test-family"
        assert d["quantization"] == "Q4_K_M"
        assert d["parameters"] == "7B"
        assert d["last_seen"] == now
        assert d["first_seen"] == now - 100

    def test_from_dict(self) -> None:
        data = {
            "name": "test-model:cloud",
            "size_bytes": 99999,
            "family": "test",
            "quantization": "Q8_0",
            "parameters": "13B",
            "last_seen": 12345.0,
            "first_seen": 12000.0,
        }
        record = ModelRecord.from_dict(data)
        assert record.name == "test-model:cloud"
        assert record.size_bytes == 99999
        assert record.family == "test"
        assert record.quantization == "Q8_0"
        assert record.parameters == "13B"
        assert record.last_seen == 12345.0
        assert record.first_seen == 12000.0

    def test_from_dict_defaults(self) -> None:
        record = ModelRecord.from_dict({})
        assert record.name == ""
        assert record.size_bytes == 0
        assert record.family == ""

    def test_roundtrip(self) -> None:
        now = time.time()
        original = ModelRecord(
            name="roundtrip-test",
            size_bytes=42,
            family="roundtrip",
            quantization="F16",
            parameters="1B",
            last_seen=now,
            first_seen=now - 1,
        )
        restored = ModelRecord.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.size_bytes == original.size_bytes
        assert restored.family == original.family
        assert restored.quantization == original.quantization
        assert restored.parameters == original.parameters


# ── ModelScanner Tests ────────────────────────────────────────────────────────


class TestModelScanner:
    """Test ModelScanner — scanning Ollama API for models."""

    def test_scan_success(self) -> None:
        """Test successful scan with mock Ollama API response."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get, \
             patch("hlf_mcp.hlf.ollama_pulse.httpx.post") as mock_post:

            # Mock /api/tags
            mock_tags_resp = MagicMock()
            mock_tags_resp.status_code = 200
            mock_tags_resp.json.return_value = {
                "models": [
                    {
                        "name": "kimi-k2.6:cloud",
                        "size": 10000000000,
                        "details": {
                            "family": "kimi",
                            "quantization_level": "Q4_K_M",
                            "parameter_size": "200B",
                        },
                    },
                    {
                        "name": "llama3.2:latest",
                        "size": 2000000000,
                        "details": {
                            "family": "llama",
                            "quantization_level": "Q4_0",
                            "parameter_size": "3B",
                        },
                    },
                ]
            }
            mock_get.return_value = mock_tags_resp

            # Mock /api/show for each model
            mock_show_resp = MagicMock()
            mock_show_resp.status_code = 200
            mock_show_resp.json.return_value = {
                "size": 10000000000,
                "details": {
                    "family": "kimi",
                    "quantization_level": "Q4_K_M",
                    "parameter_size": "200B",
                },
            }
            mock_post.return_value = mock_show_resp

            scanner = ModelScanner()
            models = scanner.scan()

            assert len(models) >= 1
            assert "kimi-k2.6:cloud" in models or "llama3.2:latest" in models

    def test_scan_ollama_unavailable(self) -> None:
        """Test graceful handling when Ollama is not running."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            from httpx import ConnectError
            mock_get.side_effect = ConnectError("Connection refused")

            scanner = ModelScanner()
            models = scanner.scan()

            assert models == {}
            assert scanner.scan_error is not None
            assert "not running" in scanner.scan_error.lower()

    def test_scan_request_error(self) -> None:
        """Test handling of general request errors."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            from httpx import RequestError
            mock_get.side_effect = RequestError("timeout")

            scanner = ModelScanner()
            models = scanner.scan()

            assert models == {}

    def test_scan_parse_error(self) -> None:
        """Test handling of malformed JSON responses."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.side_effect = json.JSONDecodeError("bad json", "", 0)
            mock_get.return_value = mock_resp

            scanner = ModelScanner()
            models = scanner.scan()

            assert models == {}

    def test_scan_empty_models(self) -> None:
        """Test scanning when no models are installed."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": []}
            mock_get.return_value = mock_resp

            scanner = ModelScanner()
            models = scanner.scan()

            assert models == {}

    def test_is_ollama_available_true(self) -> None:
        """Test availability check when Ollama is up."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_get.return_value = mock_resp

            scanner = ModelScanner()
            assert scanner.is_ollama_available() is True

    def test_is_ollama_available_false(self) -> None:
        """Test availability check when Ollama is down."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            from httpx import ConnectError
            mock_get.side_effect = ConnectError("nope")

            scanner = ModelScanner()
            assert scanner.is_ollama_available() is False

    def test_scan_tracks_first_seen(self) -> None:
        """Test that first_seen persists across scans for existing models."""
        now = time.time()
        initial_models = {
            "persistent-model": ModelRecord(
                name="persistent-model",
                size_bytes=100,
                family="test",
                last_seen=now - 100,
                first_seen=now - 1000,
            )
        }

        scanner = ModelScanner()
        # Pre-load last scan state
        scanner._last_scan_models = dict(initial_models)
        scanner._last_scan_time = now - 100

        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get, \
             patch("hlf_mcp.hlf.ollama_pulse.httpx.post") as mock_post:
            mock_tags_resp = MagicMock()
            mock_tags_resp.status_code = 200
            mock_tags_resp.json.return_value = {
                "models": [
                    {
                        "name": "persistent-model",
                        "size": 100,
                        "details": {"family": "test"},
                    },
                ]
            }
            mock_get.return_value = mock_tags_resp

            mock_show_resp = MagicMock()
            mock_show_resp.status_code = 200
            mock_show_resp.json.return_value = {}
            mock_post.return_value = mock_show_resp

            models = scanner.scan()
            assert "persistent-model" in models
            # first_seen should persist from original
            assert models["persistent-model"].first_seen == pytest.approx(now - 1000)


# ── CatalogUpdater Tests ──────────────────────────────────────────────────────


class TestCatalogUpdater:
    """Test CatalogUpdater — TTL, diffs, persistence."""

    def test_initial_state_stale(self, temp_catalog_path: Path) -> None:
        """Test that a new catalog is immediately stale."""
        updater = CatalogUpdater(catalog_path=temp_catalog_path, ttl=60.0)
        assert updater.is_stale is True
        assert updater.last_updated == 0.0

    def test_update_makes_fresh(self, temp_catalog_path: Path,
                                 sample_models: dict[str, ModelRecord]) -> None:
        """Test that updating the catalog makes it fresh."""
        updater = CatalogUpdater(catalog_path=temp_catalog_path, ttl=60.0)
        updater.update(sample_models)
        assert updater.is_stale is False
        assert updater.last_updated > 0

    def test_ttl_expiry(self, temp_catalog_path: Path,
                         sample_models: dict[str, ModelRecord]) -> None:
        """Test that catalog becomes stale after TTL expires."""
        updater = CatalogUpdater(catalog_path=temp_catalog_path, ttl=0.1)
        updater.update(sample_models)
        assert updater.is_stale is False
        time.sleep(0.15)
        assert updater.is_stale is True

    def test_persistence(self, temp_catalog_path: Path,
                          sample_models: dict[str, ModelRecord]) -> None:
        """Test that catalog persists to disk and loads back."""
        updater = CatalogUpdater(catalog_path=temp_catalog_path, ttl=60.0)
        updater.update(sample_models)

        # Create a new updater pointing to same file
        updater2 = CatalogUpdater(catalog_path=temp_catalog_path, ttl=60.0)
        assert updater2.catalog is not None
        assert len(updater2.catalog) == len(sample_models)
        for name in sample_models:
            assert name in updater2.catalog

    def test_diff_no_changes(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test diff when models are identical."""
        updater = CatalogUpdater(ttl=60.0)
        diff = updater.compute_diff(sample_models, sample_models)
        assert diff.has_changes is False
        assert len(diff.added) == 0
        assert len(diff.removed) == 0
        assert len(diff.changed) == 0
        assert len(diff.unchanged) == len(sample_models)

    def test_diff_added(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test diff detection for newly added models."""
        old = dict(sample_models)
        new = dict(sample_models)
        new["new-model"] = ModelRecord(
            name="new-model",
            size_bytes=500,
            family="new",
            last_seen=time.time(),
            first_seen=time.time(),
        )

        updater = CatalogUpdater(ttl=60.0)
        diff = updater.compute_diff(old, new)
        assert diff.has_changes is True
        assert len(diff.added) == 1
        assert diff.added[0].name == "new-model"
        assert len(diff.removed) == 0

    def test_diff_removed(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test diff detection for removed models."""
        old = dict(sample_models)
        new = dict(sample_models)
        removed_name = list(new.keys())[0]
        del new[removed_name]

        updater = CatalogUpdater(ttl=60.0)
        diff = updater.compute_diff(old, new)
        assert diff.has_changes is True
        assert len(diff.removed) == 1
        assert diff.removed[0].name == removed_name
        assert len(diff.added) == 0

    def test_diff_changed(self) -> None:
        """Test diff detection for changed model metadata."""
        now = time.time()
        old = {
            "test-model": ModelRecord(
                name="test-model",
                size_bytes=100,
                family="old-family",
                quantization="Q4_0",
                parameters="7B",
                last_seen=now,
            )
        }
        new = {
            "test-model": ModelRecord(
                name="test-model",
                size_bytes=200,  # size changed
                family="old-family",
                quantization="Q5_K_M",  # quantization changed
                parameters="7B",
                last_seen=now + 1,
            )
        }

        updater = CatalogUpdater(ttl=60.0)
        diff = updater.compute_diff(old, new)
        assert diff.has_changes is True
        assert len(diff.changed) == 1
        assert len(diff.added) == 0
        assert len(diff.removed) == 0

    def test_diff_mixed(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test diff with added, removed, and unchanged models."""
        old = dict(sample_models)
        new = dict(sample_models)
        removed_name = list(new.keys())[0]
        del new[removed_name]
        new["brand-new"] = ModelRecord(
            name="brand-new",
            size_bytes=999,
            family="new",
            last_seen=time.time(),
            first_seen=time.time(),
        )

        updater = CatalogUpdater(ttl=60.0)
        diff = updater.compute_diff(old, new)
        assert diff.has_changes is True
        assert len(diff.added) == 1
        assert len(diff.removed) == 1
        assert diff.summary["added_count"] == 1
        assert diff.summary["removed_count"] == 1

    def test_get_model(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test retrieving a single model from catalog."""
        updater = CatalogUpdater(ttl=60.0)
        updater.update(sample_models)
        model = updater.get_model("kimi-k2.6:cloud")
        assert model is not None
        assert model.name == "kimi-k2.6:cloud"

    def test_get_model_missing(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test retrieving a non-existent model."""
        updater = CatalogUpdater(ttl=60.0)
        updater.update(sample_models)
        assert updater.get_model("nonexistent") is None

    def test_list_models(self, sample_models: dict[str, ModelRecord]) -> None:
        """Test listing all models in catalog."""
        updater = CatalogUpdater(ttl=60.0)
        updater.update(sample_models)
        models = updater.list_models()
        assert len(models) == len(sample_models)
        names = [m.name for m in models]
        assert names == sorted(names)  # sorted by name

    def test_summary(self, sample_models: dict[str, ModelRecord],
                      temp_catalog_path: Path) -> None:
        """Test catalog summary output."""
        updater = CatalogUpdater(catalog_path=temp_catalog_path, ttl=60.0)
        updater.update(sample_models)
        summary = updater.summary()
        assert summary["model_count"] == len(sample_models)
        assert summary["is_stale"] is False
        assert "last_updated" in summary
        assert "ttl" in summary


# ── PulseMonitor Tests ────────────────────────────────────────────────────────


class TestPulseMonitor:
    """Test PulseMonitor — periodic scanning and catalog sync."""

    def test_scan_triggers_scanner(self) -> None:
        """Test that scan() delegates to scanner and tracks count."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": []}
            mock_get.return_value = mock_resp

            monitor = PulseMonitor(scan_interval=999)
            result = monitor.scan()
            assert isinstance(result, dict)
            assert monitor.scan_count == 1

    def test_update_catalog(self) -> None:
        """Test update_catalog scans and syncs."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "models": [
                    {
                        "name": "test-model",
                        "size": 100,
                        "details": {"family": "test"},
                    }
                ]
            }
            mock_get.return_value = mock_resp

            with patch("hlf_mcp.hlf.ollama_pulse.httpx.post") as mock_post:
                mock_show = MagicMock()
                mock_show.status_code = 200
                mock_show.json.return_value = {}
                mock_post.return_value = mock_show

                monitor = PulseMonitor(scan_interval=999)
                diff = monitor.update_catalog()

                assert diff is not None
                assert monitor.last_diff is not None

    def test_ensure_fresh_when_stale(self) -> None:
        """Test ensure_fresh scans when catalog is stale."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": []}
            mock_get.return_value = mock_resp

            monitor = PulseMonitor(scan_interval=999, catalog_ttl=0.0)
            # Initially stale
            assert monitor.updater.is_stale is True
            result = monitor.ensure_fresh()
            # Should have scanned since it was stale
            assert result is not None

    def test_ensure_fresh_when_fresh(self) -> None:
        """Test ensure_fresh skips scan when catalog is fresh."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"models": []}
            mock_get.return_value = mock_resp

            monitor = PulseMonitor(scan_interval=999, catalog_ttl=9999)
            # Pre-populate to make it fresh
            monitor.updater.update({})
            assert monitor.updater.is_stale is False

            result = monitor.ensure_fresh()
            assert result is None  # Should not have scanned

    def test_status(self) -> None:
        """Test status output."""
        monitor = PulseMonitor(scan_interval=999)
        status = monitor.status()
        assert "running" in status
        assert "endpoint" in status
        assert "catalog" in status
        assert "scan_count" in status
        assert "error_count" in status

    def test_start_stop(self) -> None:
        """Test starting and stopping the background thread."""
        monitor = PulseMonitor(scan_interval=0.5)
        assert monitor.is_running is False

        monitor.start()
        assert monitor.is_running is True

        monitor.stop(timeout=2.0)
        assert monitor.is_running is False

    def test_start_when_running(self) -> None:
        """Test start() is idempotent — logs warning if already running."""
        monitor = PulseMonitor(scan_interval=999)
        monitor.start()
        assert monitor.is_running is True

        # Second start should be a no-op
        monitor.start()
        assert monitor.is_running is True

        monitor.stop(timeout=2.0)

    def test_error_count_increments(self) -> None:
        """Test that scan errors increment error_count."""
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            from httpx import ConnectError
            mock_get.side_effect = ConnectError("refused")

            monitor = PulseMonitor(scan_interval=999)
            assert monitor.error_count == 0
            monitor.scan()
            assert monitor.error_count == 1

    def test_graceful_offline_handling(self) -> None:
        """Test full graceful handling when Ollama is offline.
        
        Key assertion: no exceptions are raised, even when Ollama is unreachable.
        """
        with patch("hlf_mcp.hlf.ollama_pulse.httpx.get") as mock_get:
            from httpx import ConnectError
            mock_get.side_effect = ConnectError("refused")

            monitor = PulseMonitor(scan_interval=999, catalog_ttl=0.0)
            # 1. update_catalog should not crash
            diff = monitor.update_catalog()
            assert diff is not None  # returns DiffResult even on empty scan
            
            # 2. ensure_fresh should not crash
            #    (with ttl=0.0, catalog is immediately stale after update)
            result = monitor.ensure_fresh()
            assert result is not None  # stale → scans again
            
            # 3. status should not crash
            status = monitor.status()
            assert "error_count" in status


# ── Global Singleton Tests ────────────────────────────────────────────────────


class TestGlobalPulseMonitor:
    """Test global PulseMonitor singleton."""

    def test_get_pulse_monitor_creates(self) -> None:
        """Test that get_pulse_monitor creates a singleton."""
        import hlf_mcp.hlf.ollama_pulse as op
        # Reset global
        op._global_pulse_monitor = None

        m1 = get_pulse_monitor(auto_start=False)
        m2 = get_pulse_monitor(auto_start=False)
        assert m1 is m2  # Singleton

        # Cleanup
        op._global_pulse_monitor = None

    def test_get_pulse_monitor_custom_params(self) -> None:
        """Test get_pulse_monitor with custom endpoint."""
        import hlf_mcp.hlf.ollama_pulse as op
        op._global_pulse_monitor = None

        monitor = get_pulse_monitor(
            endpoint="http://custom:9999",
            scan_interval=60.0,
            catalog_ttl=120.0,
            auto_start=False,
        )
        assert monitor.scanner.endpoint == "http://custom:9999"

        op._global_pulse_monitor = None
