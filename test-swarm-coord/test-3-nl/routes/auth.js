const express = require('express');

function createAuthRoutes(authService) {
  const router = express.Router();

  router.post('/register', async (req, res, next) => {
    try {
      const result = await authService.register(req.body);
      res.status(201).json(result);
    } catch (err) {
      next(err);
    }
  });

  router.post('/login', async (req, res, next) => {
    try {
      const result = await authService.login(req.body);
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  });

  router.post('/logout', async (req, res, next) => {
    try {
      const result = authService.logout({ refreshToken: req.body.refreshToken });
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  });

  router.post('/refresh', async (req, res, next) => {
    try {
      const result = await authService.refresh({ refreshToken: req.body.refreshToken });
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  });

  router.get('/me', authService.authenticate, async (req, res, next) => {
    try {
      res.status(200).json({ user: req.user });
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createAuthRoutes };
