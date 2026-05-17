const express = require("express");

module.exports = function usersRouteFactory(models, auth, validation) {
  const router = express.Router();

  // GET /users/:id — public profile (optional auth)
  router.get("/users/:id", auth.optionalAuth, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: "Invalid user id" });
      }

      const user = await models.User.findById(id);
      if (!user) {
        return res.status(404).json({ error: "User not found" });
      }

      const isSelf = req.user && req.user.id === id;
      const profile = {
        id: user.id,
        display_name: user.display_name,
        created_at: user.created_at,
        updated_at: user.updated_at,
      };
      if (isSelf) {
        profile.email = user.email;
      }

      res.status(200).json(profile);
    } catch (err) {
      next(err);
    }
  });

  // GET /users/:id/tasks — user's tasks (optional auth)
  router.get("/users/:id/tasks", auth.optionalAuth, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: "Invalid user id" });
      }

      const tasks = await models.Task.findByAssignee(id);
      res.status(200).json(tasks);
    } catch (err) {
      next(err);
    }
  });

  // PUT /users/:id — update own profile only
  router.put("/users/:id", auth.authenticate, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      if (!Number.isInteger(id) || id <= 0) {
        return res.status(400).json({ error: "Invalid user id" });
      }

      if (req.user.id !== id) {
        return res.status(403).json({ error: "Forbidden" });
      }

      const validationResult = validation.validateUserUpdate(req.body);
      if (!validationResult.valid) {
        return res.status(400).json({ error: "Validation failed", details: validationResult.errors });
      }

      const updated = await models.User.update(id, req.body);
      if (!updated) {
        return res.status(404).json({ error: "User not found" });
      }

      res.status(200).json(updated);
    } catch (err) {
      next(err);
    }
  });

  // POST /auth/register — delegate to auth.register
  router.post("/auth/register", (req, res, next) => {
    auth.register(req, res, next);
  });

  // POST /auth/login — delegate to auth.login
  router.post("/auth/login", (req, res, next) => {
    auth.login(req, res, next);
  });

  // POST /auth/refresh — delegate to auth.refresh
  router.post("/auth/refresh", (req, res, next) => {
    auth.refresh(req, res, next);
  });

  return router;
};
