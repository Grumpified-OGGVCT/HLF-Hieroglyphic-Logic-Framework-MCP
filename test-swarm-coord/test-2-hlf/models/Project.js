/**
 * Project model factory
 * @param {import("knex").Knex} knex
 * @returns {object} Project model
 */
module.exports = function ProjectFactory(knex) {
  return {
    async create(data) {
      let ownerId = data.owner_id;
      if (!ownerId && data.owner_username) {
        const user = await knex("users")
          .select("id")
          .where({ display_name: data.owner_username })
          .first();
        if (!user) {
          throw new Error(`User not found: ${data.owner_username}`);
        }
        ownerId = user.id;
      }
      const [project] = await knex("projects")
        .insert({
          owner_id: ownerId,
          name: data.name,
          description: data.description,
        })
        .returning(["id", "owner_id", "name", "description", "created_at", "updated_at"]);
      return project;
    },

    async findById(id) {
      const project = await knex("projects")
        .select(
          "projects.id",
          "projects.owner_id",
          "users.display_name as owner_username",
          "projects.name",
          "projects.description",
          "projects.created_at",
          "projects.updated_at"
        )
        .leftJoin("users", "projects.owner_id", "users.id")
        .where("projects.id", id)
        .first();
      return project || null;
    },

    async findAll(filters = {}) {
      const query = knex("projects")
        .select(
          "projects.id",
          "projects.owner_id",
          "users.display_name as owner_username",
          "projects.name",
          "projects.description",
          "projects.created_at",
          "projects.updated_at"
        )
        .leftJoin("users", "projects.owner_id", "users.id");
      if (filters.name) {
        query.where("projects.name", "ilike", `%${filters.name}%`);
      }
      if (filters.owner_id) {
        query.where("projects.owner_id", filters.owner_id);
      }
      return query;
    },

    async update(id, data) {
      const updateData = { ...data };
      delete updateData.owner_username;
      const [project] = await knex("projects")
        .where({ id })
        .update({ ...updateData, updated_at: knex.fn.now() })
        .returning(["id", "owner_id", "name", "description", "created_at", "updated_at"]);
      return project || null;
    },

    async delete(id) {
      const count = await knex("projects").where({ id }).del();
      return count;
    },

    async findByOwner(ownerId) {
      return knex("projects")
        .select(
          "projects.id",
          "projects.owner_id",
          "users.display_name as owner_username",
          "projects.name",
          "projects.description",
          "projects.created_at",
          "projects.updated_at"
        )
        .leftJoin("users", "projects.owner_id", "users.id")
        .where("projects.owner_id", ownerId);
    },
  };
};
