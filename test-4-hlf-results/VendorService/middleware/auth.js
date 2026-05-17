const auth = (req, res, next) => {
  const authHeader = req.headers.authorization;
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'No token provided' });
  }
  const token = authHeader.split(' ')[1];
  const [userId, role] = token.split(':');
  if (!userId || !role) {
    return res.status(401).json({ error: 'Invalid token' });
  }
  req.user = { id: userId, role };
  next();
};

const requireAdmin = (req, res, next) => {
  if (req.user.role !== 'admin') {
    return res.status(403).json({ error: 'Admin access required' });
  }
  next();
};

module.exports = auth;
module.exports.requireAdmin = requireAdmin;
