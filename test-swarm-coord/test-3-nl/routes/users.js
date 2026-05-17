const express = require('express');

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function createUserRoutes(userService) {
  const router = express.Router();

  router.post('/register', async (req, res, next) => {
    try {
      const { username, email, password, display_name, avatar_url, status } = req.body;

      if (!email || !isValidEmail(email)) {
        return res.status(400).json({ error: 'Invalid email format' });
      }
      if (!password || password.length < 6) {
        return res.status(400).json({ error: 'Password must be at least 6 characters' });
      }
      if (!username) {
        return res.status(400).json({ error: 'Username is required' });
      }

      const existingEmail = await userService.findByEmail(email);
      if (existingEmail) {
        return res.status(409).json({ error: 'Email already in use' });
      }
      const existingUsername = await userService.findByUsername(username);
      if (existingUsername) {
        return res.status(409).json({ error: 'Username already taken' });
      }

      const user = await userService.create({
        username,
        email,
        password,
        display_name,
        avatar_url,
        status,
      });
      res.status(201).json(user);
    } catch (err) {
      next(err);
    }
  });

  router.post('/login', async (req, res, next) => {
    try {
      const { email, password } = req.body;
      if (!email || !password) {
        return res.status(400).json({ error: 'Email and password are required' });
      }

      const user = await userService.findByEmail(email);
      if (!user) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      const valid = await userService.verifyPassword(password, user.password_hash);
      if (!valid) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      const safeUser = { ...user };
      delete safeUser.password_hash;
      res.json(safeUser);
    } catch (err) {
      next(err);
    }
  });

  router.get('/:id', async (req, res, next) => {
    try {
      const user = await userService.findById(req.params.id);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }
      res.json(user);
    } catch (err) {
      next(err);
    }
  });

  router.put('/:id', async (req, res, next) => {
    try {
      const user = await userService.update(req.params.id, req.body);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }
      res.json(user);
    } catch (err) {
      next(err);
    }
  });

  router.delete('/:id', async (req, res, next) => {
    try {
      const removed = await userService.remove(req.params.id);
      if (!removed) {
        return res.status(404).json({ error: 'User not found' });
      }
      res.status(204).send();
    } catch (err) {
      next(err);
    }
  });

  router.get('/', async (req, res, next) => {
    try {
      const q = req.query.q;
      const limit = Math.min(parseInt(req.query.limit, 10) || 20, 100);
      const offset = Math.max(parseInt(req.query.offset, 10) || 0, 0);

      if (q) {
        const users = await userService.search(q, { limit, offset });
        return res.json(users);
      }
      const users = await userService.list({ limit, offset });
      res.json(users);
    } catch (err) {
      next(err);
    }
  });

  return router;
}

module.exports = { createUserRoutes };
