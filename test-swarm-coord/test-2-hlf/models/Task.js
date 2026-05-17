/**
 * Task model factory
 * @param {import("knex").Knex} knex
 * @returns {object} Task model
 */
module.exports = function TaskFactory(knex) {
  return {
    async create(data) {
      const [task] = await knex("tasks")
        .insert(data)
        .returning([
          "id",
          "project_id",
          "assignee_id",
          "title",
          "description",
          "status",
          "priority",
          "created_at",
          "updated_at",
        ]);
      return task;
    },

    async findById(id) {
      const task = await knex("tasks")
        .select(
          "tasks.id",
          "tasks.project_id",
          "projects.name as project_name",
          "tasks.assignee_id",
          "users.display_name as assignee_username",
          "tasks.title",
          "tasks.description",
          "tasks.status",
          "tasks.priority",
          "tasks.created_at",
          "tasks.updated_at"
        )
        .leftJoin("projects", "tasks.project_id", "projects.id")
        .leftJoin("users", "tasks.assignee_id", "users.id")
        .where("tasks.id", id)
        .first();
      if (!task) return null;
      task.labels = await this.getLabels(id);
      return task;
    },

    async findAll(filters = {}) {
      const query = knex("tasks")
        .select(
          "tasks.id",
          "tasks.project_id",
          "projects.name as project_name",
          "tasks.assignee_id",
          "users.display_name as assignee_username",
          "tasks.title",
          "tasks.description",
          "tasks.status",
          "tasks.priority",
          "tasks.created_at",
          "tasks.updated_at"
        )
        .leftJoin("projects", "tasks.project_id", "projects.id")
        .leftJoin("users", "tasks.assignee_id", "users.id");
      if (filters.project_id) {
        query.where("tasks.project_id", filters.project_id);
      }
      if (filters.assignee_id) {
        query.where("tasks.assignee_id", filters.assignee_id);
      }
      if (filters.status) {
        query.where("tasks.status", filters.status);
      }
      if (filters.priority) {
        query.where("tasks.priority", filters.priority);
      }
      if (filters.title) {
        query.where("tasks.title", "ilike", `%${filters.title}%`);
      }
      return query;
    },

    async update(id, data) {
      const [task] = await knex("tasks")
        .where({ id })
        .update({ ...data, updated_at: knex.fn.now() })
        .returning([
          "id",
          "project_id",
          "assignee_id",
          "title",
          "description",
          "status",
          "priority",
          "created_at",
          "updated_at",
        ]);
      return task || null;
    },

    async delete(id) {
      const count = await knex("tasks").where({ id }).del();
      return count;
    },

    async findByProject(projectId) {
      return knex("tasks")
        .select(
          "tasks.id",
          "tasks.project_id",
          "projects.name as project_name",
          "tasks.assignee_id",
          "users.display_name as assignee_username",
          "tasks.title",
          "tasks.description",
          "tasks.status",
          "tasks.priority",
          "tasks.created_at",
          "tasks.updated_at"
        )
        .leftJoin("projects", "tasks.project_id", "projects.id")
        .leftJoin("users", "tasks.assignee_id", "users.id")
        .where("tasks.project_id", projectId);
    },

    async findByAssignee(assigneeId) {
      return knex("tasks")
        .select(
          "tasks.id",
          "tasks.project_id",
          "projects.name as project_name",
          "tasks.assignee_id",
          "users.display_name as assignee_username",
          "tasks.title",
          "tasks.description",
          "tasks.status",
          "tasks.priority",
          "tasks.created_at",
          "tasks.updated_at"
        )
        .leftJoin("projects", "tasks.project_id", "projects.id")
        .leftJoin("users", "tasks.assignee_id", "users.id")
        .where("tasks.assignee_id", assigneeId);
    },

    async addLabel(taskId, labelId) {
      await knex("task_labels").insert({ task_id: taskId, label_id: labelId }).onConflict().ignore();
      return this.getLabels(taskId);
    },

    async removeLabel(taskId, labelId) {
      await knex("task_labels").where({ task_id: taskId, label_id: labelId }).del();
      return this.getLabels(taskId);
    },

    async getLabels(taskId) {
      return knex("labels")
        .select("labels.id", "labels.name", "labels.color")
        .join("task_labels", "labels.id", "task_labels.label_id")
        .where("task_labels.task_id", taskId);
    },

    async getComments(taskId) {
      return knex("comments")
        .select(
          "comments.id",
          "comments.task_id",
          "comments.author_id",
          "users.display_name as username",
          "comments.content",
          "comments.created_at",
          "comments.updated_at"
        )
        .leftJoin("users", "comments.author_id", "users.id")
        .where("comments.task_id", taskId)
        .orderBy("comments.created_at", "asc");
    },
  };
};
