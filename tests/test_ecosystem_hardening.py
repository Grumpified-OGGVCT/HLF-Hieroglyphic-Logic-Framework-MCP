"""
Tests for HLF Ecosystem Hardening — rate limiting, circuit breaking,
retry policies, credential management, and bridge integration.

Validates:
  - TokenBucket: basic consumption, burst, refill, thread safety, headers
  - RateLimiter: per-effect limits, global limits, composite consumption
  - CircuitBreaker: CLOSED/OPEN/HALF_OPEN transitions, recovery, backoff
  - RetryPolicy: exponential backoff, jitter, budget, per-effect-class config
  - CredentialManager: scoped keys, TTL, rotation, validation, revocation
  - Bridge integration: hardened MCPBridge.dispatch_tool_call,
    hardened RESTBridge route mounting

Integration points:
  - hlf_mcp.ecosystem.rate_limiter (TokenBucket, RateLimiter)
  - hlf_mcp.ecosystem.circuit_breaker (CircuitBreaker, CircuitState, CircuitOpenError)
  - hlf_mcp.ecosystem.retry_policy (RetryPolicy, RetryDecision, retry_policy_for_effect)
  - hlf_mcp.ecosystem.credential_manager (CredentialManager, CredentialScope, Credential)
  - hlf_mcp.ecosystem.mcp_bridge (MCPBridge)
  - hlf_mcp.ecosystem.rest_bridge (RESTBridge)
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time

import pytest

os.environ.setdefault("PYTHONPATH", os.getcwd())

from hlf_mcp.ecosystem.rate_limiter import (
    TokenBucket,
    RateLimiter,
)
from hlf_mcp.ecosystem.circuit_breaker import (
    CircuitState,
    CircuitOpenError,
    CircuitBreaker,
)
from hlf_mcp.ecosystem.retry_policy import (
    RetryDecision,
    RetryPolicy,
    READ_RETRY_POLICY,
    WRITE_RETRY_POLICY,
    DEFAULT_RETRY_POLICY,
    retry_policy_for_effect,
)
from hlf_mcp.ecosystem.credential_manager import (
    CredentialScope,
    Credential,
    CredentialManager,
)
from hlf_mcp.ecosystem.mcp_bridge import (
    MCPBridge,
    MCPToolRegistration,
)
from hlf_mcp.ecosystem.rest_bridge import (
    RESTBridge,
    RESTEndpoint,
)
from hlf_mcp.hlf.capability_manifest import (
    CapabilityManifest,
    EFFECT_TO_TRUST_TIER,
    TRUST_TIER_ORDER,
)
from hlf_mcp.hlf.typed_contracts import (
    TypedEffectDeclaration,
    InputContract,
    OutputContract,
    EffectClass,
    FailureMode,
    ProofRequirement,
    HlfType,
    TypeContract,
    ParametricType,
    RefinementType,
)
from hlf_mcp.ecosystem.schema_translator import (
    SchemaTranslator,
    SchemaFormat,
    SchemaTranslationResult,
)
from hlf_mcp.ecosystem.distributed_rate_limiter import (
    DistributedRateLimiter,
    CoordinationMode,
    RateLimitState,
)
from hlf_mcp.ecosystem.resilience_coordinator import (
    ResilienceCoordinator,
    ResiliencePolicy,
    ResilienceEvent,
    ResilienceAction,
)
from hlf_mcp.ecosystem.bridge_health import (
    BridgeHealthAggregator,
    BridgeHealth,
    HealthAggregation,
    HealthStatus,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture(autouse=True)
def _disable_strict_for_writes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disable HLF_STRICT so FILE_WRITE and EXEC tests can compile."""
    monkeypatch.setenv("HLF_STRICT", "0")


@pytest.fixture
def sample_manifest() -> CapabilityManifest:
    """A multi-effect manifest for bridge integration tests."""
    return CapabilityManifest(
        program_id="hardening_test_001",
        effects=[
            TypedEffectDeclaration(
                function_name="read_data",
                input_contract=InputContract(
                    function_name="read_data",
                    parameters=[
                        TypeContract(name="file_path", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="read_data",
                    return_type=HlfType.STRING,
                ),
                effect_class=EffectClass.FILE_READ,
                failure_modes=[FailureMode.IO_ERROR],
                proof_requirement=ProofRequirement.NONE,
            ),
            TypedEffectDeclaration(
                function_name="write_data",
                input_contract=InputContract(
                    function_name="write_data",
                    parameters=[
                        TypeContract(name="file_path", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                        TypeContract(name="content", hlf_type=HlfType.STRING, json_schema_type="string", required=True),
                    ],
                ),
                output_contract=OutputContract(
                    function_name="write_data",
                    return_type=HlfType.STRING,
                ),
                effect_class=EffectClass.FILE_WRITE,
                safety_class="guarded",
            ),
        ],
        required_capabilities={"filesystem"},
        input_contracts=[],
        output_contracts=[],
        proof_surfaces=[],
        trust_tier="trusted",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# TokenBucket tests (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimiterBasic:
    """Unit tests for TokenBucket rate limiter."""

    def test_bucket_starts_full(self):
        """A new bucket should start with burst tokens."""
        bucket = TokenBucket(rate=10.0, burst=20.0)
        assert bucket.available_tokens() == pytest.approx(20.0)

    def test_consume_deducts_tokens(self):
        """Consuming tokens should reduce available count."""
        bucket = TokenBucket(rate=10.0, burst=20.0)
        assert bucket.consume(5.0) is True
        assert bucket.available_tokens() == pytest.approx(15.0)

    def test_consume_rejects_when_empty(self):
        """Consuming more tokens than burst should reject."""
        bucket = TokenBucket(rate=10.0, burst=5.0)
        assert bucket.consume(6.0) is False
        assert bucket.total_rejected == 1

    def test_refill_over_time(self):
        """Tokens should refill at the configured rate."""
        bucket = TokenBucket(rate=100.0, burst=10.0)
        bucket.consume(10.0)  # drain it
        assert bucket.available_tokens() == pytest.approx(0.0, abs=0.1)
        time.sleep(0.05)  # wait 50ms, should refill ~5 tokens
        tokens = bucket.available_tokens()
        assert tokens > 0.0
        assert tokens <= 10.0

    def test_rate_limit_headers(self):
        """Headers should contain standard X-RateLimit-* fields."""
        bucket = TokenBucket(rate=10.0, burst=100.0)
        headers = bucket.rate_limit_headers(cost=1.0)
        assert "X-RateLimit-Limit" in headers
        assert "X-RateLimit-Remaining" in headers
        assert "X-RateLimit-Reset" in headers
        assert "X-RateLimit-Cost" in headers
        assert headers["X-RateLimit-Limit"] == "100"
        assert headers["X-RateLimit-Cost"] == "1"


# ═══════════════════════════════════════════════════════════════════════════════
# RateLimiter per-effect tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimiterPerEffect:
    """Tests for per-effect rate limiting via RateLimiter."""

    def test_add_effect_limit(self):
        """Adding a per-effect limit should create a separate bucket."""
        rl = RateLimiter(global_rate=100, global_burst=200)
        bucket = rl.add_effect_limit("file_read", rate=10, burst=20)
        assert isinstance(bucket, TokenBucket)
        assert "file_read" in rl.effect_buckets

    def test_per_effect_consume_enforces_limit(self):
        """Per-effect consumption should respect the effect bucket."""
        rl = RateLimiter(global_rate=100, global_burst=200)
        rl.add_effect_limit("web_search", rate=10, burst=2)
        # Consume 2 (full burst) — should work
        assert rl.consume("web_search", cost=1.0) is True
        assert rl.consume("web_search", cost=1.0) is True
        # Third should be rejected by per-effect limit
        assert rl.consume("web_search", cost=1.0) is False

    def test_unregistered_effect_uses_global_only(self):
        """An effect without a per-effect bucket uses only the global limit."""
        rl = RateLimiter(global_rate=100, global_burst=200)
        # No per-effect limit for "unknown_effect"
        assert rl.consume("unknown_effect", cost=10.0) is True
        stats = rl.stats()
        assert stats["global"]["consumed"] == 1


# ═══════════════════════════════════════════════════════════════════════════════
# CircuitBreaker state tests (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreakerStates:
    """Tests for CircuitBreaker CLOSED/OPEN/HALF_OPEN states."""

    def test_starts_closed(self):
        """A new circuit breaker should be CLOSED."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        assert cb.state == CircuitState.CLOSED
        assert cb.is_closed()

    def test_trips_to_open_after_threshold(self):
        """Recording enough failures should trip the circuit to OPEN."""
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED  # not yet
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_open()

    def test_open_rejects_requests(self):
        """An OPEN circuit should reject allow_request()."""
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        """After recovery_timeout, circuit should transition to HALF_OPEN."""
        cb = CircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=0.01
        )
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)  # wait past timeout
        # allow_request should transition to HALF_OPEN
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_triggers_transition(self):
        """HALF_OPEN → CLOSED after enough successful probes."""
        cb = CircuitBreaker(
            name="test", failure_threshold=2, recovery_timeout=0.01,
            half_open_probe_count=2,
        )
        # Trip to OPEN
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        # Probe: HALF_OPEN
        assert cb.allow_request() is True
        cb.record_success()
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True
        cb.record_success()  # second success should close
        assert cb.state == CircuitState.CLOSED


# ═══════════════════════════════════════════════════════════════════════════════
# CircuitBreaker recovery tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCircuitBreakerRecovery:
    """Tests for CircuitBreaker auto-recovery and backoff."""

    def test_exponential_backoff_on_repeated_trips(self):
        """Repeated trips should increase recovery timeout exponentially."""
        cb = CircuitBreaker(
            name="test", failure_threshold=1, recovery_timeout=0.01,
            backoff_multiplier=2.0, max_recovery_timeout=100.0,
        )
        # First trip
        cb.record_failure()
        assert cb.trip_count == 1
        # recovery_timeout = 0.01 * 2^(0) = 0.01

        # Wait for recovery, then trip again
        time.sleep(0.03)
        cb.allow_request()  # → HALF_OPEN
        cb.record_failure()  # → OPEN again
        assert cb.trip_count == 2
        # recovery_timeout = 0.01 * 2^(1) = 0.02
        assert cb._current_recovery_timeout() == pytest.approx(0.02)

    def test_manual_reset(self):
        """Manual reset should return circuit to CLOSED."""
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_call_wrapper_open_raises(self):
        """CircuitBreaker.call() should raise CircuitOpenError when OPEN."""
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=10.0)
        cb.record_failure()  # trip
        with pytest.raises(CircuitOpenError) as exc_info:
            cb.call(lambda: "ok")
        assert "test" in str(exc_info.value)
        assert exc_info.value.retry_after > 0


# ═══════════════════════════════════════════════════════════════════════════════
# RetryPolicy backoff tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetryPolicyBackoff:
    """Tests for RetryPolicy exponential backoff and jitter."""

    def test_backoff_without_jitter(self):
        """Backoff delay should follow exponential curve when jitter is off."""
        rp = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=60.0, jitter=False)
        assert rp.backoff_delay(1) == pytest.approx(1.0)    # 1.0 * 2^0
        assert rp.backoff_delay(2) == pytest.approx(2.0)    # 1.0 * 2^1
        assert rp.backoff_delay(3) == pytest.approx(4.0)    # 1.0 * 2^2
        assert rp.backoff_delay(4) == pytest.approx(8.0)    # 1.0 * 2^3

    def test_backoff_capped_at_max_delay(self):
        """Backoff delay should not exceed max_delay."""
        rp = RetryPolicy(max_retries=10, base_delay=10.0, max_delay=30.0, jitter=False)
        delay = rp.backoff_delay(10)  # 10 * 2^9 = 5120, capped at 30
        assert delay == pytest.approx(30.0)

    def test_backoff_with_jitter(self):
        """Jitter should produce a value between 0 and the computed delay."""
        rp = RetryPolicy(max_retries=3, base_delay=1.0, max_delay=60.0, jitter=True)
        delays = [rp.backoff_delay(1) for _ in range(50)]
        # All should be between 0 and 1.0
        assert all(0.0 <= d <= 1.0 for d in delays)
        # At least some variation (not all identical)
        assert len(set(round(d, 4) for d in delays)) >= 2

    def test_should_retry_within_max(self):
        """should_retry should return RETRY when within limits."""
        rp = RetryPolicy(max_retries=3)
        assert rp.should_retry(1) == RetryDecision.RETRY
        assert rp.should_retry(2) == RetryDecision.RETRY
        assert rp.should_retry(3) == RetryDecision.RETRY
        assert rp.should_retry(4) == RetryDecision.MAX_RETRIES


# ═══════════════════════════════════════════════════════════════════════════════
# RetryPolicy effect-class tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetryPolicyEffectClass:
    """Tests for per-effect-class retry configuration."""

    def test_read_effects_get_read_policy(self):
        """READ effects (file_read) should get the READ retry policy."""
        policy = retry_policy_for_effect("file_read")
        assert policy.max_retries == 5
        assert policy.base_delay == 0.5
        assert policy.max_budget == 200

    def test_write_effects_get_write_policy(self):
        """WRITE effects (file_write) should get the WRITE retry policy."""
        policy = retry_policy_for_effect("file_write")
        assert policy.max_retries == 2
        assert policy.base_delay == 1.0
        assert policy.max_budget == 50

    def test_unknown_effect_gets_default(self):
        """Unknown effects should get the DEFAULT retry policy."""
        policy = retry_policy_for_effect("some_unknown_effect")
        assert policy.max_retries == 3
        assert policy.base_delay == 1.0
        assert policy.max_budget == 100


# ═══════════════════════════════════════════════════════════════════════════════
# CredentialManager scoping tests (4 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCredentialManagerScoping:
    """Tests for CredentialManager credential scoping by trust tier."""

    def test_hearth_gets_full_scope(self):
        """HEARTH tier should get FULL credential scope."""
        cm = CredentialManager(master_secret="test-secret")
        raw_key = cm.issue_key("hearth", ttl=3600)
        cred = cm.validate(raw_key)
        assert cred is not None
        assert cred.scope == CredentialScope.FULL
        assert cred.trust_tier == "hearth"

    def test_advisory_gets_limited_scope(self):
        """ADVISORY tier should get LIMITED_READ credential scope."""
        cm = CredentialManager(master_secret="test-secret")
        raw_key = cm.issue_key("advisory", ttl=3600)
        cred = cm.validate(raw_key)
        assert cred is not None
        assert cred.scope == CredentialScope.LIMITED_READ

    def test_validate_with_scope_enforces_minimum(self):
        """validate_with_scope should reject credentials with insufficient scope."""
        cm = CredentialManager(master_secret="test-secret")
        raw_key = cm.issue_key("advisory", ttl=3600)
        # Advisory scope should NOT pass for FULL requirement
        cred = cm.validate_with_scope(raw_key, CredentialScope.FULL)
        assert cred is None
        # But should pass for LIMITED_READ
        cred = cm.validate_with_scope(raw_key, CredentialScope.LIMITED_READ)
        assert cred is not None

    def test_unknown_tier_gets_none_scope(self):
        """An unknown trust tier should get NONE scope."""
        cm = CredentialManager(master_secret="test-secret")
        scope = cm._scope_for_tier("nonexistent_tier")
        assert scope == CredentialScope.NONE


# ═══════════════════════════════════════════════════════════════════════════════
# CredentialManager rotation tests (3 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestCredentialManagerRotation:
    """Tests for CredentialManager key rotation."""

    def test_rotate_deactivates_old_key(self):
        """Rotation should deactivate the old credential."""
        cm = CredentialManager(master_secret="rotation-secret")
        raw_key = cm.issue_key("trusted", ttl=3600)
        old_cred = cm.validate(raw_key)
        assert old_cred is not None
        assert old_cred.is_active

        new_cred = cm.rotate_credential(old_cred.key_id, new_ttl=3600)
        assert new_cred is not None
        # Old credential should now be inactive
        old_cred_after = cm.validate(raw_key)
        assert old_cred_after is None  # inactive → validate returns None

    def test_new_key_after_rotation_works(self):
        """The newly issued key after rotation should validate successfully."""
        cm = CredentialManager(master_secret="rotation-secret")
        raw_key = cm.issue_key("trusted", ttl=3600)
        old_cred = cm.validate(raw_key)

        new_cred = cm.rotate_credential(old_cred.key_id, new_ttl=3600)
        new_raw = cm._derive_key(new_cred.key_id)
        validated = cm.validate(new_raw)
        assert validated is not None
        assert validated.rotated_from == old_cred.key_id

    def test_revoke_immediately_invalidates(self):
        """Revocation should immediately invalidate a credential."""
        cm = CredentialManager(master_secret="revoke-secret")
        raw_key = cm.issue_key("trusted", ttl=3600)
        cred = cm.validate(raw_key)
        assert cred is not None

        result = cm.revoke(cred.key_id)
        assert result is True
        assert cm.validate(raw_key) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Bridge integration hardened tests (5 tests)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBridgeIntegrationHardened:
    """Integration tests for hardened MCPBridge and RESTBridge."""

    def test_mcp_bridge_hardened_fields_default_none(self):
        """MCPBridge hardening fields should default to None (backward compat)."""
        bridge = MCPBridge()
        assert bridge.rate_limiter is None
        assert bridge.circuit_breaker is None
        assert bridge.retry_policy is None

    def test_mcp_bridge_accepts_hardening_components(self):
        """MCPBridge should accept RateLimiter, CircuitBreaker, and RetryPolicy."""
        rl = RateLimiter(global_rate=100, global_burst=200)
        cb = CircuitBreaker(name="mcp_test", failure_threshold=3)
        rp = RetryPolicy(max_retries=2)

        bridge = MCPBridge(
            rate_limiter=rl,
            circuit_breaker=cb,
            retry_policy=rp,
        )
        assert bridge.rate_limiter is rl
        assert bridge.circuit_breaker is cb
        assert bridge.retry_policy is rp

    def test_dispatch_tool_call_rate_limited(self):
        """dispatch_tool_call should reject when rate limited."""
        rl = RateLimiter(global_rate=0.1, global_burst=1)  # tiny burst
        bridge = MCPBridge(rate_limiter=rl)
        # Consume the single burst token
        rl.global_bucket.consume(1.0)
        # Now should be rate limited
        result = bridge.dispatch_tool_call(
            "hlf_file_read__read_data",
            {"file_path": "/tmp/x"},
        )
        assert result["status"] == "rate_limited"

    def test_dispatch_tool_call_passes_through(self):
        """dispatch_tool_call should pass through when no hardening is configured."""
        bridge = MCPBridge()
        result = bridge.dispatch_tool_call(
            "hlf_file_read__read_data",
            {"file_path": "/tmp/x"},
        )
        assert result["status"] == "ok"
        assert result["tool"] == "hlf_file_read__read_data"

    def test_rest_bridge_hardened_fields_default_none(self, sample_manifest):
        """RESTBridge hardening fields should default to None (backward compat)."""
        bridge = RESTBridge()
        assert bridge.rate_limiter is None
        assert bridge.circuit_breaker is None
        assert bridge.credential_manager is None

        # Still generates OpenAPI specs correctly
        spec = bridge.generate_openapi_spec([sample_manifest], title="Test API")
        assert spec["openapi"] == "3.1.0"
        assert spec["info"]["title"] == "Test API"
        assert "paths" in spec


# ═══════════════════════════════════════════════════════════════════════════════
# Additional edge case and concurrency tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRateLimiterEdgeCases:
    """Edge case tests for rate limiting components."""

    def test_negative_rate_raises(self):
        """Negative rate should raise ValueError."""
        with pytest.raises(ValueError):
            TokenBucket(rate=-1.0, burst=10.0)

    def test_zero_burst_raises(self):
        """Zero burst should raise ValueError."""
        with pytest.raises(ValueError):
            TokenBucket(rate=10.0, burst=0.0)

    def test_reset_refills_bucket(self):
        """Reset should refill bucket to burst capacity."""
        bucket = TokenBucket(rate=10.0, burst=20.0)
        bucket.consume(15.0)
        assert bucket.available_tokens() == pytest.approx(5.0)
        bucket.reset()
        assert bucket.available_tokens() == pytest.approx(20.0)
        assert bucket.total_consumed == 0

    def test_thread_safety_consume(self):
        """Concurrent consumption should be thread-safe."""
        bucket = TokenBucket(rate=1000.0, burst=1000.0)
        errors: list[Exception] = []

        def _consume_many() -> None:
            try:
                for _ in range(100):
                    bucket.consume(1.0)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_consume_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        # 10 threads * 100 = 1000 total calls, all should have been consumed
        # since rate is high enough, but tokens may run out
        assert bucket.total_consumed + bucket.total_rejected == 1000


class TestCircuitBreakerEdgeCases:
    """Edge case tests for circuit breaker."""

    def test_negative_failure_threshold_raises(self):
        """Failure threshold < 1 should raise ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(failure_threshold=0)

    def test_zero_recovery_timeout_raises(self):
        """Recovery timeout <= 0 should raise ValueError."""
        with pytest.raises(ValueError):
            CircuitBreaker(recovery_timeout=0.0)

    def test_stats_returns_all_fields(self):
        """Stats should include all monitoring fields."""
        cb = CircuitBreaker(name="stats_test")
        stats = cb.stats()
        assert stats["name"] == "stats_test"
        assert stats["state"] == "CLOSED"
        assert "failure_count" in stats
        assert "trip_count" in stats
        assert "retry_after" in stats

    def test_per_bridge_isolation(self):
        """Separate circuit breakers should not affect each other."""
        cb_mcp = CircuitBreaker(name="mcp", failure_threshold=2)
        cb_rest = CircuitBreaker(name="rest", failure_threshold=2)

        # Trip only MCP
        cb_mcp.record_failure()
        cb_mcp.record_failure()
        assert cb_mcp.state == CircuitState.OPEN
        assert cb_rest.state == CircuitState.CLOSED

    def test_retry_after_returns_zero_when_closed(self):
        """retry_after should return 0 when circuit is CLOSED."""
        cb = CircuitBreaker(name="test")
        assert cb.retry_after() == 0.0


class TestRetryPolicyEdgeCases:
    """Edge case tests for retry policy."""

    def test_execute_retries_and_succeeds(self):
        """execute() should retry on failure and return on success."""
        call_count = [0]

        def flaky_func() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("transient")
            return "success"

        rp = RetryPolicy(
            max_retries=5,
            base_delay=0.01,
            jitter=False,
            retryable_exceptions=(ConnectionError,),
        )
        result = rp.execute(flaky_func)
        assert result == "success"
        assert call_count[0] == 3

    def test_execute_exhausts_retries(self):
        """execute() should raise after exhausting max_retries."""
        rp = RetryPolicy(
            max_retries=2,
            base_delay=0.01,
            jitter=False,
            retryable_exceptions=(ValueError,),
        )
        with pytest.raises(ValueError):
            rp.execute(lambda: (_ for _ in ()).throw(ValueError("always fails")))

    def test_non_retryable_raises_immediately(self):
        """Non-retryable exceptions should raise without retrying."""
        rp = RetryPolicy(
            max_retries=5,
            retryable_exceptions=(ConnectionError,),
        )
        with pytest.raises(ValueError):
            rp.execute(lambda: (_ for _ in ()).throw(ValueError("not retryable")))

    def test_budget_tracks_retries(self):
        """Retry budget should track and limit retries."""
        rp = RetryPolicy(
            max_retries=10,
            base_delay=0.01,
            jitter=False,
            max_budget=3,
            retryable_exceptions=(ValueError,),
        )
        # First 4 calls should consume budget (initial + 3 retries)
        with pytest.raises(ValueError):
            rp.execute(lambda: (_ for _ in ()).throw(ValueError("fail")))
        # Budget should now be exhausted
        assert rp.remaining_budget() <= 3  # some consumed

    def test_reset_budget_clears(self):
        """Reset budget should clear all tracked retries."""
        rp = RetryPolicy(max_budget=10, budget_window=60.0)
        rp._consume_budget()
        rp._consume_budget()
        assert rp.remaining_budget() <= 8
        rp.reset_budget()
        assert rp.remaining_budget() == 10


class TestCredentialManagerEdgeCases:
    """Edge case tests for credential management."""

    def test_expired_credential_fails_validation(self):
        """An expired credential should not validate."""
        cm = CredentialManager(master_secret="edge-secret")
        raw_key = cm.issue_key("trusted", ttl=-1)  # already expired
        cred = cm.validate(raw_key)
        assert cred is None

    def test_revoke_nonexistent_returns_false(self):
        """Revoking a nonexistent key_id should return False."""
        cm = CredentialManager(master_secret="edge-secret")
        assert cm.revoke("nonexistent_key") is False

    def test_list_active_excludes_revoked(self):
        """list_active should exclude revoked credentials."""
        cm = CredentialManager(master_secret="edge-secret")
        raw_key = cm.issue_key("trusted", ttl=3600)
        cred = cm.validate(raw_key)
        cm.revoke(cred.key_id)
        active = cm.list_active()
        assert len(active) == 0

    def test_sign_and_verify_credential(self):
        """Credential signing should be verifiable."""
        cm = CredentialManager(master_secret="sign-secret")
        raw_key = cm.issue_key("hearth", ttl=3600)
        signature = cm.sign_credential(raw_key)
        assert cm.verify_credential_signature(raw_key, signature) is True
        assert cm.verify_credential_signature(raw_key, "bad_signature") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Translator Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaTranslator:
    """Tests for SchemaTranslator — HLF type → JSON Schema / OpenAPI."""

    def test_schema_translator_int_to_json(self):
        """HlfType INTEGER maps to {"type": "integer"}."""
        translator = SchemaTranslator(name="test-translator")
        result = translator.hlf_type_to_json_schema(HlfType.INTEGER)
        assert result == {"type": "integer"}

    def test_schema_translator_list_to_json(self):
        """LIST[INT] maps correctly with items."""
        translator = SchemaTranslator(name="test-translator")
        list_int_type = ParametricType(
            base=HlfType.LIST,
            params=(HlfType.INTEGER,),
        )
        result = translator.hlf_type_to_json_schema(list_int_type)
        assert result["type"] == "array"
        assert result["items"] == {"type": "integer"}

    def test_schema_translator_optional_to_json(self):
        """OPTIONAL[STR] maps to anyOf with null via contract."""
        translator = SchemaTranslator(name="test-translator")
        tc = TypeContract(
            name="email",
            hlf_type=HlfType.STRING,
            required=False,
        )
        contract = InputContract(
            function_name="send_notification",
            parameters=[tc],
        )
        result = translator.contract_to_schema(contract, SchemaFormat.JSON_SCHEMA)
        prop_schema = result.schema["properties"]["email"]
        assert "anyOf" in prop_schema
        assert {"type": "null"} in prop_schema["anyOf"]

    def test_schema_translator_contract_to_schema(self):
        """InputContract translates to JSON Schema with required fields."""
        translator = SchemaTranslator(name="test-translator")
        tc_name = TypeContract(
            name="username",
            hlf_type=HlfType.STRING,
            required=True,
        )
        tc_age = TypeContract(
            name="age",
            hlf_type=HlfType.INTEGER,
            required=True,
        )
        contract = InputContract(
            function_name="create_user",
            parameters=[tc_name, tc_age],
        )
        result = translator.contract_to_schema(contract, SchemaFormat.JSON_SCHEMA)
        assert result.schema["type"] == "object"
        assert "username" in result.schema["properties"]
        assert "age" in result.schema["properties"]
        assert result.schema["required"] == ["username", "age"]
        assert result.format == SchemaFormat.JSON_SCHEMA

    def test_schema_translator_manifest_to_openapi(self):
        """CapabilityManifest produces valid OpenAPI structure with paths, info, servers."""
        translator = SchemaTranslator(name="test-translator")

        # Build mock TypedEffectDeclaration with proper contracts
        input_contract = InputContract(
            function_name="hello_world",
            parameters=[
                TypeContract(name="name", hlf_type=HlfType.STRING, required=True),
            ],
        )
        output_contract = OutputContract(
            function_name="hello_world",
            return_type=HlfType.STRING,
        )

        MockEffect = type("MockEffect", (), {
            "function_name": "hello_world",
            "effect_class": EffectClass.LOCAL_ANALYSIS,
            "safety_class": "none",
            "input_contract": input_contract,
            "output_contract": output_contract,
        })

        MockManifest = type("MockManifest", (), {
            "program_id": "abc123def456abc123def456abc123def456abc123def456",
            "compiler_version": "3.0.0",
            "trust_tier": "advisory",
            "effects": [MockEffect],
        })

        manifest = MockManifest()
        spec = translator.manifest_to_openapi(manifest, base_url="http://localhost:8000")

        assert spec["openapi"] == "3.0.3"
        assert "info" in spec
        assert "servers" in spec
        assert spec["servers"][0]["url"] == "http://localhost:8000"
        assert "paths" in spec
        assert "/effects/hello_world" in spec["paths"]
        path_item = spec["paths"]["/effects/hello_world"]
        assert "post" in path_item
        assert path_item["post"]["operationId"] == "execute_hello_world"

    def test_schema_translator_validate_payload_valid(self):
        """Valid payload passes validation."""
        translator = SchemaTranslator(name="test-translator")
        tc = TypeContract(name="name", hlf_type=HlfType.STRING, required=True)
        contract = InputContract(function_name="greet", parameters=[tc])
        valid, errors = translator.validate_payload({"name": "Alice"}, contract)
        assert valid is True
        assert errors == []

    def test_schema_translator_validate_payload_invalid(self):
        """Missing required field returns errors."""
        translator = SchemaTranslator(name="test-translator")
        tc = TypeContract(name="name", hlf_type=HlfType.STRING, required=True)
        contract = InputContract(function_name="greet", parameters=[tc])
        valid, errors = translator.validate_payload({}, contract)
        assert valid is False
        assert len(errors) > 0

    def test_schema_translator_generate_client_sdk(self):
        """Python SDK string contains expected patterns."""
        translator = SchemaTranslator(name="test-translator")
        tc = TypeContract(
            name="username",
            hlf_type=HlfType.STRING,
            required=True,
            constraints={"description": "User handle"},
        )
        contract = InputContract(function_name="create_user", parameters=[tc])
        sdk_code = translator.generate_client_sdk(contract, language="python")
        assert "class CreateUserInput" in sdk_code
        assert "BaseModel" in sdk_code
        assert "username" in sdk_code
        assert "from pydantic" in sdk_code

    def test_schema_translator_string_to_json(self):
        """HlfType STRING maps to {"type": "string"}."""
        translator = SchemaTranslator(name="test-translator")
        result = translator.hlf_type_to_json_schema(HlfType.STRING)
        assert result == {"type": "string"}

    def test_schema_translator_boolean_to_json(self):
        """HlfType BOOLEAN maps to {"type": "boolean"}."""
        translator = SchemaTranslator(name="test-translator")
        result = translator.hlf_type_to_json_schema(HlfType.BOOLEAN)
        assert result == {"type": "boolean"}


# ═══════════════════════════════════════════════════════════════════════════════
# Distributed Rate Limiter Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestDistributedRateLimiter:
    """Tests for DistributedRateLimiter — multi-instance token coordination."""

    def test_distributed_limiter_register_instance(self):
        """Register an instance and verify it returns an instance_id."""
        limiter = DistributedRateLimiter(
            name="test-dlr",
            total_capacity=100.0,
            refill_rate=10.0,
            max_instances=5,
        )
        iid = limiter.register_instance()
        assert iid.startswith("hlf-dlr-")
        assert iid in limiter.instances
        assert limiter.instances[iid].tokens_available > 0

    def test_distributed_limiter_acquire_tokens(self):
        """Acquire consumes tokens from the instance's allocation."""
        limiter = DistributedRateLimiter(total_capacity=100.0, refill_rate=50.0)
        iid = limiter.register_instance()
        # First acquire should succeed with enough capacity
        result = limiter.acquire(iid, tokens=1.0)
        assert result is True
        # Tokens should have been consumed
        state = limiter.instances[iid]
        assert state.tokens_available < 100.0

    def test_distributed_limiter_deregister(self):
        """Deregister removes an instance."""
        limiter = DistributedRateLimiter(total_capacity=100.0)
        iid = limiter.register_instance()
        assert iid in limiter.instances
        removed = limiter.deregister_instance(iid)
        assert removed is True
        assert iid not in limiter.instances

    def test_distributed_limiter_fairness_score(self):
        """Jain's fairness index computed for registered instances."""
        limiter = DistributedRateLimiter(total_capacity=100.0)
        limiter.register_instance()
        limiter.register_instance()
        score = limiter.fairness_score()
        assert 0.0 <= score <= 1.0
        # With equal allocation, fairness should be 1.0
        assert score == pytest.approx(1.0, abs=0.01)

    def test_distributed_limiter_rebalance(self):
        """Rebalance distributes tokens across instances."""
        limiter = DistributedRateLimiter(total_capacity=1000.0, refill_rate=0.001)
        iid1 = limiter.register_instance("inst-a")
        iid2 = limiter.register_instance("inst-b")
        # Consume tokens from iid1 — with very low refill_rate, negligible auto-refill
        limiter.acquire(iid1, tokens=200.0)
        limiter.acquire(iid1, tokens=200.0)
        diff_before = abs(
            limiter.instances[iid1].tokens_available
            - limiter.instances[iid2].tokens_available
        )
        limiter.rebalance()
        diff_after = abs(
            limiter.instances[iid1].tokens_available
            - limiter.instances[iid2].tokens_available
        )
        assert diff_after < diff_before  # Rebalance should reduce disparity

    def test_distributed_limiter_heartbeat(self):
        """sync_heartbeat updates the reported_at timestamp."""
        limiter = DistributedRateLimiter(total_capacity=100.0)
        iid = limiter.register_instance()
        original_ts = limiter.instances[iid].reported_at
        # Small delay to ensure timestamp changes
        time.sleep(0.01)
        limiter.sync_heartbeat(iid)
        assert limiter.instances[iid].reported_at != original_ts

    def test_distributed_limiter_max_instances(self):
        """max_instances limit enforced."""
        limiter = DistributedRateLimiter(total_capacity=100.0, max_instances=2)
        limiter.register_instance("inst-a")
        limiter.register_instance("inst-b")
        with pytest.raises(RuntimeError, match="max_instances"):
            limiter.register_instance("inst-c")

    def test_distributed_limiter_global_state(self):
        """State dict returned by get_global_state has expected keys."""
        limiter = DistributedRateLimiter(
            name="test-global",
            total_capacity=100.0,
            refill_rate=10.0,
        )
        limiter.register_instance("instance-1")
        state = limiter.get_global_state()
        assert state["name"] == "test-global"
        assert state["total_capacity"] == 100.0
        assert state["instance_count"] == 1
        assert "fairness_index" in state
        assert "per_instance" in state
        assert "instance-1" in state["per_instance"]


# ═══════════════════════════════════════════════════════════════════════════════
# Resilience Coordinator Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestResilienceCoordinator:
    """Tests for ResilienceCoordinator — unified resilience cascade."""

    @staticmethod
    def _make_circuit_breaker():
        """Create a mock circuit breaker with state tracking."""
        class MockCB:
            def __init__(self):
                self.state = CircuitState.CLOSED
                self.trip_count = 0
                self.failure_count = 0
                self._probe_successes = 0
                self._probe_failures = 0

            def trip(self):
                self.state = CircuitState.OPEN
                self.trip_count += 1

            def reset(self):
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.trip_count = 0

            def record_success(self):
                if self.state == CircuitState.HALF_OPEN:
                    self._probe_successes += 1
                    if self._probe_successes >= 3:
                        self.state = CircuitState.CLOSED
                        self.failure_count = 0

            def record_failure(self):
                if self.state == CircuitState.CLOSED:
                    self.failure_count += 1
                    if self.failure_count >= 5:
                        self.state = CircuitState.OPEN
                        self.trip_count += 1
                elif self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.OPEN
                    self.trip_count += 1

            def is_open(self):
                return self.state == CircuitState.OPEN

        return MockCB()

    @staticmethod
    def _make_credential_manager():
        """Create a mock credential manager."""
        class MockCM:
            def __init__(self):
                self._creds = [{"key_id": "key-1"}, {"key_id": "key-2"}]
                self._rotation_count = 0

            def list_active(self):
                return list(self._creds)

            def rotate_credential(self, key_id):
                self._rotation_count += 1
                return {"key_id": f"rotated-{key_id}", "value": "new-secret"}

            def stats(self):
                return {"active": len(self._creds), "rotations": self._rotation_count}

            def count_active(self):
                return len(self._creds)

        return MockCM()

    @staticmethod
    def _make_retry_policy():
        """Create a mock retry policy."""
        class MockRP:
            def __init__(self):
                self.base_delay = 1.0
                self.max_delay = 30.0
                self.max_retries = 3

            def stats(self):
                return {
                    "max_retries": self.max_retries,
                    "base_delay": self.base_delay,
                }

        return MockRP()

    def test_resilience_register_service(self):
        """Service registered successfully with all components."""
        coordinator = ResilienceCoordinator(name="test-coordinator")
        cb = self._make_circuit_breaker()
        cm = self._make_credential_manager()
        rp = self._make_retry_policy()
        coordinator.register_service("test-svc", cb, cm, rp)
        assert "test-svc" in coordinator.circuit_breakers
        assert "test-svc" in coordinator.credential_managers
        assert "test-svc" in coordinator.retry_policies
        assert "test-svc" in coordinator.failure_counters

    def test_resilience_handle_auth_failure(self):
        """Auth failure opens circuit + rotates credentials after threshold."""
        coordinator = ResilienceCoordinator(
            name="test-coordinator",
            policy=ResiliencePolicy(
                auth_failure_threshold=2,
                credential_rotation_on_open=True,
            ),
        )
        cb = self._make_circuit_breaker()
        cm = self._make_credential_manager()
        rp = self._make_retry_policy()
        coordinator.register_service("test-svc", cb, cm, rp)

        # First auth failure — should not trip yet
        events1 = coordinator.handle_failure("test-svc", PermissionError("unauthorized"))
        assert cb.state == CircuitState.CLOSED

        # Second auth failure — should trip circuit + rotate credentials
        events2 = coordinator.handle_failure("test-svc", PermissionError("forbidden"))
        assert cb.state == CircuitState.OPEN
        assert cb.trip_count == 1
        actions = [e.action for e in events2]
        assert ResilienceAction.OPEN_CIRCUIT in actions
        assert ResilienceAction.ROTATE_CREDENTIALS in actions

    def test_resilience_handle_timeout(self):
        """Timeout opens circuit immediately."""
        coordinator = ResilienceCoordinator(name="test-coordinator")
        cb = self._make_circuit_breaker()
        cm = self._make_credential_manager()
        rp = self._make_retry_policy()
        coordinator.register_service("test-svc", cb, cm, rp)

        events = coordinator.handle_failure("test-svc", TimeoutError("timed out"))
        assert cb.state == CircuitState.OPEN
        assert any(e.action == ResilienceAction.OPEN_CIRCUIT for e in events)

    def test_resilience_handle_success_closes_circuit(self):
        """Success after HALF_OPEN closes circuit."""
        coordinator = ResilienceCoordinator(name="test-coordinator")
        cb = self._make_circuit_breaker()
        cm = self._make_credential_manager()
        rp = self._make_retry_policy()
        coordinator.register_service("test-svc", cb, cm, rp)

        # First open the circuit
        coordinator.handle_failure("test-svc", TimeoutError("timeout"))
        assert cb.state == CircuitState.OPEN

        # Transition to HALF_OPEN and record success probes
        cb.state = CircuitState.HALF_OPEN
        cb._probe_successes = 2
        events = coordinator.handle_success("test-svc")
        assert cb.state == CircuitState.CLOSED
        assert any(e.action == ResilienceAction.CLOSE_CIRCUIT for e in events)
        assert any(e.action == ResilienceAction.RESET_FAILURE_COUNT for e in events)

    def test_resilience_get_service_status(self):
        """Status returns circuit state, failure count."""
        coordinator = ResilienceCoordinator(name="test-coordinator")
        cb = self._make_circuit_breaker()
        cm = self._make_credential_manager()
        rp = self._make_retry_policy()
        coordinator.register_service("test-svc", cb, cm, rp)

        coordinator.handle_failure("test-svc", TimeoutError("timeout"))
        status = coordinator.get_service_status("test-svc")
        assert status["service_name"] == "test-svc"
        assert status["registered"] is True
        assert status["failure_counters"]["timeout"] >= 1
        assert status["circuit"] is not None
        assert status["circuit"]["state"] == "OPEN"

    def test_resilience_global_status(self):
        """Aggregated status across all registered services."""
        coordinator = ResilienceCoordinator(name="test-coordinator")
        cb1 = self._make_circuit_breaker()
        cm1 = self._make_credential_manager()
        rp1 = self._make_retry_policy()
        coordinator.register_service("svc-a", cb1, cm1, rp1)

        cb2 = self._make_circuit_breaker()
        cm2 = self._make_credential_manager()
        rp2 = self._make_retry_policy()
        coordinator.register_service("svc-b", cb2, cm2, rp2)

        gs = coordinator.global_status()
        assert gs["coordinator"] == "test-coordinator"
        assert gs["service_count"] == 2
        assert "svc-a" in gs["services"]
        assert "svc-b" in gs["services"]
        assert "global_health_score" in gs
        assert "health_interpretation" in gs

    def test_resilience_simulate_cascade(self):
        """Simulation returns events without side effects."""
        coordinator = ResilienceCoordinator(
            name="test-coordinator",
            policy=ResiliencePolicy(
                auth_failure_threshold=2,
                credential_rotation_on_open=True,
            ),
        )
        cb = self._make_circuit_breaker()
        cm = self._make_credential_manager()
        rp = self._make_retry_policy()
        coordinator.register_service("test-svc", cb, cm, rp)

        # Simulate a cascade of "auth", "auth", "timeout"
        sim_results = coordinator.simulate_cascade("test-svc", ["auth", "auth", "timeout"])

        assert len(sim_results) == 3
        # Step 0: first auth — no threshold yet
        assert len(sim_results[0]) == 0
        # Step 1: second auth — triggers OPEN_CIRCUIT + ROTATE_CREDENTIALS
        step1_actions = [e.action for e in sim_results[1]]
        assert ResilienceAction.OPEN_CIRCUIT in step1_actions
        assert ResilienceAction.ROTATE_CREDENTIALS in step1_actions
        # Step 2: timeout — triggers OPEN_CIRCUIT
        step2_actions = [e.action for e in sim_results[2]]
        assert ResilienceAction.OPEN_CIRCUIT in step2_actions

        # Real state should be untouched (simulation only)
        assert cb.state == CircuitState.CLOSED
        assert coordinator.failure_counters.get("test-svc", {}).get("total", 0) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# Bridge Health Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBridgeHealth:
    """Tests for BridgeHealthAggregator — bridge health monitoring."""

    @staticmethod
    def _make_mock_bridge(bridge_type="mcp", **attrs):
        """Create a mock bridge with expected attributes."""
        defaults = {
            "tool_registrations": {"tool_a": {}, "tool_b": {}} if bridge_type == "mcp" else None,
            "endpoints": [{"path": "/health"}, {"path": "/api"}] if bridge_type == "rest" else None,
            "circuit_breaker": None,
            "rate_limiter": None,
            "credential_manager": None,
        }
        defaults.update(attrs)

        class MockBridge:
            pass

        bridge = MockBridge()
        for k, v in defaults.items():
            if v is not None or hasattr(bridge, k) is False:
                setattr(bridge, k, v)

        def stats_method():
            return {"requests": 42, "errors": 2}

        bridge.stats = stats_method
        return bridge

    def test_bridge_health_register(self):
        """Bridge registered with type."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        bridge = self._make_mock_bridge("mcp")
        aggregator.register_bridge("mcp-main", "mcp", bridge)
        assert "mcp-main" in aggregator.bridges
        assert aggregator.bridges["mcp-main"][0] == "mcp"

    def test_bridge_health_register_invalid_type(self):
        """Invalid bridge type raises ValueError."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        bridge = self._make_mock_bridge("mcp")
        with pytest.raises(ValueError, match="bridge_type"):
            aggregator.register_bridge("bad-bridge", "invalid", bridge)

    def test_bridge_health_check(self):
        """Health check returns BridgeHealth with metrics."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        bridge = self._make_mock_bridge("mcp")
        aggregator.register_bridge("mcp-main", "mcp", bridge)
        health = aggregator.check_bridge("mcp-main")
        assert isinstance(health, BridgeHealth)
        assert health.bridge_name == "mcp-main"
        assert health.bridge_type == "mcp"
        assert health.latency_ms >= 0
        assert health.error_rate == 0.0

    def test_bridge_health_check_rest(self):
        """REST bridge health check returns BridgeHealth with metrics."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        bridge = self._make_mock_bridge("rest")
        aggregator.register_bridge("rest-api", "rest", bridge)
        health = aggregator.check_bridge("rest-api")
        assert isinstance(health, BridgeHealth)
        assert health.bridge_type == "rest"
        assert "registered_endpoints" in health.details

    def test_bridge_health_check_all(self):
        """Aggregation has overall_score and bridge_healths."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        bridge1 = self._make_mock_bridge("mcp")
        bridge2 = self._make_mock_bridge("rest")
        aggregator.register_bridge("mcp-main", "mcp", bridge1)
        aggregator.register_bridge("rest-api", "rest", bridge2)
        aggregation = aggregator.check_all()
        assert isinstance(aggregation, HealthAggregation)
        assert aggregation.overall_score >= 0.0
        assert len(aggregation.bridge_healths) == 2
        assert isinstance(aggregation.bridge_healths[0], BridgeHealth)

    def test_bridge_health_score_computation(self):
        """health_score computes weighted value."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        health = BridgeHealth(
            bridge_name="test",
            bridge_type="mcp",
            latency_ms=100.0,
            error_rate=0.0,
            uptime_pct=100.0,
            consecutive_failures=0,
        )
        score = aggregator.health_score(health)
        assert 0.9 <= score <= 1.0  # Perfect health should be near 1.0

        # Degraded health
        bad_health = BridgeHealth(
            bridge_name="degraded",
            bridge_type="mcp",
            latency_ms=4000.0,
            error_rate=0.5,
            uptime_pct=80.0,
            consecutive_failures=5,
        )
        bad_score = aggregator.health_score(bad_health)
        assert bad_score < 0.7

    def test_bridge_health_trend_analysis(self):
        """Trend shows direction."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        bridge = self._make_mock_bridge("mcp")
        aggregator.register_bridge("mcp-main", "mcp", bridge)

        # Run multiple health checks to build history
        for _ in range(5):
            aggregator.check_bridge("mcp-main")

        trends = aggregator.trend_analysis(window=10)
        assert "mcp-main" in trends
        assert trends["mcp-main"]["direction"] in ("stable", "improving", "degrading")
        assert "slope" in trends["mcp-main"]
        assert "confidence" in trends["mcp-main"]

    def test_bridge_health_recommendations(self):
        """Degraded bridges generate recommendations."""
        aggregator = BridgeHealthAggregator(
            name="test-agg",
            degradation_threshold=0.9,
            unhealthy_threshold=0.5,
        )

        # Create a DEGRADED health with high latency
        degraded = HealthAggregation(
            overall_status=HealthStatus.DEGRADED,
            overall_score=0.75,
            bridge_healths=[
                BridgeHealth(
                    bridge_name="slow-bridge",
                    bridge_type="mcp",
                    status=HealthStatus.DEGRADED,
                    latency_ms=2000.0,
                    error_rate=0.0,
                    uptime_pct=95.0,
                ),
            ],
            degraded_bridges=["slow-bridge"],
            unhealthy_bridges=[],
        )
        recs = aggregator.generate_recommendations(degraded)
        assert len(recs) > 0
        assert any("latency" in r.lower() for r in recs)

    def test_bridge_health_alerts(self):
        """Alerts generated for unhealthy bridges."""
        aggregator = BridgeHealthAggregator(name="test-agg")

        aggregation = HealthAggregation(
            overall_status=HealthStatus.UNHEALTHY,
            overall_score=0.3,
            bridge_healths=[
                BridgeHealth(
                    bridge_name="down-bridge",
                    bridge_type="mcp",
                    status=HealthStatus.DOWN,
                    consecutive_failures=5,
                    error_rate=1.0,
                ),
                BridgeHealth(
                    bridge_name="unhealthy-bridge",
                    bridge_type="rest",
                    status=HealthStatus.UNHEALTHY,
                    error_rate=0.6,
                ),
            ],
            degraded_bridges=[],
            unhealthy_bridges=["down-bridge", "unhealthy-bridge"],
        )
        alerts = aggregator.alert_on_degradation(aggregation)
        assert len(alerts) >= 2
        severities = [a["severity"] for a in alerts]
        assert "critical" in severities
        assert "warning" in severities

    def test_bridge_health_check_unregistered_raises(self):
        """Checking an unregistered bridge raises KeyError."""
        aggregator = BridgeHealthAggregator(name="test-agg")
        with pytest.raises(KeyError):
            aggregator.check_bridge("nonexistent")
