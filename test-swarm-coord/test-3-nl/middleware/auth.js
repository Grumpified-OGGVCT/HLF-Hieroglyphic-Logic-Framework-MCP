function createAuthMiddleware(authService) {
  return {
    authenticate: authService.authenticate,
    optionalAuth: authService.optionalAuth,
  };
}

module.exports = { createAuthMiddleware };
