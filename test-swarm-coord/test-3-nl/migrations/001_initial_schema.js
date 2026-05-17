exports.up = async function (knex) {
  await knex.raw('CREATE EXTENSION IF NOT EXISTS pgcrypto');

  await knex.schema.createTable('users', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('username', 50).notNullable().unique();
    table.string('email', 255).notNullable().unique();
    table.string('password_hash', 255).notNullable();
    table.string('display_name', 100).nullable();
    table.text('avatar_url').nullable();
    table.string('status', 20).notNullable().defaultTo('offline');
    table.timestamps(true, true);
    table.check("status IN ('online', 'away', 'offline')", [], 'chk_users_status');
  });

  await knex.schema.createTable('workspaces', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('name', 100).notNullable();
    table.string('slug', 100).notNullable().unique();
    table.uuid('owner_id').notNullable().references('id').inTable('users').onDelete('RESTRICT');
    table.timestamps(true, true);
  });

  await knex.schema.createTable('workspace_members', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('workspace_id').notNullable().references('id').inTable('workspaces').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.string('role', 20).notNullable().defaultTo('member');
    table.timestamp('joined_at').defaultTo(knex.fn.now());
    table.unique(['workspace_id', 'user_id']);
    table.check("role IN ('admin', 'member', 'guest')", [], 'chk_workspace_members_role');
  });

  await knex.schema.createTable('channels', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('workspace_id').notNullable().references('id').inTable('workspaces').onDelete('CASCADE');
    table.string('name', 100).notNullable();
    table.string('slug', 100).notNullable();
    table.string('type', 20).notNullable().defaultTo('public');
    table.uuid('created_by').notNullable().references('id').inTable('users').onDelete('RESTRICT');
    table.timestamps(true, true);
    table.unique(['workspace_id', 'slug']);
    table.check("type IN ('public', 'private', 'direct_message')", [], 'chk_channels_type');
  });

  await knex.schema.createTable('channel_members', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('channel_id').notNullable().references('id').inTable('channels').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.timestamp('last_read_at').nullable();
    table.unique(['channel_id', 'user_id']);
  });

  await knex.schema.createTable('messages', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('channel_id').notNullable().references('id').inTable('channels').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('RESTRICT');
    table.uuid('parent_id').nullable().references('id').inTable('messages').onDelete('SET NULL');
    table.text('content').nullable();
    table.string('type', 20).notNullable().defaultTo('text');
    table.timestamps(true, true);
    table.timestamp('deleted_at').nullable();
    table.check("type IN ('text', 'file', 'system')", [], 'chk_messages_type');
  });

  await knex.schema.createTable('reactions', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('message_id').notNullable().references('id').inTable('messages').onDelete('CASCADE');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.string('emoji', 50).notNullable();
    table.timestamp('created_at').defaultTo(knex.fn.now());
    table.unique(['message_id', 'user_id', 'emoji']);
  });

  await knex.schema.createTable('files', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('message_id').nullable().references('id').inTable('messages').onDelete('SET NULL');
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('RESTRICT');
    table.string('original_name', 255).notNullable();
    table.text('storage_path').notNullable();
    table.string('mime_type', 100).notNullable();
    table.bigInteger('size_bytes').notNullable();
    table.timestamp('created_at').defaultTo(knex.fn.now());
    table.check('size_bytes >= 0', [], 'chk_files_size_bytes');
  });

  await knex.schema.createTable('notifications', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.uuid('user_id').notNullable().references('id').inTable('users').onDelete('CASCADE');
    table.string('type', 30).notNullable();
    table.uuid('reference_id').nullable();
    table.timestamp('read_at').nullable();
    table.timestamp('created_at').defaultTo(knex.fn.now());
    table.check("type IN ('mention', 'reply', 'workspace_invite')", [], 'chk_notifications_type');
  });

  await knex.schema.createTable('roles_permissions', (table) => {
    table.uuid('id').primary().defaultTo(knex.raw('gen_random_uuid()'));
    table.string('role_name', 50).notNullable();
    table.string('resource_type', 50).notNullable();
    table.string('action', 50).notNullable();
    table.jsonb('conditions').nullable();
    table.unique(['role_name', 'resource_type', 'action']);
  });

  await knex.schema.raw('CREATE INDEX idx_users_username ON users(username)');
  await knex.schema.raw('CREATE INDEX idx_users_email ON users(email)');
  await knex.schema.raw('CREATE INDEX idx_users_status ON users(status)');
  await knex.schema.raw('CREATE INDEX idx_workspaces_owner_id ON workspaces(owner_id)');
  await knex.schema.raw('CREATE INDEX idx_workspaces_slug ON workspaces(slug)');
  await knex.schema.raw('CREATE INDEX idx_workspace_members_workspace_id ON workspace_members(workspace_id)');
  await knex.schema.raw('CREATE INDEX idx_workspace_members_user_id ON workspace_members(user_id)');
  await knex.schema.raw('CREATE INDEX idx_channels_workspace_id ON channels(workspace_id)');
  await knex.schema.raw('CREATE INDEX idx_channels_workspace_slug ON channels(workspace_id, slug)');
  await knex.schema.raw('CREATE INDEX idx_channel_members_channel_id ON channel_members(channel_id)');
  await knex.schema.raw('CREATE INDEX idx_channel_members_user_id ON channel_members(user_id)');
  await knex.schema.raw('CREATE INDEX idx_messages_channel_id ON messages(channel_id)');
  await knex.schema.raw('CREATE INDEX idx_messages_channel_created_at ON messages(channel_id, created_at)');
  await knex.schema.raw('CREATE INDEX idx_messages_user_id ON messages(user_id)');
  await knex.schema.raw('CREATE INDEX idx_messages_parent_id ON messages(parent_id)');
  await knex.schema.raw('CREATE INDEX idx_messages_created_at ON messages(created_at)');
  await knex.schema.raw('CREATE INDEX idx_messages_deleted_at ON messages(deleted_at) WHERE deleted_at IS NULL');
  await knex.schema.raw('CREATE INDEX idx_reactions_message_id ON reactions(message_id)');
  await knex.schema.raw('CREATE INDEX idx_reactions_user_id ON reactions(user_id)');
  await knex.schema.raw('CREATE INDEX idx_files_message_id ON files(message_id)');
  await knex.schema.raw('CREATE INDEX idx_files_user_id ON files(user_id)');
  await knex.schema.raw('CREATE INDEX idx_notifications_user_id ON notifications(user_id)');
  await knex.schema.raw('CREATE INDEX idx_notifications_user_created_at ON notifications(user_id, created_at DESC)');
  await knex.schema.raw('CREATE INDEX idx_notifications_read_at ON notifications(read_at) WHERE read_at IS NULL');
  await knex.schema.raw('CREATE INDEX idx_notifications_type ON notifications(type)');
  await knex.schema.raw('CREATE INDEX idx_roles_permissions_role_name ON roles_permissions(role_name)');
  await knex.schema.raw('CREATE INDEX idx_roles_permissions_resource_type ON roles_permissions(resource_type)');
};

exports.down = async function (knex) {
  await knex.schema.dropTableIfExists('roles_permissions');
  await knex.schema.dropTableIfExists('notifications');
  await knex.schema.dropTableIfExists('files');
  await knex.schema.dropTableIfExists('reactions');
  await knex.schema.dropTableIfExists('messages');
  await knex.schema.dropTableIfExists('channel_members');
  await knex.schema.dropTableIfExists('channels');
  await knex.schema.dropTableIfExists('workspace_members');
  await knex.schema.dropTableIfExists('workspaces');
  await knex.schema.dropTableIfExists('users');
};
