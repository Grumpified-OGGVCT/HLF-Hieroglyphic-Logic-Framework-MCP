'use strict';

function createPermissionService({ knex }) {
  const ROLES = {
    ADMIN: 'admin',
    MEMBER: 'member',
    GUEST: 'guest',
  };

  const PERMISSIONS_MATRIX = {
    [ROLES.ADMIN]: [
      'create_channel',
      'delete_channel',
      'invite_member',
      'remove_member',
      'manage_workspace',
      'post_message',
    ],
    [ROLES.MEMBER]: [
      'create_channel',
      'invite_member',
      'post_message',
    ],
    [ROLES.GUEST]: [
      'post_message',
    ],
  };

  async function getRole(userId, workspaceId) {
    const member = await knex('workspace_members')
      .where({ workspace_id: workspaceId, user_id: userId })
      .first();
    return member ? member.role : null;
  }

  function getPermissions(role) {
    return PERMISSIONS_MATRIX[role] || [];
  }

  async function hasPermission(userId, workspaceId, permission) {
    const role = await getRole(userId, workspaceId);
    return getPermissions(role).includes(permission);
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
