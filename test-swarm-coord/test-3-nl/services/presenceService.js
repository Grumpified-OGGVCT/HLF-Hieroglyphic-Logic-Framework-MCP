const VALID_STATUSES = ['online', 'away', 'offline', 'dnd'];

function createPresenceService({ knex }) {
  async function updateStatus(userId, status) {
    if (!VALID_STATUSES.includes(status)) {
      throw new Error(`Invalid status: ${status}. Must be one of ${VALID_STATUSES.join(', ')}`);
    }
    const [user] = await knex('users')
      .where({ id: userId })
      .update({ status, updated_at: knex.fn.now() })
      .returning('*');
    return user || null;
  }

  async function getStatus(userId) {
    const user = await knex('users')
      .where({ id: userId })
      .select('id', 'username', 'display_name', 'avatar_url', 'status', 'updated_at')
      .first();
    return user || null;
  }

  async function getOnlineUsers(workspaceId) {
    return knex('workspace_members')
      .join('users', 'workspace_members.user_id', 'users.id')
      .where('workspace_members.workspace_id', workspaceId)
      .whereIn('users.status', ['online', 'away'])
      .select(
        'users.id',
        'users.username',
        'users.display_name',
        'users.avatar_url',
        'users.status',
        'users.updated_at',
        'workspace_members.role'
      )
      .orderBy('users.username', 'asc');
  }

  async function setLastActivity(userId) {
    const [user] = await knex('users')
      .where({ id: userId })
      .update({ updated_at: knex.fn.now() })
      .returning('*');
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
