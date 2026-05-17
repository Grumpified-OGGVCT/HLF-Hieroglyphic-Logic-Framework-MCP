'use strict';

require('dotenv').config();

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const knexfile = require('./knexfile');
const knex = require('knex')(knexfile.development);

const app = express();
const server = http.createServer(app);
const io = new Server(server, {
  cors: {
    origin: process.env.CLIENT_ORIGIN || '*',
    methods: ['GET', 'POST'],
  },
});

// Global express middleware
app.use(helmet());
app.use(cors());
app.use(compression());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// Health check (before rate limiter)
app.get('/health', (req, res) => {
  res.json({ status: 'ok', timestamp: Date.now() });
});

// Initialize services via factories
const services = {};

const serviceFactories = {
  userService: require('./services/userService'),
  authService: require('./services/authService'),
  workspaceService: require('./services/workspaceService'),
  channelService: require('./services/channelService'),
  messageService: require('./services/messageService'),
  fileService: require('./services/fileService'),
  presenceService: require('./services/presenceService'),
  notificationService: require('./services/notificationService'),
  searchService: require('./services/searchService'),
  permissionService: require('./services/permissionService'),
  rateLimitService: require('./services/rateLimitService'),
};

for (const [name, factory] of Object.entries(serviceFactories)) {
  services[name] = factory({ knex });
}

// Initialize auth middleware factory
const authMiddlewareFactory = require('./middleware/auth');
const auth = authMiddlewareFactory(services.authService);

// Initialize rate limit middleware factory
const rateLimitMiddlewareFactory = require('./middleware/rateLimit');
const rateLimitMiddleware = rateLimitMiddlewareFactory(services.rateLimitService);

// Mount rate limit globally (except health which is already mounted)
app.use(rateLimitMiddleware);

// Initialize route factories
const routeFactories = {
  '/auth': require('./routes/auth'),
  '/users': require('./routes/users'),
  '/workspaces': require('./routes/workspaces'),
  '/channels': require('./routes/channels'),
  '/messages': require('./routes/messages'),
  '/files': require('./routes/files'),
  '/presence': require('./routes/presence'),
  '/notifications': require('./routes/notifications'),
  '/search': require('./routes/search'),
};

for (const [mountPath, factory] of Object.entries(routeFactories)) {
  const router = factory(services, auth, { rateLimit: rateLimitMiddleware });
  app.use(mountPath, router);
}

// Error handler middleware LAST
// eslint-disable-next-line no-unused-vars
app.use((err, req, res, next) => {
  const status = err.status || err.statusCode || 500;
  const message = err.message || 'Internal Server Error';

  console.error(`[ERROR] ${req.method} ${req.path} - ${message}`, err.stack);

  res.status(status).json({
    error: message,
    ...(process.env.NODE_ENV === 'development' && { stack: err.stack }),
  });
});

// Initialize WebSocket engine
const websocketEngineFactory = require('./websocket/engine');
websocketEngineFactory(io, services);

const PORT = process.env.PORT || 3000;

const httpServer = server.listen(PORT, () => {
  console.log(`Server listening on port ${PORT}`);
});

// Graceful shutdown
const shutdown = async (signal) => {
  console.log(`Received ${signal}. Shutting down gracefully...`);

  httpServer.close(() => {
    console.log('HTTP server closed.');
  });

  try {
    await knex.destroy();
    console.log('Knex connection pool destroyed.');
  } catch (err) {
    console.error('Error during Knex shutdown:', err);
  }

  process.exit(0);
};

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
