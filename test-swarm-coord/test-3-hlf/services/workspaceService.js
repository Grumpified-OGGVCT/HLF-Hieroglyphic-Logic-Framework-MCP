'use strict';

function createWorkspaceService({ knex }) {
  const VALID_ROLES = ['admin', 'member', 'guest'];

  function generateBaseSlug(name) {
    return name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  async function generateSlug(name) {
    let base = generateBaseSlug(name);
    if (!base) {
      base = 'workspace';
    }

    let slug = base;
    let attempt = 0;
    while (await knex('workspaces').where({ slug }).first()) {
      const suffix = Math.random().toString(36).substring(2, 8);
      slug = `${base}-${suffix}`;
      attempt++;
      if (attempt > 10) {
        const longSuffix = Math.random().toString(36).substring(2, 14);
        slug = `${base}-${longSuffix}`;
      }
    }
    return slug;
  }

  async function create(data) {
    const payload = { ...data };
    if (!payload.slug && payload.name) {
      payload.slug = await generateSlug(payload.name);
    }
    const [workspace] = await knex('workspaces').insert(payload).returning('*');

    if (workspace && payload.owner_id) {
      await knex('workspace_members')
        .insert({
          workspace_id: workspace.id,
          user_id: payload.owner_id,
          role: 'admin',
        })
        .onConflict(['workspace_id', 'user_id'])
        .merge({ role: 'admin' });
    }

    return workspace;
  }

  async function findById(id) {
    return knex('workspaces').where({ id }).first();
  }

  async function findBySlug(slug) {
    return knex('workspaces').where({ slug }).first();
  }

  async function update(id, data) {
    const payload = { ...data };
    delete payload.id;

    if (payload.name && !payload.slug) {
      payload.slug = await generateSlug(payload.name);
    }

    const [workspace] = await knex('workspaces').where({ id }).update(payload).returning('*');
    return workspace || null;
  }

  async function remove(id) {
    const count = await knex('workspaces').where({ id }).del();
    return count > 0;
  }

  async function list({ limit = 50, offset = 0 } = {}) {
    return knex('workspaces')
      .select('*')
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
  }

  async function addMember(workspaceId, userId, role = 'member') {
    if (!VALID_ROLES.includes(role)) {
      throw new Error(`Invalid role: ${role}. Must be one of ${VALID_ROLES.join(', ')}`);
    }
    const [member] = await knex('workspace_members')
      .insert({ workspace_id: workspaceId, user_id: userId, role })
      .returning('*');
    return member;
  }

  async function removeMember(workspaceId, userId) {
    const count = await knex('workspace_members')
      .where({ workspace_id: workspaceId, user_id: userId })
      .del();
    return count > 0;
  }

  async function updateMemberRole(workspaceId, userId, role) {
    if (!VALID_ROLES.includes(role)) {
      throw new Error(`Invalid role: ${role}. Must be one of ${VALID_ROLES.join(', ')}`);
    }
    const [member] = await knex('workspace_members')
      .where({ workspace_id: workspaceId, user_id: userId })
      .update({ role })
      .returning('*');
    return member || null;
  }

  async function getMembers(workspaceId) {
    return knex('workspace_members')
      .where({ workspace_id: workspaceId })
      .join('users', 'workspace_members.user_id', 'users.id')
      .select(
        'workspace_members.id as member_id',
        'workspace_members.workspace_id',
        'workspace_members.user_id',
        'workspace_members.role',
        'workspace_members.joined_at',
        'users.username',
        'users.email',
        'users.display_name',
        'users.avatar_url'
      )
      .orderBy('workspace_members.joined_at', 'asc');
  }

  async function getMemberWorkspaces(userId) {
    return knex('workspace_members')
      .where({ user_id: userId })
      .join('workspaces', 'workspace_members.workspace_id', 'workspaces.id')
      .select(
        'workspaces.*',
        'workspace_members.role as member_role',
        'workspace_members.joined_at'
      )
      .orderBy('workspace_members.joined_at', 'desc');
  }

  return {
    create,
    findById,
    findBySlug,
    update,
    remove,
    list,
    addMember,
    removeMember,
    updateMemberRole,
    getMembers,
    getMemberWorkspaces,
  };
}

module.exports = { createWorkspaceService };
