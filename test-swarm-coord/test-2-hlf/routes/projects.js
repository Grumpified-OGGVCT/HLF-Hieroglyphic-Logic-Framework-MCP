const express = require("express");

module.exports = (models, auth, validation) => {
  const router = express.Router();

  // GET /projects
  router.get("/", auth.optionalAuth, async (req, res, next) => {
    try {
      const filters = {};
      if (req.query.name) filters.name = req.query.name;
      if (req.query.owner_id) filters.owner_id = req.query.owner_id;
      const projects = await models.Project.findAll(filters);
      res.status(200).json(projects);
    } catch (err) {
      next(err);
    }
  });

  // GET /projects/:id
  router.get("/:id", auth.optionalAuth, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      const project = await models.Project.findById(id);
      if (!project) {
        return res.status(404).json({ error: "Project not found" });
      }
      res.status(200).json(project);
    } catch (err) {
      next(err);
    }
  });

  // POST /projects
  router.post("/", auth.authenticate, async (req, res, next) => {
    try {
      const result = validation.validateProject(req.body);
      if (!result.valid) {
        return res.status(400).json({ error: "Validation failed", details: result.errors });
      }
      const userId = req.user.id || req.user.userId;
      if (req.body.owner_id != userId) {
        return res.status(403).json({ error: "Forbidden" });
      }
      const project = await models.Project.create(req.body);
      res.status(201).json(project);
    } catch (err) {
      next(err);
    }
  });

  // PUT /projects/:id
  router.put("/:id", auth.authenticate, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      const project = await models.Project.findById(id);
      if (!project) {
        return res.status(404).json({ error: "Project not found" });
      }
      const userId = req.user.id || req.user.userId;
      if (project.owner_id != userId) {
        return res.status(403).json({ error: "Forbidden" });
      }
      const result = validation.validateProjectUpdate(req.body);
      if (!result.valid) {
        return res.status(400).json({ error: "Validation failed", details: result.errors });
      }
      const updated = await models.Project.update(id, req.body);
      res.status(200).json(updated);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /projects/:id
  router.delete("/:id", auth.authenticate, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      const project = await models.Project.findById(id);
      if (!project) {
        return res.status(404).json({ error: "Project not found" });
      }
      const userId = req.user.id || req.user.userId;
      if (project.owner_id != userId) {
        return res.status(403).json({ error: "Forbidden" });
      }
      await models.Project.delete(id);
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  // GET /projects/:id/tasks
  router.get("/:id/tasks", auth.optionalAuth, async (req, res, next) => {
    try {
      const id = parseInt(req.params.id, 10);
      const project = await models.Project.findById(id);
      if (!project) {
        return res.status(404).json({ error: "Project not found" });
      }
      const tasks = await models.Task.findByProject(id);
      res.status(200).json(tasks);
    } catch (err) {
      next(err);
    }
  });

  return router;
};
