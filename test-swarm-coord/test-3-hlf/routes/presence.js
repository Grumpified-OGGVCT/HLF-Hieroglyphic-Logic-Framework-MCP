'use strict';

const express = require('express');

const VALID_STATUSES = ['online', 'away', 'offline', 'dnd'];

function createPresenceRoutes(presenceService, authMiddleware) {
  const router = express.Router();

  router.use(authMiddleware);

  router.put('/status', async (req, res) => {
    try {
      const { status } = req.body;
      const userId = req.user?.id;

      if (!userId) {
        return res.status(401).json({ error: 'Unauthorized' });
      }
      if (!status || typeof status !== 'string') {
        return res.status(400).json({ error: 'Status is required' });
      }
      if (!VALID_STATUSES.includes(status)) {
        return res.status(400).json({
          error: `Invalid status. Must be one of: ${VALID_STATUSES.join(', ')}`,
        });
      }

      const user = await presenceService.updateStatus(userId, status);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }

      return res.status(200).json(user);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/status/:userId', async (req, res) => {
    try {
      const { userId } = req.params;
      const status = await presenceService.getStatus(userId);

      if (!status) {
        return res.status(404).json({ error: 'User not found' });
      }

      return res.status(200).json(status);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/online/:workspaceId', async (req, res) => {
    try {
      const { workspaceId } = req.params;
      const users = await presenceService.getOnlineUsers(workspaceId);
      return res.status(200).json(users);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  return router;
}

module.exports = { createPresenceRoutes };
