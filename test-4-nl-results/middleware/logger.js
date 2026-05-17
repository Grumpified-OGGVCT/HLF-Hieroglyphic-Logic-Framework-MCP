const fs = require('fs');
const path = require('path');

const logStream = fs.createWriteStream(path.join(__dirname, '..', 'access.log'), { flags: 'a' });

const logger = (req, res, next) => {
  const start = Date.now();
  res.on('finish', () => {
    const duration = Date.now() - start;
    const logLine = `${new Date().toISOString()} ${req.method} ${req.originalUrl} ${res.statusCode} ${duration}ms\n`;
    console.log(logLine.trim());
    logStream.write(logLine);
  });
  next();
};

module.exports = logger;
