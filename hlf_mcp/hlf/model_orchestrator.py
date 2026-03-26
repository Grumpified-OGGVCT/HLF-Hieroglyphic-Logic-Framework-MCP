"""Hybrid Model Escalation Orchestrator.

Drives multi-provider model selection with governed escalation:
  - Priority-ordered provider chains (Ollama Cloud → OpenRouter)
  - Per-model circuit breakers
  - Configurable escalation triggers (timeout, rate-limit, error, auth)
  - Free-tier preference for OpenRouter when enabled
  - Full audit trail for every attempt
  - Lane-aware model selection from governed config

This module sits between the MCP tool layer and the individual provider
clients (ollama_client, openrouter_client), implementing the escalation
and routing logic defined in model_providers.toml.

Usage:
    from hlf_mcp.hlf.model_orchestrator import ModelOrchestrator
    from hlf_mcp.hlf.model_config import load_model_config

    cfg = load_model_config()
    orch = ModelOrchestrator(cfg)
    result = await orch.complete(
        lane="reasoning",
        messages=[{"role": "user", "content": "Analyze this HLF program"}],
    )
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

from hlf_mcp.hlf.model_config import (
    CloudModelEntry,
    EscalationConfig,
    ModelSubstrateConfig,
    ProviderConfig,
    build_remote_direct_entries,
    enabled_models_for_lane,
    escalation_chain_for_lane,
    get_api_key,
    get_ollama_endpoint,
    get_openrouter_endpoint,
)
from hlf_mcp.hlf.model_availability import ModelAvailabilityCache
from hlf_mcp.hlf.response_validation import (
    RELAXED_VALIDATION,
    ValidationConfig,
    validate_ollama_response,
    validate_openrouter_response,
)

logger = logging.getLogger(__name__)


# ── result types ─────────────────────────────────────────────────────────────


@dataclass(slots=True)
class OrchestrationResult:
    """Result from a multi-provider orchestrated completion."""

    content: str
    model_used: str
    model_requested: str
    provider_used: str  # "ollama_cloud" | "openrouter"
    lane: str
    finish_reason: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    latency_s: float
    streamed: bool
    cost: float | None
    thinking: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    escalation_depth: int = 0  # 0 = primary succeeded; 1+ = fell back N times
    total_attempts: int = 0
    audit_trail: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class EscalationAttempt:
    """Record of a single escalation attempt for audit."""

    model: str
    provider: str
    success: bool
    status: str  # "ok" | "timeout" | "rate_limit" | "error" | "circuit_open" | "auth_fail"
    latency_s: float = 0.0
    error_detail: str = ""


# ── orchestrator ─────────────────────────────────────────────────────────────


class ModelOrchestrator:
    """Multi-provider escalation orchestrator.

    Drives completions across Ollama Cloud and OpenRouter with governed
    escalation, circuit breakers, and full audit trail.
    """

    def __init__(self, config: ModelSubstrateConfig):
        self._config = config
        self._ollama_client: Any = None
        self._openrouter_client: Any = None
        self._availability_cache: ModelAvailabilityCache | None = None
        self._last_validation: Any = None
        self._initialized = False

    async def _ensure_clients(self) -> None:
        """Lazy-initialize provider clients."""
        if self._initialized:
            return

        # OpenRouter client
        or_provider = self._config.providers.get("openrouter")
        if or_provider and or_provider.enabled:
            try:
                from hlf_mcp.hlf.openrouter_client import OpenRouterClient

                or_key = get_api_key(self._config, "openrouter")
                self._openrouter_client = OpenRouterClient.from_provider_config(
                    or_provider, api_key=or_key
                )
                # Initialize availability cache with TTL from discovery config
                self._availability_cache = ModelAvailabilityCache(
                    self._openrouter_client,
                    ttl_s=self._config.discovery.discovery_cache_ttl_s,
                )
            except Exception as exc:
                logger.warning("Failed to initialize OpenRouter client: %s", exc)

        # Ollama Cloud client — uses the ollama pip package if available
        ollama_provider = self._config.providers.get("ollama_cloud")
        if ollama_provider and ollama_provider.enabled:
            try:
                import ollama as _ollama_mod  # noqa: F401

                self._ollama_client = _ollama_mod
            except ImportError:
                logger.info("ollama package not installed — Ollama Cloud via HTTP fallback")

        self._initialized = True

    async def close(self) -> None:
        """Shutdown provider clients."""
        if self._openrouter_client is not None:
            await self._openrouter_client.close()
            self._openrouter_client = None
        self._initialized = False

    # ── main entry point ─────────────────────────────────────────────────

    async def complete(
        self,
        lane: str,
        messages: list[dict[str, Any]],
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        tools: list[dict[str, Any]] | None = None,
        prefer_free: bool | None = None,
        model_override: str | None = None,
        governed: bool = False,
    ) -> OrchestrationResult:
        """Execute a completion with escalation across providers.

        Parameters
        ----------
        lane : str
            The HLF lane to select models for (e.g. "reasoning", "coding").
        messages : list[dict]
            OpenAI-format messages.
        system : str
            System message to prepend.
        temperature : float | None
            Sampling temperature.
        max_tokens : int | None
            Maximum tokens.
        stream : bool
            Use streaming.
        tools : list | None
            Tool definitions.
        prefer_free : bool | None
            Override provider's prefer_free setting.
        model_override : str | None
            Skip lane selection; use this specific model.
        governed : bool
            If True, apply governed-path constraints: exclude auto/free
            routers, verify response models strictly, require live
            availability.
        """
        await self._ensure_clients()

        # Build full message list
        full_messages = list(messages)
        if system:
            full_messages.insert(0, {"role": "system", "content": system})

        # Resolve the escalation chain
        if model_override:
            chain = self._resolve_model_override(model_override)
        else:
            chain = escalation_chain_for_lane(self._config, lane)

        if not chain:
            raise ModelOrchestrationError(
                f"No models available for lane '{lane}'",
                lane=lane,
                audit_trail=[],
            )

        # Governed-path filtering: only applies to OpenRouter models in the
        # chain. Ollama Cloud models (primary) are never filtered by the
        # availability cache — they don't have the autorouter/deprecation
        # problem that OpenRouter has.
        if governed and self._availability_cache is not None:
            gov_cfg = self._config.governed_paths
            filtered_chain: list[CloudModelEntry] = []
            for m in chain:
                if m.provider != "openrouter":
                    # Ollama models always pass — primary provider
                    filtered_chain.append(m)
                    continue
                # Check excluded routers
                if m.name in gov_cfg.excluded_routers:
                    logger.info(
                        "Governed path: excluding %s (excluded router)", m.name
                    )
                    continue
                # Check live availability if required
                if gov_cfg.require_live_availability:
                    ok, reason = await self._availability_cache.is_usable_for_governed_path(m.name)
                    if not ok:
                        logger.info(
                            "Governed path: excluding %s (%s)", m.name, reason
                        )
                        continue
                filtered_chain.append(m)
            chain = filtered_chain

            if not chain:
                raise ModelOrchestrationError(
                    f"No models available for governed lane '{lane}' "
                    "after availability filtering",
                    lane=lane,
                    audit_trail=[],
                )

        # Apply free-tier preference
        use_free = prefer_free if prefer_free is not None else (
            self._config.providers.get("openrouter", ProviderConfig(
                name="", enabled=False, base_url="", api_key_env="", priority=99
            )).prefer_free
        )
        if use_free:
            chain = self._sort_free_first(chain)

        # Execute with escalation
        audit: list[dict[str, Any]] = []
        t0_total = time.monotonic()

        for depth, model in enumerate(chain):
            attempt = await self._try_model(
                model=model,
                messages=full_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                tools=tools,
                governed=governed,
            )
            audit.append({
                "depth": depth,
                "model": model.name,
                "provider": model.provider,
                "success": attempt.success,
                "status": attempt.status,
                "latency_s": attempt.latency_s,
                "error": attempt.error_detail,
            })

            if attempt.success:
                return self._last_result_with_audit(
                    lane=lane,
                    depth=depth,
                    total_attempts=depth + 1,
                    audit=audit,
                    t0=t0_total,
                )

            # Check escalation rules
            if not self._should_escalate(attempt.status):
                logger.warning(
                    "Escalation blocked by config: status=%s for %s",
                    attempt.status, model.name,
                )
                break

        # All models exhausted
        total_time = time.monotonic() - t0_total
        raise ModelOrchestrationError(
            f"All {len(chain)} models in lane '{lane}' failed after {len(audit)} attempts",
            lane=lane,
            audit_trail=audit,
            total_latency_s=round(total_time, 3),
        )

    # ── governed verdict entry point ─────────────────────────────────────────

    async def complete_with_verdict(
        self,
        verdict: Any,  # GovernedRouteVerdict — imported lazily to avoid circulars
        messages: list[dict[str, Any]],
        *,
        system: str = "",
        temperature: float | None = None,
        max_tokens: int | None = None,
        tools: list[dict[str, Any]] | None = None,
        advisory_fallback: bool = True,
    ) -> "OrchestrationResult":
        """Execute a completion driven by a pre-computed GovernedRouteVerdict.

        Resolution logic:
          - allowed=True → uses verdict.selected_lane + promotes
            verdict.primary_model to the head of the escalation chain.
          - allowed=False with governance_mode in {"evidence_required",
            "qualification_constrained"} + advisory_fallback=True →
            attempts completion in advisory (ungoverned) mode; useful during
            bootstrap when benchmark evidence has not yet been recorded.
          - All other denied verdicts raise ModelOrchestrationError.

        The 'governed' flag passed to complete() is True only when the
        verdict decision is "governed_cloud_completion" — i.e. the routing
        layer made a positive governed decision, not just an advisory pass.
        """
        if not verdict.allowed:
            if advisory_fallback and getattr(verdict, "governance_mode", "") in (
                "evidence_required",
                "qualification_constrained",
            ):
                logger.warning(
                    "Routing verdict denied (%s) — advisory fallback on lane '%s'",
                    verdict.governance_mode,
                    verdict.selected_lane,
                )
                return await self.complete(
                    lane=verdict.selected_lane,
                    messages=messages,
                    system=system,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                    governed=False,
                )
            raise ModelOrchestrationError(
                f"Routing verdict denied: {verdict.decision} ({verdict.governance_mode})",
                lane=verdict.selected_lane,
                audit_trail=[],
            )

        primary = (verdict.primary_model or "").strip()
        return await self.complete(
            lane=verdict.selected_lane,
            messages=messages,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=tools,
            model_override=primary or None,
            governed=(verdict.decision == "governed_cloud_completion"),
        )

    # ── per-model dispatch ───────────────────────────────────────────────

    _last_chat_result: Any = None

    async def _try_model(
        self,
        model: CloudModelEntry,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict[str, Any]] | None,
        governed: bool = False,
    ) -> EscalationAttempt:
        """Try a single model. Returns an EscalationAttempt (never raises).

        When ``governed=True``, every response — Ollama or OpenRouter — is
        validated before being accepted.  Truncated, empty, or model-mismatched
        responses are treated as failures so escalation can continue.
        """
        t0 = time.monotonic()
        if governed:
            # Build ValidationConfig from TOML-driven governed_paths settings
            gp = self._config.governed_paths
            val_cfg = ValidationConfig(
                require_non_empty_content=True,
                min_content_chars=gp.min_content_chars,
                require_model_match=gp.require_model_match,
                allow_ollama_tag_suffix=True,
                reject_on_truncation=gp.reject_truncated,
                warn_on_missing_done=True,
                require_nonzero_tokens=gp.require_nonzero_tokens,
                reject_autorouter_responses=True,
            )
        else:
            val_cfg = RELAXED_VALIDATION

        try:
            if model.provider == "openrouter":
                result = await self._call_openrouter(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    tools=tools,
                )
            elif model.provider == "ollama_cloud":
                result = await self._call_ollama_cloud(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    tools=tools,
                )
            else:
                return EscalationAttempt(
                    model=model.name,
                    provider=model.provider,
                    success=False,
                    status="unknown_provider",
                    latency_s=round(time.monotonic() - t0, 3),
                    error_detail=f"Unknown provider: {model.provider}",
                )

            # ── response validation (both providers) ─────────────────────
            if model.provider == "ollama_cloud" and isinstance(result, dict):
                vr = validate_ollama_response(result, model.name, val_cfg)
            elif model.provider == "openrouter" and hasattr(result, "content"):
                vr = validate_openrouter_response(result, model.name, val_cfg)
            else:
                vr = None  # Unknown shape — skip validation

            if vr is not None and not vr.passed:
                return EscalationAttempt(
                    model=model.name,
                    provider=model.provider,
                    success=False,
                    status="validation_failed",
                    latency_s=round(time.monotonic() - t0, 3),
                    error_detail="; ".join(vr.rejection_reasons)[:300],
                )

            self._last_chat_result = result
            self._last_validation = vr
            return EscalationAttempt(
                model=model.name,
                provider=model.provider,
                success=True,
                status="ok",
                latency_s=round(time.monotonic() - t0, 3),
            )

        except Exception as exc:
            latency = round(time.monotonic() - t0, 3)
            status = self._classify_error(exc)
            logger.info(
                "Model %s (%s) failed: %s [%s, %.1fs]",
                model.name, model.provider, exc, status, latency,
            )
            return EscalationAttempt(
                model=model.name,
                provider=model.provider,
                success=False,
                status=status,
                latency_s=latency,
                error_detail=str(exc)[:300],
            )

    async def _call_openrouter(
        self,
        model: CloudModelEntry,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict[str, Any]] | None,
    ) -> Any:
        """Dispatch to OpenRouter client."""
        if self._openrouter_client is None:
            raise RuntimeError("OpenRouter client not initialized")

        # Build provider routing preferences from TOML config
        provider_prefs = self._config.provider_preferences.to_provider_dict()

        return await self._openrouter_client.chat_completion(
            model=model.name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=stream,
            tools=tools,
            provider=provider_prefs,
        )

    async def _call_ollama_cloud(
        self,
        model: CloudModelEntry,
        messages: list[dict[str, Any]],
        temperature: float | None,
        max_tokens: int | None,
        stream: bool,
        tools: list[dict[str, Any]] | None,
    ) -> Any:
        """Dispatch to Ollama Cloud API.

        Uses the ``ollama`` pip package if available, otherwise falls back
        to a direct HTTP call.
        """
        if self._ollama_client is not None:
            # Use official ollama package
            options: dict[str, Any] = {}
            if temperature is not None:
                options["temperature"] = temperature
            if max_tokens is not None:
                options["num_predict"] = max_tokens

            kwargs: dict[str, Any] = {
                "model": model.name,
                "messages": messages,
                "options": options,
                "stream": False,  # Always non-streaming for simplicity in v1
            }

            if tools:
                kwargs["tools"] = tools

            # ollama.chat() is sync — run in executor
            loop = asyncio.get_running_loop()
            api_key = os.environ.get(
                self._config.providers.get("ollama_cloud", ProviderConfig(
                    name="", enabled=False, base_url="", api_key_env="", priority=99
                )).api_key_env, ""
            )
            client = self._ollama_client.Client(
                host=get_ollama_endpoint(self._config),
            )
            response = await loop.run_in_executor(
                None, lambda: client.chat(**kwargs)
            )
            return response

        # Fallback: direct HTTP (requires httpx)
        try:
            import httpx
        except ImportError:
            raise RuntimeError(
                "Neither 'ollama' package nor 'httpx' available for Ollama Cloud calls"
            )

        endpoint = get_ollama_endpoint(self._config)
        api_key = os.environ.get(
            self._config.providers.get("ollama_cloud", ProviderConfig(
                name="", enabled=False, base_url="", api_key_env="", priority=99
            )).api_key_env, ""
        )
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        body: dict[str, Any] = {
            "model": model.name,
            "messages": messages,
            "stream": False,
        }
        if temperature is not None:
            body["options"] = {"temperature": temperature}
        if tools:
            body["tools"] = tools

        provider_cfg = self._config.providers.get("ollama_cloud")
        timeout = provider_cfg.timeout_total_s if provider_cfg else 600.0

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            resp = await client.post(f"{endpoint}/chat", json=body, headers=headers)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Ollama Cloud {resp.status_code}: {resp.text[:300]}"
                )
            return resp.json()

    # ── helpers ───────────────────────────────────────────────────────────

    def _resolve_model_override(self, model_name: str) -> list[CloudModelEntry]:
        """Resolve a model name to a single-element chain."""
        # Check all models
        all_models = {
            **self._config.ollama_models,
            **self._config.openrouter_models,
        }
        if model_name in all_models:
            return [all_models[model_name]]

        # Check with openrouter: prefix stripped
        stripped = model_name.removeprefix("openrouter:")
        if stripped in all_models:
            return [all_models[stripped]]

        # Build a synthetic entry for unknown model names
        provider = "openrouter" if "/" in model_name else "ollama_cloud"
        return [CloudModelEntry(
            name=model_name,
            provider=provider,
            enabled=True,
            family="unknown",
            lanes=(),
            capabilities=(),
            languages=(),
            context_k=0,
            description=f"User-overridden model: {model_name}",
        )]

    def _sort_free_first(self, chain: list[CloudModelEntry]) -> list[CloudModelEntry]:
        """Re-sort an escalation chain putting free-tier models first."""
        free = [m for m in chain if m.is_free]
        paid = [m for m in chain if not m.is_free]
        return free + paid

    def _should_escalate(self, status: str) -> bool:
        """Check if the escalation config allows falling through on this status."""
        esc = self._config.escalation
        if status == "auth_fail":
            return esc.fallback_on_auth_failure
        if status == "rate_limit":
            return esc.fallback_on_rate_limit
        if status == "model_not_found":
            return esc.fallback_on_model_not_found
        if status == "timeout":
            return esc.fallback_on_timeout
        if status in ("server_error", "error", "connect_error"):
            return esc.fallback_on_server_error
        if status == "circuit_open":
            return True  # Always try next model if circuit is open
        if status == "validation_failed":
            return True  # Always escalate on validation failure (content quality)
        return True  # Default: escalate on unknown errors

    def _classify_error(self, exc: Exception) -> str:
        """Classify an exception into an escalation status category."""
        exc_str = str(exc).lower()

        # Check for OpenRouter-specific errors
        try:
            from hlf_mcp.hlf.openrouter_client import OpenRouterAPIError

            if isinstance(exc, OpenRouterAPIError):
                code = exc.status_code
                if code == 401:
                    return "auth_fail"
                if code == 429:
                    return "rate_limit"
                if code == 404:
                    return "model_not_found"
                if code >= 500:
                    return "server_error"
                return "error"
        except ImportError:
            pass

        if "timeout" in exc_str:
            return "timeout"
        if "401" in exc_str or "unauthorized" in exc_str or "auth" in exc_str:
            return "auth_fail"
        if "429" in exc_str or "rate" in exc_str:
            return "rate_limit"
        if "404" in exc_str or "not found" in exc_str:
            return "model_not_found"
        if "circuit" in exc_str:
            return "circuit_open"
        if "connect" in exc_str:
            return "connect_error"
        return "error"

    def _last_result_with_audit(
        self,
        lane: str,
        depth: int,
        total_attempts: int,
        audit: list[dict[str, Any]],
        t0: float,
    ) -> OrchestrationResult:
        """Wrap the last successful ChatResult into an OrchestrationResult."""
        result = self._last_chat_result
        total_latency = time.monotonic() - t0

        # Handle different result types (OpenRouter ChatResult vs Ollama dict)
        if hasattr(result, "content"):
            # OpenRouter ChatResult
            return OrchestrationResult(
                content=result.content,
                model_used=result.model_used,
                model_requested=result.model_requested,
                provider_used="openrouter",
                lane=lane,
                finish_reason=getattr(result, "finish_reason", ""),
                prompt_tokens=getattr(result, "prompt_tokens", 0),
                completion_tokens=getattr(result, "completion_tokens", 0),
                total_tokens=getattr(result, "total_tokens", 0),
                latency_s=round(total_latency, 3),
                streamed=getattr(result, "streamed", False),
                cost=getattr(result, "cost", None),
                thinking=getattr(result, "thinking", ""),
                tool_calls=getattr(result, "tool_calls", []),
                escalation_depth=depth,
                total_attempts=total_attempts,
                audit_trail=audit,
            )
        elif isinstance(result, dict):
            # Ollama response dict
            message = result.get("message", {})
            # Use audit trail to get the actual requested model name
            # rather than the returned model (which may have :latest suffix)
            requested_model = (
                audit[-1]["model"] if audit else str(result.get("model", ""))
            )
            return OrchestrationResult(
                content=str(message.get("content", "")),
                model_used=str(result.get("model", "")),
                model_requested=requested_model,
                provider_used="ollama_cloud",
                lane=lane,
                finish_reason=str(result.get("done_reason", "")),
                prompt_tokens=int(result.get("prompt_eval_count", 0)),
                completion_tokens=int(result.get("eval_count", 0)),
                total_tokens=(
                    int(result.get("prompt_eval_count", 0))
                    + int(result.get("eval_count", 0))
                ),
                latency_s=round(total_latency, 3),
                streamed=False,
                cost=None,
                thinking="",
                tool_calls=message.get("tool_calls", []),
                escalation_depth=depth,
                total_attempts=total_attempts,
                audit_trail=audit,
            )
        else:
            return OrchestrationResult(
                content=str(result),
                model_used="unknown",
                model_requested="unknown",
                provider_used="unknown",
                lane=lane,
                finish_reason="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_s=round(total_latency, 3),
                streamed=False,
                cost=None,
                escalation_depth=depth,
                total_attempts=total_attempts,
                audit_trail=audit,
            )

    # ── info methods ─────────────────────────────────────────────────────

    def get_lane_models(self, lane: str) -> list[dict[str, Any]]:
        """Return info about available models for a lane (for MCP surface)."""
        chain = escalation_chain_for_lane(self._config, lane)
        return [
            {
                "name": m.name,
                "provider": m.provider,
                "family": m.family,
                "capabilities": list(m.capabilities),
                "context_k": m.context_k,
                "is_free": m.is_free,
                "description": m.description,
            }
            for m in chain
        ]

    def get_all_lanes(self) -> dict[str, int]:
        """Return all lanes with their model counts."""
        lane_names = set()
        for m in self._config.ollama_models.values():
            lane_names.update(m.lanes)
        for m in self._config.openrouter_models.values():
            lane_names.update(m.lanes)
        return {
            lane: len(escalation_chain_for_lane(self._config, lane))
            for lane in sorted(lane_names)
        }

    def get_config_summary(self) -> dict[str, Any]:
        """Return a summary of the current substrate config (for MCP surface)."""
        return {
            "version": self._config.version,
            "source": self._config.source_path,
            "providers": {
                name: {
                    "enabled": p.enabled,
                    "base_url": p.base_url,
                    "priority": p.priority,
                    "has_key": bool(get_api_key(self._config, name)),
                }
                for name, p in self._config.providers.items()
            },
            "primary_provider": "ollama_cloud",
            "fallback_provider": "openrouter",
            "ollama_models": len(self._config.ollama_models),
            "openrouter_models": len(self._config.openrouter_models),
            "escalation_strategy": self._config.escalation.strategy,
            "lanes": self.get_all_lanes(),
            "chain_overrides": list(self._config.chain_overrides.keys()),
            "provider_preferences": {
                "sort": self._config.provider_preferences.sort,
                "data_collection": self._config.provider_preferences.data_collection,
                "require_parameters": self._config.provider_preferences.require_parameters,
            },
            "governed_paths": {
                "excluded_routers": list(self._config.governed_paths.excluded_routers),
                "strict_model_verification": self._config.governed_paths.strict_model_verification,
                "require_live_availability": self._config.governed_paths.require_live_availability,
            },
            "availability_cache_active": self._availability_cache is not None,
        }

    @property
    def availability_cache(self) -> ModelAvailabilityCache | None:
        """Expose the availability cache for direct queries (MCP tools etc.)."""
        return self._availability_cache


# ── error class ──────────────────────────────────────────────────────────────


class ModelOrchestrationError(Exception):
    """Raised when escalation across all models fails."""

    def __init__(
        self,
        message: str,
        lane: str = "",
        audit_trail: list[dict[str, Any]] | None = None,
        total_latency_s: float = 0.0,
    ):
        self.lane = lane
        self.audit_trail = audit_trail or []
        self.total_latency_s = total_latency_s
        super().__init__(message)
