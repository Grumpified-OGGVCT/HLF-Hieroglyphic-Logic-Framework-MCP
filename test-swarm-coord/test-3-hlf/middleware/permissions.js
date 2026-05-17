'use strict';

function createPermissionMiddleware(permissionService) {
  function requirePermission(permission) {
    return async function middleware(req, res, next) {
      const userId = req.user?.id;
      if (!userId) {
        return res.status(401).json({ error: 'Unauthorized' });
      }

      const workspaceId = req.params?.workspaceId || req.body?.workspaceId;
      if (!workspaceId) {
        return res.status(400).json({ error: 'workspaceId is required' });
      }

      const role = await permissionService.getRole(userId, workspaceId);
      const permissions = permissionService.getPermissions(role);

      if (!permissions.includes(permission)) {
        return res.status(403).json({ error: 'Forbidden' });
      }

      next();
    };
  }

  return {
    requirePermission,
  };
}

module.exports = { createPermissionMiddleware };
