'use strict';

function createNotificationService({ knex }) {
  async function create({ userId, type, referenceId, messageId }) {
    const payload = {
      user_id: userId,
      type,
      reference_id: referenceId,
      message_id: messageId || null,
    };
    const [notification] = await knex('notifications').insert(payload).returning('*');
    return notification;
  }

  async function findById(id) {
    const notification = await knex('notifications').where({ id }).first();
    return notification || null;
  }

  async function listForUser(userId, { limit = 20, offset = 0 } = {}) {
    const notifications = await knex('notifications')
      .where({ 'notifications.user_id': userId })
      .leftJoin('messages', function () {
        this.on('notifications.message_id', 'messages.id').andOnNull('messages.deleted_at');
      })
      .leftJoin('workspaces', 'notifications.reference_id', 'workspaces.id')
      .leftJoin('users as message_authors', 'messages.user_id', 'message_authors.id')
      .select(
        'notifications.*',
        'messages.content as message_content',
        'messages.channel_id as message_channel_id',
        'message_authors.username as message_author_username',
        'message_authors.display_name as message_author_display_name',
        'message_authors.avatar_url as message_author_avatar_url',
        'workspaces.name as workspace_name',
        'workspaces.slug as workspace_slug'
      )
      .orderBy('notifications.created_at', 'desc')
      .limit(limit)
      .offset(offset);
    return notifications;
  }

  async function markAsRead(notificationId) {
    const [notification] = await knex('notifications')
      .where({ id: notificationId })
      .whereNull('read_at')
      .update({ read_at: new Date() })
      .returning('*');
    return notification || null;
  }

  async function markAllAsRead(userId) {
    const count = await knex('notifications')
      .where({ user_id: userId })
      .whereNull('read_at')
      .update({ read_at: new Date() });
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
    if (typeof content !== 'string' || !content) return [];
    const mentionRegex = /@([a-zA-Z0-9_]+)/g;
    const mentions = [];
    let match;
    while ((match = mentionRegex.exec(content)) !== null) {
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
