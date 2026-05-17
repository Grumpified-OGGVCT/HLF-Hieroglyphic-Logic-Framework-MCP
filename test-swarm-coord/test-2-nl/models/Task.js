module.exports = (knex) => ({
  async create(data) {
    const [id] = await knex('tasks').insert(data).returning('id');
    return this.findById(id);
  },

  async findById(id) {
    const task = await knex('tasks')
      .where('tasks.id', id)
      .leftJoin('projects', 'tasks.project_id', 'projects.id')
      .leftJoin('users', 'tasks.assignee_id', 'users.id')
      .select(
        'tasks.id',
        'tasks.title',
        'tasks.description',
        'tasks.status',
        'tasks.priority',
        'tasks.project_id',
        'tasks.assignee_id',
        'tasks.created_at',
        'tasks.updated_at',
        'projects.name as project_name',
        'users.username as assignee_username'
      )
      .first();

    if (!task) return null;

    const labels = await this.getLabels(id);
    task.labels = labels;

    return task;
  },

  async findAll(filters = {}) {
    const query = knex('tasks')
      .leftJoin('projects', 'tasks.project_id', 'projects.id')
      .leftJoin('users', 'tasks.assignee_id', 'users.id')
      .select(
        'tasks.id',
        'tasks.title',
        'tasks.description',
        'tasks.status',
        'tasks.priority',
        'tasks.project_id',
        'tasks.assignee_id',
        'tasks.created_at',
        'tasks.updated_at',
        'projects.name as project_name',
        'users.username as assignee_username'
      );

    if (filters.status) {
      query.where('tasks.status', filters.status);
    }
    if (filters.priority) {
      query.where('tasks.priority', filters.priority);
    }
    if (filters.project_id) {
      query.where('tasks.project_id', filters.project_id);
    }
    if (filters.assignee_id) {
      query.where('tasks.assignee_id', filters.assignee_id);
    }

    return query;
  },

  async update(id, data) {
    const [updated] = await knex('tasks')
      .where({ id })
      .update({ ...data, updated_at: knex.fn.now() })
      .returning('*');
    return updated ? this.findById(updated.id) : null;
  },

  async delete(id) {
    const count = await knex('tasks').where({ id }).del();
    return count;
  },

  async findByProject(projectId) {
    return knex('tasks')
      .where('tasks.project_id', projectId)
      .leftJoin('projects', 'tasks.project_id', 'projects.id')
      .leftJoin('users', 'tasks.assignee_id', 'users.id')
      .select(
        'tasks.id',
        'tasks.title',
        'tasks.description',
        'tasks.status',
        'tasks.priority',
        'tasks.project_id',
        'tasks.assignee_id',
        'tasks.created_at',
        'tasks.updated_at',
        'projects.name as project_name',
        'users.username as assignee_username'
      );
  },

  async findByAssignee(userId) {
    return knex('tasks')
      .where('tasks.assignee_id', userId)
      .leftJoin('projects', 'tasks.project_id', 'projects.id')
      .leftJoin('users', 'tasks.assignee_id', 'users.id')
      .select(
        'tasks.id',
        'tasks.title',
        'tasks.description',
        'tasks.status',
        'tasks.priority',
        'tasks.project_id',
        'tasks.assignee_id',
        'tasks.created_at',
        'tasks.updated_at',
        'projects.name as project_name',
        'users.username as assignee_username'
      );
  },

  async addLabel(taskId, labelId) {
    await knex('task_labels').insert({ task_id: taskId, label_id: labelId });
    return this.getLabels(taskId);
  },

  async removeLabel(taskId, labelId) {
    await knex('task_labels')
      .where({ task_id: taskId, label_id: labelId })
      .del();
    return this.getLabels(taskId);
  },

  async getLabels(taskId) {
    return knex('labels')
      .join('task_labels', 'labels.id', 'task_labels.label_id')
      .where('task_labels.task_id', taskId)
      .select('labels.id', 'labels.name', 'labels.color', 'labels.created_at');
  },

  async getComments(taskId) {
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
});
