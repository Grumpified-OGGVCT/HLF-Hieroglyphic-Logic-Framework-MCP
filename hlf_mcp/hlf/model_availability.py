"""Dynamic Model Availability Cache with Deprecation Detection.

Provides a TTL-cached layer over OpenRouter's /models endpoint that:
  - Detects deprecated models via ``expiration_date``
  - Cross-references TOML config models against the live catalog
  - Uses ``canonical_slug`` for stable identity tracking
  - Marks models as available / deprecated / unavailable
  - Excludes ``openrouter/auto`` and ``openrouter/free`` from governed paths
  - Reports availability status for the MCP surface and orchestrator

Usage:
    from hlf_mcp.hlf.model_availability import ModelAvailabilityCache
    from hlf_mcp.hlf.openrouter_client import OpenRouterClient

    client = OpenRouterClient(api_key=...)
    cache = ModelAvailabilityCache(client, ttl_s=3600)
    status = await cache.check_model("deepseek/deepseek-r1")
    report = await cache.get_availability_report()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hlf_mcp.hlf.openrouter_client import ModelInfo, OpenRouterClient

logger = logging.getLogger(__name__)


# ── types ────────────────────────────────────────────────────────────────────


class ModelStatus(str, Enum):
    """Availability status for a model."""

    AVAILABLE = "available"
    DEPRECATED = "deprecated"          # expiration_date is set and past/near
    EXPIRING_SOON = "expiring_soon"    # expiration_date is set but still in future
    UNAVAILABLE = "unavailable"        # not found in live catalog
    EXCLUDED = "excluded"              # explicitly excluded (auto/free routers)


# Models that MUST NEVER be used for governed knowledge paths
_EXCLUDED_ROUTERS: frozenset[str] = frozenset({
    "openrouter/auto",
    "openrouter/free",
})

# Days threshold for "expiring soon" warning
_EXPIRY_WARNING_DAYS = 14


@dataclass(slots=True)
class ModelAvailabilityEntry:
    """Cached availability state for a single model."""

    model_id: str
    canonical_slug: str
    status: ModelStatus
    expiration_date: str | None
    supported_parameters: list[str]
    context_length: int
    is_free: bool
    pricing_prompt: float
    pricing_completion: float
    input_modalities: list[str]
    output_modalities: list[str]
    last_checked: float  # monotonic timestamp
    detail: str = ""     # human-readable status detail


@dataclass(slots=True)
class AvailabilityReport:
    """Summary of the full model availability check."""

    total_checked: int
    available: int
    deprecated: int
    expiring_soon: int
    unavailable: int
    excluded: int
    stale_config_models: list[str]  # config models not found in live catalog
    deprecated_models: list[str]    # config models that are deprecated
    expiring_models: list[str]      # config models expiring within warning window
    last_refresh: float             # monotonic timestamp of last full refresh
    cache_ttl_s: int


# ── cache ────────────────────────────────────────────────────────────────────


class ModelAvailabilityCache:
    """TTL-cached model availability layer over the OpenRouter /models API.

    Parameters
    ----------
    client : OpenRouterClient
        The OpenRouter client used to fetch live model data.
    ttl_s : int
        Cache time-to-live in seconds (default: 3600 = 1 hour).
    expiry_warning_days : int
        How many days before expiration to flag a model as "expiring_soon".
    """

    def __init__(
        self,
        client: OpenRouterClient,
        *,
        ttl_s: int = 3600,
        expiry_warning_days: int = _EXPIRY_WARNING_DAYS,
    ):
        self._client = client
        self._ttl_s = ttl_s
        self._expiry_warning_days = expiry_warning_days
        self._cache: dict[str, ModelAvailabilityEntry] = {}
        self._slug_index: dict[str, str] = {}  # canonical_slug -> model_id
        self._last_refresh: float = 0.0
        self._refreshing = False

    @property
    def is_stale(self) -> bool:
        """Whether the cache needs refreshing."""
        if not self._cache:
            return True
        return (time.monotonic() - self._last_refresh) >= self._ttl_s

    async def refresh(self, *, force: bool = False) -> int:
        """Refresh the cache from the live OpenRouter /models endpoint.

        Parameters
        ----------
        force : bool
            If True, refresh even if the cache is still valid.

        Returns
        -------
        int
            Number of models loaded into the cache.
        """
        if not force and not self.is_stale:
            return len(self._cache)

        if self._refreshing:
            logger.debug("Refresh already in progress — skipping")
            return len(self._cache)

        self._refreshing = True
        try:
            models = await self._client.list_models(
                include_free=True,
                max_models=0,  # unlimited — we want the full catalog
            )

            now = time.monotonic()
            new_cache: dict[str, ModelAvailabilityEntry] = {}
            new_slug_index: dict[str, str] = {}

            for m in models:
                status = self._evaluate_status(m)
                detail = self._status_detail(m, status)

                entry = ModelAvailabilityEntry(
                    model_id=m.id,
                    canonical_slug=m.canonical_slug,
                    status=status,
                    expiration_date=m.expiration_date,
                    supported_parameters=m.supported_parameters,
                    context_length=m.context_length,
                    is_free=m.is_free,
                    pricing_prompt=m.pricing_prompt,
                    pricing_completion=m.pricing_completion,
                    input_modalities=m.input_modalities,
                    output_modalities=m.output_modalities,
                    last_checked=now,
                    detail=detail,
                )
                new_cache[m.id] = entry

                if m.canonical_slug:
                    new_slug_index[m.canonical_slug] = m.id

            self._cache = new_cache
            self._slug_index = new_slug_index
            self._last_refresh = now

            deprecated_count = sum(
                1 for e in new_cache.values()
                if e.status == ModelStatus.DEPRECATED
            )
            expiring_count = sum(
                1 for e in new_cache.values()
                if e.status == ModelStatus.EXPIRING_SOON
            )

            logger.info(
                "Model availability cache refreshed: %d models "
                "(%d deprecated, %d expiring soon)",
                len(new_cache), deprecated_count, expiring_count,
            )
            return len(new_cache)

        except Exception as exc:
            logger.error("Failed to refresh model availability cache: %s", exc)
            # Keep stale cache rather than clearing it
            return len(self._cache)
        finally:
            self._refreshing = False

    async def check_model(self, model_id: str) -> ModelAvailabilityEntry | None:
        """Check availability of a specific model.

        Auto-refreshes if the cache is stale. Returns None if the model
        is not in the live catalog at all.
        """
        if self.is_stale:
            await self.refresh()

        # Direct lookup by ID
        if model_id in self._cache:
            return self._cache[model_id]

        # Try slug index
        if model_id in self._slug_index:
            real_id = self._slug_index[model_id]
            return self._cache.get(real_id)

        return None

    def is_excluded_router(self, model_id: str) -> bool:
        """Check if a model ID is an excluded auto/free router."""
        return model_id in _EXCLUDED_ROUTERS

    async def is_usable_for_governed_path(self, model_id: str) -> tuple[bool, str]:
        """Check if a model is safe for governed knowledge-critical paths.

        Returns (is_usable, reason). A model is NOT usable if:
        - It's an excluded router (auto/free)
        - It's deprecated (expiration_date is past)
        - It's not found in the live catalog
        """
        if self.is_excluded_router(model_id):
            return False, f"Model '{model_id}' is an excluded router — never use for governed paths"

        entry = await self.check_model(model_id)
        if entry is None:
            return False, f"Model '{model_id}' not found in live OpenRouter catalog"

        if entry.status == ModelStatus.DEPRECATED:
            return False, (
                f"Model '{model_id}' is deprecated "
                f"(expiration_date: {entry.expiration_date})"
            )

        if entry.status == ModelStatus.EXCLUDED:
            return False, f"Model '{model_id}' is explicitly excluded"

        # Expiring soon is allowed but generates a warning
        if entry.status == ModelStatus.EXPIRING_SOON:
            logger.warning(
                "Model %s is expiring soon (expiration_date: %s) — "
                "consider migrating to a replacement",
                model_id, entry.expiration_date,
            )

        return True, "ok"

    async def filter_chain_for_governed_path(
        self, model_ids: list[str]
    ) -> list[str]:
        """Filter an escalation chain, removing models that are unsafe for
        governed knowledge-critical paths.

        Returns a new list with only usable models.
        """
        if self.is_stale:
            await self.refresh()

        usable: list[str] = []
        for mid in model_ids:
            ok, reason = await self.is_usable_for_governed_path(mid)
            if ok:
                usable.append(mid)
            else:
                logger.info("Filtered out model %s: %s", mid, reason)
        return usable

    async def validate_config_models(
        self, config_model_ids: list[str]
    ) -> dict[str, ModelAvailabilityEntry | None]:
        """Validate a list of TOML-configured model IDs against the live catalog.

        Returns a dict mapping each model_id to its availability entry,
        or None if the model is not found in the live catalog.
        """
        if self.is_stale:
            await self.refresh()

        results: dict[str, ModelAvailabilityEntry | None] = {}
        for mid in config_model_ids:
            results[mid] = self._cache.get(mid)
        return results

    async def get_availability_report(
        self, config_model_ids: list[str] | None = None
    ) -> AvailabilityReport:
        """Generate a full availability report.

        Parameters
        ----------
        config_model_ids : list[str] | None
            If provided, cross-reference these TOML-configured model IDs
            against the live catalog. Otherwise just report on cache contents.
        """
        if self.is_stale:
            await self.refresh()

        available = sum(1 for e in self._cache.values() if e.status == ModelStatus.AVAILABLE)
        deprecated = sum(1 for e in self._cache.values() if e.status == ModelStatus.DEPRECATED)
        expiring = sum(1 for e in self._cache.values() if e.status == ModelStatus.EXPIRING_SOON)
        unavailable = 0
        excluded = sum(1 for e in self._cache.values() if e.status == ModelStatus.EXCLUDED)

        stale_config: list[str] = []
        deprecated_config: list[str] = []
        expiring_config: list[str] = []

        if config_model_ids:
            for mid in config_model_ids:
                entry = self._cache.get(mid)
                if entry is None:
                    stale_config.append(mid)
                    unavailable += 1
                elif entry.status == ModelStatus.DEPRECATED:
                    deprecated_config.append(mid)
                elif entry.status == ModelStatus.EXPIRING_SOON:
                    expiring_config.append(mid)

        return AvailabilityReport(
            total_checked=len(self._cache),
            available=available,
            deprecated=deprecated,
            expiring_soon=expiring,
            unavailable=unavailable,
            excluded=excluded,
            stale_config_models=stale_config,
            deprecated_models=deprecated_config,
            expiring_models=expiring_config,
            last_refresh=self._last_refresh,
            cache_ttl_s=self._ttl_s,
        )

    # ── internal helpers ─────────────────────────────────────────────────

    def _evaluate_status(self, model: ModelInfo) -> ModelStatus:
        """Determine the availability status of a model."""
        if model.id in _EXCLUDED_ROUTERS:
            return ModelStatus.EXCLUDED

        if model.expiration_date:
            try:
                exp_dt = datetime.fromisoformat(
                    model.expiration_date.replace("Z", "+00:00")
                )
                now_utc = datetime.now(timezone.utc)

                if exp_dt <= now_utc:
                    return ModelStatus.DEPRECATED

                days_until = (exp_dt - now_utc).days
                if days_until <= self._expiry_warning_days:
                    return ModelStatus.EXPIRING_SOON

            except (ValueError, TypeError):
                # Unparseable date — treat as deprecated to be safe
                logger.warning(
                    "Unparseable expiration_date for %s: %s — treating as deprecated",
                    model.id, model.expiration_date,
                )
                return ModelStatus.DEPRECATED

        return ModelStatus.AVAILABLE

    def _status_detail(self, model: ModelInfo, status: ModelStatus) -> str:
        """Generate a human-readable status detail string."""
        if status == ModelStatus.EXCLUDED:
            return "Auto/free router — excluded from governed paths"
        if status == ModelStatus.DEPRECATED:
            return f"Deprecated (expiration_date: {model.expiration_date})"
        if status == ModelStatus.EXPIRING_SOON:
            return f"Expiring soon (expiration_date: {model.expiration_date})"
        if status == ModelStatus.UNAVAILABLE:
            return "Not found in live catalog"
        return "Active and available"
