/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.up = async function (knex) {
  await knex.schema
    .createTable("users", (table) => {
      table.increments("id").primary();
      table.string("email", 255).notNullable().unique();
      table.string("password_hash", 255).notNullable();
      table.string("display_name", 255).notNullable();
      table.timestamp("created_at", { useTz: true }).defaultTo(knex.fn.now());
      table.timestamp("updated_at", { useTz: true }).defaultTo(knex.fn.now());
      table.index("email", "idx_users_email");
    })
    .createTable("projects", (table) => {
      table.increments("id").primary();
      table.integer("owner_id").unsigned().notNullable();
      table.string("name", 255).notNullable();
      table.text("description");
      table.timestamp("created_at", { useTz: true }).defaultTo(knex.fn.now());
      table.timestamp("updated_at", { useTz: true }).defaultTo(knex.fn.now());
      table.foreign("owner_id").references("users.id").onDelete("CASCADE");
      table.index("owner_id", "idx_projects_owner_id");
    })
    .createTable("labels", (table) => {
      table.increments("id").primary();
      table.string("name", 100).notNullable().unique();
      table.string("color", 7);
      table.timestamp("created_at", { useTz: true }).defaultTo(knex.fn.now());
    })
    .createTable("tasks", (table) => {
      table.increments("id").primary();
      table.integer("project_id").unsigned().notNullable();
      table.integer("assignee_id").unsigned().nullable();
      table.string("title", 255).notNullable();
      table.text("description");
      table.string("status", 50).notNullable().defaultTo("todo");
      table.string("priority", 50).defaultTo("medium");
      table.timestamp("created_at", { useTz: true }).defaultTo(knex.fn.now());
      table.timestamp("updated_at", { useTz: true }).defaultTo(knex.fn.now());
      table.foreign("project_id").references("projects.id").onDelete("CASCADE");
      table.foreign("assignee_id").references("users.id").onDelete("SET NULL");
      table.index("project_id", "idx_tasks_project_id");
      table.index("assignee_id", "idx_tasks_assignee_id");
      table.index("status", "idx_tasks_status");
    })
    .createTable("task_labels", (table) => {
      table.integer("task_id").unsigned().notNullable();
      table.integer("label_id").unsigned().notNullable();
      table.primary(["task_id", "label_id"]);
      table.foreign("task_id").references("tasks.id").onDelete("CASCADE");
      table.foreign("label_id").references("labels.id").onDelete("CASCADE");
      table.index("label_id", "idx_task_labels_label_id");
    })
    .createTable("comments", (table) => {
      table.increments("id").primary();
      table.integer("task_id").unsigned().notNullable();
      table.integer("author_id").unsigned().notNullable();
      table.text("content").notNullable();
      table.timestamp("created_at", { useTz: true }).defaultTo(knex.fn.now());
      table.timestamp("updated_at", { useTz: true }).defaultTo(knex.fn.now());
      table.foreign("task_id").references("tasks.id").onDelete("CASCADE");
      table.foreign("author_id").references("users.id").onDelete("CASCADE");
      table.index("task_id", "idx_comments_task_id");
      table.index("author_id", "idx_comments_author_id");
    });
};

/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.down = async function (knex) {
  await knex.schema
    .dropTableIfExists("comments")
    .dropTableIfExists("task_labels")
    .dropTableIfExists("tasks")
    .dropTableIfExists("labels")
    .dropTableIfExists("projects")
    .dropTableIfExists("users");
};
