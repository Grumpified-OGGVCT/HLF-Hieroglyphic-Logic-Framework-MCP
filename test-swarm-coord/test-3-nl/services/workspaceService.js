const crypto = require('crypto');

const VALID_ROLES = ['admin', 'member', 'guest'];

function createWorkspaceService({ knex }) {
  function generateSlug(name) {
    return name
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  async function generateUniqueSlug(name) {
    const baseSlug = generateSlug(name);
    let slug = baseSlug;
    for (let attempt = 0; attempt < 10; attempt++) {
      const existing = await knex('workspaces').where({ slug }).first();
      if (!existing) return slug;
      const suffix = crypto.randomBytes(3).toString('hex');
      slug = `${baseSlug}-${suffix}`;
    }
    throw new Error('Unable to generate unique slug after 10 attempts');
  }

  async function create({ name, description, owner_id, is_public = false }) {
    const slug = await generateUniqueSlug(name);
    const workspace = await knex.transaction(async (trx) => {
      const [ws] = await trx('workspaces')
        .insert({ name, slug, description, owner_id, is_public })
        .returning('*');
      await trx('workspace_members').insert({
        workspace_id: ws.id,
        user_id: owner_id,
        role: 'admin',
      });
      return ws;
    });
    return workspace;
  }

  async function findById(id) {
    return knex('workspaces').where({ id }).first() || null;
  }

  async function findBySlug(slug) {
    return knex('workspaces').where({ slug }).first() || null;
  }

  async function update(id, updates) {
    const payload = { ...updates, updated_at: knex.fn.now() };
    delete payload.id;
    delete payload.created_at;
    const [workspace] = await knex('workspaces')
      .where({ id })
      .update(payload)
      .returning('*');
    return workspace || null;
  }

  async function remove(id) {
    const count = await knex('workspaces').where({ id }).del();
    return count > 0;
  }

  async function list({ limit = 20, offset = 0 } = {}) {
    return knex('workspaces')
      .select('*')
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
  }

  async function addMember(workspace_id, user_id, role = 'member') {
    if (!VALID_ROLES.includes(role)) {
      throw new Error(`Invalid role: ${role}. Must be one of ${VALID_ROLES.join(', ')}`);
    }
    const [member] = await knex('workspace_members')
      .insert({ workspace_id, user_id, role })
      .onConflict(['workspace_id', 'user_id'])
      .merge(['role', 'updated_at'])
      .returning('*');
    return member;
  }

  async function removeMember(workspace_id, user_id) {
    const count = await knex('workspace_members')
      .where({ workspace_id, user_id })
      .del();
    return count > 0;
  }

  async function updateMemberRole(workspace_id, user_id, role) {
    if (!VALID_ROLES.includes(role)) {
      throw new Error(`Invalid role: ${role}. Must be one of ${VALID_ROLES.join(', ')}`);
    }
    const [member] = await knex('workspace_members')
      .where({ workspace_id, user_id })
      .update({ role, updated_at: knex.fn.now() })
      .returning('*');
    return member || null;
  }

  async function getMembers(workspace_id) {
    return knex('workspace_members')
      .join('users', 'workspace_members.user_id', 'users.id')
      .where('workspace_members.workspace_id', workspace_id)
      .select(
        'workspace_members.id as member_id',
        'workspace_members.workspace_id',
        'workspace_members.user_id',
        'workspace_members.role',
        'workspace_members.created_at as joined_at',
        'users.username',
        'users.email',
        'users.display_name',
        'users.avatar_url',
        'users.status'
      )
      .orderBy('workspace_members.created_at', 'asc');
  }

  async function getMemberWorkspaces(user_id) {
    return knex('workspace_members')
      .join('workspaces', 'workspace_members.workspace_id', 'workspaces.id')
      .where('workspace_members.user_id', user_id)
      .select(
        'workspace_members.id as member_id',
        'workspace_members.role',
        'workspace_members.created_at as joined_at',
        'workspaces.id',
        'workspaces.name',
        'workspaces.slug',
        'workspaces.description',
        'workspaces.owner_id',
        'workspaces.is_public',
        'workspaces.created_at',
        'workspaces.updated_at'
      )
      .orderBy('workspace_members.created_at', 'desc');
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
