module.exports = (knex) => ({
  async create(data) {
    const [id] = await knex('projects').insert(data).returning('id');
    return this.findById(id);
  },

  async findById(id) {
    const project = await knex('projects')
      .where('projects.id', id)
      .join('users', 'projects.owner_id', 'users.id')
      .select(
        'projects.id',
        'projects.name',
        'projects.description',
        'projects.owner_id',
        'projects.created_at',
        'projects.updated_at',
        'users.username as owner_username'
      )
      .first();
    return project || null;
  },

  async findAll(filters = {}) {
    const query = knex('projects')
      .leftJoin('users', 'projects.owner_id', 'users.id')
      .select(
        'projects.id',
        'projects.name',
        'projects.description',
        'projects.owner_id',
        'projects.created_at',
        'projects.updated_at',
        'users.username as owner_username'
      );

    if (filters.name) {
      query.where('projects.name', 'like', `%${filters.name}%`);
    }
    if (filters.owner_id) {
      query.where('projects.owner_id', filters.owner_id);
    }

    return query;
  },

  async update(id, data) {
    const [updated] = await knex('projects')
      .where({ id })
      .update({ ...data, updated_at: knex.fn.now() })
      .returning('*');
    return updated ? this.findById(updated.id) : null;
  },

  async delete(id) {
    const count = await knex('projects').where({ id }).del();
    return count;
  },

  async findByOwner(ownerId) {
    return knex('projects')
      .where('projects.owner_id', ownerId)
      .join('users', 'projects.owner_id', 'users.id')
      .select(
        'projects.id',
        'projects.name',
        'projects.description',
        'projects.owner_id',
        'projects.created_at',
        'projects.updated_at',
        'users.username as owner_username'
      );
  },
});
