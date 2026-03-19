from __future__ import annotations

import json
from pathlib import Path

import pytest

from hlf_mcp.hlf.hlfpm import HlfPackageManager, HlfPmError
from hlf_mcp.hlf.oci_client import OCIError, OCIModuleRef


class FakeOCIClient:
    def __init__(
        self,
        pulled_path: Path | None = None,
        checksum: str | None = None,
        tags: list[str] | None = None,
    ):
        self.pulled_path = pulled_path
        self.checksum = checksum
        self.tags = tags or []
        self.pull_calls: list[str] = []

    def pull(self, ref: OCIModuleRef) -> Path:
        self.pull_calls.append(str(ref))
        if self.pulled_path is None:
            raise OCIError("offline")
        return self.pulled_path

    def get_checksum(self, ref: OCIModuleRef) -> str | None:
        return self.checksum

    def list_tags(self, repository: str) -> list[str]:
        return list(self.tags)


def test_install_offline_creates_stub_module(tmp_path: Path) -> None:
    install_root = tmp_path / "modules"
    pm = HlfPackageManager(
        install_root=install_root, lockfile=tmp_path / "hlf.lock.json", oci_client=FakeOCIClient()
    )

    result = pm.install("math@v1.0.0")

    assert result["status"] == "stub_installed"
    meta = json.loads((install_root / "math" / "module.json").read_text(encoding="utf-8"))
    assert meta["name"] == "math"
    assert meta["status"] == "stub"


def test_install_copies_pulled_module_and_respects_checksum(tmp_path: Path) -> None:
    source_root = tmp_path / "cache" / "math"
    source_root.mkdir(parents=True)
    (source_root / "module.json").write_text(
        json.dumps({"name": "math", "ref": "registry.hlf.io/library/math:v1.0.0"}, indent=2),
        encoding="utf-8",
    )
    (source_root / "math.hlf").write_text('[HLF-v3]\nRESULT 0 "ok"\nΩ\n', encoding="utf-8")

    temp_pm = HlfPackageManager(
        install_root=tmp_path / "unused",
        lockfile=tmp_path / "unused.lock.json",
        oci_client=FakeOCIClient(),
    )
    checksum = temp_pm._compute_checksum(source_root)

    pm = HlfPackageManager(
        install_root=tmp_path / "modules",
        lockfile=tmp_path / "hlf.lock.json",
        oci_client=FakeOCIClient(pulled_path=source_root, checksum=checksum),
    )

    result = pm.install("math@v1.0.0")

    assert result["status"] == "installed"
    assert (tmp_path / "modules" / "math" / "math.hlf").exists()
    listed = pm.list_installed()
    assert listed[0]["name"] == "math"


def test_install_raises_on_checksum_mismatch(tmp_path: Path) -> None:
    source_root = tmp_path / "cache" / "crypto"
    source_root.mkdir(parents=True)
    (source_root / "module.json").write_text(json.dumps({"name": "crypto"}), encoding="utf-8")

    pm = HlfPackageManager(
        install_root=tmp_path / "modules",
        lockfile=tmp_path / "hlf.lock.json",
        oci_client=FakeOCIClient(pulled_path=source_root, checksum="deadbeef"),
    )

    with pytest.raises(HlfPmError, match="Checksum mismatch"):
        pm.install("crypto@v1")


def test_uninstall_and_freeze_roundtrip(tmp_path: Path) -> None:
    install_root = tmp_path / "modules"
    module_dir = install_root / "string"
    module_dir.mkdir(parents=True)
    (module_dir / "module.json").write_text(
        json.dumps({"name": "string", "ref": "registry.hlf.io/library/string:latest"}, indent=2),
        encoding="utf-8",
    )
    (module_dir / "impl.py").write_text("VALUE = 1\n", encoding="utf-8")

    lockfile = tmp_path / "hlf.lock.json"
    pm = HlfPackageManager(install_root=install_root, lockfile=lockfile, oci_client=FakeOCIClient())

    frozen = pm.freeze()
    assert frozen["version"] == "1.0"
    assert frozen["packages"][0]["name"] == "string"
    assert lockfile.exists()

    result = pm.uninstall("string")
    assert result["status"] == "uninstalled"
    assert not module_dir.exists()


def test_search_and_update_behave_against_client_and_installed_state(tmp_path: Path) -> None:
    install_root = tmp_path / "modules"
    pm = HlfPackageManager(
        install_root=install_root,
        lockfile=tmp_path / "hlf.lock.json",
        oci_client=FakeOCIClient(tags=["v1.0.0", "latest"]),
    )

    search = pm.search("math")
    assert search[0]["name"] == "math"
    assert {item["tag"] for item in search} == {"v1.0.0", "latest"}

    source_root = tmp_path / "cache" / "math"
    source_root.mkdir(parents=True)
    (source_root / "module.json").write_text(json.dumps({"name": "math"}), encoding="utf-8")
    pm.oci_client.pulled_path = source_root
    pm.oci_client.checksum = pm._compute_checksum(source_root)

    update_result = pm.update("math")
    assert update_result["status"] in {"installed", "stub_installed"}
