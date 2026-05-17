const fs = require('fs');

function parsePlanFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const lines = content.split('\n');
  const commands = [];
  for (let line of lines) {
    line = line.trim();
    if (!line || line.startsWith('#')) continue;
    let command = parseLine(line);
    if (command) commands.push(command);
  }
  return commands;
}

function parseLine(line) {
  const parts = line.split(' ');
  const command = parts[0];
  if (command.startsWith('table:')) {
    // table:tableName create columns(...)
    const tableMatch = command.match(/^table:(\w+)$/);
    if (!tableMatch) throw new Error('Invalid table command: ' + line);
    const tableName = tableMatch[1];
    const action = parts[1];
    if (action === 'create') {
      const columnsStr = parts.slice(3).join(' '); // skip "columns" keyword
      const columnsStrTrimmed = columnsStr.substring(columnsStr.indexOf('(') + 1, columnsStr.lastIndexOf(')')).trim();
      const columnDefs = columnsStrTrimmed.split(',').map(def => def.trim()).filter(Boolean);
      return { type: 'create_table', table: tableName, columns: columnDefs };
    }
  } else if (command === 'add' && parts[1] === 'column:') {
    // add column:users age INT
    const tablePart = parts[1]; // "column:users"
    if (!tablePart.startsWith('column:')) throw new Error('Invalid add column: ' + line);
    const tableName = tablePart.replace('column:', '');
    const columnDef = parts.slice(2).join(' ');
    return { type: 'add_column', table: tableName, columnDef };
  } else if (command === 'drop' && parts[1] === 'table:') {
    const tableName = parts[2];
    return { type: 'drop_table', table: tableName };
  }
  return null;
}

module.exports = { parsePlanFile };