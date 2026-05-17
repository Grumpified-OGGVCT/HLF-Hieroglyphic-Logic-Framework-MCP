const PERMISSION_METHOD_MAP = {
  create_channel: 'canCreateChannel',
  delete_channel: 'canDeleteChannel',
  invite_member: 'canInviteMember',
  remove_member: 'canRemoveMember',
  manage_workspace: 'canManageWorkspace',
  post_message: 'canPostMessage',
};

function createPermissionMiddleware(permissionService) {
  function requirePermission(permission) {
    return async function permissionMiddleware(req, res, next) {
      try {
        if (!req.user || !req.user.id) {
          return res.status(401).json({ error: 'Unauthorized' });
        }

        const workspaceId =
          req.params?.workspaceId ||
          req.params?.workspace_id ||
          req.body?.workspaceId ||
          req.body?.workspace_id ||
          null;

        if (!workspaceId) {
          return res
            .status(400)
            .json({ error: 'Missing workspace identifier' });
        }

        const methodName = PERMISSION_METHOD_MAP[permission];
        if (!methodName || !permissionService[methodName]) {
          return res.status(500).json({ error: 'Unknown permission' });
        }

        const allowed = await permissionService[methodName](
          req.user.id,
          workspaceId
        );

        if (!allowed) {
          return res.status(403).json({ error: 'Forbidden' });
        }

        next();
      } catch (err) {
        next(err);
      }
    };
  }

  return { requirePermission };
}

module.exports = { createPermissionMiddleware };
