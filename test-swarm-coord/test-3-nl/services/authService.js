let jwt;
try {
  jwt = require('jsonwebtoken');
} catch {
  jwt = null;
}

function createAuthService({ userService, jwtSecret, refreshSecret }) {
  const refreshTokens = new Map();

  const ACCESS_EXPIRY = '15m';
  const REFRESH_EXPIRY_MS = 7 * 24 * 60 * 60 * 1000; // 7 days

  function signToken(payload, secret, options = {}) {
    if (jwt) return jwt.sign(payload, secret, options);
    const header = Buffer.from(JSON.stringify({ alg: 'none', typ: 'JWT' })).toString('base64url');
    const body = Buffer.from(JSON.stringify({ ...payload, iat: Date.now() })).toString('base64url');
    return `${header}.${body}.mocksignature`;
  }

  function verifyTokenRaw(token, secret) {
    if (jwt) return jwt.verify(token, secret);
    const parts = token.split('.');
    if (parts.length !== 3) throw new Error('Invalid token');
    return JSON.parse(Buffer.from(parts[1], 'base64url').toString());
  }

  function decodeToken(token) {
    if (jwt) return jwt.decode(token);
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    return JSON.parse(Buffer.from(parts[1], 'base64url').toString());
  }

  function generateAccessToken(user) {
    return signToken(
      { sub: String(user.id), username: user.username, email: user.email },
      jwtSecret,
      { expiresIn: ACCESS_EXPIRY }
    );
  }

  function generateRefreshToken(user) {
    return signToken({ sub: String(user.id), type: 'refresh' }, refreshSecret, { expiresIn: '7d' });
  }

  async function register({ username, email, password, display_name, avatar_url }) {
    const existingEmail = await userService.findByEmail(email);
    if (existingEmail) {
      const err = new Error('Email already in use');
      err.statusCode = 409;
      throw err;
    }
    const existingUsername = await userService.findByUsername(username);
    if (existingUsername) {
      const err = new Error('Username already taken');
      err.statusCode = 409;
      throw err;
    }
    const user = await userService.create({ username, email, password, display_name, avatar_url });
    const accessToken = generateAccessToken(user);
    const refreshToken = generateRefreshToken(user);
    refreshTokens.set(refreshToken, { userId: user.id, expiresAt: Date.now() + REFRESH_EXPIRY_MS });
    return { user, accessToken, refreshToken };
  }

  async function login({ email, password }) {
    const user = await userService.findByEmailWithPassword(email);
    if (!user) {
      const err = new Error('Invalid credentials');
      err.statusCode = 401;
      throw err;
    }
    const valid = await userService.verifyPassword(password, user.password_hash);
    if (!valid) {
      const err = new Error('Invalid credentials');
      err.statusCode = 401;
      throw err;
    }
    const safeUser = { id: user.id, username: user.username, email: user.email, display_name: user.display_name, avatar_url: user.avatar_url, status: user.status, created_at: user.created_at, updated_at: user.updated_at };
    const accessToken = generateAccessToken(safeUser);
    const refreshToken = generateRefreshToken(safeUser);
    refreshTokens.set(refreshToken, { userId: safeUser.id, expiresAt: Date.now() + REFRESH_EXPIRY_MS });
    return { user: safeUser, accessToken, refreshToken };
  }

  function logout({ refreshToken }) {
    if (refreshToken) {
      refreshTokens.delete(refreshToken);
    }
    return { success: true };
  }

  async function refresh({ refreshToken }) {
    if (!refreshToken) {
      const err = new Error('Refresh token required');
      err.statusCode = 400;
      throw err;
    }
    const stored = refreshTokens.get(refreshToken);
    if (!stored) {
      const err = new Error('Invalid refresh token');
      err.statusCode = 401;
      throw err;
    }
    if (Date.now() > stored.expiresAt) {
      refreshTokens.delete(refreshToken);
      const err = new Error('Refresh token expired');
      err.statusCode = 401;
      throw err;
    }
    let payload;
    try {
      payload = verifyTokenRaw(refreshToken, refreshSecret);
    } catch {
      refreshTokens.delete(refreshToken);
      const err = new Error('Invalid refresh token');
      err.statusCode = 401;
      throw err;
    }
    const user = await userService.findById(Number(payload.sub));
    if (!user) {
      refreshTokens.delete(refreshToken);
      const err = new Error('User not found');
      err.statusCode = 401;
      throw err;
    }
    const accessToken = generateAccessToken(user);
    return { accessToken };
  }

  function verifyToken(token) {
    try {
      return verifyTokenRaw(token, jwtSecret);
    } catch (err) {
      err.statusCode = 401;
      throw err;
    }
  }

  function authenticate(req, res, next) {
    const authHeader = req.headers.authorization || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
    if (!token) {
      return res.status(401).json({ error: 'Unauthorized' });
    }
    try {
      const payload = verifyTokenRaw(token, jwtSecret);
      req.user = payload;
      next();
    } catch {
      return res.status(401).json({ error: 'Unauthorized' });
    }
  }

  function optionalAuth(req, res, next) {
    const authHeader = req.headers.authorization || '';
    const token = authHeader.startsWith('Bearer ') ? authHeader.slice(7) : null;
    if (token) {
      try {
        const payload = verifyTokenRaw(token, jwtSecret);
        req.user = payload;
      } catch {
        // leave req.user undefined
      }
    }
    next();
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
