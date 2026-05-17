const express = require('express');

function createSearchRoutes(searchService, authMiddleware) {
  const router = express.Router();

  router.get('/messages', authMiddleware, async (req, res, next) => {
    try {
      const q = req.query.q;
      if (!q || q.trim() === '') {
        return res.status(400).json({ error: 'Query parameter q is required' });
      }

      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
      const channelId = req.query.channelId || null;
      const workspaceId = req.query.workspaceId || null;
      const userId = req.query.userId || null;

      const result = await searchService.searchMessages(q, {
        channelId,
        workspaceId,
        userId,
        limit,
        offset,
      });
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  router.get('/channels', authMiddleware, async (req, res, next) => {
    try {
      const q = req.query.q;
      if (!q || q.trim() === '') {
        return res.status(400).json({ error: 'Query parameter q is required' });
      }

      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
      const workspaceId = req.query.workspaceId || null;

      const result = await searchService.searchChannels(q, {
        workspaceId,
        limit,
        offset,
      });
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  router.get('/users', authMiddleware, async (req, res, next) => {
    try {
      const q = req.query.q;
      if (!q || q.trim() === '') {
        return res.status(400).json({ error: 'Query parameter q is required' });
      }

      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);

      const result = await searchService.searchUsers(q, {
        limit,
        offset,
      });
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createSearchRoutes };
