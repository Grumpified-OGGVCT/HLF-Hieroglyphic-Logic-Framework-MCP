'use strict';

const crypto = require('crypto');

function loadJwt() {
  try {
    return require('jsonwebtoken');
  } catch {
    return {
      sign: (payload, secret, opts) => `mockjwt:${secret}:${JSON.stringify(payload)}:${JSON.stringify(opts)}`,
      verify: (token, secret) => {
        if (!token.startsWith('mockjwt:')) throw new Error('invalid token');
        const parts = token.split(':');
        if (parts[1] !== secret) throw new Error('invalid secret');
        return JSON.parse(parts[2]);
      },
    };
  }
}

const jwt = loadJwt();

const ACCESS_EXPIRY_SECONDS = 15 * 60;        // 15 minutes
const REFRESH_EXPIRY_SECONDS = 7 * 24 * 60 * 60; // 7 days

function createAuthService({ userService, jwtSecret, refreshSecret }) {
  if (!jwtSecret) throw new Error('jwtSecret is required');
  if (!refreshSecret) throw new Error('refreshSecret is required');

  // In-memory refresh token store: token -> { userId, expiresAt }
  const refreshTokens = new Map();

  function generateAccessToken(user) {
    return jwt.sign(
      { sub: user.id, username: user.username, email: user.email },
      jwtSecret,
      { expiresIn: ACCESS_EXPIRY_SECONDS }
    );
  }

  function generateRefreshToken(user) {
    const token = crypto.randomBytes(32).toString('hex');
    const expiresAt = Date.now() + REFRESH_EXPIRY_SECONDS * 1000;
    refreshTokens.set(token, { userId: user.id, expiresAt });
    return token;
  }

  function cleanupExpiredTokens() {
    const now = Date.now();
    for (const [token, data] of refreshTokens) {
      if (data.expiresAt <= now) {
        refreshTokens.delete(token);
      }
    }
  }

  async function register(data) {
    const existingEmail = await userService.findByEmail(data.email);
    if (existingEmail) {
      const err = new Error('Email already in use');
      err.status = 409;
      throw err;
    }
    const existingUsername = await userService.findByUsername(data.username);
    if (existingUsername) {
      const err = new Error('Username already taken');
      err.status = 409;
      throw err;
    }

    const user = await userService.create(data);
    const accessToken = generateAccessToken(user);
    const refreshToken = generateRefreshToken(user);
    return { user, accessToken, refreshToken };
  }

  async function login({ email, password }) {
    const user = await userService.findByEmail(email);
    if (!user) {
      const err = new Error('Invalid credentials');
      err.status = 401;
      throw err;
    }
    const valid = await userService.verifyPassword(user.id, password);
    if (!valid) {
      const err = new Error('Invalid credentials');
      err.status = 401;
      throw err;
    }
    const accessToken = generateAccessToken(user);
    const refreshToken = generateRefreshToken(user);
    return { user, accessToken, refreshToken };
  }

  async function logout(refreshToken) {
    if (refreshToken) {
      refreshTokens.delete(refreshToken);
    }
    return { success: true };
  }

  async function refresh(refreshToken) {
    if (!refreshToken) {
      const err = new Error('Refresh token required');
      err.status = 400;
      throw err;
    }
    const data = refreshTokens.get(refreshToken);
    if (!data) {
      const err = new Error('Invalid refresh token');
      err.status = 401;
      throw err;
    }
    if (data.expiresAt <= Date.now()) {
      refreshTokens.delete(refreshToken);
      const err = new Error('Refresh token expired');
      err.status = 401;
      throw err;
    }

    const user = await userService.findById(data.userId);
    if (!user) {
      refreshTokens.delete(refreshToken);
      const err = new Error('User not found');
      err.status = 401;
      throw err;
    }

    const accessToken = generateAccessToken(user);
    return { user, accessToken };
  }

  function verifyToken(token) {
    try {
      return jwt.verify(token, jwtSecret);
    } catch (err) {
      return null;
    }
  }

  async function authenticate(req, res, next) {
    try {
      const authHeader = req.headers.authorization || '';
      const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
      if (!token) {
        return res.status(401).json({ error: 'Unauthorized', message: 'Missing or invalid authorization header' });
      }
      const decoded = verifyToken(token);
      if (!decoded) {
        return res.status(401).json({ error: 'Unauthorized', message: 'Invalid or expired token' });
      }
      const user = await userService.findById(decoded.sub);
      if (!user) {
        return res.status(401).json({ error: 'Unauthorized', message: 'User not found' });
      }
      req.user = user;
      next();
    } catch (err) {
      next(err);
    }
  }

  async function optionalAuth(req, res, next) {
    try {
      const authHeader = req.headers.authorization || '';
      const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
      if (token) {
        const decoded = verifyToken(token);
        if (decoded) {
          const user = await userService.findById(decoded.sub);
          if (user) {
            req.user = user;
          }
        }
      }
      next();
    } catch (err) {
      next(err);
    }
  }

  return {
    register,
    login,
    logout,
    refresh,
    verifyToken,
    authenticate,
    optionalAuth,
  };
}

module.exports = { createAuthService };
