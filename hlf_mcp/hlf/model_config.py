"""HLF Model Substrate Configuration Loader.

Loads governed model provider config from TOML, validates it, and
produces structured provider/model/escalation data for the rest of
the model substrate (model_catalog.py, openrouter_client.py, etc.).

Resolution order (highest precedence first):
  1. HLF_MODEL_CONFIG env var -> path to user TOML override
  2. ~/.hlf/model_providers.toml (per-user)
  3. governance/model_providers.toml (repo default)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# tomllib is stdlib from 3.11+; tomli is the pip backport
try:
    import tomllib  # type: ignore[import-not-found]
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[import-not-found,no-redef]
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


_GOVERNANCE_DEFAULT = (
    Path(__file__).resolve().parents[2] / "governance" / "model_providers.toml"
)
_USER_HOME_CONFIG = Path.home() / ".hlf" / "model_providers.toml"


# ── dataclasses ──────────────────────────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class ProviderConfig:
    """Connection and resilience parameters for a single cloud provider."""
    name: str
    enabled: bool
    base_url: str
    api_key_env: str
    priority: int
    timeout_connect_s: float = 20.0
    timeout_read_s: float = 60.0
    timeout_total_s: float = 600.0
    max_retries: int = 3
    backoff_base_s: float = 2.0
    backoff_max_s: float = 90.0
    circuit_breaker_threshold: int = 4
    circuit_breaker_recovery_s: float = 300.0
    # OpenRouter-specific
    app_name: str = ""
    app_url: str = ""
    prefer_free: bool = False


@dataclass(slots=True, frozen=True)
class CloudModelEntry:
    """A single model from the TOML registry (Ollama Cloud or OpenRouter)."""
    name: str
    provider: str  # "ollama_cloud" | "openrouter"
    enabled: bool
    family: str
    lanes: tuple[str, ...]
    capabilities: tuple[str, ...]
    languages: tuple[str, ...]
    context_k: int
    description: str = ""
    supports_think: bool = False
    is_free: bool = False


@dataclass(slots=True, frozen=True)
class EscalationConfig:
    """Cross-provider escalation rules."""
    strategy: str  # "priority" | "round-robin" | "cost-optimized"
    fallback_on_auth_failure: bool = False
    fallback_on_rate_limit: bool = True
    fallback_on_model_not_found: bool = True
    fallback_on_timeout: bool = True
    fallback_on_server_error: bool = True


@dataclass(slots=True, frozen=True)
class DiscoveryConfig:
    """Model auto-discovery settings."""
    auto_discover_ollama: bool = True
    auto_discover_openrouter: bool = True
    discovery_cache_ttl_s: int = 3600
    openrouter_family_filter: tuple[str, ...] = ()
    openrouter_include_free: bool = True
    openrouter_max_models: int = 200


@dataclass(slots=True, frozen=True)
class ProviderPreferencesConfig:
    """OpenRouter provider routing preferences (request-level ``provider`` object)."""
    require_parameters: bool = True
    data_collection: str = "deny"   # "allow" | "deny"
    sort: str = "price"             # "price" | "throughput" | "latency"
    allow_fallbacks: bool = True
    quantizations: tuple[str, ...] = ()
    only: tuple[str, ...] = ()      # whitelist provider slugs
    ignore: tuple[str, ...] = ()    # blacklist provider slugs
    max_price_prompt: str | None = None    # USD per token cap
    max_price_completion: str | None = None

    def to_provider_dict(self) -> dict[str, Any]:
        """Build the OpenRouter ``provider`` request body object."""
        d: dict[str, Any] = {
            "require_parameters": self.require_parameters,
            "data_collection": self.data_collection,
            "sort": self.sort,
            "allow_fallbacks": self.allow_fallbacks,
        }
        if self.quantizations:
            d["quantizations"] = list(self.quantizations)
        if self.only:
            d["only"] = list(self.only)
        if self.ignore:
            d["ignore"] = list(self.ignore)
        max_price: dict[str, str] = {}
        if self.max_price_prompt is not None:
            max_price["prompt"] = self.max_price_prompt
        if self.max_price_completion is not None:
            max_price["completion"] = self.max_price_completion
        if max_price:
            d["max_price"] = max_price
        return d


@dataclass(slots=True, frozen=True)
class GovernedPathsConfig:
    """Hard safety constraints for knowledge-critical execution paths."""
    excluded_routers: tuple[str, ...] = ("openrouter/auto", "openrouter/free")
    strict_model_verification: bool = True
    require_live_availability: bool = True
    # Response quality gates — apply to ALL providers including Ollama
    reject_truncated: bool = True
    min_content_chars: int = 1
    require_model_match: bool = True
    require_nonzero_tokens: bool = True


@dataclass(slots=True)
class ModelSubstrateConfig:
    """Top-level config produced by loading model_providers.toml."""
    version: str
    providers: dict[str, ProviderConfig] = field(default_factory=dict)
    ollama_models: dict[str, CloudModelEntry] = field(default_factory=dict)
    openrouter_models: dict[str, CloudModelEntry] = field(default_factory=dict)
    escalation: EscalationConfig = field(
        default_factory=lambda: EscalationConfig(strategy="priority")
    )
    discovery: DiscoveryConfig = field(default_factory=DiscoveryConfig)
    provider_preferences: ProviderPreferencesConfig = field(
        default_factory=ProviderPreferencesConfig
    )
    governed_paths: GovernedPathsConfig = field(
        default_factory=GovernedPathsConfig
    )
    chain_overrides: dict[str, list[str]] = field(default_factory=dict)
    source_path: str = ""


# ── parsing helpers ──────────────────────────────────────────────────────────

def _parse_provider(name: str, raw: dict[str, Any]) -> ProviderConfig:
    return ProviderConfig(
        name=name,
        enabled=bool(raw.get("enabled", True)),
        base_url=str(raw.get("base_url", "")),
        api_key_env=str(raw.get("api_key_env", "")),
        priority=int(raw.get("priority", 99)),
        timeout_connect_s=float(raw.get("timeout_connect_s", 20)),
        timeout_read_s=float(raw.get("timeout_read_s", 60)),
        timeout_total_s=float(raw.get("timeout_total_s", 600)),
        max_retries=int(raw.get("max_retries", 3)),
        backoff_base_s=float(raw.get("backoff_base_s", 2.0)),
        backoff_max_s=float(raw.get("backoff_max_s", 90.0)),
        circuit_breaker_threshold=int(raw.get("circuit_breaker_threshold", 4)),
        circuit_breaker_recovery_s=float(raw.get("circuit_breaker_recovery_s", 300.0)),
        app_name=str(raw.get("app_name", "")),
        app_url=str(raw.get("app_url", "")),
        prefer_free=bool(raw.get("prefer_free", False)),
    )


def _parse_model(key: str, raw: dict[str, Any], provider: str) -> CloudModelEntry:
    return CloudModelEntry(
        name=key,
        provider=provider,
        enabled=bool(raw.get("enabled", True)),
        family=str(raw.get("family", "unknown")),
        lanes=tuple(str(s) for s in raw.get("lanes", [])),
        capabilities=tuple(str(s) for s in raw.get("capabilities", [])),
        languages=tuple(str(s) for s in raw.get("languages", [])),
        context_k=int(raw.get("context_k", 0)),
        description=str(raw.get("description", "")),
        supports_think=bool(raw.get("supports_think", False)),
        is_free=bool(raw.get("is_free", False)),
    )


def _parse_escalation(raw: dict[str, Any]) -> EscalationConfig:
    return EscalationConfig(
        strategy=str(raw.get("strategy", "priority")),
        fallback_on_auth_failure=bool(raw.get("fallback_on_auth_failure", False)),
        fallback_on_rate_limit=bool(raw.get("fallback_on_rate_limit", True)),
        fallback_on_model_not_found=bool(raw.get("fallback_on_model_not_found", True)),
        fallback_on_timeout=bool(raw.get("fallback_on_timeout", True)),
        fallback_on_server_error=bool(raw.get("fallback_on_server_error", True)),
    )


def _parse_discovery(raw: dict[str, Any]) -> DiscoveryConfig:
    return DiscoveryConfig(
        auto_discover_ollama=bool(raw.get("auto_discover_ollama", True)),
        auto_discover_openrouter=bool(raw.get("auto_discover_openrouter", True)),
        discovery_cache_ttl_s=int(raw.get("discovery_cache_ttl_s", 3600)),
        openrouter_family_filter=tuple(
            str(s) for s in raw.get("openrouter_family_filter", [])
        ),
        openrouter_include_free=bool(raw.get("openrouter_include_free", True)),
        openrouter_max_models=int(raw.get("openrouter_max_models", 200)),
    )


def _parse_provider_preferences(raw: dict[str, Any]) -> ProviderPreferencesConfig:
    max_price = raw.get("max_price", {})
    return ProviderPreferencesConfig(
        require_parameters=bool(raw.get("require_parameters", True)),
        data_collection=str(raw.get("data_collection", "deny")),
        sort=str(raw.get("sort", "price")),
        allow_fallbacks=bool(raw.get("allow_fallbacks", True)),
        quantizations=tuple(str(s) for s in raw.get("quantizations", [])),
        only=tuple(str(s) for s in raw.get("only", [])),
        ignore=tuple(str(s) for s in raw.get("ignore", [])),
        max_price_prompt=str(max_price["prompt"]) if "prompt" in max_price else None,
        max_price_completion=str(max_price["completion"]) if "completion" in max_price else None,
    )


def _parse_governed_paths(raw: dict[str, Any]) -> GovernedPathsConfig:
    return GovernedPathsConfig(
        excluded_routers=tuple(
            str(s) for s in raw.get("excluded_routers", ["openrouter/auto", "openrouter/free"])
        ),
        strict_model_verification=bool(raw.get("strict_model_verification", True)),
        require_live_availability=bool(raw.get("require_live_availability", True)),
        reject_truncated=bool(raw.get("reject_truncated", True)),
        min_content_chars=int(raw.get("min_content_chars", 1)),
        require_model_match=bool(raw.get("require_model_match", True)),
        require_nonzero_tokens=bool(raw.get("require_nonzero_tokens", True)),
    )


# ── main loader ──────────────────────────────────────────────────────────────

def _resolve_config_path() -> Path | None:
    """Resolve the TOML config path using the 3-level precedence chain."""
    env_override = os.environ.get("HLF_MODEL_CONFIG")
    if env_override:
        p = Path(env_override)
        if p.is_file():
            return p
        logger.warning("HLF_MODEL_CONFIG=%s does not exist — falling through", env_override)

    if _USER_HOME_CONFIG.is_file():
        return _USER_HOME_CONFIG

    if _GOVERNANCE_DEFAULT.is_file():
        return _GOVERNANCE_DEFAULT

    return None


def load_model_config(path: Path | str | None = None) -> ModelSubstrateConfig:
    """Load and validate the model substrate configuration.

    Parameters
    ----------
    path : Path | str | None
        Explicit path to a TOML file. If ``None``, uses the standard
        resolution chain (env var → user home → governance default).

    Returns
    -------
    ModelSubstrateConfig
        Fully parsed and validated configuration.

    Raises
    ------
    RuntimeError
        If no TOML parser is available (Python < 3.11 without ``tomli``).
    FileNotFoundError
        If no config file is found at any resolution level.
    """
    if tomllib is None:
        raise RuntimeError(
            "No TOML parser available. Install 'tomli' or use Python 3.11+."
        )

    resolved = Path(path) if path else _resolve_config_path()
    if resolved is None or not resolved.is_file():
        raise FileNotFoundError(
            f"No model_providers.toml found. Searched: "
            f"HLF_MODEL_CONFIG env, {_USER_HOME_CONFIG}, {_GOVERNANCE_DEFAULT}"
        )

    logger.info("Loading model substrate config from %s", resolved)
    with open(resolved, "rb") as f:
        raw = tomllib.load(f)

    # Providers
    providers: dict[str, ProviderConfig] = {}
    for pname, pdata in raw.get("providers", {}).items():
        providers[pname] = _parse_provider(pname, pdata)

    # Ollama Cloud models
    ollama_models: dict[str, CloudModelEntry] = {}
    for mkey, mdata in raw.get("ollama_cloud_models", {}).items():
        ollama_models[mkey] = _parse_model(mkey, mdata, "ollama_cloud")

    # OpenRouter models
    openrouter_models: dict[str, CloudModelEntry] = {}
    for mkey, mdata in raw.get("openrouter_models", {}).items():
        openrouter_models[mkey] = _parse_model(mkey, mdata, "openrouter")

    # Escalation
    escalation = _parse_escalation(raw.get("escalation", {}))

    # Discovery
    discovery = _parse_discovery(raw.get("discovery", {}))

    # Provider preferences (OpenRouter routing)
    provider_preferences = _parse_provider_preferences(
        raw.get("provider_preferences", {})
    )

    # Governed path constraints
    governed_paths = _parse_governed_paths(raw.get("governed_paths", {}))

    # Chain overrides
    chain_overrides: dict[str, list[str]] = {}
    for lane, ldata in raw.get("chain_overrides", {}).items():
        models_list = ldata.get("models", []) if isinstance(ldata, dict) else []
        chain_overrides[lane] = [str(m) for m in models_list]

    config = ModelSubstrateConfig(
        version=str(raw.get("meta", {}).get("version", "0")),
        providers=providers,
        ollama_models=ollama_models,
        openrouter_models=openrouter_models,
        escalation=escalation,
        discovery=discovery,
        provider_preferences=provider_preferences,
        governed_paths=governed_paths,
        chain_overrides=chain_overrides,
        source_path=str(resolved),
    )

    _validate(config)
    return config


def _validate(config: ModelSubstrateConfig) -> None:
    """Run basic validation on a loaded config."""
    for name, provider in config.providers.items():
        if provider.enabled and not provider.base_url:
            logger.warning("Provider %s is enabled but has no base_url", name)
        if provider.enabled and not provider.api_key_env:
            logger.warning(
                "Provider %s is enabled but api_key_env is empty — "
                "API calls will fail without a key",
                name,
            )
        # Check that the env var actually has a value (warn, don't fail)
        if provider.enabled and provider.api_key_env:
            if not os.environ.get(provider.api_key_env):
                logger.warning(
                    "Provider %s: env var %s is not set",
                    name, provider.api_key_env,
                )


# ── catalog bridge helpers ───────────────────────────────────────────────────

def get_ollama_endpoint(config: ModelSubstrateConfig) -> str:
    """Return the Ollama Cloud base URL from config, or the standard default."""
    provider = config.providers.get("ollama_cloud")
    if provider and provider.enabled:
        return provider.base_url
    return "https://ollama.com/api"


def get_openrouter_endpoint(config: ModelSubstrateConfig) -> str:
    """Return the OpenRouter base URL from config."""
    provider = config.providers.get("openrouter")
    if provider and provider.enabled:
        return provider.base_url
    return "https://openrouter.ai/api/v1"


def build_remote_direct_entries(
    config: ModelSubstrateConfig,
) -> list[dict[str, Any]]:
    """Build ``remote_direct_entries`` dicts for ``sync_model_catalog()`` from
    enabled OpenRouter models in the config.

    Each entry matches the schema expected by ``sync_model_catalog``'s
    ``remote_direct_entries`` parameter.
    """
    provider = config.providers.get("openrouter")
    if not provider or not provider.enabled:
        return []

    entries: list[dict[str, Any]] = []
    for key, model in config.openrouter_models.items():
        if not model.enabled:
            continue
        entries.append({
            "name": f"openrouter:{key}",
            "family": model.family,
            "lanes": list(model.lanes),
            "capabilities": list(model.capabilities),
            "supported_languages": list(model.languages),
            "endpoint": provider.base_url,
            "reachable": True,  # assume reachable at config time; runtime checks later
            "known_but_impractical": False,
            "privacy_preserving": False,
            "min_vram_gb": 0.0,
            "rationale": [
                f"OpenRouter model: {model.description}" if model.description
                else f"OpenRouter model {key}",
                f"Free tier: {model.is_free}",
                f"Context window: {model.context_k}k",
            ],
        })
    return entries


def get_api_key(config: ModelSubstrateConfig, provider_name: str) -> str | None:
    """Resolve the API key for a named provider from the environment.

    Returns None if the provider doesn't exist or the env var is unset.
    Never logs or stores the actual key value.
    """
    provider = config.providers.get(provider_name)
    if not provider or not provider.api_key_env:
        return None
    return os.environ.get(provider.api_key_env)


def enabled_models_for_lane(
    config: ModelSubstrateConfig, lane: str
) -> list[CloudModelEntry]:
    """Return all enabled models (Ollama + OpenRouter) that serve a given lane,
    sorted by provider priority.
    """
    result: list[tuple[int, CloudModelEntry]] = []
    for model in config.ollama_models.values():
        if model.enabled and lane in model.lanes:
            prio = config.providers.get("ollama_cloud")
            result.append((prio.priority if prio else 99, model))
    for model in config.openrouter_models.values():
        if model.enabled and lane in model.lanes:
            prio = config.providers.get("openrouter")
            result.append((prio.priority if prio else 99, model))
    return [m for _, m in sorted(result, key=lambda t: t[0])]


def escalation_chain_for_lane(
    config: ModelSubstrateConfig, lane: str
) -> list[CloudModelEntry]:
    """Build an escalation chain for a lane.

    If ``chain_overrides`` exist for the lane, use those model names.
    Otherwise, fall back to ``enabled_models_for_lane`` sorted by priority.
    """
    override_names = config.chain_overrides.get(lane)
    if override_names:
        # Resolve names to model entries
        all_models = {**config.ollama_models, **config.openrouter_models}
        # Also check with/without "openrouter:" prefix
        expanded: dict[str, CloudModelEntry] = {}
        for k, v in all_models.items():
            expanded[k] = v
            expanded[f"openrouter:{k}"] = v
        return [
            expanded[name]
            for name in override_names
            if name in expanded and expanded[name].enabled
        ]
    return enabled_models_for_lane(config, lane)
