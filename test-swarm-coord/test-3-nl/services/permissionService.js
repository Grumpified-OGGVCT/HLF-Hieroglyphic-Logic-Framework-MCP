const VALID_ROLES = ['admin', 'member', 'guest'];

const PERMISSIONS_MATRIX = {
  admin: [
    'create_channel',
    'delete_channel',
    'invite_member',
    'remove_member',
    'manage_workspace',
    'post_message',
  ],
  member: ['create_channel', 'invite_member', 'post_message'],
  guest: ['post_message'],
};

function createPermissionService({ knex }) {
  async function getRole(userId, workspaceId) {
    if (!userId || !workspaceId) {
      return null;
    }
    const member = await knex('workspace_members')
      .where({ user_id: userId, workspace_id: workspaceId })
      .first();
    return member?.role || null;
  }

  function getPermissions(role) {
    if (!role || !VALID_ROLES.includes(role)) {
      return [];
    }
    return PERMISSIONS_MATRIX[role] || [];
  }

  async function hasPermission(userId, workspaceId, permission) {
    const role = await getRole(userId, workspaceId);
    const permissions = getPermissions(role);
    return permissions.includes(permission);
  }

  async function canCreateChannel(userId, workspaceId) {
    return hasPermission(userId, workspaceId, 'create_channel');
  }

  async function canDeleteChannel(userId, workspaceId) {
    return hasPermission(userId, workspaceId, 'delete_channel');
  }

  async function canInviteMember(userId, workspaceId) {
    return hasPermission(userId, workspaceId, 'invite_member');
  }

  async function canRemoveMember(userId, workspaceId) {
    return hasPermission(userId, workspaceId, 'remove_member');
  }

  async function canManageWorkspace(userId, workspaceId) {
    return hasPermission(userId, workspaceId, 'manage_workspace');
  }

  async function canPostMessage(userId, workspaceId) {
    return hasPermission(userId, workspaceId, 'post_message');
  }

  return {
    canCreateChannel,
    canDeleteChannel,
    canInviteMember,
    canRemoveMember,
    canManageWorkspace,
    canPostMessage,
    getRole,
    getPermissions,
  };
}

module.exports = { createPermissionService };
