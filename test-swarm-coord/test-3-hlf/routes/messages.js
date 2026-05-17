'use strict';

const { Router } = require('express');

function createMessageRoutes(messageService, authMiddleware) {
  const router = Router();

  // POST / - create message (auth required)
  router.post('/', authMiddleware, async (req, res, next) => {
    try {
      const data = {
        ...req.body,
        user_id: req.user.id,
      };
      const message = await messageService.create(data);
      res.status(201).json(message);
    } catch (err) {
      next(err);
    }
  });

  // GET /:id - get message (auth required)
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

  // PUT /:id - update message (auth required)
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

  // DELETE /:id - soft delete message (auth required)
  router.delete('/:id', authMiddleware, async (req, res, next) => {
    try {
      const removed = await messageService.remove(req.params.id);
      if (!removed) {
        return res.status(404).json({ error: 'Message not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  // GET /channel/:channelId - list messages in channel (auth required)
  router.get('/channel/:channelId', authMiddleware, async (req, res, next) => {
    try {
      const { limit, offset } = req.query;
      const messages = await messageService.listByChannel(req.params.channelId, {
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(messages);
    } catch (err) {
      next(err);
    }
  });

  // GET /:id/thread - list thread replies (auth required)
  router.get('/:id/thread', authMiddleware, async (req, res, next) => {
    try {
      const messages = await messageService.listThread(req.params.id);
      res.json(messages);
    } catch (err) {
      next(err);
    }
  });

  // POST /:id/reactions - add reaction (auth required)
  router.post('/:id/reactions', authMiddleware, async (req, res, next) => {
    try {
      const { emoji } = req.body;
      const reaction = await messageService.addReaction({
        message_id: req.params.id,
        user_id: req.user.id,
        emoji,
      });
      res.status(201).json(reaction);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /:id/reactions - remove reaction (auth required)
  router.delete('/:id/reactions', authMiddleware, async (req, res, next) => {
    try {
      const { emoji } = req.body;
      const removed = await messageService.removeReaction({
        message_id: req.params.id,
        user_id: req.user.id,
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

  // GET /:id/reactions - list reactions for a message (auth required)
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
