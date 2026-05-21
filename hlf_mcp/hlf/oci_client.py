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
                        # Re-validate every member before extracting without filter support
                        for member in tar.getmembers():
                            member_path = (target / member.name).resolve()
                            if not str(member_path).startswith(str(target.resolve())):
                                raise OCIError(f"Path traversal detected in layer: {member.name}")
                        tar.extractall(target)  # nosec B202
            except tarfile.TarError as exc:
                raise OCIError(f"Layer extraction failed: {exc}") from exc

    def push(self, ref: OCIModuleRef, module_path: Path) -> dict[str, Any]:
        """Push module to OCI registry.

        Strategy (in priority order):
        1. HTTP push to live registries (localhost, configured remotes)
        2. OCI Image Layout push to local cache (always works offline)

        Returns:
            Dict with status, ref, digest, size, and push_target (registry or layout path).
        """
        # Create tar.gz layer
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            tar.add(str(module_path), arcname=ref.module)
        layer_data = buf.getvalue()
        layer_digest = "sha256:" + hashlib.sha256(layer_data).hexdigest()
        size = len(layer_data)

        # Build an OCI image manifest
        manifest = {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "config": {
                "mediaType": "application/vnd.hlf.module.config.v1+json",
                "digest": layer_digest,
                "size": size,
            },
            "layers": [
                {
                    "mediaType": "application/vnd.hlf.module.layer.v1+tar+gzip",
                    "digest": layer_digest,
                    "size": size,
                    "annotations": {
                        "org.opencontainers.image.title": ref.module,
                        "hlf.namespace": ref.namespace,
                        "hlf.tag": ref.tag,
                        "hlf.version": "0.4.0",
                    },
                }
            ],
            "annotations": {
                "hlf.module": ref.module,
                "hlf.namespace": ref.namespace,
                "hlf.version": "0.4.0",
            },
        }
        manifest_bytes = json.dumps(manifest, indent=2).encode("utf-8")
        manifest_digest = "sha256:" + hashlib.sha256(manifest_bytes).hexdigest()

        # ── Strategy 1: HTTP push to live registry ──────────────────────────
        if self._is_live_registry(ref.registry):
            try:
                return self._push_http(ref, layer_data, layer_digest, manifest_bytes, manifest_digest)
            except Exception as exc:
                logger.warning("HTTP push failed, falling back to OCI layout: %s", exc)

        # ── Strategy 2: OCI Image Layout push (always works) ────────────────
        return self._push_layout(ref, layer_data, layer_digest, manifest_bytes, manifest_digest)

    def _is_live_registry(self, registry: str) -> bool:
        """Check if registry is a reachable HTTP endpoint."""
        if registry == DEFAULT_REGISTRY:
            # Check if the registry is actually running locally
            try:
                url = f"https://{registry}/v2/"
                req = urllib.request.Request(url, headers={"User-Agent": "HLF-OCI-Client/0.4.0"})
                with urllib.request.urlopen(req, timeout=3) as resp:
                    return resp.status == 200
            except Exception:
                pass
        if registry.startswith("localhost") or registry.startswith("127."):
            return True
        # Check for custom registries that respond
        try:
            url = f"https://{registry}/v2/"
            req = urllib.request.Request(url, headers={"User-Agent": "HLF-OCI-Client/0.4.0"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except Exception:
            pass
        return False

    def _push_http(
        self,
        ref: OCIModuleRef,
        layer_data: bytes,
        layer_digest: str,
        manifest_bytes: bytes,
        manifest_digest: str,
    ) -> dict[str, Any]:
        """Push to an OCI Distribution Spec HTTP registry."""
        repo = f"{ref.namespace}/{ref.module}"

        # 1. Initiate blob upload
        upload_url = f"https://{ref.registry}/v2/{repo}/blobs/uploads/"
        headers = {"User-Agent": "HLF-OCI-Client/0.4.0"}
        try:
            req = urllib.request.Request(upload_url, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                location = resp.headers.get("Location", upload_url)
        except urllib.error.HTTPError as exc:
            raise OCIError(f"Blob upload initiation failed: {exc.code} {exc.reason}") from exc

        # 2. Upload the blob
        upload_req = urllib.request.Request(
            f"{location}&digest={layer_digest}",
            data=layer_data,
            method="PUT",
            headers={**headers, "Content-Type": "application/octet-stream", "Content-Length": str(len(layer_data))},
        )
        try:
            with urllib.request.urlopen(upload_req, timeout=self.timeout) as resp:
                if resp.status not in (200, 201, 202):
                    raise OCIError(f"Blob upload failed: status {resp.status}")
        except urllib.error.HTTPError as exc:
            raise OCIError(f"Blob upload failed: {exc.code} {exc.reason}") from exc

        # 3. Push the manifest
        manifest_url = f"https://{ref.registry}/v2/{repo}/manifests/{ref.tag}"
        manifest_req = urllib.request.Request(
            manifest_url,
            data=manifest_bytes,
            method="PUT",
            headers={
                **headers,
                "Content-Type": "application/vnd.oci.image.manifest.v1+json",
                "Content-Length": str(len(manifest_bytes)),
            },
        )
        try:
            with urllib.request.urlopen(manifest_req, timeout=self.timeout) as resp:
                if resp.status not in (200, 201, 202):
                    raise OCIError(f"Manifest push failed: status {resp.status}")
        except urllib.error.HTTPError as exc:
            raise OCIError(f"Manifest push failed: {exc.code} {exc.reason}") from exc

        logger.info("OCI push (HTTP) succeeded: %s → %s", ref, ref.registry)
        return {
            "status": "pushed",
            "ref": str(ref),
            "digest": layer_digest,
            "manifest_digest": manifest_digest,
            "size": len(layer_data),
            "push_target": str(ref.registry),
        }

    def _push_layout(
        self,
        ref: OCIModuleRef,
        layer_data: bytes,
        layer_digest: str,
        manifest_bytes: bytes,
        manifest_digest: str,
    ) -> dict[str, Any]:
        """Push to an OCI Image Layout directory (local publishing)."""
        layout_dir = self.cache_path / "oci-layout"
        blobs_dir = layout_dir / "blobs" / "sha256"
        blobs_dir.mkdir(parents=True, exist_ok=True)

        # Write layer blob
        layer_hash = layer_digest.replace("sha256:", "")
        layer_path = blobs_dir / layer_hash
        if not layer_path.exists():
            layer_path.write_bytes(layer_data)

        # Write manifest blob
        mf_hash = manifest_digest.replace("sha256:", "")
        mf_path = blobs_dir / mf_hash
        if not mf_path.exists():
            mf_path.write_bytes(manifest_bytes)

        # Write/update OCI layout file
        oci_layout_path = layout_dir / "oci-layout"
        if not oci_layout_path.exists():
            oci_layout_path.write_text(json.dumps({"imageLayoutVersion": "1.0.0"}))

        # Write/update index.json
        index_path = layout_dir / "index.json"
        existing_index: dict[str, Any] = {"schemaVersion": 2, "manifests": []}
        if index_path.exists():
            try:
                existing_index = json.loads(index_path.read_text())
            except Exception:
                pass

        manifest_entry = {
            "mediaType": "application/vnd.oci.image.manifest.v1+json",
            "digest": manifest_digest,
            "size": len(manifest_bytes),
            "annotations": {
                "org.opencontainers.image.ref.name": str(ref),
                "hlf.module": ref.module,
                "hlf.namespace": ref.namespace,
            },
            "platform": {
                "architecture": "hlf",
                "os": "hlf-mcp",
            },
        }

        # Deduplicate: replace existing entry for same ref
        manifests = existing_index.get("manifests", [])
        manifests = [m for m in manifests if m.get("annotations", {}).get("org.opencontainers.image.ref.name") != str(ref)]
        manifests.append(manifest_entry)
        existing_index["manifests"] = manifests
        index_path.write_text(json.dumps(existing_index, indent=2))

        logger.info("OCI push (layout) succeeded: %s → %s", ref, layout_dir)
        return {
            "status": "pushed",
            "ref": str(ref),
            "digest": layer_digest,
            "manifest_digest": manifest_digest,
            "size": len(layer_data),
            "push_target": str(layout_dir),
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
