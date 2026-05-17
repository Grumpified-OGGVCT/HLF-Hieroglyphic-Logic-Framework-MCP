const express = require('express');

function createMessageRoutes(messageService, authMiddleware) {
  const router = express.Router();

  router.post('/', authMiddleware, async (req, res, next) => {
    try {
      const { channel_id, content, parent_id, type } = req.body;
      const user_id = req.user?.sub || req.user?.id;

      if (!channel_id) {
        return res.status(400).json({ error: 'channel_id is required' });
      }
      if (!user_id) {
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const message = await messageService.create({
        channel_id,
        user_id,
        content,
        parent_id,
        type,
      });
      res.status(201).json(message);
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id', authMiddleware, async (req, res, next) => {
    try {
      const message = await messageService.findById(req.params.id);
      if (!message) {
        return res.status(404).json({ error: 'Message not found' });
      }
      res.json(message);
    } catch (err) {
      next(err);
    }
  });

  router.put('/:id', authMiddleware, async (req, res, next) => {
    try {
      const message = await messageService.update(req.params.id, req.body);
      if (!message) {
        return res.status(404).json({ error: 'Message not found' });
      }
      res.json(message);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id', authMiddleware, async (req, res, next) => {
    try {
      const deleted = await messageService.remove(req.params.id);
      if (!deleted) {
        return res.status(404).json({ error: 'Message not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.get('/channel/:channelId', authMiddleware, async (req, res, next) => {
    try {
      const channel_id = req.params.channelId;
      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
      const messages = await messageService.listByChannel(channel_id, {
        limit,
        offset,
      });
      res.json(messages);
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id/thread', authMiddleware, async (req, res, next) => {
    try {
      const limit = Math.min(parseInt(req.query.limit, 10) || 50, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);
      const messages = await messageService.listThread(req.params.id, {
        limit,
        offset,
      });
      res.json(messages);
    } catch (err) {
      next(err);
    }
  });

  router.post('/:id/reactions', authMiddleware, async (req, res, next) => {
    try {
      const { emoji } = req.body;
      const user_id = req.user?.sub || req.user?.id;
      const message_id = req.params.id;

      if (!emoji) {
        return res.status(400).json({ error: 'emoji is required' });
      }
      if (!user_id) {
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const reaction = await messageService.addReaction({
        message_id,
        user_id,
        emoji,
      });
      res.status(201).json(reaction);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id/reactions', authMiddleware, async (req, res, next) => {
    try {
      const { emoji } = req.body;
      const user_id = req.user?.sub || req.user?.id;
      const message_id = req.params.id;

      if (!emoji) {
        return res.status(400).json({ error: 'emoji is required' });
      }
      if (!user_id) {
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const removed = await messageService.removeReaction({
        message_id,
        user_id,
        emoji,
      });
      if (!removed) {
        return res.status(404).json({ error: 'Reaction not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id/reactions', authMiddleware, async (req, res, next) => {
    try {
      const reactions = await messageService.getReactions(req.params.id);
      res.json(reactions);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createMessageRoutes };
