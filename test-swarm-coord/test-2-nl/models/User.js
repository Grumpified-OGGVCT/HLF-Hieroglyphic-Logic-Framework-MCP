module.exports = (knex) => ({
  async create(data) {
    const [id] = await knex('users').insert(data).returning('id');
    return this.findById(id);
  },

  async findById(id) {
    const user = await knex('users')
      .where({ id })
      .select('id', 'username', 'email', 'created_at', 'updated_at')
      .first();
    return user || null;
  },

  async findByEmail(email) {
    const user = await knex('users').where({ email }).first();
    return user || null;
  },

  async findAll(filters = {}) {
    const query = knex('users')
      .select('id', 'username', 'email', 'created_at', 'updated_at');

    if (filters.username) {
      query.where('username', 'like', `%${filters.username}%`);
    }
    if (filters.email) {
      query.where('email', 'like', `%${filters.email}%`);
    }

    return query;
  },

  async update(id, data) {
    const [updated] = await knex('users')
      .where({ id })
      .update({ ...data, updated_at: knex.fn.now() })
      .returning(['id', 'username', 'email', 'created_at', 'updated_at']);
    return updated || null;
  },

  async delete(id) {
    const count = await knex('users').where({ id }).del();
    return count;
  },

  async findByUsername(username) {
    const user = await knex('users')
      .where({ username })
      .select('id', 'username', 'email', 'created_at', 'updated_at')
      .first();
    return user || null;
  },
});
