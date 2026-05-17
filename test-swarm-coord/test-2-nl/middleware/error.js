function getStatusCode(err) {
  // Explicit status on error object
  if (err.status >= 400) return err.status;
  if (err.statusCode >= 400) return err.statusCode;

  // Named error types
  if (err.name === 'ValidationError') return 400;
  if (err.name === 'UnauthorizedError') return 401;
  if (err.name === 'JsonWebTokenError') return 401;
  if (err.name === 'TokenExpiredError') return 401;
  if (err.name === 'SyntaxError') return 400;
  if (err.name === 'CastError') return 400;
  if (err.name === 'NotFoundError') return 404;

  // Message-based detection
  if (err.message) {
    const msg = err.message.toLowerCase();
    if (msg.includes('not found')) return 404;
    if (msg.includes('unique') || msg.includes('duplicate')) return 409;
  }

  // Default
  return 500;
}

function errorHandler(err, req, res, next) {
  const statusCode = getStatusCode(err);

  console.error(`[ERROR] ${err.message}`);
  console.error(err.stack);

  const response = {
    error: err.message,
    status: statusCode,
    timestamp: new Date().toISOString()
  };

  if (process.env.NODE_ENV === 'development') {
    response.stack = err.stack;
  }

  res.status(statusCode).json(response);
}

function notFoundHandler(req, res, next) {
  const error = new Error(`Route ${req.method} ${req.path} not found`);
  error.status = 404;
  next(error);
}

function setupErrorHandlers() {
  process.on('unhandledRejection', (reason, promise) => {
    console.error('Unhandled Rejection:', reason);
  });

  process.on('uncaughtException', (err) => {
    console.error('Uncaught Exception:', err);
    process.exit(1);
  });
}

module.exports = () => ({
  errorHandler,
  notFoundHandler,
  setupErrorHandlers
});
