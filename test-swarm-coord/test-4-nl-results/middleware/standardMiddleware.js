const { parse } = require('url');
const querystring = require('querystring');

/**
 * Collect request body as a string
 * @param {import('http').IncomingMessage} req
 * @returns {Promise<string>}
 */
function collectRequestBody(req) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    req.on('data', chunk => chunks.push(chunk));
    req.on('end', () => resolve(Buffer.concat(chunks).toString()));
    req.on('error', reject);
  });
}

/**
 * Middleware that parses JSON request bodies.
 * Sets req.body to the parsed object.
 * If parsing fails, responds with 400.
 */
function jsonBodyParser() {
  return async function jsonParserMiddleware(req, res, next) {
    if (req.headers['content-type'] && req.headers['content-type'].includes('application/json')) {
      try {
        const raw = await collectRequestBody(req);
        if (raw) {
          req.body = JSON.parse(raw);
        }
      } catch (err) {
        res.statusCode = 400;
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ error: 'Invalid JSON body' }));
        return;
      }
    }
    await next();
  };
}

/**
 * Middleware that parses URL-encoded request bodies.
 * Sets req.body with parsed key-value pairs.
 */
function urlencodedBodyParser() {
  return async function urlencodedParserMiddleware(req, res, next) {
    if (req.headers['content-type'] && req.headers['content-type'].includes('application/x-www-form-urlencoded')) {
      try {
        const raw = await collectRequestBody(req);
        if (raw) {
          req.body = querystring.parse(raw);
        }
      } catch (err) {
        res.statusCode = 400;
        res.setHeader('Content-Type', 'text/plain');
        res.end('Invalid URL-encoded body');
        return;
      }
    }
    await next();
  };
}

/**
 * Basic CORS middleware.
 * Allows all origins, methods, and headers by default.
 */
function corsMiddleware(options = {}) {
  const {
    origin = '*',
    methods = 'GET,HEAD,PUT,PATCH,POST,DELETE',
    allowedHeaders = 'Content-Type,Authorization',
    credentials = true,
  } = options;

  return async function corsMiddlewareHandler(req, res, next) {
    res.setHeader('Access-Control-Allow-Origin', origin);
    res.setHeader('Access-Control-Allow-Methods', methods);
    res.setHeader('Access-Control-Allow-Headers', allowedHeaders);
    if (credentials) {
      res.setHeader('Access-Control-Allow-Credentials', 'true');
    }
    if (req.method === 'OPTIONS') {
      res.statusCode = 204;
      res.end();
      return;
    }
    await next();
  };
}

/**
 * Simple request/response logging middleware.
 */
function loggingMiddleware(logger = console) {
  return async function loggingMiddlewareHandler(req, res, next) {
    const start = Date.now();
    const { method, url } = req;
    const parsed = parse(url);
    logger.info(`--> ${method} ${parsed.pathname}`);

    await next();

    const duration = Date.now() - start;
    logger.info(`<-- ${method} ${parsed.pathname} ${res.statusCode} ${duration}ms`);
  };
}

/**
 * Compose an array of middlewares into a single request handler.
 * Middlewares must be async functions (req, res, next) => Promise<void>.
 * The final handler is optional; if not provided, a default 404 is sent.
 */
function composeMiddleware(middlewares, finalHandler) {
  return async function composedHandler(req, res) {
    let index = -1;

    const dispatch = async (i) => {
      if (i <= index) {
        throw new Error('next() called multiple times');
      }
      index = i;
      const middleware = middlewares[i];
      if (middleware) {
        await middleware(req, res, () => dispatch(i + 1));
      } else if (finalHandler) {
        await finalHandler(req, res);
      } else {
        res.statusCode = 404;
        res.setHeader('Content-Type', 'text/plain');
        res.end('Not Found');
      }
    };

    try {
      await dispatch(0);
    } catch (err) {
      if (!res.headersSent) {
        res.statusCode = 500;
        res.setHeader('Content-Type', 'application/json');
        res.end(JSON.stringify({ error: 'Internal Server Error', message: err.message }));
      }
    }
  };
}

module.exports = {
  jsonBodyParser,
  urlencodedBodyParser,
  corsMiddleware,
  loggingMiddleware,
  composeMiddleware,
};
