const bcrypt = require("bcryptjs");
const jwt = require("jsonwebtoken");

const JWT_SECRET = process.env.JWT_SECRET || "dev-secret-change-me";
const JWT_EXPIRES_IN = process.env.JWT_EXPIRES_IN || "15m";
const REFRESH_EXPIRES_IN = process.env.REFRESH_EXPIRES_IN || "7d";

function generateTokens(user) {
  const payload = { id: user.id, email: user.email };
  const token = jwt.sign(payload, JWT_SECRET, { expiresIn: JWT_EXPIRES_IN });
  const refreshToken = jwt.sign(
    { ...payload, type: "refresh" },
    JWT_SECRET,
    { expiresIn: REFRESH_EXPIRES_IN }
  );
  return { token, refreshToken };
}

module.exports = function authFactory(models) {
  async function register(req, res, next) {
    try {
      const { email, password, display_name } = req.body;
      if (!email || !password || !display_name) {
        return res.status(400).json({ error: "Email, password and display_name are required" });
      }

      const existing = await models.User.findByEmail(email);
      if (existing) {
        return res.status(409).json({ error: "Email already registered" });
      }

      const password_hash = await bcrypt.hash(password, 10);
      const user = await models.User.create({ email, password_hash, display_name });
      const { token, refreshToken } = generateTokens(user);
      res.status(201).json({ token, refreshToken, user });
    } catch (err) {
      next(err);
    }
  }

  async function login(req, res, next) {
    try {
      const { email, password } = req.body;
      if (!email || !password) {
        return res.status(400).json({ error: "Email and password are required" });
      }

      const user = await models.User.findByEmail(email);
      if (!user || !user.password_hash) {
        return res.status(401).json({ error: "Invalid credentials" });
      }

      const valid = await bcrypt.compare(password, user.password_hash);
      if (!valid) {
        return res.status(401).json({ error: "Invalid credentials" });
      }

      const { token, refreshToken } = generateTokens(user);
      res.status(200).json({ token, refreshToken, user });
    } catch (err) {
      next(err);
    }
  }

  async function authenticate(req, res, next) {
    try {
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith("Bearer ")) {
        return res.status(401).json({ error: "Unauthorized" });
      }

      const token = authHeader.slice(7);
      const decoded = jwt.verify(token, JWT_SECRET);
      const user = await models.User.findById(decoded.id);
      if (!user) {
        return res.status(401).json({ error: "Unauthorized" });
      }

      req.user = user;
      next();
    } catch (err) {
      if (err.name === "JsonWebTokenError" || err.name === "TokenExpiredError") {
        return res.status(401).json({ error: "Unauthorized" });
      }
      next(err);
    }
  }

  async function refresh(req, res, next) {
    try {
      const { refreshToken } = req.body;
      if (!refreshToken) {
        return res.status(400).json({ error: "Refresh token required" });
      }

      const decoded = jwt.verify(refreshToken, JWT_SECRET);
      if (decoded.type !== "refresh") {
        return res.status(401).json({ error: "Invalid token type" });
      }

      const user = await models.User.findById(decoded.id);
      if (!user) {
        return res.status(401).json({ error: "Unauthorized" });
      }

      const tokens = generateTokens(user);
      res.status(200).json(tokens);
    } catch (err) {
      if (err.name === "JsonWebTokenError" || err.name === "TokenExpiredError") {
        return res.status(401).json({ error: "Unauthorized" });
      }
      next(err);
    }
  }

  async function optionalAuth(req, res, next) {
    try {
      const authHeader = req.headers.authorization;
      if (!authHeader || !authHeader.startsWith("Bearer ")) {
        return next();
      }

      const token = authHeader.slice(7);
      const decoded = jwt.verify(token, JWT_SECRET);
      const user = await models.User.findById(decoded.id);
      if (user) {
        req.user = user;
      }
      next();
    } catch (err) {
      next();
    }
  }

  return {
    register,
    login,
    authenticate,
    refresh,
    optionalAuth,
    export_shape: { register, login, authenticate, refresh, optionalAuth },
  };
};
