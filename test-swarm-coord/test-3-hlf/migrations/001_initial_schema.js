/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.up = async function (knex) {
  await knex.raw('CREATE EXTENSION IF NOT EXISTS "pgcrypto"');

  await knex.schema.createTable('users', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('username', 50).notNullable().unique();
    table.string('email', 255).notNullable().unique();
    table.text('password_hash').notNullable();
    table.string('display_name', 100);
    table.text('avatar_url');
    table.enum('status', ['online', 'away', 'offline']).notNullable().defaultTo('offline');
    table.timestamps(true, true);
  });

  await knex.schema.createTable('workspaces', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('name', 100).notNullable();
    table.string('slug', 100).notNullable().unique();
    table.uuid('owner_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.timestamps(true, true);
  });

  await knex.schema.createTable('workspace_members', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('workspace_id').notNullable().references('id').inTable('workspaces').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.enum('role', ['admin', 'member', 'guest']).notNullable().defaultTo('member');
    table.timestamp('joined_at').notNullable().defaultTo(knex.fn.now());
    table.unique(['workspace_id', 'user_id']);
  });

  await knex.schema.createTable('channels', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('workspace_id').notNullable().references('id').inTable('workspaces').onDelete('CASCADE');
    table.string('name', 100).notNullable();
    table.string('slug', 100).notNullable();
    table.enum('type', ['public', 'private', 'direct_message']).notNullable().defaultTo('public');
    table.uuid('created_by').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.timestamps(true, true);
    table.unique(['workspace_id', 'slug']);
  });

  await knex.schema.createTable('channel_members', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('channel_id').notNullable().references('id').inTable('channels').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.timestamp('last_read_at');
    table.unique(['channel_id', 'user_id']);
  });

  await knex.schema.createTable('messages', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('channel_id').notNullable().references('id').inTable('channels').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.uuid('parent_id').references('id').inTable('messages').onDelete('CASCADE');
    table.text('content').notNullable();
    table.enum('type', ['text', 'file', 'system']).notNullable().defaultTo('text');
    table.timestamps(true, true);
    table.timestamp('deleted_at');
    table.index(['channel_id', 'created_at']);
    table.index(['parent_id']);
  });

  await knex.schema.createTable('reactions', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('message_id').notNullable().references('id').inTable('messages').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.string('emoji', 50).notNullable();
    table.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
    table.unique(['message_id', 'user_id', 'emoji']);
  });

  await knex.schema.createTable('files', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('message_id').references('id').inTable('messages').onDelete('SET NULL');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.string('original_name', 255).notNullable();
    table.text('storage_path').notNullable();
    table.string('mime_type', 100).notNullable();
    table.bigInteger('size_bytes').notNullable();
    table.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
    table.index(['message_id']);
    table.index(['user_id']);
  });

  await knex.schema.createTable('notifications', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.enum('type', ['mention', 'reply', 'workspace_invite']).notNullable();
    table.uuid('reference_id').notNullable();
    table.timestamp('read_at');
    table.timestamp('created_at').notNullable().defaultTo(knex.fn.now());
    table.index(['user_id', 'created_at']);
    table.index(['user_id', 'read_at']);
  });

  await knex.schema.createTable('roles_permissions', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('role_name', 50).notNullable();
    table.string('resource_type', 50).notNullable();
    table.string('action', 50).notNullable();
    table.jsonb('conditions');
    table.unique(['role_name', 'resource_type', 'action']);
    table.index(['role_name']);
    table.index(['resource_type', 'action']);
  });
};

/**
 * @param { import("knex").Knex } knex
 * @returns { Promise<void> }
 */
exports.down = async function (knex) {
  const tables = [
    'roles_permissions',
    'notifications',
    'files',
    'reactions',
    'messages',
    'channel_members',
    'channels',
    'workspace_members',
    'workspaces',
    'users',
  ];
  for (const t of tables) {
    await knex.schema.dropTableIfExists(t);
  }
};
