'use strict';

function createAuthMiddleware(authService) {
  if (!authService || typeof authService.authenticate !== 'function') {
    throw new Error('authService with authenticate method is required');
  }

  return {
    authenticate: authService.authenticate,
    optionalAuth: authService.optionalAuth,
  };
}

module.exports = { createAuthMiddleware };
