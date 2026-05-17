function generateSql(commands) {
  let sql = '';
  for (let cmd of commands) {
    switch (cmd.type) {
      case 'create_table':
        sql += `CREATE TABLE ${cmd.table} (\n  ${cmd.columns.join(',\n  ')}\n);\n\n`;
        break;
      case 'add_column':
        sql += `ALTER TABLE ${cmd.table} ADD COLUMN ${cmd.columnDef};\n\n`;
        break;
      case 'drop_table':
        sql += `DROP TABLE IF EXISTS ${cmd.table};\n\n`;
        break;
      default:
        throw new Error(`Unknown command type: ${cmd.type}`);
    }
  }
  return sql.trim();
}

module.exports = { generateSql };