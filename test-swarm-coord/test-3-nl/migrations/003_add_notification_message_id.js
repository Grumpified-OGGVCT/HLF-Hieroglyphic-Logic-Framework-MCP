exports.up = async function (knex) {
  await knex.schema.table('notifications', (table) => {
    table.uuid('message_id').nullable().references('id').inTable('messages').onDelete('SET NULL');
  });
  await knex.raw('CREATE INDEX IF NOT EXISTS idx_notifications_message_id ON notifications(message_id)');
};

exports.down = async function (knex) {
  await knex.raw('DROP INDEX IF EXISTS idx_notifications_message_id');
  await knex.schema.table('notifications', (table) => {
    table.dropColumn('message_id');
  });
};
