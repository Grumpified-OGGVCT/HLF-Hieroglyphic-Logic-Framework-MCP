require('dotenv').config();

const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const helmet = require('helmet');
const compression = require('compression');
const knex = require('knex');

const knexConfig = require('./knexfile');

const { createAuthService } = require('./services/authService');
const { createUserService } = require('./services/userService');
const { createWorkspaceService } = require('./services/workspaceService');
const { createChannelService } = require('./services/channelService');
const { createMessageService } = require('./services/messageService');
const { createFileService } = require('./services/fileService');
const { createPresenceService } = require('./services/presenceService');
const { createNotificationService } = require('./services/notificationService');
const { createSearchService } = require('./services/searchService');
const { createPermissionService } = require('./services/permissionService');
const { createRateLimitService } = require('./services/rateLimitService');

const { createAuthMiddleware } = require('./middleware/auth');
const { createRateLimitMiddleware } = require('./middleware/rateLimit');

const { createAuthRoutes } = require('./routes/auth');
const { createUserRoutes } = require('./routes/users');
const { createWorkspaceRoutes } = require('./routes/workspaces');
const { createChannelRoutes } = require('./routes/channels');
const { createMessageRoutes } = require('./routes/messages');
const { createFileRoutes } = require('./routes/files');
const { createPresenceRoutes } = require('./routes/presence');
const { createNotificationRoutes } = require('./routes/notifications');
const { createSearchRoutes } = require('./routes/search');

const { createWebSocketEngine } = require('./websocket/engine');

async function main() {
  const app = express();
  const server = http.createServer(app);
  const io = new Server(server, {
    cors: {
      origin: process.env.CORS_ORIGIN || '*',
      methods: ['GET', 'POST'],
    },
  });

  app.use(helmet());
  app.use(cors({
    origin: process.env.CORS_ORIGIN || '*',
  }));
  app.use(compression());
  app.use(express.json());
  app.use(express.urlencoded({ extended: true }));

  const db = knex(knexConfig.development);

  const userService = createUserService({ knex: db });
  const workspaceService = createWorkspaceService({ knex: db });
  const channelService = createChannelService({ knex: db });
  const messageService = createMessageService({ knex: db });
  const fileService = createFileService({ knex: db, storagePath: process.env.FILE_STORAGE_PATH || './uploads' });
  const presenceService = createPresenceService({ knex: db });
  const notificationService = createNotificationService({ knex: db });
  const searchService = createSearchService({ knex: db });
  const permissionService = createPermissionService({ knex: db });

  const authService = createAuthService({
    userService,
    jwtSecret: process.env.JWT_SECRET || 'default-secret',
    refreshSecret: process.env.JWT_REFRESH_SECRET || 'default-refresh-secret',
  });

  const authMiddleware = createAuthMiddleware(authService);

  const rateLimitService = createRateLimitService(null);
  const rateLimitMiddleware = createRateLimitMiddleware(rateLimitService);
  app.use(rateLimitMiddleware);

  app.get('/health', (req, res) => {
    res.json({ status: 'ok', timestamp: Date.now() });
  });

  app.use('/auth', createAuthRoutes(authService));
  app.use('/users', createUserRoutes(userService));
  app.use('/workspaces', createWorkspaceRoutes(workspaceService, authMiddleware));
  app.use('/channels', createChannelRoutes(channelService, authMiddleware));
  app.use('/messages', createMessageRoutes(messageService, authMiddleware));
  app.use('/files', createFileRoutes(fileService, authMiddleware));
  app.use('/presence', createPresenceRoutes(presenceService, authMiddleware));
  app.use('/notifications', createNotificationRoutes(notificationService, authMiddleware));
  app.use('/search', createSearchRoutes(searchService, authMiddleware));

  app.use((req, res) => {
    res.status(404).json({ error: 'Not found' });
  });

  app.use((err, req, res, next) => {
    const statusCode = err.statusCode || err.status || 500;
    res.status(statusCode).json({
      error: err.message || 'Internal Server Error',
      statusCode,
    });
  });

  const wsEngine = createWebSocketEngine({
    io,
    messageService,
    channelService,
    userService,
    jwtSecret: process.env.JWT_SECRET || 'default-secret',
  });
  wsEngine.initialize();

  const PORT = process.env.PORT || 3000;
  server.listen(PORT, () => {
    console.log(`Server listening on port ${PORT}`);
  });

  function gracefulShutdown(signal) {
    return async () => {
      console.log(`Received ${signal}. Shutting down gracefully...`);
      server.close(async () => {
        await db.destroy();
        console.log('Database connections closed.');
        process.exit(0);
      });
    };
  }

  process.on('SIGTERM', gracefulShutdown('SIGTERM'));
  process.on('SIGINT', gracefulShutdown('SIGINT'));
}

main().catch((err) => {
  console.error('Failed to start server:', err);
  process.exit(1);
});
