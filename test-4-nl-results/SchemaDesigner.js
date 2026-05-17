const fs = require('fs');
const path = require('path');

class SchemaDesigner {
  /**
   * @param {string} planPath - path to the PLAN.md file (defaults to PLAN.md in the same directory)
   */
  constructor(planPath = path.join(__dirname, 'PLAN.md')) {
    this.planPath = planPath;
  }

  /**
   * Reads the PLAN.md file and parses it into a structured database schema representation.
   * The expected markdown structure:
   *   # Plan Name
   *   ## Entities
   *   - EntityName
   *   ### EntityName
   *   - fieldName: Type [optional constraints]
   *   ...
   *   ## Relationships
   *   - sourceEntity fieldName -> targetEntity
   *
   * @returns {Promise<object>} A schema object with tables, columns, types, and relationships.
   */
  async designSchema() {
    const markdown = await fs.promises.readFile(this.planPath, 'utf-8');
    const lines = markdown.split('\n');
    const schema = { tables: [] };
    let currentEntity = null;
    let mode = 'none'; // 'entities' or 'relationships'

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('## Entities') || trimmed.startsWith('## Entities:')) {
        mode = 'entities';
        continue;
      }
      if (trimmed.startsWith('## Relationships') || trimmed.startsWith('## Relationships:')) {
        mode = 'relationships';
        continue;
      }
      if (trimmed.startsWith('### ')) {
        // Entity header
        const entityName = trimmed.substring(4).trim();
        currentEntity = {
          name: entityName,
          columns: []
        };
        schema.tables.push(currentEntity);
        continue;
      }
      if (currentEntity && mode === 'entities' && trimmed.startsWith('- ')) {
        // field definition: - fieldName: Type [constraints]
        const fieldDef = trimmed.substring(2).trim();
        const colonIdx = fieldDef.indexOf(':');
        if (colonIdx !== -1) {
          const fieldName = fieldDef.substring(0, colonIdx).trim();
          const rest = fieldDef.substring(colonIdx + 1).trim();
          // split type and constraints
          const parts = rest.split(/\s+/);
          const type = parts[0] || 'String';
          const constraints = parts.slice(1).join(' ');
          currentEntity.columns.push({ name: fieldName, type, constraints });
        }
        continue;
      }
      if (mode === 'relationships' && trimmed.startsWith('- ')) {
        // relationship: - sourceEntity fieldName -> targetEntity
        const relDef = trimmed.substring(2).trim();
        const arrowIdx = relDef.indexOf('->');
        if (arrowIdx !== -1) {
          const leftPart = relDef.substring(0, arrowIdx).trim();
          const targetPart = relDef.substring(arrowIdx + 2).trim();
          const leftTokens = leftPart.split(/\s+/);
          if (leftTokens.length >= 2) {
            const sourceEntity = leftTokens[0];
            const fieldName = leftTokens[1];
            const targetEntity = targetPart.trim();
            // Find the source table and add a relationship entry
            const table = schema.tables.find(t => t.name === sourceEntity);
            if (table) {
              if (!table.relationships) table.relationships = [];
              table.relationships.push({ field: fieldName, target: targetEntity });
            }
          }
        }
      }
    }

    return schema;
  }
}

module.exports = SchemaDesigner;
