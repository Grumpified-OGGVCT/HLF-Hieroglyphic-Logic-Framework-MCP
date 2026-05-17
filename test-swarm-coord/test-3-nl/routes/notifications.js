const express = require('express');

function createNotificationRoutes(notificationService, authMiddleware) {
  const router = express.Router();

  router.get('/', authMiddleware, async (req, res, next) => {
    try {
      const limit = parseInt(req.query.limit, 10) || 20;
      const offset = parseInt(req.query.offset, 10) || 0;
      const notifications = await notificationService.listForUser(req.user.id, {
        limit,
        offset,
      });
      res.json(notifications);
    } catch (err) {
      next(err);
    }
  });

  router.get('/unread-count', authMiddleware, async (req, res, next) => {
    try {
      const count = await notificationService.getUnreadCount(req.user.id);
      res.json({ count });
    } catch (err) {
      next(err);
    }
  });

  router.put('/:id/read', authMiddleware, async (req, res, next) => {
    try {
      const notification = await notificationService.markAsRead(
        req.params.id,
        req.user.id
      );
      if (!notification) {
        return res.status(404).json({ error: 'Notification not found or already read' });
      }
      res.json(notification);
    } catch (err) {
      next(err);
    }
  });

  router.put('/read-all', authMiddleware, async (req, res, next) => {
    try {
      const count = await notificationService.markAllAsRead(req.user.id);
      res.json({ count });
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createNotificationRoutes };
