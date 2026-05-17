'use strict';

const { Router } = require('express');

function createChannelRoutes(channelService, authMiddleware) {
  const router = Router();

  // POST / - create channel (auth required)
  router.post('/', authMiddleware, async (req, res, next) => {
    try {
      const data = {
        ...req.body,
        created_by: req.user.id,
      };
      const channel = await channelService.create(data);
      res.status(201).json(channel);
    } catch (err) {
      next(err);
    }
  });

  // GET / - list public channels (no auth)
  router.get('/', async (req, res, next) => {
    try {
      const { limit, offset } = req.query;
      const channels = await channelService.list({
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(channels);
    } catch (err) {
      next(err);
    }
  });

  // GET /:id - get channel (auth required)
  router.get('/:id', authMiddleware, async (req, res, next) => {
    try {
      const channel = await channelService.findById(req.params.id);
      if (!channel) {
        return res.status(404).json({ error: 'Channel not found' });
      }
      res.json(channel);
    } catch (err) {
      next(err);
    }
  });

  // PUT /:id - update channel (auth required)
  router.put('/:id', authMiddleware, async (req, res, next) => {
    try {
      const channel = await channelService.update(req.params.id, req.body);
      if (!channel) {
        return res.status(404).json({ error: 'Channel not found' });
      }
      res.json(channel);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /:id - delete channel (auth required)
  router.delete('/:id', authMiddleware, async (req, res, next) => {
    try {
      const removed = await channelService.remove(req.params.id);
      if (!removed) {
        return res.status(404).json({ error: 'Channel not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  // GET /workspace/:workspaceId - list channels in workspace (auth required)
  router.get('/workspace/:workspaceId', authMiddleware, async (req, res, next) => {
    try {
      const { limit, offset } = req.query;
      const channels = await channelService.listByWorkspace(req.params.workspaceId, {
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(channels);
    } catch (err) {
      next(err);
    }
  });

  // POST /:id/members - add member (auth required)
  router.post('/:id/members', authMiddleware, async (req, res, next) => {
    try {
      const { userId } = req.body;
      const member = await channelService.addMember(req.params.id, userId);
      res.status(201).json(member);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /:id/members/:userId - remove member (auth required)
  router.delete('/:id/members/:userId', authMiddleware, async (req, res, next) => {
    try {
      const removed = await channelService.removeMember(req.params.id, req.params.userId);
      if (!removed) {
        return res.status(404).json({ error: 'Member not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  // GET /:id/members - list members (auth required)
  router.get('/:id/members', authMiddleware, async (req, res, next) => {
    try {
      const members = await channelService.getMembers(req.params.id);
      res.json(members);
    } catch (err) {
      next(err);
    }
  });

  // POST /direct - get or create DM channel (auth required)
  router.post('/direct', authMiddleware, async (req, res, next) => {
    try {
      const { workspaceId, userId } = req.body;
      const channel = await channelService.getDirectChannel(
        workspaceId,
        req.user.id,
        userId
      );
      res.status(201).json(channel);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createChannelRoutes };
