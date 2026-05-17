'use strict';

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
      const { email, password } = req.body;
      if (!email || !password) {
        return res.status(400).json({ error: 'Bad Request', message: 'Email and password are required' });
      }
      const result = await authService.login({ email, password });
      res.status(200).json(result);
    } catch (err) {
      next(err);
    }
  });

  router.post('/logout', async (req, res, next) => {
    try {
      const { refreshToken } = req.body;
      await authService.logout(refreshToken);
      res.status(200).json({ success: true });
    } catch (err) {
      next(err);
    }
  });

  router.post('/refresh', async (req, res, next) => {
    try {
      const { refreshToken } = req.body;
      const result = await authService.refresh(refreshToken);
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
