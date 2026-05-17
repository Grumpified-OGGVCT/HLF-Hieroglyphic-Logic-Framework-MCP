/**
 * Comment model factory
 * @param {import("knex").Knex} knex
 * @returns {object} Comment model
 */
module.exports = function CommentFactory(knex) {
  return {
    async create(data) {
      let authorId = data.author_id;
      if (!authorId && data.username) {
        const user = await knex("users")
          .select("id")
          .where({ display_name: data.username })
          .first();
        if (!user) {
          throw new Error(`User not found: ${data.username}`);
        }
        authorId = user.id;
      }
      const [comment] = await knex("comments")
        .insert({
          task_id: data.task_id,
          author_id: authorId,
          content: data.content,
        })
        .returning(["id", "task_id", "author_id", "content", "created_at", "updated_at"]);
      return comment;
    },

    async findById(id) {
      const comment = await knex("comments")
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
        .where("comments.id", id)
        .first();
      return comment || null;
    },

    async findAll(filters = {}) {
      const query = knex("comments")
        .select(
          "comments.id",
          "comments.task_id",
          "comments.author_id",
          "users.display_name as username",
          "comments.content",
          "comments.created_at",
          "comments.updated_at"
        )
        .leftJoin("users", "comments.author_id", "users.id");
      if (filters.task_id) {
        query.where("comments.task_id", filters.task_id);
      }
      if (filters.author_id) {
        query.where("comments.author_id", filters.author_id);
      }
      return query.orderBy("comments.created_at", "asc");
    },

    async findByTask(taskId) {
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

    async update(id, data) {
      const [comment] = await knex("comments")
        .where({ id })
        .update({ content: data.content, updated_at: knex.fn.now() })
        .returning(["id", "task_id", "author_id", "content", "created_at", "updated_at"]);
      return comment || null;
    },

    async delete(id) {
      const count = await knex("comments").where({ id }).del();
      return count;
    },
  };
};
