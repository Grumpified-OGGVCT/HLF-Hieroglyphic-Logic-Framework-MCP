exports.up = function(knex) {
  return knex.schema
    .createTable('users', (table) => {
      table.increments('id').primary();
      table.string('username', 30).notNullable().unique();
      table.string('email', 255).notNullable().unique();
      table.string('password_hash', 255).notNullable();
      table.timestamp('created_at').defaultTo(knex.fn.now());
      table.timestamp('updated_at').defaultTo(knex.fn.now());
    })
    .createTable('projects', (table) => {
      table.increments('id').primary();
      table.string('name', 100).notNullable();
      table.text('description');
      table.integer('owner_id').unsigned().notNullable().references('id').inTable('users').onDelete('CASCADE');
      table.timestamp('created_at').defaultTo(knex.fn.now());
      table.timestamp('updated_at').defaultTo(knex.fn.now());
      table.index('owner_id');
    })
    .createTable('tasks', (table) => {
      table.increments('id').primary();
      table.string('title', 200).notNullable();
      table.text('description');
      table.enu('status', ['todo', 'in_progress', 'done']).defaultTo('todo');
      table.enu('priority', ['low', 'medium', 'high']).defaultTo('medium');
      table.integer('project_id').unsigned().references('id').inTable('projects').onDelete('SET NULL');
      table.integer('assignee_id').unsigned().references('id').inTable('users').onDelete('SET NULL');
      table.timestamp('created_at').defaultTo(knex.fn.now());
      table.timestamp('updated_at').defaultTo(knex.fn.now());
      table.index('project_id');
      table.index('assignee_id');
      table.index('status');
    })
    .createTable('labels', (table) => {
      table.increments('id').primary();
      table.string('name', 50).notNullable();
      table.string('color', 7).defaultTo('#000000');
      table.timestamp('created_at').defaultTo(knex.fn.now());
    })
    .createTable('task_labels', (table) => {
      table.integer('task_id').unsigned().notNullable().references('id').inTable('tasks').onDelete('CASCADE');
      table.integer('label_id').unsigned().notNullable().references('id').inTable('labels').onDelete('CASCADE');
      table.primary(['task_id', 'label_id']);
      table.index('label_id');
    })
    .createTable('comments', (table) => {
      table.increments('id').primary();
      table.integer('task_id').unsigned().notNullable().references('id').inTable('tasks').onDelete('CASCADE');
      table.integer('user_id').unsigned().notNullable().references('id').inTable('users').onDelete('CASCADE');
      table.text('content').notNullable();
      table.timestamp('created_at').defaultTo(knex.fn.now());
      table.index('task_id');
      table.index('user_id');
    });
};

exports.down = function(knex) {
  return knex.schema
    .dropTableIfExists('comments')
    .dropTableIfExists('task_labels')
    .dropTableIfExists('labels')
    .dropTableIfExists('tasks')
    .dropTableIfExists('projects')
    .dropTableIfExists('users');
};
