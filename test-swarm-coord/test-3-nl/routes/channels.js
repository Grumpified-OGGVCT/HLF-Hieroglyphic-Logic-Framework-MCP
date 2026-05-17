const express = require('express');

function createChannelRoutes(channelService, authMiddleware) {
  const router = express.Router();

  router.post('/', authMiddleware, async (req, res, next) => {
    try {
      const { workspace_id, name, type } = req.body;
      const created_by = req.user?.sub || req.user?.id;
      if (!workspace_id) {
        return res.status(400).json({ error: 'workspace_id is required' });
      }
      if (!name) {
        return res.status(400).json({ error: 'name is required' });
      }
      if (!created_by) {
        return res.status(401).json({ error: 'Unauthorized' });
      }
      const channel = await channelService.create({
        workspace_id,
        name,
        type,
        created_by,
      });
      res.status(201).json(channel);
    } catch (err) {
      next(err);
    }
  });

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

  router.delete('/:id', authMiddleware, async (req, res, next) => {
    try {
      const deleted = await channelService.remove(req.params.id);
      if (!deleted) {
        return res.status(404).json({ error: 'Channel not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.get('/', async (req, res, next) => {
    try {
      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
      const user_id = req.user?.sub || req.user?.id;
      const channels = await channelService.list({ limit, offset, user_id });
      res.json(channels);
    } catch (err) {
      next(err);
    }
  });

  router.get('/workspace/:workspaceId', authMiddleware, async (req, res, next) => {
    try {
      const workspace_id = req.params.workspaceId;
      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
      const user_id = req.user?.sub || req.user?.id;
      const channels = await channelService.listByWorkspace(workspace_id, {
        limit,
        offset,
        user_id,
      });
      res.json(channels);
    } catch (err) {
      next(err);
    }
  });

  router.post('/:id/members', authMiddleware, async (req, res, next) => {
    try {
      const { user_id: memberUserId } = req.body;
      if (!memberUserId) {
        return res.status(400).json({ error: 'user_id is required' });
      }
      const member = await channelService.addMember(req.params.id, memberUserId);
      res.status(201).json(member);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id/members/:userId', authMiddleware, async (req, res, next) => {
    try {
      const removed = await channelService.removeMember(
        req.params.id,
        req.params.userId
      );
      if (!removed) {
        return res.status(404).json({ error: 'Member not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id/members', authMiddleware, async (req, res, next) => {
    try {
      const members = await channelService.getMembers(req.params.id);
      res.json(members);
    } catch (err) {
      next(err);
    }
  });

  router.post('/direct', authMiddleware, async (req, res, next) => {
    try {
      const { workspace_id, user_id: otherUserId } = req.body;
      const currentUserId = req.user?.sub || req.user?.id;
      if (!workspace_id) {
        return res.status(400).json({ error: 'workspace_id is required' });
      }
      if (!otherUserId) {
        return res.status(400).json({ error: 'user_id is required' });
      }
      if (!currentUserId) {
        return res.status(401).json({ error: 'Unauthorized' });
      }
      const channel = await channelService.getDirectChannel(
        workspace_id,
        currentUserId,
        otherUserId
      );
      res.status(200).json(channel);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createChannelRoutes };
