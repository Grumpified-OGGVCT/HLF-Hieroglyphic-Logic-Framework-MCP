const express = require('express');

function createPresenceRoutes(presenceService, authMiddleware) {
  const router = express.Router();

  router.put('/status', authMiddleware.authenticate, async (req, res, next) => {
    try {
      const { status } = req.body;
      if (!status) {
        return res.status(400).json({ error: 'Status is required' });
      }
      const userId = req.user.sub || req.user.id;
      const user = await presenceService.updateStatus(userId, status);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }
      res.json(user);
    } catch (err) {
      next(err);
    }
  });

  router.get('/status/:userId', authMiddleware.authenticate, async (req, res, next) => {
    try {
      const user = await presenceService.getStatus(req.params.userId);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }
      res.json(user);
    } catch (err) {
      next(err);
    }
  });

  router.get('/online/:workspaceId', authMiddleware.authenticate, async (req, res, next) => {
    try {
      const users = await presenceService.getOnlineUsers(req.params.workspaceId);
      res.json(users);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createPresenceRoutes };
