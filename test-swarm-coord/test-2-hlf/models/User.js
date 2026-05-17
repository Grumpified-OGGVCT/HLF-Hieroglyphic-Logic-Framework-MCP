/**
 * User model factory
 * @param {import("knex").Knex} knex
 * @returns {object} User model
 */
module.exports = function UserFactory(knex) {
  return {
    async create(data) {
      const [user] = await knex("users")
        .insert(data)
        .returning(["id", "email", "display_name", "created_at", "updated_at"]);
      return user;
    },

    async findById(id) {
      const user = await knex("users")
        .select("id", "email", "display_name", "created_at", "updated_at")
        .where({ id })
        .first();
      return user || null;
    },

    async findByEmail(email) {
      const user = await knex("users")
        .select("id", "email", "display_name", "created_at", "updated_at")
        .where({ email })
        .first();
      return user || null;
    },

    async findByUsername(displayName) {
      const user = await knex("users")
        .select("id", "email", "display_name", "created_at", "updated_at")
        .where({ display_name: displayName })
        .first();
      return user || null;
    },

    async findAll(filters = {}) {
      const query = knex("users").select(
        "id",
        "email",
        "display_name",
        "created_at",
        "updated_at"
      );
      if (filters.email) {
        query.where("email", "ilike", `%${filters.email}%`);
      }
      if (filters.display_name) {
        query.where("display_name", "ilike", `%${filters.display_name}%`);
      }
      return query;
    },

    async update(id, data) {
      const [user] = await knex("users")
        .where({ id })
        .update({ ...data, updated_at: knex.fn.now() })
        .returning(["id", "email", "display_name", "created_at", "updated_at"]);
      return user || null;
    },

    async delete(id) {
      const count = await knex("users").where({ id }).del();
      return count;
    },
  };
};
