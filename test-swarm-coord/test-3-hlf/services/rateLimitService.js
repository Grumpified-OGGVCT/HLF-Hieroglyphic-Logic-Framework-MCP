/**
 * RateLimitService — sliding-window rate limiter with Redis or in-memory fallback.
 *
 * Factory shape: factory(redis) -> { check, consume, reset }
 */

function createRateLimitService(redis) {
  // In-memory fallback when no Redis client is provided
  const memory = new Map();

  function now() {
    return Date.now();
  }

  function getResetAt(windowMs) {
    return new Date(now() + windowMs);
  }

  // ---- In-memory helpers ----
  function memoryCheck(identifier, windowMs, maxRequests) {
    const entries = memory.get(identifier) || [];
    const cutoff = now() - windowMs;
    const fresh = entries.filter((ts) => ts > cutoff);
    const count = fresh.length;
    const allowed = count < maxRequests;
    const remaining = Math.max(0, maxRequests - count);
    // Update trimmed array to keep memory bounded
    memory.set(identifier, fresh);
    return { allowed, remaining, resetAt: getResetAt(windowMs) };
  }

  function memoryConsume(identifier, windowMs, maxRequests) {
    const entries = memory.get(identifier) || [];
    const cutoff = now() - windowMs;
    const fresh = entries.filter((ts) => ts > cutoff);
    const count = fresh.length;
    const allowed = count < maxRequests;
    if (allowed) {
      fresh.push(now());
    }
    memory.set(identifier, fresh);
    const remaining = Math.max(0, maxRequests - fresh.length);
    return { allowed, remaining, resetAt: getResetAt(windowMs) };
  }

  function memoryReset(identifier) {
    memory.delete(identifier);
  }

  // ---- Redis helpers (sorted-set sliding window) ----
  async function redisCheck(identifier, windowMs, maxRequests) {
    const key = `ratelimit:${identifier}`;
    const t = now();
    const cutoff = t - windowMs;
    const pipeline = redis.pipeline();
    pipeline.zremrangebyscore(key, 0, cutoff);
    pipeline.zcard(key);
    const results = await pipeline.exec();
    const count = results[1][1] || 0;
    const allowed = count < maxRequests;
    const remaining = Math.max(0, maxRequests - count);
    return { allowed, remaining, resetAt: getResetAt(windowMs) };
  }

  async function redisConsume(identifier, windowMs, maxRequests) {
    const key = `ratelimit:${identifier}`;
    const t = now();
    const cutoff = t - windowMs;
    const member = `${t}-${Math.random().toString(36).slice(2, 8)}`;
    const pipeline = redis.pipeline();
    pipeline.zremrangebyscore(key, 0, cutoff);
    pipeline.zcard(key);
    const preResults = await pipeline.exec();
    const count = preResults[1][1] || 0;
    const allowed = count < maxRequests;

    if (allowed) {
      await redis.zadd(key, t, member);
      await redis.pexpire(key, windowMs);
    }

    const finalCount = allowed ? count + 1 : count;
    const remaining = Math.max(0, maxRequests - finalCount);
    return { allowed, remaining, resetAt: getResetAt(windowMs) };
  }

  async function redisReset(identifier) {
    const key = `ratelimit:${identifier}`;
    await redis.del(key);
  }

  // Detect Redis availability
  const hasRedis =
    redis &&
    typeof redis.pipeline === 'function' &&
    typeof redis.zadd === 'function';

  return {
    check: hasRedis
      ? (identifier, windowMs, maxRequests) =>
          redisCheck(identifier, windowMs, maxRequests)
      : (identifier, windowMs, maxRequests) =>
          Promise.resolve(memoryCheck(identifier, windowMs, maxRequests)),
    consume: hasRedis
      ? (identifier, windowMs, maxRequests) =>
          redisConsume(identifier, windowMs, maxRequests)
      : (identifier, windowMs, maxRequests) =>
          Promise.resolve(memoryConsume(identifier, windowMs, maxRequests)),
    reset: hasRedis
      ? (identifier) => redisReset(identifier)
      : (identifier) => Promise.resolve(memoryReset(identifier)),
  };
}

module.exports = createRateLimitService;
