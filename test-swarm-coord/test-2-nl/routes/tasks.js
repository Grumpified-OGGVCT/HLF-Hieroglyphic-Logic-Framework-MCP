const router = require('express').Router();

module.exports = (models, auth, validation) => {
  const { Task } = models;
  const { authenticate, optionalAuth } = auth;
  const { validateTask, validateTaskUpdate, validateTaskFilters } = validation;

  // GET /tasks - List tasks with optional filters
  router.get('/', optionalAuth, async (req, res, next) => {
    try {
      const filters = {};
      if (req.query.status) filters.status = req.query.status;
      if (req.query.priority) filters.priority = req.query.priority;
      if (req.query.project_id) filters.project_id = req.query.project_id;
      if (req.query.assignee_id) filters.assignee_id = req.query.assignee_id;

      const filterValidation = validateTaskFilters(filters);
      if (!filterValidation.valid) {
        const error = new Error('Invalid query filters');
        error.status = 400;
        error.details = filterValidation.errors;
        return next(error);
      }

      const tasks = await Task.findAll(filters);
      res.status(200).json(tasks);
    } catch (error) {
      next(error);
    }
  });

  // GET /tasks/:id - Get single task
  router.get('/:id', optionalAuth, async (req, res, next) => {
    try {
      const task = await Task.findById(req.params.id);
      if (!task) {
        const error = new Error('Task not found');
        error.status = 404;
        return next(error);
      }
      res.status(200).json(task);
    } catch (error) {
      next(error);
    }
  });

  // POST /tasks - Create task
  router.post('/', authenticate, async (req, res, next) => {
    try {
      const validationResult = validateTask(req.body);
      if (!validationResult.valid) {
        const error = new Error('Validation failed');
        error.status = 400;
        error.details = validationResult.errors;
        return next(error);
      }

      const data = { ...req.body };
      if (!data.assignee_id && req.user && req.user.userId) {
        data.assignee_id = req.user.userId;
      }

      const task = await Task.create(data);
      res.status(201).json(task);
    } catch (error) {
      next(error);
    }
  });

  // PUT /tasks/:id - Update task
  router.put('/:id', authenticate, async (req, res, next) => {
    try {
      const validationResult = validateTaskUpdate(req.body);
      if (!validationResult.valid) {
        const error = new Error('Validation failed');
        error.status = 400;
        error.details = validationResult.errors;
        return next(error);
      }

      const task = await Task.update(req.params.id, req.body);
      if (!task) {
        const error = new Error('Task not found');
        error.status = 404;
        return next(error);
      }
      res.status(200).json(task);
    } catch (error) {
      next(error);
    }
  });

  // DELETE /tasks/:id - Delete task
  router.delete('/:id', authenticate, async (req, res, next) => {
    try {
      const count = await Task.delete(req.params.id);
      if (count === 0) {
        const error = new Error('Task not found');
        error.status = 404;
        return next(error);
      }
      res.status(204).send();
    } catch (error) {
      next(error);
    }
  });

  // POST /tasks/:id/labels/:labelId - Add label to task
  router.post('/:id/labels/:labelId', authenticate, async (req, res, next) => {
    try {
      const task = await Task.findById(req.params.id);
      if (!task) {
        const error = new Error('Task not found');
        error.status = 404;
        return next(error);
      }

      const labels = await Task.addLabel(req.params.id, req.params.labelId);
      res.status(200).json(labels);
    } catch (error) {
      next(error);
    }
  });

  // DELETE /tasks/:id/labels/:labelId - Remove label from task
  router.delete('/:id/labels/:labelId', authenticate, async (req, res, next) => {
    try {
      const task = await Task.findById(req.params.id);
      if (!task) {
        const error = new Error('Task not found');
        error.status = 404;
        return next(error);
      }

      const labels = await Task.removeLabel(req.params.id, req.params.labelId);
      res.status(200).json(labels);
    } catch (error) {
      next(error);
    }
  });

  // GET /tasks/:id/comments - Get task comments
  router.get('/:id/comments', optionalAuth, async (req, res, next) => {
    try {
      const task = await Task.findById(req.params.id);
      if (!task) {
        const error = new Error('Task not found');
        error.status = 404;
        return next(error);
      }

      const comments = await Task.getComments(req.params.id);
      res.status(200).json(comments);
    } catch (error) {
      next(error);
    }
  });

  return router;
};
