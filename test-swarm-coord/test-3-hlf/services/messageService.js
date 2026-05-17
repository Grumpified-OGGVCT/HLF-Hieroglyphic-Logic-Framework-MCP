'use strict';

function createMessageService({ knex }) {
  async function create(data) {
    const payload = {
      channel_id: data.channel_id,
      user_id: data.user_id,
      content: data.content,
      type: data.type || 'text',
    };
    if (data.parent_id !== undefined && data.parent_id !== null) {
      payload.parent_id = data.parent_id;
    }
    const [message] = await knex('messages').insert(payload).returning('*');
    return message;
  }

  async function findById(id) {
    const message = await knex('messages')
      .where({ id })
      .whereNull('deleted_at')
      .first();
    return message || null;
  }

  async function update(id, data) {
    const payload = { ...data };
    delete payload.id;
    delete payload.channel_id;
    delete payload.user_id;
    delete payload.created_at;

    const [message] = await knex('messages')
      .where({ id })
      .whereNull('deleted_at')
      .update(payload)
      .returning('*');
    return message || null;
  }

  async function remove(id) {
    const [message] = await knex('messages')
      .where({ id })
      .whereNull('deleted_at')
      .update({ deleted_at: new Date() })
      .returning('*');
    return !!message;
  }

  async function listByChannel(channelId, { limit = 50, offset = 0 } = {}) {
    const messages = await knex('messages')
      .where({ channel_id: channelId })
      .whereNull('deleted_at')
      .leftJoin('users', 'messages.user_id', 'users.id')
      .select(
        'messages.*',
        'users.username',
        'users.display_name',
        'users.avatar_url'
      )
      .orderBy('messages.created_at', 'desc')
      .limit(limit)
      .offset(offset);
    return messages;
  }

  async function listThread(parentId) {
    const messages = await knex('messages')
      .where({ parent_id: parentId })
      .whereNull('deleted_at')
      .leftJoin('users', 'messages.user_id', 'users.id')
      .select(
        'messages.*',
        'users.username',
        'users.display_name',
        'users.avatar_url'
      )
      .orderBy('messages.created_at', 'asc');
    return messages;
  }

  async function addReaction({ message_id, user_id, emoji }) {
    const [reaction] = await knex('reactions')
      .insert({ message_id, user_id, emoji })
      .onConflict(['message_id', 'user_id', 'emoji'])
      .merge()
      .returning('*');
    return reaction;
  }

  async function removeReaction({ message_id, user_id, emoji }) {
    const count = await knex('reactions')
      .where({ message_id, user_id, emoji })
      .del();
    return count > 0;
  }

  async function getReactions(messageId) {
    const reactions = await knex('reactions')
      .where({ message_id: messageId })
      .join('users', 'reactions.user_id', 'users.id')
      .select(
        'reactions.id',
        'reactions.message_id',
        'reactions.emoji',
        'reactions.created_at',
        'users.id as user_id',
        'users.username',
        'users.display_name',
        'users.avatar_url'
      )
      .orderBy('reactions.created_at', 'asc');
    return reactions;
  }

  return {
    create,
    findById,
    update,
    remove,
    listByChannel,
    listThread,
    addReaction,
    removeReaction,
    getReactions,
  };
}

module.exports = { createMessageService };
