'use strict';

function createChannelService({ knex }) {
  const VALID_TYPES = ['public', 'private', 'direct_message'];

  function generateBaseSlug(name) {
    return name
      .toLowerCase()
      .trim()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  async function generateSlug(workspaceId, name) {
    let base = generateBaseSlug(name);
    if (!base) {
      base = 'channel';
    }

    let slug = base;
    let attempt = 0;
    while (await knex('channels').where({ workspace_id: workspaceId, slug }).first()) {
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

    if (!VALID_TYPES.includes(payload.type)) {
      throw new Error(`Invalid channel type: ${payload.type}. Must be one of ${VALID_TYPES.join(', ')}`);
    }

    if (!payload.slug && payload.name) {
      payload.slug = await generateSlug(payload.workspace_id, payload.name);
    }

    const [channel] = await knex('channels').insert(payload).returning('*');

    if (channel && payload.created_by) {
      await knex('channel_members')
        .insert({
          channel_id: channel.id,
          user_id: payload.created_by,
        })
        .onConflict(['channel_id', 'user_id'])
        .merge();
    }

    return channel;
  }

  async function findById(id) {
    return knex('channels').where({ id }).first();
  }

  async function update(id, data) {
    const payload = { ...data };
    delete payload.id;

    if (payload.type && !VALID_TYPES.includes(payload.type)) {
      throw new Error(`Invalid channel type: ${payload.type}. Must be one of ${VALID_TYPES.join(', ')}`);
    }

    if (payload.name && !payload.slug) {
      const workspaceId = payload.workspace_id || (await findById(id))?.workspace_id;
      if (workspaceId) {
        payload.slug = await generateSlug(workspaceId, payload.name);
      }
    }

    const [channel] = await knex('channels').where({ id }).update(payload).returning('*');
    return channel || null;
  }

  async function remove(id) {
    const count = await knex('channels').where({ id }).del();
    return count > 0;
  }

  async function list({ limit = 50, offset = 0 } = {}) {
    return knex('channels')
      .select('*')
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
  }

  async function listByWorkspace(workspaceId, { limit = 50, offset = 0 } = {}) {
    return knex('channels')
      .where({ workspace_id: workspaceId })
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');
  }

  async function addMember(channelId, userId) {
    const [member] = await knex('channel_members')
      .insert({ channel_id: channelId, user_id: userId })
      .returning('*');
    return member;
  }

  async function removeMember(channelId, userId) {
    const count = await knex('channel_members')
      .where({ channel_id: channelId, user_id: userId })
      .del();
    return count > 0;
  }

  async function getMembers(channelId) {
    return knex('channel_members')
      .where({ channel_id: channelId })
      .join('users', 'channel_members.user_id', 'users.id')
      .select(
        'users.id',
        'users.username',
        'users.email',
        'users.display_name',
        'users.avatar_url',
        'users.status',
        'channel_members.last_read_at'
      )
      .orderBy('users.username', 'asc');
  }

  async function isMember(channelId, userId) {
    const row = await knex('channel_members')
      .where({ channel_id: channelId, user_id: userId })
      .first();
    return !!row;
  }

  async function getDirectChannel(workspaceId, userA, userB) {
    const sorted = [userA, userB].sort();
    const dmName = `dm-${sorted[0]}-${sorted[1]}`;

    let channel = await knex('channels')
      .where({
        workspace_id: workspaceId,
        slug: dmName,
        type: 'direct_message',
      })
      .first();

    if (channel) {
      return channel;
    }

    const [created] = await knex('channels')
      .insert({
        workspace_id: workspaceId,
        name: dmName,
        slug: dmName,
        type: 'direct_message',
        created_by: userA,
      })
      .returning('*');

    await knex('channel_members')
      .insert([
        { channel_id: created.id, user_id: userA },
        { channel_id: created.id, user_id: userB },
      ])
      .onConflict(['channel_id', 'user_id'])
      .merge();

    return created;
  }

  return {
    create,
    findById,
    update,
    remove,
    list,
    listByWorkspace,
    addMember,
    removeMember,
    getMembers,
    isMember,
    getDirectChannel,
  };
}

module.exports = { createChannelService };
