function createSearchService({ knex }) {
  async function searchMessages(
    query,
    { channelId, workspaceId, userId, limit = 20, offset = 0 } = {}
  ) {
    if (!query || query.trim() === '') {
      return { results: [], total: 0, limit, offset };
    }

    const tsVectorRaw = "to_tsvector('english', messages.content)";
    const tsQueryRaw = "plainto_tsquery('english', ?)";

    const resultsQuery = knex('messages')
      .select([
        'messages.id',
        'messages.channel_id',
        'messages.user_id',
        'messages.parent_id',
        'messages.content',
        'messages.type',
        'messages.created_at',
        'messages.updated_at',
        'messages.deleted_at',
        'users.username as user_username',
        'users.display_name as user_display_name',
        'users.avatar_url as user_avatar_url',
        knex.raw(`ts_rank(${tsVectorRaw}, ${tsQueryRaw}) as rank`, [query]),
      ])
      .join('users', 'messages.user_id', 'users.id')
      .whereNull('messages.deleted_at')
      .whereRaw(`${tsVectorRaw} @@ ${tsQueryRaw}`, [query]);

    if (channelId) {
      resultsQuery.andWhere('messages.channel_id', channelId);
    }
    if (workspaceId) {
      resultsQuery
        .join('channels', 'messages.channel_id', 'channels.id')
        .andWhere('channels.workspace_id', workspaceId);
    }
    if (userId) {
      resultsQuery.andWhere('messages.user_id', userId);
    }

    const results = await resultsQuery
      .orderBy('rank', 'desc')
      .orderBy('messages.created_at', 'desc')
      .limit(limit)
      .offset(offset);

    const countQuery = knex('messages').count('* as count');
    if (workspaceId) {
      countQuery.join('channels', 'messages.channel_id', 'channels.id');
    }
    countQuery
      .whereNull('messages.deleted_at')
      .whereRaw(`${tsVectorRaw} @@ ${tsQueryRaw}`, [query]);

    if (channelId) {
      countQuery.andWhere('messages.channel_id', channelId);
    }
    if (workspaceId) {
      countQuery.andWhere('channels.workspace_id', workspaceId);
    }
    if (userId) {
      countQuery.andWhere('messages.user_id', userId);
    }

    const [{ count }] = await countQuery;

    return { results, total: parseInt(count, 10), limit, offset };
  }

  async function searchChannels(
    query,
    { workspaceId, limit = 20, offset = 0 } = {}
  ) {
    if (!query || query.trim() === '') {
      return { results: [], total: 0, limit, offset };
    }

    const likeQuery = `%${query}%`;
    const baseQuery = knex('channels')
      .whereILike('name', likeQuery);

    if (workspaceId) {
      baseQuery.andWhere('workspace_id', workspaceId);
    }

    const results = await baseQuery
      .clone()
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');

    const countQuery = knex('channels')
      .count('* as count')
      .whereILike('name', likeQuery);

    if (workspaceId) {
      countQuery.andWhere('workspace_id', workspaceId);
    }

    const [{ count }] = await countQuery;

    return { results, total: parseInt(count, 10), limit, offset };
  }

  async function searchUsers(
    query,
    { limit = 20, offset = 0 } = {}
  ) {
    if (!query || query.trim() === '') {
      return { results: [], total: 0, limit, offset };
    }

    const likeQuery = `%${query}%`;
    const baseQuery = knex('users').where(function () {
      this.whereILike('display_name', likeQuery)
        .orWhereILike('username', likeQuery)
        .orWhereILike('email', likeQuery);
    });

    const results = await baseQuery
      .clone()
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');

    const [{ count }] = await knex('users')
      .count('* as count')
      .where(function () {
        this.whereILike('display_name', likeQuery)
          .orWhereILike('username', likeQuery)
          .orWhereILike('email', likeQuery);
      });

    return { results, total: parseInt(count, 10), limit, offset };
  }

  return {
    searchMessages,
    searchChannels,
    searchUsers,
  };
}

module.exports = { createSearchService };
