function createMessageService({ knex }) {
  const VALID_TYPES = ['text', 'file', 'system'];

  const MESSAGE_COLUMNS = [
    'messages.id',
    'messages.channel_id',
    'messages.user_id',
    'messages.parent_id',
    'messages.content',
    'messages.type',
    'messages.created_at',
    'messages.updated_at',
    'messages.deleted_at',
  ];

  const USER_COLUMNS = [
    'users.username as user_username',
    'users.display_name as user_display_name',
    'users.avatar_url as user_avatar_url',
  ];

  function baseMessageQuery() {
    return knex('messages')
      .select([...MESSAGE_COLUMNS, ...USER_COLUMNS])
      .join('users', 'messages.user_id', 'users.id')
      .whereNull('messages.deleted_at');
  }

  async function create({ channel_id, user_id, content, parent_id, type = 'text' }) {
    if (!VALID_TYPES.includes(type)) {
      throw new Error(
        `Invalid type: ${type}. Must be one of ${VALID_TYPES.join(', ')}`
      );
    }
    const [message] = await knex('messages')
      .insert({ channel_id, user_id, content, parent_id, type })
      .returning('*');
    return message;
  }

  async function findById(id) {
    const message = await baseMessageQuery().where('messages.id', id).first();
    return message || null;
  }

  async function update(id, updates) {
    const payload = { ...updates, updated_at: knex.fn.now() };
    delete payload.id;
    delete payload.created_at;
    delete payload.channel_id;
    delete payload.user_id;
    delete payload.parent_id;

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
      .update({ deleted_at: knex.fn.now() })
      .returning('*');
    return !!message;
  }

  async function listByChannel(channel_id, { limit = 20, offset = 0 } = {}) {
    return baseMessageQuery()
      .where('messages.channel_id', channel_id)
      .orderBy('messages.created_at', 'desc')
      .limit(limit)
      .offset(offset);
  }

  async function listThread(parent_id, { limit = 50, offset = 0 } = {}) {
    return baseMessageQuery()
      .where('messages.parent_id', parent_id)
      .orderBy('messages.created_at', 'asc')
      .limit(limit)
      .offset(offset);
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

  async function getReactions(message_id) {
    return knex('reactions')
      .select(
        'reactions.id',
        'reactions.message_id',
        'reactions.user_id',
        'reactions.emoji',
        'reactions.created_at',
        'users.username as user_username',
        'users.display_name as user_display_name',
        'users.avatar_url as user_avatar_url'
      )
      .join('users', 'reactions.user_id', 'users.id')
      .where('reactions.message_id', message_id)
      .orderBy('reactions.created_at', 'asc');
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
