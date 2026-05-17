const events = require('./events');

let jwt;
try {
  jwt = require('jsonwebtoken');
} catch {
  jwt = null;
}

function verifyToken(token, secret) {
  if (jwt) return jwt.verify(token, secret);
  const parts = token.split('.');
  if (parts.length !== 3) throw new Error('Invalid token');
  return JSON.parse(Buffer.from(parts[1], 'base64url').toString());
}

function createWebSocketEngine({ io, messageService, channelService, userService, jwtSecret }) {
  const connectedUsers = new Map();
  const secret = jwtSecret || process.env.JWT_SECRET || 'default-secret';

  async function authenticate(socket) {
    const token = socket.handshake.query.token;
    if (!token) {
      throw new Error('Authentication required');
    }
    try {
      const payload = verifyToken(token, secret);
      const user = await userService.findById(Number(payload.sub));
      if (!user) {
        throw new Error('User not found');
      }
      return user;
    } catch {
      throw new Error('Invalid token');
    }
  }

  function getConnectedUsers() {
    return Array.from(connectedUsers.values());
  }

  function initialize() {
    io.on('connection', async (socket) => {
      let user;
      try {
        user = await authenticate(socket);
      } catch (err) {
        socket.emit(events.ERROR, { message: err.message });
        socket.disconnect(true);
        return;
      }

      connectedUsers.set(socket.id, {
        socketId: socket.id,
        userId: user.id,
        username: user.username,
        displayName: user.display_name,
        avatarUrl: user.avatar_url,
      });

      socket.on(events.JOIN_ROOM, async ({ channelId }) => {
        try {
          if (!channelId) {
            socket.emit(events.ERROR, { message: 'channelId is required' });
            return;
          }
          const channel = await channelService.findById(channelId);
          if (!channel) {
            socket.emit(events.ERROR, { message: 'Channel not found' });
            return;
          }
          const isMember = await channelService.isMember(channelId, user.id);
          if (!isMember && channel.type !== 'public') {
            socket.emit(events.ERROR, { message: 'Access denied' });
            return;
          }
          socket.join(`channel:${channelId}`);
          socket.to(`channel:${channelId}`).emit(events.USER_JOINED, {
            userId: user.id,
            username: user.username,
            channelId,
          });
        } catch (err) {
          socket.emit(events.ERROR, { message: err.message });
        }
      });

      socket.on(events.LEAVE_ROOM, ({ channelId }) => {
        if (!channelId) {
          socket.emit(events.ERROR, { message: 'channelId is required' });
          return;
        }
        socket.leave(`channel:${channelId}`);
        socket.to(`channel:${channelId}`).emit(events.USER_LEFT, {
          userId: user.id,
          username: user.username,
          channelId,
        });
      });

      socket.on(events.SEND_MESSAGE, async ({ channelId, content, parentId }) => {
        try {
          if (!channelId || typeof content !== 'string' || content.trim().length === 0) {
            socket.emit(events.ERROR, { message: 'channelId and non-empty content are required' });
            return;
          }
          const channel = await channelService.findById(channelId);
          if (!channel) {
            socket.emit(events.ERROR, { message: 'Channel not found' });
            return;
          }
          const isMember = await channelService.isMember(channelId, user.id);
          if (!isMember && channel.type !== 'public') {
            socket.emit(events.ERROR, { message: 'Access denied' });
            return;
          }
          const created = await messageService.create({
            channel_id: channelId,
            user_id: user.id,
            content: content.trim(),
            parent_id: parentId || null,
            type: 'text',
          });
          const message = await messageService.findById(created.id);
          io.to(`channel:${channelId}`).emit(events.MESSAGE_RECEIVED, {
            ...message,
            channelId,
          });
        } catch (err) {
          socket.emit(events.ERROR, { message: err.message });
        }
      });

      socket.on(events.TYPING, ({ channelId, isTyping }) => {
        if (!channelId) {
          socket.emit(events.ERROR, { message: 'channelId is required' });
          return;
        }
        socket.to(`channel:${channelId}`).emit(events.TYPING, {
          userId: user.id,
          username: user.username,
          channelId,
          isTyping: !!isTyping,
        });
      });

      socket.on('disconnect', () => {
        connectedUsers.delete(socket.id);
      });
    });
  }

  return {
    initialize,
    getConnectedUsers,
  };
}

module.exports = { createWebSocketEngine };
