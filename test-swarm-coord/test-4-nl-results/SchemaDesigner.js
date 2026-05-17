class SchemaDesigner {
  /**
   * Generate a JSON schema representation from a natural language description.
   * This is a stub implementation that returns a static example.
   * In a real implementation, you'd call an AI service.
   * @param {string} description
   * @returns {object} schema object with tables and columns
   */
  generateFromDescription(description) {
    // TODO: Replace with actual AI-based generation.
    // For now, return a simple example schema.
    return {
      tables: [
        {
          name: 'users',
          columns: [
            { name: 'id', type: 'INTEGER', primaryKey: true, autoIncrement: true },
            { name: 'name', type: 'VARCHAR(255)', nullable: false },
            { name: 'email', type: 'VARCHAR(255)', unique: true, nullable: false },
            { name: 'created_at', type: 'TIMESTAMP', defaultValue: 'CURRENT_TIMESTAMP' }
          ]
        },
        {
          name: 'posts',
          columns: [
            { name: 'id', type: 'INTEGER', primaryKey: true, autoIncrement: true },
            { name: 'user_id', type: 'INTEGER', references: { table: 'users', column: 'id' } },
            { name: 'title', type: 'VARCHAR(255)', nullable: false },
            { name: 'content', type: 'TEXT' },
            { name: 'created_at', type: 'TIMESTAMP', defaultValue: 'CURRENT_TIMESTAMP' }
          ]
        }
      ]
    };
  }

  /**
   * Convert a JSON schema object into SQL CREATE statements.
   * @param {object} schema - The schema object with tables and columns.
   * @returns {string} SQL DDL statements.
   */
  toSQL(schema) {
    if (!schema || !Array.isArray(schema.tables)) {
      throw new Error('Invalid schema: must contain a "tables" array.');
    }

    const statements = schema.tables.map((table) => {
      const columns = table.columns.map((col) => {
        let def = `${col.name} ${col.type}`;
        if (col.primaryKey) {
          def += ' PRIMARY KEY';
          if (col.autoIncrement) def += ' AUTOINCREMENT';
        }
        if (col.notNull || col.nullable === false) def += ' NOT NULL';
        if (col.unique) def += ' UNIQUE';
        if (col.defaultValue !== undefined) def += ` DEFAULT ${col.defaultValue}`;
        if (col.references) {
          const ref = col.references;
          if (ref.table && ref.column) {
            def += ` REFERENCES ${ref.table}(${ref.column})`;
          }
        }
        return def;
      }).join(',\n  ');

      return `CREATE TABLE ${table.name} (\n  ${columns}\n);`;
    });

    return statements.join('\n\n');
  }

  /**
   * Validate a schema for common issues.
   * @param {object} schema
   * @returns {{ valid: boolean, errors: string[] }}
   */
  validateSchema(schema) {
    const errors = [];
    if (!schema || !Array.isArray(schema.tables)) {
      errors.push('Schema must have a "tables" array.');
      return { valid: false, errors };
    }

    const tableNames = new Set();
    schema.tables.forEach((table, index) => {
      if (!table.name) {
        errors.push(`Table at index ${index} is missing a name.`);
        return;
      }
      if (tableNames.has(table.name)) {
        errors.push(`Duplicate table name: "${table.name}".`);
      } else {
        tableNames.add(table.name);
      }

      if (!Array.isArray(table.columns) || table.columns.length === 0) {
        errors.push(`Table "${table.name}" must have at least one column.`);
        return;
      }

      const columnNames = new Set();
      table.columns.forEach((col) => {
        if (!col.name) {
          errors.push(`A column in table "${table.name}" is missing a name.`);
        } else {
          if (columnNames.has(col.name)) {
            errors.push(`Duplicate column name "${col.name}" in table "${table.name}".`);
          } else {
            columnNames.add(col.name);
          }
        }
        if (col.references) {
          const ref = col.references;
          if (!ref.table || !ref.column) {
            errors.push(`Column "${col.name}" in table "${table.name}" has incomplete reference.`);
          } else if (!tableNames.has(ref.table)) {
            errors.push(`Column "${col.name}" references unknown table "${ref.table}".`);
          }
        }
      });
    });

    return { valid: errors.length === 0, errors };
  }
}

module.exports = SchemaDesigner;
