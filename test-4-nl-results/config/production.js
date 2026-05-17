module.exports = {
  port: process.env.PORT || 80,
  db: {
    host: process.env.DB_HOST || 'localhost',
    port: process.env.DB_PORT || 27017,
    name: process.env.DB_NAME || 'proddb',
  },
  logLevel: 'info',
};
