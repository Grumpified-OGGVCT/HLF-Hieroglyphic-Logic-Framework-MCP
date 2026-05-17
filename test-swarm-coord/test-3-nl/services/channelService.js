function createChannelService({ knex }) {
  const VALID_TYPES = ['public', 'private', 'direct_message'];

  function generateSlug(name) {
    return name
      .toLowerCase()
      .replace(/\s+/g, '-')
      .replace(/[^a-z0-9-]/g, '')
      .replace(/-+/g, '-')
      .replace(/^-|-$/g, '');
  }

  async function generateUniqueSlug(workspaceId, name) {
    const baseSlug = generateSlug(name);
    let slug = baseSlug;
    for (let attempt = 0; attempt < 10; attempt++) {
      const existing = await knex('channels')
        .where({ workspace_id: workspaceId, slug })
        .first();
      if (!existing) return slug;
      const suffix = Math.random().toString(36).slice(2, 8);
      slug = `${baseSlug}-${suffix}`;
    }
    throw new Error('Unable to generate unique slug after 10 attempts');
  }

  function getDirectMessageName(userA, userB) {
    const sorted = [userA, userB].sort();
    return `dm-${sorted[0]}-${sorted[1]}`;
  }

  async function create({ workspace_id, name, type = 'public', created_by }) {
    if (!VALID_TYPES.includes(type)) {
      throw new Error(
        `Invalid type: ${type}. Must be one of ${VALID_TYPES.join(', ')}`
      );
    }
    const slug = await generateUniqueSlug(workspace_id, name);
    const channel = await knex.transaction(async (trx) => {
      const [ch] = await trx('channels')
        .insert({ workspace_id, name, slug, type, created_by })
        .returning('*');
      await trx('channel_members').insert({
        channel_id: ch.id,
        user_id: created_by,
      });
      return ch;
    });
    return channel;
  }

  async function findById(id) {
    return knex('channels').where({ id }).first() || null;
  }

  async function update(id, updates) {
    const payload = { ...updates, updated_at: knex.fn.now() };
    delete payload.id;
    delete payload.created_at;
    delete payload.workspace_id;
    const [channel] = await knex('channels')
      .where({ id })
      .update(payload)
      .returning('*');
    return channel || null;
  }

  async function remove(id) {
    const count = await knex('channels').where({ id }).del();
    return count > 0;
  }

  async function list({ limit = 20, offset = 0, user_id } = {}) {
    const query = knex('channels')
      .select('*')
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');

    if (user_id) {
      query.where(function () {
        this.where('type', 'public').orWhereExists(function () {
          this.select(1)
            .from('channel_members')
            .whereRaw('channel_members.channel_id = channels.id')
            .andWhere('channel_members.user_id', user_id);
        });
      });
    } else {
      query.where('type', 'public');
    }

    return query;
  }

  async function listByWorkspace(workspace_id, { limit = 20, offset = 0, user_id } = {}) {
    const query = knex('channels')
      .where({ workspace_id })
      .limit(limit)
      .offset(offset)
      .orderBy('created_at', 'desc');

    if (user_id) {
      query.where(function () {
        this.where('type', 'public').orWhereExists(function () {
          this.select(1)
            .from('channel_members')
            .whereRaw('channel_members.channel_id = channels.id')
            .andWhere('channel_members.user_id', user_id);
        });
      });
    } else {
      query.where('type', 'public');
    }

    return query;
  }

  async function addMember(channel_id, user_id) {
    const [member] = await knex('channel_members')
      .insert({ channel_id, user_id })
      .onConflict(['channel_id', 'user_id'])
      .merge()
      .returning('*');
    return member;
  }

  async function removeMember(channel_id, user_id) {
    const count = await knex('channel_members')
      .where({ channel_id, user_id })
      .del();
    return count > 0;
  }

  async function getMembers(channel_id) {
    return knex('channel_members')
      .join('users', 'channel_members.user_id', 'users.id')
      .where('channel_members.channel_id', channel_id)
      .select(
        'channel_members.id as member_id',
        'channel_members.channel_id',
        'channel_members.user_id',
        'channel_members.last_read_at',
        'users.username',
        'users.email',
        'users.display_name',
        'users.avatar_url',
        'users.status'
      )
      .orderBy('channel_members.id', 'asc');
  }

  async function isMember(channel_id, user_id) {
    const row = await knex('channel_members')
      .where({ channel_id, user_id })
      .first();
    return !!row;
  }

  async function getDirectChannel(workspace_id, userA, userB) {
    const dmName = getDirectMessageName(userA, userB);
    let channel = await knex('channels')
      .where({
        workspace_id,
        name: dmName,
        type: 'direct_message',
      })
      .first();

    if (!channel) {
      channel = await knex.transaction(async (trx) => {
        const [ch] = await trx('channels')
          .insert({
            workspace_id,
            name: dmName,
            slug: await generateUniqueSlug(workspace_id, dmName),
            type: 'direct_message',
            created_by: userA,
          })
          .returning('*');
        await trx('channel_members').insert([
          { channel_id: ch.id, user_id: userA },
          { channel_id: ch.id, user_id: userB },
        ]);
        return ch;
      });
    }

    return channel;
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
