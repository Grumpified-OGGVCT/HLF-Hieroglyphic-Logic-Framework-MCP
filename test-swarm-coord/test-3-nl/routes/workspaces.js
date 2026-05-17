const express = require('express');

function createWorkspaceRoutes(workspaceService, authMiddleware) {
  const router = express.Router();

  router.post('/', authMiddleware, async (req, res, next) => {
    try {
      const { name, description, is_public } = req.body;
      const owner_id = req.user?.id;
      if (!name) return res.status(400).json({ error: 'name is required' });
      if (!owner_id) return res.status(401).json({ error: 'Unauthorized' });
      const workspace = await workspaceService.create({
        name,
        description,
        owner_id,
        is_public,
      });
      res.status(201).json(workspace);
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id', authMiddleware, async (req, res, next) => {
    try {
      const workspace = await workspaceService.findById(req.params.id);
      if (!workspace) return res.status(404).json({ error: 'Workspace not found' });
      res.json(workspace);
    } catch (err) {
      next(err);
    }
  });

  router.get('/slug/:slug', async (req, res, next) => {
    try {
      const workspace = await workspaceService.findBySlug(req.params.slug);
      if (!workspace) return res.status(404).json({ error: 'Workspace not found' });
      res.json(workspace);
    } catch (err) {
      next(err);
    }
  });

  router.put('/:id', authMiddleware, async (req, res, next) => {
    try {
      const workspace = await workspaceService.update(req.params.id, req.body);
      if (!workspace) return res.status(404).json({ error: 'Workspace not found' });
      res.json(workspace);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id', authMiddleware, async (req, res, next) => {
    try {
      const deleted = await workspaceService.remove(req.params.id);
      if (!deleted) return res.status(404).json({ error: 'Workspace not found' });
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.get('/', async (req, res, next) => {
    try {
      const { limit, offset } = req.query;
      const workspaces = await workspaceService.list({
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      res.json(workspaces);
    } catch (err) {
      next(err);
    }
  });

  router.post('/:id/members', authMiddleware, async (req, res, next) => {
    try {
      const { user_id, role } = req.body;
      if (!user_id) return res.status(400).json({ error: 'user_id is required' });
      const member = await workspaceService.addMember(req.params.id, user_id, role);
      res.status(201).json(member);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id/members/:userId', authMiddleware, async (req, res, next) => {
    try {
      const removed = await workspaceService.removeMember(req.params.id, req.params.userId);
      if (!removed) return res.status(404).json({ error: 'Member not found' });
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.put('/:id/members/:userId/role', authMiddleware, async (req, res, next) => {
    try {
      const { role } = req.body;
      if (!role) return res.status(400).json({ error: 'role is required' });
      const member = await workspaceService.updateMemberRole(req.params.id, req.params.userId, role);
      if (!member) return res.status(404).json({ error: 'Member not found' });
      res.json(member);
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id/members', authMiddleware, async (req, res, next) => {
    try {
      const members = await workspaceService.getMembers(req.params.id);
      res.json(members);
    } catch (err) {
      next(err);
    }
  });

  router.get('/user/:userId/workspaces', authMiddleware, async (req, res, next) => {
    try {
      const workspaces = await workspaceService.getMemberWorkspaces(req.params.userId);
      res.json(workspaces);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createWorkspaceRoutes };
