'use strict';

function createSearchService({ knex }) {
  async function searchMessages(query, options = {}) {
    const { channelId, workspaceId, userId, limit = 20, offset = 0 } = options;

    if (!query || typeof query !== 'string' || query.trim().length === 0) {
      return { results: [], total: 0, limit, offset };
    }

    const searchTerm = query.trim();

    let baseQuery = knex('messages')
      .whereRaw(
        "to_tsvector('english', messages.content) @@ plainto_tsquery('english', ?)",
        [searchTerm]
      )
      .whereNull('messages.deleted_at');

    if (channelId) {
      baseQuery = baseQuery.andWhere('messages.channel_id', channelId);
    }

    if (workspaceId) {
      baseQuery = baseQuery
        .join('channels', 'messages.channel_id', 'channels.id')
        .andWhere('channels.workspace_id', workspaceId);
    }

    if (userId) {
      baseQuery = baseQuery.andWhere('messages.user_id', userId);
    }

    const countResult = await baseQuery
      .clone()
      .clearSelect()
      .count('* as count')
      .first();
    const total = parseInt(countResult.count, 10);

    let resultsQuery = baseQuery
      .clone()
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

    const results = await resultsQuery;

    return { results, total, limit, offset };
  }

  async function searchChannels(query, options = {}) {
    const { workspaceId, limit = 20, offset = 0 } = options;

    if (!query || typeof query !== 'string' || query.trim().length === 0) {
      return { results: [], total: 0, limit, offset };
    }

    const searchTerm = `%${query.trim()}%`;

    let baseQuery = knex('channels')
      .whereILike('channels.name', searchTerm);

    if (workspaceId) {
      baseQuery = baseQuery.andWhere('channels.workspace_id', workspaceId);
    }

    const countResult = await baseQuery
      .clone()
      .clearSelect()
      .count('* as count')
      .first();
    const total = parseInt(countResult.count, 10);

    const results = await baseQuery
      .clone()
      .select('channels.*')
      .orderBy('channels.name', 'asc')
      .limit(limit)
      .offset(offset);

    return { results, total, limit, offset };
  }

  async function searchUsers(query, options = {}) {
    const { limit = 20, offset = 0 } = options;

    if (!query || typeof query !== 'string' || query.trim().length === 0) {
      return { results: [], total: 0, limit, offset };
    }

    const searchTerm = `%${query.trim()}%`;

    const baseQuery = knex('users')
      .whereILike('users.display_name', searchTerm)
      .orWhereILike('users.username', searchTerm)
      .orWhereILike('users.email', searchTerm);

    const countResult = await baseQuery
      .clone()
      .clearSelect()
      .count('* as count')
      .first();
    const total = parseInt(countResult.count, 10);

    const results = await baseQuery
      .clone()
      .select('users.id', 'users.username', 'users.display_name', 'users.email', 'users.avatar_url')
      .orderBy('users.display_name', 'asc')
      .limit(limit)
      .offset(offset);

    return { results, total, limit, offset };
  }

  return {
    searchMessages,
    searchChannels,
    searchUsers,
  };
}

module.exports = { createSearchService };
