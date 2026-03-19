"""
HLF OCI Client — OCI Distribution Spec client for HLF module registry.

Default registry: registry.hlf.io (simulated for offline use)
Cache: ~/.hlf/oci_cache/{registry}/{namespace}/{module}/{tag}/
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import logging
import tarfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_REGISTRY = "registry.hlf.io"


class OCIError(Exception):
    pass


@dataclasses.dataclass
class OCIModuleRef:
    registry: str
    namespace: str
    module: str
    tag: str

    @classmethod
    def parse(cls, ref: str) -> OCIModuleRef:
        """Parse reference forms like `module`, `module@v1`, `ns/module[:tag]`, or `registry/ns/module[:tag]`."""
        normalized = ref.strip()
        if not normalized:
            raise OCIError(f"Invalid module reference: {ref!r}")
        if normalized.startswith("oci://"):
            normalized = normalized[len("oci://") :]

        parts = [part for part in normalized.split("/") if part]
        if not parts:
            raise OCIError(f"Invalid module reference: {ref!r}")

        registry = DEFAULT_REGISTRY
        if len(parts) >= 3 and ("." in parts[0] or ":" in parts[0] or parts[0] == "localhost"):
            registry = parts[0]
            remainder = parts[1:]
        else:
            remainder = parts

        if len(remainder) == 1:
            namespace = "library"
            module_tag = remainder[0]
        else:
            namespace = "/".join(remainder[:-1])
            module_tag = remainder[-1]

        if "@" in module_tag:
            module, tag = module_tag.rsplit("@", 1)
        elif ":" in module_tag:
            module, tag = module_tag.rsplit(":", 1)
        else:
            module, tag = module_tag, "latest"

        if not module or not namespace:
            raise OCIError(f"Invalid module reference: {ref!r}")
        return cls(registry=registry, namespace=namespace, module=module, tag=tag)

    def __str__(self) -> str:
        return f"{self.registry}/{self.namespace}/{self.module}:{self.tag}"


class OCIClient:
    """OCI Distribution Spec client for HLF modules."""

    def __init__(self, cache_path: Path | None = None, timeout: int = 30):
        self.cache_path = cache_path or Path.home() / ".hlf" / "oci_cache"
        self.timeout = timeout

    def pull(self, ref: OCIModuleRef) -> Path:
        """Pull module, returning local path. Uses cache if available."""
        cached = self._cache_path(ref)
        if cached.exists():
            logger.debug("OCI cache hit: %s", ref)
            return cached
        try:
            manifest = self._fetch_manifest(ref)
            layers: list[bytes] = []
            for layer_desc in manifest.get("layers", []):
                blob = self._fetch_blob(ref, layer_desc["digest"])
                layers.append(blob)
            self._extract_layers(layers, cached)
            return cached
        except OCIError:
            raise
        except Exception as exc:
            raise OCIError(f"Pull failed for {ref}: {exc}") from exc

    def _fetch_manifest(self, ref: OCIModuleRef) -> dict[str, Any]:
        url = f"https://{ref.registry}/v2/{ref.namespace}/{ref.module}/manifests/{ref.tag}"
        headers = {
            "Accept": "application/vnd.oci.image.manifest.v1+json",
            "User-Agent": "HLF-OCI-Client/0.4.0",
        }
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise OCIError(f"Manifest fetch failed: {exc.code} {exc.reason}") from exc
        except Exception as exc:
            raise OCIError(f"Manifest fetch failed: {exc}") from exc

    def _fetch_blob(self, ref: OCIModuleRef, digest: str) -> bytes:
        url = f"https://{ref.registry}/v2/{ref.namespace}/{ref.module}/blobs/{digest}"
        request = urllib.request.Request(url, headers={"User-Agent": "HLF-OCI-Client/0.4.0"})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as resp:
                return resp.read()
        except Exception as exc:
            raise OCIError(f"Blob fetch failed ({digest[:16]}...): {exc}") from exc

    def _extract_layers(self, layers: list[bytes], target: Path) -> None:
        target.mkdir(parents=True, exist_ok=True)
        for layer_data in layers:
            try:
                with tarfile.open(fileobj=io.BytesIO(layer_data), mode="r:gz") as tar:
                    for member in tar.getmembers():
                        member_path = (target / member.name).resolve()
                        if not str(member_path).startswith(str(target.resolve())):
                            raise OCIError(f"Path traversal detected in layer: {member.name}")
                    try:
                        tar.extractall(target, filter="data")
                    except TypeError:  # pragma: no cover - older Python fallback
                        tar.extractall(target)
            except tarfile.TarError as exc:
                raise OCIError(f"Layer extraction failed: {exc}") from exc

    def push(self, ref: OCIModuleRef, module_path: Path) -> dict[str, Any]:
        """Push module to OCI registry — creates a tar.gz layer and uploads."""
        # Create tar.gz layer
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(module_path), arcname=ref.module)
        layer_data = buf.getvalue()
        digest = "sha256:" + hashlib.sha256(layer_data).hexdigest()
        size = len(layer_data)
        # For local/offline use, simulate success
        logger.warning("OCI push is simulated (no live registry configured): %s", ref)
        return {
            "status": "simulated",
            "ref": str(ref),
            "digest": digest,
            "size": size,
        }

    def list_tags(self, repository: str) -> list[str]:
        """List available tags for a repository (best-effort)."""
        parts = repository.split("/")
        namespace = parts[-2] if len(parts) >= 2 else "library"
        module = parts[-1].replace("*", "")
        url = f"https://{DEFAULT_REGISTRY}/v2/{namespace}/{module}/tags/list"
        try:
            with urllib.request.urlopen(url, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("tags", [])
        except Exception:
            return []

    def get_checksum(self, ref: OCIModuleRef) -> str | None:
        """Get expected SHA-256 checksum from manifest annotations."""
        try:
            manifest = self._fetch_manifest(ref)
            return manifest.get("annotations", {}).get("hlf.checksum")
        except Exception:
            return None

    def _cache_path(self, ref: OCIModuleRef) -> Path:
        return self.cache_path / ref.registry / ref.namespace / ref.module / ref.tag
