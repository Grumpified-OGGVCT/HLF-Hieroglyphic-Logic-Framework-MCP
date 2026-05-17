/**
 * Sliding-window rate limiter backed by Redis sorted sets,
 * with an in-memory Map fallback when Redis is absent.
 */

function createRateLimitService(redis) {
  const WINDOW_MS = 60000;
  const MAX_REQUESTS = 100;

  // In-memory fallback: ip -> [{ timestamp }]
  const memoryStore = new Map();

  /**
   * Trim in-memory entries older than (now - windowMs).
   * @param {Array<{ts:number}>} entries
   * @param {number} now
   * @returns {Array<{ts:number}>}
   */
  function trimMemoryEntries(entries, now) {
    const cutoff = now - WINDOW_MS;
    let i = 0;
    while (i < entries.length && entries[i].ts <= cutoff) {
      i++;
    }
    if (i > 0) {
      return entries.slice(i);
    }
    return entries;
  }

  /**
   * Generate a Redis key for an IP.
   * @param {string} ip
   * @returns {string}
   */
  function keyFor(ip) {
    return `ratelimit:${ip}`;
  }

  /**
   * Shared result builder.
   * @param {boolean} allowed
   * @param {number} count
   * @param {number} now
   * @returns {{allowed:boolean, remaining:number, resetAt:Date}}
   */
  function buildResult(allowed, count, now) {
    const remaining = Math.max(0, MAX_REQUESTS - count);
    const resetAt = new Date(now + WINDOW_MS);
    return { allowed, remaining, resetAt };
  }

  /**
   * Check whether a request from `ip` would be allowed right now
   * without actually consuming a request.
   * @param {string} ip
   * @param {{windowMs?:number, maxRequests?:number}} [options]
   * @returns {Promise<{allowed:boolean, remaining:number, resetAt:Date}>}
   */
  async function check(ip, options = {}) {
    const windowMs = options.windowMs ?? WINDOW_MS;
    const maxRequests = options.maxRequests ?? MAX_REQUESTS;
    const now = Date.now();

    if (redis) {
      const key = keyFor(ip);
      const pipeline = redis.pipeline();
      pipeline.zremrangebyscore(key, 0, now - windowMs);
      pipeline.zcard(key);
      const [, [, count]] = await pipeline.exec();
      const allowed = count < maxRequests;
      const remaining = Math.max(0, maxRequests - count);
      return {
        allowed,
        remaining,
        resetAt: new Date(now + windowMs),
      };
    }

    // In-memory fallback
    let entries = memoryStore.get(ip) || [];
    entries = trimMemoryEntries(entries, now);
    const count = entries.length;
    const allowed = count < maxRequests;
    const remaining = Math.max(0, maxRequests - count);
    return {
      allowed,
      remaining,
      resetAt: new Date(now + windowMs),
    };
  }

  /**
   * Consume one request from the sliding window for `ip`.
   * @param {string} ip
   * @param {{windowMs?:number, maxRequests?:number}} [options]
   * @returns {Promise<{allowed:boolean, remaining:number, resetAt:Date}>}
   */
  async function consume(ip, options = {}) {
    const windowMs = options.windowMs ?? WINDOW_MS;
    const maxRequests = options.maxRequests ?? MAX_REQUESTS;
    const now = Date.now();

    if (redis) {
      const key = keyFor(ip);
      const pipeline = redis.pipeline();
      pipeline.zremrangebyscore(key, 0, now - windowMs);
      pipeline.zcard(key);
      const [, [, countBefore]] = await pipeline.exec();

      if (countBefore >= maxRequests) {
        return buildResult(false, countBefore, now);
      }

      await redis.zadd(key, now, `${now}:${Math.random().toString(36).slice(2)}`);
      await redis.pexpire(key, windowMs);
      const newCount = countBefore + 1;
      return buildResult(true, newCount, now);
    }

    // In-memory fallback
    let entries = memoryStore.get(ip) || [];
    entries = trimMemoryEntries(entries, now);
    const countBefore = entries.length;

    if (countBefore >= maxRequests) {
      memoryStore.set(ip, entries);
      return buildResult(false, countBefore, now);
    }

    entries.push({ ts: now });
    memoryStore.set(ip, entries);
    return buildResult(true, entries.length, now);
  }

  /**
   * Reset the sliding window for `ip`.
   * @param {string} ip
   * @returns {Promise<{allowed:boolean, remaining:number, resetAt:Date}>}
   */
  async function reset(ip) {
    const now = Date.now();

    if (redis) {
      const key = keyFor(ip);
      await redis.del(key);
    } else {
      memoryStore.delete(ip);
    }

    return buildResult(true, 0, now);
  }

  return { check, consume, reset };
}

module.exports = { createRateLimitService };
