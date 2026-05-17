module.exports = (knex) => ({
  async create(data) {
    const [id] = await knex('labels').insert(data).returning('id');
    return this.findById(id);
  },

  async findById(id) {
    const label = await knex('labels').where({ id }).first();
    return label || null;
  },

  async findAll() {
    return knex('labels').select('*');
  },

  async update(id, data) {
    const [updated] = await knex('labels')
      .where({ id })
      .update(data)
      .returning('*');
    return updated || null;
  },

  async delete(id) {
    const count = await knex('labels').where({ id }).del();
    return count;
  },
});
