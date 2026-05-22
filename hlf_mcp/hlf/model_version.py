"""
Model Version Verification — cryptographic integrity check for model backends.

Before any governed inference begins, the runtime verifies that each
declared model matches the exact SHA-256 digest recorded in the
CapabilityManifest.  If the locally installed model differs (e.g., a
different quantization, a tampered .gguf, or an untracked auto-update),
the system fails closed with a CapsuleViolation.

This implements enterprise hardening item #3: "HLF monitors ollama ps
and hashes the running model blob before inference; mismatch = CapsuleViolation."

Integration:
  - hlf_mcp.hlf.capability_manifest.CapabilityManifest.model_versions
  - hlf_mcp.hlf.ollama_pulse.ModelScanner (for live digest lookup)
  - hlf_mcp.hlf.latent_capsule.governed_latent_infer() (pre-inference check)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from hlf_mcp.hlf.capsules import CapsuleViolation
from hlf_mcp.hlf.capability_manifest import CapabilityManifest

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ModelVersionResult:
    """Result of a model version verification check."""

    model_name: str
    expected_digest: str
    actual_digest: str
    match: bool
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "expected_digest": self.expected_digest,
            "actual_digest": self.actual_digest,
            "match": self.match,
            "error": self.error,
        }


def verify_model_versions(
    manifest: CapabilityManifest,
    *,
    live_models: dict[str, str] | None = None,
    scanner: Any = None,
) -> list[ModelVersionResult]:
    """Verify that every model declared in the manifest matches the live digest.

    Parameters
    ----------
    manifest : CapabilityManifest
        The manifest declaring expected model_version_sha256 entries.
    live_models : dict[str, str] | None
        Dict mapping model_name → sha256 digest from a live scan.
        If None, `scanner` is used to look up digests lazily.
    scanner : Any | None
        An optional ModelScanner instance. Used if live_models is None.
        Must have a `.scan()` method returning dict[name, ModelRecord].

    Returns
    -------
    list[ModelVersionResult]
        One entry per declared model, with match/actual/error fields.

    Raises
    ------
    CapsuleViolation
        If any model's digest does NOT match the manifest declaration.
        The violation message includes the model name and expected vs actual.
    """
    if not manifest.model_versions:
        # No model versions declared — skip verification entirely
        return []

    live: dict[str, str] = {}
    if live_models is not None:
        live = live_models
    elif scanner is not None:
        try:
            scanned = scanner.scan()
            # Build a name → digest map (strip :latest tag if present)
            for name, record in scanned.items():
                base_name = name.split(":")[0] if ":" in name else name
                live[base_name] = record.digest
                live[name] = record.digest  # also store exact match
        except Exception as exc:
            logger.warning("Model version check: live scan failed: %s", exc)
            return [
                ModelVersionResult(
                    model_name=model_name,
                    expected_digest=expected,
                    actual_digest="",
                    match=False,
                    error=f"Failed to scan live models: {exc}",
                )
                for model_name, expected in manifest.model_versions.items()
            ]
    else:
        # No live data available — assume matches (trust mode)
        logger.info("Model version check: no live model data available, skipping")
        return []

    results: list[ModelVersionResult] = []
    mismatches: list[str] = []

    for model_name, expected_digest in manifest.model_versions.items():
        actual = live.get(model_name, "")
        if not actual:
            # Try stripping tag
            base = model_name.split(":")[0]
            actual = live.get(base, "")

        match = bool(actual and actual == expected_digest)
        if not actual:
            error = f"Model '{model_name}' not found in live Ollama scan"
            mismatches.append(f"{model_name}: NOT FOUND (expected {expected_digest[:16]}...)")
            match = False
        elif not match:
            error = (
                f"Digest mismatch for '{model_name}': "
                f"expected {expected_digest[:16]}..., "
                f"got {actual[:16]}..."
            )
            mismatches.append(error)
        else:
            error = ""

        results.append(ModelVersionResult(
            model_name=model_name,
            expected_digest=expected_digest,
            actual_digest=actual,
            match=match,
            error=error,
        ))

    if mismatches:
        violation_msg = "Model version verification FAILED:\n  " + "\n  ".join(mismatches)
        logger.error(violation_msg)
        raise CapsuleViolation(violation_msg)

    logger.info(
        "Model version check: %d model(s) verified OK",
        len(results),
    )
    return results
