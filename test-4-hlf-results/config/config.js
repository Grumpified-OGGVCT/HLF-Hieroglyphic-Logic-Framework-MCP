module.exports = {
  jwtSecret: process.env.JWT_SECRET || 'supersecretkey',
  jwtExpiry: process.env.JWT_EXPIRY || '1h',
  port: process.env.PORT || 3001
};