/**
 * rateLimit middleware — factory taking rateLimitService, returns Express middleware.
 *
 * Applies sliding-window rate limiting per IP.
 *   window = 60 000 ms
 *   max    = 100 requests
 * Skips /health endpoint.
 */

function createRateLimitMiddleware(rateLimitService) {
  const WINDOW_MS = 60000;
  const MAX_REQUESTS = 100;

  return async function rateLimitMiddleware(req, res, next) {
    if (req.path === '/health') {
      return next();
    }

    const identifier =
      req.ip ||
      req.headers['x-forwarded-for'] ||
      req.socket?.remoteAddress ||
      'unknown';

    try {
      const result = await rateLimitService.consume(
        identifier,
        WINDOW_MS,
        MAX_REQUESTS
      );

      res.setHeader('X-RateLimit-Limit', String(MAX_REQUESTS));
      res.setHeader('X-RateLimit-Remaining', String(result.remaining));
      res.setHeader(
        'X-RateLimit-Reset',
        result.resetAt.toISOString()
      );

      if (!result.allowed) {
        return res.status(429).json({
          error: 'Too Many Requests',
          retryAfter: Math.ceil(WINDOW_MS / 1000),
        });
      }

      next();
    } catch (err) {
      // Fail open: if rate limiter errors, allow request through
      next();
    }
  };
}

module.exports = createRateLimitMiddleware;
