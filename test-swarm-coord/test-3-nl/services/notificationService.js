function createNotificationService({ knex }) {
  const VALID_TYPES = ['mention', 'reply', 'workspace_invite'];

  async function create({ userId, type, referenceId, messageId }) {
    if (!VALID_TYPES.includes(type)) {
      throw new Error(
        `Invalid type: ${type}. Must be one of ${VALID_TYPES.join(', ')}`
      );
    }
    const [notification] = await knex('notifications')
      .insert({
        user_id: userId,
        type,
        reference_id: referenceId || null,
        message_id: messageId || null,
      })
      .returning('*');
    return notification;
  }

  async function findById(id) {
    const notification = await knex('notifications').where({ id }).first();
    return notification || null;
  }

  async function listForUser(userId, { limit = 20, offset = 0 } = {}) {
    const rows = await knex('notifications')
      .select(
        'notifications.id',
        'notifications.user_id',
        'notifications.type',
        'notifications.reference_id',
        'notifications.message_id',
        'notifications.read_at',
        'notifications.created_at',
        'messages.content as message_content',
        'messages.channel_id as message_channel_id',
        'workspaces.id as workspace_id',
        'workspaces.name as workspace_name',
        'users.id as sender_id',
        'users.username as sender_username',
        'users.display_name as sender_display_name',
        'users.avatar_url as sender_avatar_url'
      )
      .leftJoin('messages', function () {
        this.on('notifications.message_id', 'messages.id')
          .orOn('notifications.reference_id', 'messages.id');
      })
      .leftJoin('workspaces', 'notifications.reference_id', 'workspaces.id')
      .leftJoin('users', 'messages.user_id', 'users.id')
      .where('notifications.user_id', userId)
      .orderBy('notifications.created_at', 'desc')
      .limit(limit)
      .offset(offset);
    return rows;
  }

  async function markAsRead(notificationId, userId) {
    const [notification] = await knex('notifications')
      .where({ id: notificationId, user_id: userId })
      .whereNull('read_at')
      .update({ read_at: knex.fn.now() })
      .returning('*');
    return notification || null;
  }

  async function markAllAsRead(userId) {
    const count = await knex('notifications')
      .where({ user_id: userId })
      .whereNull('read_at')
      .update({ read_at: knex.fn.now() });
    return count;
  }

  async function getUnreadCount(userId) {
    const result = await knex('notifications')
      .where({ user_id: userId })
      .whereNull('read_at')
      .count('id as count')
      .first();
    return parseInt(result.count, 10);
  }

  function detectMentions(content) {
    if (typeof content !== 'string') return [];
    const regex = /@([a-zA-Z0-9_]+)/g;
    const mentions = [];
    let match;
    while ((match = regex.exec(content)) !== null) {
      mentions.push(match[1]);
    }
    return [...new Set(mentions)];
  }

  return {
    create,
    findById,
    listForUser,
    markAsRead,
    markAllAsRead,
    getUnreadCount,
    detectMentions,
  };
}

module.exports = { createNotificationService };
