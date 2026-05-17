const bcrypt = require('bcryptjs');
const jwt = require('jsonwebtoken');

const JWT_SECRET = process.env.JWT_SECRET || 'dev-secret-change-in-production';
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || '24h';
const REFRESH_EXPIRES_IN = process.env.REFRESH_EXPIRES_IN || '7d';

module.exports = (models) => {
  const User = models.User;

  function generateTokens(user) {
    const token = jwt.sign(
      { userId: user.id, username: user.username, email: user.email },
      JWT_SECRET,
      { expiresIn: JWT_EXPIRES_IN }
    );

    const refreshToken = jwt.sign(
      { userId: user.id, type: 'refresh' },
      JWT_SECRET,
      { expiresIn: REFRESH_EXPIRES_IN }
    );

    return { token, refreshToken };
  }

  async function register(req, res, next) {
    try {
      const { username, email, password } = req.body;

      const existingUser = await User.findByEmail(email);
      if (existingUser) {
        const error = new Error('User already exists');
        error.status = 409;
        return next(error);
      }

      const passwordHash = await bcrypt.hash(password, 10);
      const user = await User.create({ username, email, password_hash: passwordHash });

      const { token, refreshToken } = generateTokens(user);

      return res.status(201).json({
        token,
        refreshToken,
        user: { id: user.id, username: user.username, email: user.email }
      });
    } catch (error) {
      next(error);
    }
  }

  async function login(req, res, next) {
    try {
      const { email, password } = req.body;

      const user = await User.findByEmail(email);
      if (!user) {
        const error = new Error('Invalid credentials');
        error.status = 401;
        return next(error);
      }

      const isValid = await bcrypt.compare(password, user.password_hash);
      if (!isValid) {
        const error = new Error('Invalid credentials');
        error.status = 401;
        return next(error);
      }

      const { token, refreshToken } = generateTokens(user);

      return res.status(200).json({
        token,
        refreshToken,
        user: { id: user.id, username: user.username, email: user.email }
      });
    } catch (error) {
      next(error);
    }
  }

  function authenticate(req, res, next) {
    try {
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith('Bearer ')) {
        return res.status(401).json({ error: 'Unauthorized', status: 401 });
      }

      const token = authHeader.split(' ')[1];
      const decoded = jwt.verify(token, JWT_SECRET);

      req.user = {
        userId: decoded.userId,
        username: decoded.username,
        email: decoded.email
      };

      next();
    } catch (error) {
      return res.status(401).json({ error: 'Unauthorized', status: 401 });
    }
  }

  async function refresh(req, res, next) {
    try {
      const { refreshToken } = req.body;
      if (!refreshToken) {
        const error = new Error('Refresh token required');
        error.status = 400;
        return next(error);
      }

      const decoded = jwt.verify(refreshToken, JWT_SECRET);
      if (decoded.type !== 'refresh') {
        const error = new Error('Invalid token type');
        error.status = 401;
        return next(error);
      }

      const user = await User.findById(decoded.userId);
      if (!user) {
        const error = new Error('User not found');
        error.status = 401;
        return next(error);
      }

      const tokens = generateTokens(user);

      return res.status(200).json({
        token: tokens.token,
        refreshToken: tokens.refreshToken
      });
    } catch (error) {
      next(error);
    }
  }

  function optionalAuth(req, res, next) {
    try {
      const authHeader = req.headers.authorization;
      if (authHeader && authHeader.startsWith('Bearer ')) {
        const token = authHeader.split(' ')[1];
        const decoded = jwt.verify(token, JWT_SECRET);

        req.user = {
          userId: decoded.userId,
          username: decoded.username,
          email: decoded.email
        };
      }

      next();
    } catch (error) {
      next();
    }
  }

  return {
    register,
    login,
    authenticate,
    refresh,
    optionalAuth
  };
};
