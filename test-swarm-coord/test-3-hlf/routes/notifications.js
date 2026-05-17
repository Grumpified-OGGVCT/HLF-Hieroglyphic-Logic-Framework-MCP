'use strict';

const { Router } = require('express');

function createNotificationRoutes(notificationService, authMiddleware) {
  const router = Router();

  router.get('/', authMiddleware, async (req, res, next) => {
    try {
      const userId = req.user.id;
      const limit = parseInt(req.query.limit, 10) || 20;
      const offset = parseInt(req.query.offset, 10) || 0;
      const notifications = await notificationService.listForUser(userId, { limit, offset });
      res.json({ notifications });
    } catch (err) {
      next(err);
    }
  });

  router.get('/unread-count', authMiddleware, async (req, res, next) => {
    try {
      const userId = req.user.id;
      const count = await notificationService.getUnreadCount(userId);
      res.json({ count });
    } catch (err) {
      next(err);
    }
  });

  router.put('/:id/read', authMiddleware, async (req, res, next) => {
    try {
      const notificationId = req.params.id;
      const notification = await notificationService.markAsRead(notificationId);
      if (!notification) {
        return res.status(404).json({ error: 'Notification not found or already read' });
      }
      res.json({ notification });
    } catch (err) {
      next(err);
    }
  });

  router.put('/read-all', authMiddleware, async (req, res, next) => {
    try {
      const userId = req.user.id;
      const count = await notificationService.markAllAsRead(userId);
      res.json({ count });
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createNotificationRoutes };
