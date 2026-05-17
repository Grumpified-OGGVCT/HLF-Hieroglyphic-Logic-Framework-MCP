/**
 * Task routes factory
 * @param {object} models - model factories
 * @param {object} auth - auth middleware module
 * @param {object} validation - task validation module
 * @returns {import('express').Router}
 */
module.exports = (models, auth, validation) => {
  const router = require('express').Router();

  // GET /tasks — list tasks with optional filters
  router.get('/', auth.optionalAuth, async (req, res, next) => {
    try {
      const filters = { ...req.query };

      if (filters.project_id !== undefined) {
        filters.project_id = Number(filters.project_id);
      }
      if (filters.assignee_id !== undefined) {
        filters.assignee_id = filters.assignee_id === 'null' ? null : Number(filters.assignee_id);
      }
      if (filters.page !== undefined) {
        filters.page = Number(filters.page);
      }
      if (filters.limit !== undefined) {
        filters.limit = Number(filters.limit);
      }

      const result = validation.validateTaskFilters(filters);
      if (!result.valid) {
        return res.status(400).json({ errors: result.errors });
      }

      const tasks = await models.Task.findAll(filters);
      res.status(200).json(tasks);
    } catch (err) {
      next(err);
    }
  });

  // GET /tasks/:id — retrieve single task
  router.get('/:id', auth.optionalAuth, async (req, res, next) => {
    try {
      const id = Number(req.params.id);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: 'Invalid task ID' });
      }

      const task = await models.Task.findById(id);
      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }

      res.status(200).json(task);
    } catch (err) {
      next(err);
    }
  });

  // POST /tasks — create a new task
  router.post('/', auth.authenticate, async (req, res, next) => {
    try {
      const result = validation.validateTask(req.body);
      if (!result.valid) {
        return res.status(400).json({ errors: result.errors });
      }

      const task = await models.Task.create(req.body);
      res.status(201).json(task);
    } catch (err) {
      next(err);
    }
  });

  // PUT /tasks/:id — update an existing task
  router.put('/:id', auth.authenticate, async (req, res, next) => {
    try {
      const id = Number(req.params.id);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: 'Invalid task ID' });
      }

      const result = validation.validateTaskUpdate(req.body);
      if (!result.valid) {
        return res.status(400).json({ errors: result.errors });
      }

      const task = await models.Task.update(id, req.body);
      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }

      res.status(200).json(task);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /tasks/:id — remove a task
  router.delete('/:id', auth.authenticate, async (req, res, next) => {
    try {
      const id = Number(req.params.id);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: 'Invalid task ID' });
      }

      const count = await models.Task.delete(id);
      if (count === 0) {
        return res.status(404).json({ error: 'Task not found' });
      }

      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  // POST /tasks/:id/labels/:labelId — add label to task
  router.post('/:id/labels/:labelId', auth.authenticate, async (req, res, next) => {
    try {
      const id = Number(req.params.id);
      const labelId = Number(req.params.labelId);
      if (!Number.isInteger(id) || id <= 0 || !Number.isInteger(labelId) || labelId <= 0) {
        return res.status(400).json({ error: 'Invalid task ID or label ID' });
      }

      const task = await models.Task.findById(id);
      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }

      const labels = await models.Task.addLabel(id, labelId);
      res.status(201).json(labels);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /tasks/:id/labels/:labelId — remove label from task
  router.delete('/:id/labels/:labelId', auth.authenticate, async (req, res, next) => {
    try {
      const id = Number(req.params.id);
      const labelId = Number(req.params.labelId);
      if (!Number.isInteger(id) || id <= 0 || !Number.isInteger(labelId) || labelId <= 0) {
        return res.status(400).json({ error: 'Invalid task ID or label ID' });
      }

      const task = await models.Task.findById(id);
      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }

      const labels = await models.Task.removeLabel(id, labelId);
      res.status(200).json(labels);
    } catch (err) {
      next(err);
    }
  });

  // GET /tasks/:id/comments — list comments for a task
  router.get('/:id/comments', auth.optionalAuth, async (req, res, next) => {
    try {
      const id = Number(req.params.id);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: 'Invalid task ID' });
      }

      const task = await models.Task.findById(id);
      if (!task) {
        return res.status(404).json({ error: 'Task not found' });
      }

      const comments = await models.Task.getComments(id);
      res.status(200).json(comments);
    } catch (err) {
      next(err);
    }
  });

  return router;
};
