'use strict';

const events = require('./events');

let jwt;
try {
  jwt = require('jsonwebtoken');
} catch {
  jwt = null;
}

function createWebSocketEngine({ io, messageService, channelService, userService }) {
  const connectedUsers = new Map();
  const jwtSecret = process.env.JWT_SECRET || 'default-jwt-secret';

  function getConnectedUsers() {
    return Array.from(connectedUsers.values());
  }

  async function authenticate(token) {
    if (!token) {
      throw new Error('Authentication token required');
    }

    let payload;
    if (jwt) {
      payload = jwt.verify(token, jwtSecret);
    } else {
      const parts = token.split('.');
      if (parts.length !== 3) {
        throw new Error('Invalid token format');
      }
      payload = JSON.parse(Buffer.from(parts[1], 'base64').toString('utf8'));
    }

    if (!payload || !payload.userId) {
      throw new Error('Invalid token payload');
    }

    const user = await userService.findById(payload.userId);
    if (!user) {
      throw new Error('User not found');
    }

    return user;
  }

  function initialize() {
    io.on('connection', async (socket) => {
      const token = socket.handshake.query?.token;

      let user;
      try {
        user = await authenticate(token);
      } catch (err) {
        socket.emit(events.ERROR, { message: err.message });
        socket.disconnect(true);
        return;
      }

      connectedUsers.set(socket.id, {
        userId: user.id,
        username: user.username,
        displayName: user.display_name || user.username,
        avatarUrl: user.avatar_url || null,
        socketId: socket.id,
      });

      socket.on(events.JOIN_ROOM, async (data) => {
        try {
          const { channelId } = data || {};
          if (!channelId) {
            socket.emit(events.ERROR, { message: 'channelId is required' });
            return;
          }

          const isMember = await channelService.isMember(channelId, user.id);
          if (!isMember) {
            socket.emit(events.ERROR, { message: 'Not a member of this channel' });
            return;
          }

          await socket.join(String(channelId));
          socket.emit('joined', { channelId });
          socket.to(String(channelId)).emit(events.USER_JOINED, {
            channelId,
            user: {
              id: user.id,
              username: user.username,
              displayName: user.display_name || user.username,
            },
          });
        } catch (err) {
          socket.emit(events.ERROR, { message: err.message });
        }
      });

      socket.on(events.LEAVE_ROOM, (data) => {
        try {
          const { channelId } = data || {};
          if (!channelId) {
            socket.emit(events.ERROR, { message: 'channelId is required' });
            return;
          }

          socket.leave(String(channelId));
          socket.emit('left', { channelId });
          socket.to(String(channelId)).emit(events.USER_LEFT, {
            channelId,
            user: {
              id: user.id,
              username: user.username,
              displayName: user.display_name || user.username,
            },
          });
        } catch (err) {
          socket.emit(events.ERROR, { message: err.message });
        }
      });

      socket.on(events.SEND_MESSAGE, async (data) => {
        try {
          const { channelId, content, parentId } = data || {};
          if (!channelId || !content) {
            socket.emit(events.ERROR, { message: 'channelId and content are required' });
            return;
          }

          const isMember = await channelService.isMember(channelId, user.id);
          if (!isMember) {
            socket.emit(events.ERROR, { message: 'Not a member of this channel' });
            return;
          }

          const message = await messageService.create({
            channel_id: channelId,
            user_id: user.id,
            content,
            parent_id: parentId,
            type: 'text',
          });

          const enrichedMessage = {
            ...message,
            username: user.username,
            display_name: user.display_name || user.username,
            avatar_url: user.avatar_url,
          };

          io.to(String(channelId)).emit(events.MESSAGE_RECEIVED, enrichedMessage);
        } catch (err) {
          socket.emit(events.ERROR, { message: err.message });
        }
      });

      socket.on(events.TYPING, (data) => {
        try {
          const { channelId, isTyping } = data || {};
          if (!channelId) {
            socket.emit(events.ERROR, { message: 'channelId is required' });
            return;
          }

          socket.to(String(channelId)).emit(events.TYPING, {
            channelId,
            userId: user.id,
            username: user.username,
            isTyping: !!isTyping,
          });
        } catch (err) {
          socket.emit(events.ERROR, { message: err.message });
        }
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
