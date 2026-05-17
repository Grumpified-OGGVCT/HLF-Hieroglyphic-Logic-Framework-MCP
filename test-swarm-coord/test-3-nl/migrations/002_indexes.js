exports.up = async function (knex) {
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_workspace_members_workspace_id ON workspace_members(workspace_id)');
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_workspace_members_user_id ON workspace_members(user_id)');

  await knex.raw('CREATE INDEX IF NOT EXISTS idx_channel_members_channel_id ON channel_members(channel_id)');
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_channel_members_user_id ON channel_members(user_id)');

  await knex.raw('CREATE INDEX IF NOT EXISTS idx_messages_channel_created_at ON messages(channel_id, created_at)');
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_messages_parent_id ON messages(parent_id)');
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)');

  await knex.raw('CREATE INDEX IF NOT EXISTS idx_reactions_message_id ON reactions(message_id)');

  await knex.raw('CREATE INDEX IF NOT EXISTS idx_files_message_id ON files(message_id)');

  await knex.raw('CREATE INDEX IF NOT EXISTS idx_notifications_user_id_read_at ON notifications(user_id, read_at)');
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_notifications_reference_id ON notifications(reference_id)');

  await knex.raw('CREATE EXTENSION IF NOT EXISTS pg_trgm');
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_messages_content_trgm ON messages USING gin (content gin_trgm_ops)');
};

exports.down = async function (knex) {
  await knex.raw('DROP INDEX IF EXISTS idx_messages_content_trgm');
  await knex.raw('DROP INDEX IF EXISTS idx_notifications_reference_id');
  await knex.raw('DROP INDEX IF EXISTS idx_notifications_user_id_read_at');
  await knex.raw('DROP INDEX IF EXISTS idx_files_message_id');
  await knex.raw('DROP INDEX IF EXISTS idx_reactions_message_id');
  await knex.raw('DROP INDEX IF EXISTS idx_messages_user_id');
  await knex.raw('DROP INDEX IF EXISTS idx_messages_parent_id');
  await knex.raw('DROP INDEX IF EXISTS idx_messages_channel_created_at');
  await knex.raw('DROP INDEX IF EXISTS idx_channel_members_user_id');
  await knex.raw('DROP INDEX IF EXISTS idx_channel_members_channel_id');
  await knex.raw('DROP INDEX IF EXISTS idx_workspace_members_user_id');
  await knex.raw('DROP INDEX IF EXISTS idx_workspace_members_workspace_id');
};
