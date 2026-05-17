const express = require('express');

module.exports = (models, auth, validation) => {
  const router = express.Router();
  const { Project, Task } = models;
  const { authenticate, optionalAuth } = auth;
  const { validateProject, validateProjectUpdate } = validation;

  // GET /projects - list all projects with optional filters
  router.get('/', optionalAuth, async (req, res, next) => {
    try {
      const filters = {};
      if (req.query.name) filters.name = req.query.name;
      if (req.query.owner_id) filters.owner_id = req.query.owner_id;

      const projects = await Project.findAll(filters);
      return res.status(200).json(projects);
    } catch (error) {
      next(error);
    }
  });

  // GET /projects/:id - get a single project
  router.get('/:id', optionalAuth, async (req, res, next) => {
    try {
      const project = await Project.findById(req.params.id);
      if (!project) {
        const error = new Error('Project not found');
        error.status = 404;
        return next(error);
      }
      return res.status(200).json(project);
    } catch (error) {
      next(error);
    }
  });

  // POST /projects - create a new project
  router.post('/', authenticate, async (req, res, next) => {
    try {
      const { valid, errors } = validateProject(req.body);
      if (!valid) {
        const error = new Error(errors.join(', '));
        error.status = 400;
        return next(error);
      }

      const data = {
        name: req.body.name,
        description: req.body.description,
        owner_id: req.user.userId
      };

      const project = await Project.create(data);
      return res.status(201).json(project);
    } catch (error) {
      next(error);
    }
  });

  // PUT /projects/:id - update a project
  router.put('/:id', authenticate, async (req, res, next) => {
    try {
      const { valid, errors } = validateProjectUpdate(req.body);
      if (!valid) {
        const error = new Error(errors.join(', '));
        error.status = 400;
        return next(error);
      }

      const existing = await Project.findById(req.params.id);
      if (!existing) {
        const error = new Error('Project not found');
        error.status = 404;
        return next(error);
      }

      if (req.user.userId !== existing.owner_id) {
        const error = new Error('Forbidden');
        error.status = 403;
        return next(error);
      }

      const data = {};
      if (req.body.name !== undefined) data.name = req.body.name;
      if (req.body.description !== undefined) data.description = req.body.description;

      const project = await Project.update(req.params.id, data);
      return res.status(200).json(project);
    } catch (error) {
      next(error);
    }
  });

  // DELETE /projects/:id - delete a project
  router.delete('/:id', authenticate, async (req, res, next) => {
    try {
      const existing = await Project.findById(req.params.id);
      if (!existing) {
        const error = new Error('Project not found');
        error.status = 404;
        return next(error);
      }

      if (req.user.userId !== existing.owner_id) {
        const error = new Error('Forbidden');
        error.status = 403;
        return next(error);
      }

      const count = await Project.delete(req.params.id);
      if (count === 0) {
        const error = new Error('Project not found');
        error.status = 404;
        return next(error);
      }
      return res.status(204).send();
    } catch (error) {
      next(error);
    }
  });

  // GET /projects/:id/tasks - get all tasks for a project
  router.get('/:id/tasks', optionalAuth, async (req, res, next) => {
    try {
      const tasks = await Task.findByProject(req.params.id);
      return res.status(200).json(tasks);
    } catch (error) {
      next(error);
    }
  });

  return router;
};
