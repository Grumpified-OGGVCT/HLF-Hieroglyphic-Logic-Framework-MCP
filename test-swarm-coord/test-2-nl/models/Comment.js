module.exports = (knex) => ({
  async create(data) {
    const [id] = await knex('comments').insert(data).returning('id');
    return this.findById(id);
  },

  async findById(id) {
    const comment = await knex('comments')
      .where('comments.id', id)
      .join('users', 'comments.user_id', 'users.id')
      .select(
        'comments.id',
        'comments.task_id',
        'comments.user_id',
        'comments.content',
        'comments.created_at',
        'users.username'
      )
      .first();
    return comment || null;
  },

  async findByTask(taskId) {
    return knex('comments')
      .where('comments.task_id', taskId)
      .join('users', 'comments.user_id', 'users.id')
      .select(
        'comments.id',
        'comments.task_id',
        'comments.user_id',
        'comments.content',
        'comments.created_at',
        'users.username'
      )
      .orderBy('comments.created_at', 'asc');
  },

  async update(id, data) {
    const [updated] = await knex('comments')
      .where({ id })
      .update(data)
      .returning('*');
    return updated ? this.findById(updated.id) : null;
  },

  async delete(id) {
    const count = await knex('comments').where({ id }).del();
    return count;
  },
});
