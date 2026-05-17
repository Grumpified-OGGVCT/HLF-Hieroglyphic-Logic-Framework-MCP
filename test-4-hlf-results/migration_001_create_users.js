exports.up = async function(knex) {
  await knex.schema.createTable('users', (table) => {
    table.increments('id').primary();
    table.string('email', 255).notNullable();
    table.string('name', 100);
    table.timestamp('created_at').defaultTo(knex.fn.now());
    table.timestamp('updated_at').defaultTo(knex.fn.now());

    // Unique constraint on email (creates a unique index)
    table.unique('email', 'users_email_unique');

    // Index on name for faster lookups
    table.index('name', 'users_name_index');

    // Check constraint: email length must be at least 5 characters
    table.check('length(email) >= 5', [], 'users_email_length_check');
  });
};

exports.down = async function(knex) {
  await knex.schema.dropTableIfExists('users');
};
