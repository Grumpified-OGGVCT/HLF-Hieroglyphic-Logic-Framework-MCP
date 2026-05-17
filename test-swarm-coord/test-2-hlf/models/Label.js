/**
 * Label model factory
 * @param {import("knex").Knex} knex
 * @returns {object} Label model
 */
module.exports = function LabelFactory(knex) {
  return {
    async create(data) {
      const [label] = await knex("labels")
        .insert(data)
        .returning(["id", "name", "color", "created_at"]);
      return label;
    },

    async findById(id) {
      const label = await knex("labels")
        .select("id", "name", "color", "created_at")
        .where({ id })
        .first();
      return label || null;
    },

    async findAll(filters = {}) {
      const query = knex("labels").select("id", "name", "color", "created_at");
      if (filters.name) {
        query.where("name", "ilike", `%${filters.name}%`);
      }
      return query;
    },

    async update(id, data) {
      const [label] = await knex("labels")
        .where({ id })
        .update(data)
        .returning(["id", "name", "color", "created_at"]);
      return label || null;
    },

    async delete(id) {
      const count = await knex("labels").where({ id }).del();
      return count;
    },
  };
};
