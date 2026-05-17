'use strict';

const express = require('express');

function createUserRoutes(userService) {
  const router = express.Router();

  function isValidEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  }

  router.post('/register', async (req, res) => {
    try {
      const { username, email, password, display_name, avatar_url } = req.body;

      if (!username || typeof username !== 'string') {
        return res.status(400).json({ error: 'Username is required' });
      }
      if (!email || typeof email !== 'string') {
        return res.status(400).json({ error: 'Email is required' });
      }
      if (!isValidEmail(email)) {
        return res.status(400).json({ error: 'Invalid email format' });
      }
      if (!password || typeof password !== 'string' || password.length < 6) {
        return res.status(400).json({ error: 'Password must be at least 6 characters' });
      }

      const existingEmail = await userService.findByEmail(email);
      if (existingEmail) {
        return res.status(409).json({ error: 'Email already in use' });
      }

      const existingUsername = await userService.findByUsername(username);
      if (existingUsername) {
        return res.status(409).json({ error: 'Username already in use' });
      }

      const user = await userService.create({
        username,
        email,
        password,
        display_name,
        avatar_url,
      });

      return res.status(201).json(user);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.post('/login', async (req, res) => {
    try {
      const { username, password } = req.body;

      if (!username || !password) {
        return res.status(400).json({ error: 'Username and password are required' });
      }

      const user = await userService.findByUsername(username);
      if (!user) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      const valid = await userService.verifyPassword(user.id, password);
      if (!valid) {
        return res.status(401).json({ error: 'Invalid credentials' });
      }

      return res.status(200).json({ user });
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/:id', async (req, res) => {
    try {
      const user = await userService.findById(req.params.id);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }
      return res.status(200).json(user);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.put('/:id', async (req, res) => {
    try {
      const { password, ...rest } = req.body;
      const payload = { ...rest };
      if (password) {
        if (password.length < 6) {
          return res.status(400).json({ error: 'Password must be at least 6 characters' });
        }
        payload.password = password;
      }

      const user = await userService.update(req.params.id, payload);
      if (!user) {
        return res.status(404).json({ error: 'User not found' });
      }
      return res.status(200).json(user);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.delete('/:id', async (req, res) => {
    try {
      const deleted = await userService.remove(req.params.id);
      if (!deleted) {
        return res.status(404).json({ error: 'User not found' });
      }
      return res.status(204).send();
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  router.get('/', async (req, res) => {
    try {
      const { q, limit, offset } = req.query;
      if (q) {
        const users = await userService.search(q, {
          limit: limit ? parseInt(limit, 10) : undefined,
          offset: offset ? parseInt(offset, 10) : undefined,
        });
        return res.status(200).json(users);
      }
      const users = await userService.list({
        limit: limit ? parseInt(limit, 10) : undefined,
        offset: offset ? parseInt(offset, 10) : undefined,
      });
      return res.status(200).json(users);
    } catch (err) {
      return res.status(500).json({ error: err.message });
    }
  });

  return router;
}

module.exports = { createUserRoutes };
