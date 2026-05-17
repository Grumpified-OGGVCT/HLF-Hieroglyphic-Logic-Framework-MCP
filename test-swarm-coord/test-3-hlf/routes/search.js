'use strict';

const { Router } = require('express');

function createSearchRoutes(searchService, authMiddleware) {
  const router = Router();

  // GET /messages?q=&channelId=&workspaceId=&userId=&limit=&offset=
  router.get('/messages', authMiddleware, async (req, res, next) => {
    try {
      const { q, channelId, workspaceId, userId, limit, offset } = req.query;
      const result = await searchService.searchMessages(q, {
        channelId,
        workspaceId,
        userId,
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  // GET /channels?q=&workspaceId=&limit=&offset=
  router.get('/channels', authMiddleware, async (req, res, next) => {
    try {
      const { q, workspaceId, limit, offset } = req.query;
      const result = await searchService.searchChannels(q, {
        workspaceId,
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  // GET /users?q=&limit=&offset=
  router.get('/users', authMiddleware, async (req, res, next) => {
    try {
      const { q, limit, offset } = req.query;
      const result = await searchService.searchUsers(q, {
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createSearchRoutes };
