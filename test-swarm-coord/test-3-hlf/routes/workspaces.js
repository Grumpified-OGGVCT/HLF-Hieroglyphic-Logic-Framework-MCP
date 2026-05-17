'use strict';

const express = require('express');

function createWorkspaceRoutes(workspaceService, authMiddleware) {
  const router = express.Router();

  router.post('/', authMiddleware, async (req, res) => {
    try {
      const { name } = req.body;
      if (!name || typeof name !== 'string' || name.trim().length === 0) {
        return res.status(400).json({ error: 'Name is required' });
      }

      const workspace = await workspaceService.create({
        name: name.trim(),
        owner_id: req.user.id,
      });

      return res.status(201).json(workspace);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/:id', authMiddleware, async (req, res) => {
    try {
      const workspace = await workspaceService.findById(req.params.id);
      if (!workspace) {
        return res.status(404).json({ error: 'Workspace not found' });
      }
      return res.status(200).json(workspace);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/slug/:slug', async (req, res) => {
    try {
      const workspace = await workspaceService.findBySlug(req.params.slug);
      if (!workspace) {
        return res.status(404).json({ error: 'Workspace not found' });
      }
      return res.status(200).json(workspace);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.put('/:id', authMiddleware, async (req, res) => {
    try {
      const { name } = req.body;
      const payload = {};
      if (name !== undefined) {
        if (typeof name !== 'string' || name.trim().length === 0) {
          return res.status(400).json({ error: 'Name must be a non-empty string' });
        }
        payload.name = name.trim();
      }

      const workspace = await workspaceService.update(req.params.id, payload);
      if (!workspace) {
        return res.status(404).json({ error: 'Workspace not found' });
      }
      return res.status(200).json(workspace);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.delete('/:id', authMiddleware, async (req, res) => {
    try {
      const deleted = await workspaceService.remove(req.params.id);
      if (!deleted) {
        return res.status(404).json({ error: 'Workspace not found' });
      }
      return res.status(204).send();
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/', async (req, res) => {
    try {
      const { limit, offset } = req.query;
      const workspaces = await workspaceService.list({
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      return res.status(200).json(workspaces);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.post('/:id/members', authMiddleware, async (req, res) => {
    try {
      const { userId, role } = req.body;
      if (!userId) {
        return res.status(400).json({ error: 'userId is required' });
      }

      const member = await workspaceService.addMember(req.params.id, userId, role);
      return res.status(201).json(member);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.delete('/:id/members/:userId', authMiddleware, async (req, res) => {
    try {
      const removed = await workspaceService.removeMember(req.params.id, req.params.userId);
      if (!removed) {
        return res.status(404).json({ error: 'Member not found' });
      }
      return res.status(204).send();
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.put('/:id/members/:userId/role', authMiddleware, async (req, res) => {
    try {
      const { role } = req.body;
      if (!role) {
        return res.status(400).json({ error: 'role is required' });
      }

      const member = await workspaceService.updateMemberRole(req.params.id, req.params.userId, role);
      if (!member) {
        return res.status(404).json({ error: 'Member not found' });
      }
      return res.status(200).json(member);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/:id/members', authMiddleware, async (req, res) => {
    try {
      const members = await workspaceService.getMembers(req.params.id);
      return res.status(200).json(members);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/user/:userId/workspaces', authMiddleware, async (req, res) => {
    try {
      const workspaces = await workspaceService.getMemberWorkspaces(req.params.userId);
      return res.status(200).json(workspaces);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  return router;
}

module.exports = { createWorkspaceRoutes };
