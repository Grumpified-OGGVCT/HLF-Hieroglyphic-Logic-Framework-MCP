from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path

import pytest

from hlf_mcp.hlf.oci_client import OCIClient, OCIError, OCIModuleRef


def _make_tar_layer(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for name, payload in files.items():
            info = tarfile.TarInfo(name=name)
            info.size = len(payload)
            tar.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def test_module_ref_parse_supports_bare_and_fully_qualified_refs() -> None:
    bare = OCIModuleRef.parse("math")
    full = OCIModuleRef.parse("ghcr.io/org/math:v1")

    assert bare.registry == "registry.hlf.io"
    assert bare.namespace == "library"
    assert bare.module == "math"
    assert bare.tag == "latest"
    assert str(full) == "ghcr.io/org/math:v1"


def test_cache_path_is_deterministic(tmp_path: Path) -> None:
    client = OCIClient(cache_path=tmp_path)
    ref = OCIModuleRef.parse("library/math:v1")

    path1 = client._cache_path(ref)
    path2 = client._cache_path(ref)

    assert path1 == path2
    assert str(path1).endswith(str(Path("registry.hlf.io") / "library" / "math" / "v1"))


def test_pull_uses_cache_hit_without_fetching(tmp_path: Path) -> None:
    client = OCIClient(cache_path=tmp_path)
    ref = OCIModuleRef.parse("math")
    cached = client._cache_path(ref)
    cached.mkdir(parents=True)
    (cached / "module.json").write_text(json.dumps({"name": "math"}), encoding="utf-8")

    result = client.pull(ref)

    assert result == cached


def test_extract_layers_writes_files_and_blocks_path_traversal(tmp_path: Path) -> None:
    client = OCIClient(cache_path=tmp_path)
    safe_target = tmp_path / "safe"
    safe_layer = _make_tar_layer({"module.json": b'{"name":"math"}'})

    client._extract_layers([safe_layer], safe_target)
    assert (safe_target / "module.json").exists()

    malicious = _make_tar_layer({"../escape.txt": b"nope"})
    with pytest.raises(OCIError, match="Path traversal"):
        client._extract_layers([malicious], tmp_path / "blocked")


def test_push_returns_simulated_digest_and_size(tmp_path: Path) -> None:
    module_dir = tmp_path / "math"
    module_dir.mkdir()
    (module_dir / "module.json").write_text(json.dumps({"name": "math"}), encoding="utf-8")

    client = OCIClient(cache_path=tmp_path)
    result = client.push(OCIModuleRef.parse("math:v1"), module_dir)

    assert result["status"] == "simulated"
    assert result["ref"] == "registry.hlf.io/library/math:v1"
    assert result["digest"].startswith("sha256:")
    assert result["size"] > 0


def test_get_checksum_and_list_tags_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = OCIClient(cache_path=tmp_path)

    def raise_manifest(ref: OCIModuleRef) -> dict:
        raise OCIError("offline")

    monkeypatch.setattr(client, "_fetch_manifest", raise_manifest)
    assert client.get_checksum(OCIModuleRef.parse("math")) is None

    def fake_urlopen(*args, **kwargs):
        raise OSError("offline")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert client.list_tags("library/math") == []


def test_pull_fetches_manifest_and_layers_when_cache_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = OCIClient(cache_path=tmp_path)
    ref = OCIModuleRef.parse("math:v1")
    layer = _make_tar_layer({"module.json": b'{"name":"math","version":"v1"}'})
    digest = "sha256:" + hashlib.sha256(layer).hexdigest()

    monkeypatch.setattr(client, "_fetch_manifest", lambda _ref: {"layers": [{"digest": digest}]})
    monkeypatch.setattr(client, "_fetch_blob", lambda _ref, _digest: layer)

    result = client.pull(ref)

    assert result.exists()
    assert (result / "module.json").exists()
