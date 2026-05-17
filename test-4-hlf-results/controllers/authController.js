const bcrypt = require('bcryptjs');
const { signToken } = require('../utils/jwt');

// In-memory user store (simulate DB)
let users = [];

// Pre-seed an admin user for testing
(async () => {
  const hashed = await bcrypt.hash('admin123', 10);
  users.push({ id: '1', username: 'admin', password: hashed, role: 'admin' });
})();

exports.register = async (req, res) => {
  try {
    const { username, password, role } = req.body;
    if (!username || !password) {
      return res.status(400).json({ message: 'Username and password required' });
    }
    const existing = users.find(u => u.username === username);
    if (existing) {
      return res.status(400).json({ message: 'User already exists' });
    }
    const hashedPassword = await bcrypt.hash(password, 10);
    const newUser = {
      id: (users.length + 1).toString(),
      username,
      password: hashedPassword,
      role: role || 'user' // default role
    };
    users.push(newUser);
    const token = signToken({ userId: newUser.id, username: newUser.username, role: newUser.role });
    return res.status(201).json({ message: 'User registered', token });
  } catch (err) {
    return res.status(500).json({ message: 'Internal server error' });
  }
};

exports.login = async (req, res) => {
  try {
    const { username, password } = req.body;
    if (!username || !password) {
      return res.status(400).json({ message: 'Username and password required' });
    }
    const user = users.find(u => u.username === username);
    if (!user) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }
    const isMatch = await bcrypt.compare(password, user.password);
    if (!isMatch) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }
    const token = signToken({ userId: user.id, username: user.username, role: user.role });
    return res.json({ token });
  } catch (err) {
    return res.status(500).json({ message: 'Internal server error' });
  }
};

exports.protected = (req, res) => {
  res.json({ message: `Hello ${req.user.username}, role: ${req.user.role}` });
};

exports.adminOnly = (req, res) => {
  res.json({ message: 'Welcome admin!' });
};