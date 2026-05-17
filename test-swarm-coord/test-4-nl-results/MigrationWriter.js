const { parsePlanFile } = require('./planParser');
const { generateSql } = require('./sqlGenerator');
const fs = require('fs');

function writeMigration(planFilePath, outputFilePath) {
  const commands = parsePlanFile(planFilePath);
  const sql = generateSql(commands);
  fs.writeFileSync(outputFilePath, sql, 'utf8');
  console.log(`Migration file written to ${outputFilePath}`);
}

module.exports = { writeMigration };