/**
 * Express middleware factory that applies a sliding-window rate limit.
 *
 * @param {Object} rateLimitService – object with { consume }
 * @returns {Function} Express middleware
 */
function createRateLimitMiddleware(rateLimitService) {
  const WINDOW_MS = 60000;
  const MAX_REQUESTS = 100;

  /**
   * Extract the most reliable client IP from the request.
   * @param {import('express').Request} req
   * @returns {string}
   */
  function getClientIp(req) {
    const forwarded = req.headers['x-forwarded-for'];
    if (forwarded) {
      return forwarded.split(',')[0].trim();
    }
    return req.ip || req.socket?.remoteAddress || 'unknown';
  }

  /**
   * Express middleware that rate-limits requests by IP.
   */
  async function rateLimitMiddleware(req, res, next) {
    // Skip health endpoint entirely
    if (req.path === '/health') {
      return next();
    }

    const ip = getClientIp(req);

    try {
      const result = await rateLimitService.consume(ip, {
        windowMs: WINDOW_MS,
        maxRequests: MAX_REQUESTS,
      });

      // Attach rate-limit headers to every response
      res.setHeader('X-RateLimit-Limit', String(MAX_REQUESTS));
      res.setHeader('X-RateLimit-Remaining', String(result.remaining));
      res.setHeader('X-RateLimit-Reset', result.resetAt.toISOString());

      if (!result.allowed) {
        return res.status(429).json({
          error: 'Too Many Requests',
          message: 'Rate limit exceeded. Please try again later.',
        });
      }

      next();
    } catch (err) {
      // Fail open on errors
      next();
    }
  }

  return rateLimitMiddleware;
}

module.exports = { createRateLimitMiddleware };
