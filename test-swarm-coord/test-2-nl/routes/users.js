const express = require('express');

module.exports = (models, auth, validation) => {
  const router = express.Router();
  const { User, Task } = models;
  const { authenticate, optionalAuth, register, login, refresh } = auth;
  const { validateUser, validateUserUpdate } = validation;

  // GET /users/:id - Get user profile
  router.get('/users/:id', optionalAuth, async (req, res, next) => {
    try {
      const user = await User.findById(req.params.id);
      if (!user) {
        const error = new Error('User not found');
        error.status = 404;
        return next(error);
      }

      // If authenticated and viewing own profile, email is included
      // (User.findById already returns email for all users)
      return res.status(200).json(user);
    } catch (error) {
      next(error);
    }
  });

  // GET /users/:id/tasks - Get tasks assigned to user
  router.get('/users/:id/tasks', optionalAuth, async (req, res, next) => {
    try {
      const user = await User.findById(req.params.id);
      if (!user) {
        const error = new Error('User not found');
        error.status = 404;
        return next(error);
      }

      const tasks = await Task.findByAssignee(req.params.id);
      return res.status(200).json(tasks);
    } catch (error) {
      next(error);
    }
  });

  // PUT /users/:id - Update user profile
  router.put('/users/:id', authenticate, async (req, res, next) => {
    try {
      const validationResult = validateUserUpdate(req.body);
      if (!validationResult.valid) {
        const error = new Error(validationResult.errors.join(', '));
        error.status = 400;
        return next(error);
      }

      if (req.user.userId !== req.params.id) {
        const error = new Error('Forbidden: can only update your own profile');
        error.status = 403;
        return next(error);
      }

      const updated = await User.update(req.params.id, req.body);
      if (!updated) {
        const error = new Error('User not found');
        error.status = 404;
        return next(error);
      }

      return res.status(200).json(updated);
    } catch (error) {
      next(error);
    }
  });

  // POST /auth/register - Register new user
  router.post('/auth/register', (req, res, next) => {
    const validationResult = validateUser(req.body);
    if (!validationResult.valid) {
      const error = new Error(validationResult.errors.join(', '));
      error.status = 400;
      return next(error);
    }
    return register(req, res, next);
  });

  // POST /auth/login - Login user
  router.post('/auth/login', login);

  // POST /auth/refresh - Refresh tokens
  router.post('/auth/refresh', refresh);

  return router;
};
