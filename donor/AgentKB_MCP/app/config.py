"""
Configuration management module.

All configuration is loaded from environment variables with sensible defaults.
Follows the 12-factor app methodology for configuration.
"""

from pydantic_settings import BaseSettings
from pydantic import Field, SecretStr
from typing import Optional, List, Literal
from functools import lru_cache
import os


class DatabaseSettings(BaseSettings):
    """Database configuration."""
    
    url: str = Field(
        default="postgresql+asyncpg://kbpro:password@localhost:5432/kbpro",
        alias="DATABASE_URL",
        description="PostgreSQL connection URL"
    )
    pool_size: int = Field(default=5, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=10, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    echo: bool = Field(default=False, alias="DB_ECHO")

    class Config:
        env_prefix = ""
        extra = "ignore"


class RedisSettings(BaseSettings):
    """Redis configuration."""
    
    url: str = Field(
        default="redis://localhost:6379",
        alias="REDIS_URL",
        description="Redis connection URL"
    )
    cache_ttl_hit: int = Field(default=3600, description="Cache TTL for hits (seconds)")
    cache_ttl_miss: int = Field(default=60, description="Cache TTL for misses (seconds)")

    class Config:
        env_prefix = ""
        extra = "ignore"


class GoogleSettings(BaseSettings):
    """Google AI services configuration."""
    
    api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="GOOGLE_API_KEY",
        description="Google Gemini API key"
    )
    project: str = Field(
        default="",
        alias="GOOGLE_CLOUD_PROJECT",
        description="Google Cloud project ID"
    )
    file_search_store_id: str = Field(
        default="",
        alias="FILE_SEARCH_STORE_ID",
        description="Google File Search store ID"
    )
    model_name: str = Field(
        default="gemini-1.5-pro",
        alias="GEMINI_MODEL_NAME",
        description="Gemini model to use for KB queries"
    )
    research_model_name: str = Field(
        default="gemini-1.5-pro",
        alias="GEMINI_RESEARCH_MODEL_NAME",
        description="Gemini model to use for research"
    )
    embedding_model: str = Field(
        default="models/embedding-001",
        alias="GEMINI_EMBEDDING_MODEL",
        description="Embedding model for semantic operations"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class OpenRouterSettings(BaseSettings):
    """OpenRouter configuration for multi-provider LLM access."""
    
    api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="OPENROUTER_API_KEY",
        description="OpenRouter API key"
    )
    default_model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        alias="OPENROUTER_DEFAULT_MODEL",
        description="Default model for OpenRouter"
    )
    sort: str = Field(
        default="price",
        alias="OPENROUTER_SORT",
        description="Default routing sort: price, throughput, latency"
    )
    data_collection: str = Field(
        default="deny",
        alias="OPENROUTER_DATA_COLLECTION",
        description="Data collection policy: allow, deny"
    )
    zdr: bool = Field(
        default=False,
        alias="OPENROUTER_ZDR",
        description="Enforce Zero Data Retention"
    )
    max_price_prompt: float = Field(
        default=5.0,
        alias="OPENROUTER_MAX_PRICE_PROMPT",
        description="Max $/M prompt tokens"
    )
    max_price_completion: float = Field(
        default=15.0,
        alias="OPENROUTER_MAX_PRICE_COMPLETION",
        description="Max $/M completion tokens"
    )
    app_name: str = Field(
        default="Verified Developer KB Pro",
        alias="OPENROUTER_APP_NAME",
        description="App name for OpenRouter attribution"
    )
    app_url: str = Field(
        default="",
        alias="OPENROUTER_APP_URL",
        description="App URL for OpenRouter attribution"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class OllamaSettings(BaseSettings):
    """Ollama (local + cloud) configuration."""

    # Default to the local Ollama server; direct ollama.com API is backup-only.
    base_url: str = Field(
        default="http://localhost:11434/api",
        alias="OLLAMA_BASE_URL",
        description="Ollama base URL including /api (cloud: https://ollama.com/api, local: http://localhost:11434/api)",
    )
    api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="OLLAMA_API_KEY",
        description="Ollama API key (required for ollama.com cloud API; not required for local)",
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class ModelPolicySettings(BaseSettings):
    """
    Admin-only model policy (NOT user-facing).

    This controls which provider+model pairs power each internal purpose.
    """

    # ----------------------------------------------------------------------------
    # RTD / "grounded general" chain
    # ----------------------------------------------------------------------------
    rtd_primary_provider: Literal["ollama", "openrouter", "gemini"] = Field(
        default="ollama", alias="MODEL_RTD_PRIMARY_PROVIDER"
    )
    rtd_primary_model: str = Field(
        default="gemini-3-flash-preview", alias="MODEL_RTD_PRIMARY_MODEL"
    )
    # Handle preview → non-preview rename gracefully.
    rtd_primary_model_aliases: str = Field(
        default="gemini-3-flash-preview,gemini-3-flash",
        alias="MODEL_RTD_PRIMARY_MODEL_ALIASES",
        description="Comma-separated list of acceptable Ollama model slugs for RTD primary.",
    )

    rtd_fallback_openrouter_model: str = Field(
        default="", alias="MODEL_RTD_FALLBACK_OPENROUTER_MODEL"
    )
    rtd_fallback_gemini_model: str = Field(
        default="", alias="MODEL_RTD_FALLBACK_GEMINI_MODEL"
    )

    # ----------------------------------------------------------------------------
    # Strong reasoning chain (non-RTD)
    # ----------------------------------------------------------------------------
    reasoner_primary_provider: Literal["ollama", "openrouter", "gemini"] = Field(
        default="ollama", alias="MODEL_REASONER_PRIMARY_PROVIDER"
    )
    reasoner_primary_model: str = Field(
        default="glm-4.7", alias="MODEL_REASONER_PRIMARY_MODEL"
    )
    reasoner_fallback_openrouter_model: str = Field(
        default="", alias="MODEL_REASONER_FALLBACK_OPENROUTER_MODEL"
    )

    # ----------------------------------------------------------------------------
    # Final QA pass (secondary critique)
    # ----------------------------------------------------------------------------
    qa_enabled: bool = Field(default=True, alias="MODEL_QA_ENABLED")
    qa_provider: Literal["ollama", "openrouter", "gemini"] = Field(
        default="ollama", alias="MODEL_QA_PROVIDER"
    )
    qa_model: str = Field(default="glm-4.7", alias="MODEL_QA_MODEL")

    # ----------------------------------------------------------------------------
    # Guardrails
    # ----------------------------------------------------------------------------
    disallow_premium_models: bool = Field(
        default=True, alias="MODEL_DISALLOW_PREMIUM_MODELS"
    )
    premium_models: str = Field(
        default="gemini-3-pro-preview",
        alias="MODEL_PREMIUM_MODELS",
        description="Comma-separated list of premium/limited models to avoid by default.",
    )

    @property
    def rtd_primary_model_aliases_list(self) -> List[str]:
        raw = (self.rtd_primary_model_aliases or "").strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    @property
    def premium_models_list(self) -> List[str]:
        raw = (self.premium_models or "").strip()
        if not raw:
            return []
        return [x.strip() for x in raw.split(",") if x.strip()]

    class Config:
        env_prefix = ""
        extra = "ignore"

class LLMRoutingSettings(BaseSettings):
    """LLM routing configuration."""
    
    strategy: str = Field(
        default="fallback",
        alias="LLM_ROUTING_STRATEGY",
        description="Routing strategy: primary_only, fallback, openrouter_only, cost_optimized, throughput, privacy_first"
    )
    primary_provider: str = Field(
        default="ollama",
        alias="LLM_PRIMARY_PROVIDER",
        description="Primary LLM provider: ollama, openrouter, gemini"
    )
    fallback_enabled: bool = Field(
        default=True,
        alias="LLM_FALLBACK_ENABLED",
        description="Enable fallback to secondary provider"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class FallbackSettings(BaseSettings):
    """Fallback AI services configuration."""
    
    anthropic_api_key: SecretStr = Field(
        default=SecretStr(""),
        alias="ANTHROPIC_API_KEY",
        description="Anthropic API key for Claude Haiku fallback"
    )
    qdrant_url: str = Field(
        default="http://localhost:6333",
        alias="QDRANT_URL",
        description="Qdrant URL for local vector DB fallback"
    )
    enabled: bool = Field(
        default=True,
        alias="FALLBACK_ENABLED",
        description="Enable fallback chain"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class SecuritySettings(BaseSettings):
    """Security configuration."""
    
    secret_key: SecretStr = Field(
        default=SecretStr("change-me-in-production"),
        alias="SECRET_KEY",
        description="Secret key for signing"
    )
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        alias="ALLOWED_ORIGINS",
        description="CORS allowed origins"
    )
    
    class Config:
        env_prefix = ""
        extra = "ignore"
        
    @property
    def allowed_origins_list(self) -> List[str]:
        """Parse allowed origins from comma-separated string if needed."""
        if isinstance(self.allowed_origins, str):
            return [origin.strip() for origin in self.allowed_origins.split(",")]
        return self.allowed_origins


class KBSettings(BaseSettings):
    """Knowledge Base configuration."""
    
    kb_files_path: str = Field(
        default="./kb_files",
        alias="KB_FILES_PATH",
        description="Path to production KB files"
    )
    kb_staging_path: str = Field(
        default="./kb_staging",
        alias="KB_STAGING_PATH",
        description="Path to staging KB files"
    )
    stack_packs_path: str = Field(
        default="./stack_packs",
        alias="STACK_PACKS_PATH",
        description="Path to stack pack manifests"
    )
    locks_path: str = Field(
        default="./locks",
        alias="LOCKS_PATH",
        description="Path to lockfiles"
    )
    alerts_path: str = Field(
        default="./alerts",
        alias="ALERTS_PATH",
        description="Path to alert flags"
    )
    confidence_threshold: float = Field(
        default=0.80,
        alias="CONFIDENCE_THRESHOLD",
        description="Minimum confidence for a hit"
    )
    confidence_decay_rate: float = Field(
        default=0.95,
        alias="CONFIDENCE_DECAY_RATE",
        description="Monthly confidence decay factor"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class WorkerSettings(BaseSettings):
    """Research worker configuration."""
    
    worker_id: str = Field(
        default="",
        alias="WORKER_ID",
        description="Unique worker identifier"
    )
    heartbeat_interval: int = Field(
        default=30,
        alias="WORKER_HEARTBEAT_INTERVAL",
        description="Heartbeat interval in seconds"
    )
    max_retries: int = Field(
        default=3,
        alias="WORKER_MAX_RETRIES",
        description="Max retries before DLQ"
    )
    emergency_stop_threshold: int = Field(
        default=5,
        alias="EMERGENCY_STOP_THRESHOLD",
        description="Consecutive failures before emergency stop"
    )
    poll_interval: int = Field(
        default=5,
        alias="WORKER_POLL_INTERVAL",
        description="Queue poll interval in seconds"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.worker_id:
            import socket
            import uuid
            self.worker_id = f"{socket.gethostname()}-{uuid.uuid4().hex[:8]}"


class CircuitBreakerSettings(BaseSettings):
    """Circuit breaker configuration."""
    
    fail_max: int = Field(
        default=3,
        alias="CIRCUIT_BREAKER_FAIL_MAX",
        description="Failures before circuit opens"
    )
    reset_timeout: int = Field(
        default=300,
        alias="CIRCUIT_BREAKER_RESET_TIMEOUT",
        description="Seconds before circuit resets"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class MonitoringSettings(BaseSettings):
    """Monitoring and observability configuration."""
    
    prometheus_port: int = Field(
        default=9090,
        alias="PROMETHEUS_PORT"
    )
    log_level: str = Field(
        default="INFO",
        alias="LOG_LEVEL"
    )
    log_format: str = Field(
        default="json",
        alias="LOG_FORMAT",
        description="Log format: json or console"
    )

    class Config:
        env_prefix = ""
        extra = "ignore"


class Settings(BaseSettings):
    """Main application settings aggregator."""
    
    # Application metadata
    app_name: str = "Verified Developer KB Pro"
    app_version: str = "1.0.0"
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    
    # Nested settings
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    openrouter: OpenRouterSettings = Field(default_factory=OpenRouterSettings)
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    model_policy: ModelPolicySettings = Field(default_factory=ModelPolicySettings)
    llm_routing: LLMRoutingSettings = Field(default_factory=LLMRoutingSettings)
    fallback: FallbackSettings = Field(default_factory=FallbackSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    kb: KBSettings = Field(default_factory=KBSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    circuit_breaker: CircuitBreakerSettings = Field(default_factory=CircuitBreakerSettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)

    class Config:
        env_prefix = ""
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
    
    # Convenience properties for common access patterns
    @property
    def google_api_key(self) -> str:
        """Get Google API key as string."""
        return self.google.api_key.get_secret_value()
    
    @property
    def openrouter_api_key(self) -> str:
        """Get OpenRouter API key as string."""
        return self.openrouter.api_key.get_secret_value()

    @property
    def ollama_api_key(self) -> str:
        """Get Ollama API key as string."""
        return self.ollama.api_key.get_secret_value()
    
    @property
    def llm_routing_strategy(self) -> str:
        """Get LLM routing strategy."""
        return self.llm_routing.strategy


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once
    and reused across the application.
    """
    return Settings()


# Convenience function for quick access
settings = get_settings()

