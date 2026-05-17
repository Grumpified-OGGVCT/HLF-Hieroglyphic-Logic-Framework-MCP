'use strict';

const VALID_STATUSES = ['online', 'away', 'offline', 'dnd'];

function createPresenceService({ knex }) {
  async function updateStatus(userId, status) {
    if (!VALID_STATUSES.includes(status)) {
      throw new Error(`Invalid status: ${status}. Must be one of ${VALID_STATUSES.join(', ')}`);
    }

    const [user] = await knex('users')
      .where({ id: userId })
      .update({ status, updated_at: knex.fn.now() })
      .returning(['id', 'username', 'status', 'updated_at']);

    return user || null;
  }

  async function getStatus(userId) {
    const user = await knex('users')
      .where({ id: userId })
      .first(['id', 'username', 'status', 'updated_at']);

    return user || null;
  }

  async function getOnlineUsers(workspaceId) {
    const users = await knex('users')
      .join('workspace_members', 'users.id', 'workspace_members.user_id')
      .where('workspace_members.workspace_id', workspaceId)
      .whereIn('users.status', ['online', 'away'])
      .select(
        'users.id',
        'users.username',
        'users.display_name',
        'users.avatar_url',
        'users.status',
        'users.updated_at',
        'workspace_members.role',
        'workspace_members.joined_at'
      )
      .orderBy('users.updated_at', 'desc');

    return users;
  }

  async function setLastActivity(userId) {
    const [user] = await knex('users')
      .where({ id: userId })
      .update({ updated_at: knex.fn.now() })
      .returning(['id', 'username', 'status', 'updated_at']);

    return user || null;
  }

  return {
    updateStatus,
    getStatus,
    getOnlineUsers,
    setLastActivity,
  };
}

module.exports = { createPresenceService };
