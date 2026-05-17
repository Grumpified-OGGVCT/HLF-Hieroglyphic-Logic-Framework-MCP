const fs = require('fs');
const path = require('path');

/**
 * DevOpsAssembler - reads a PLAN.md file and creates filesystem artifacts.
 * Implementation: CommonJS, no external dependencies.
 */

/**
 * Parse PLAN.md content into an array of file specifications.
 * Supports two formats:
 * 1. ### file: <relative/path>
 *    ```language
 *    content
 *    ```
 * 2. ## File: <relative/path>
 *    content (all lines until next heading or end)
 *
 * @param {string} planContent
 * @returns {Array<{ filePath: string, content: string }>}
 */
function parsePlan(planContent) {
  const files = [];
  const lines = planContent.split('\n');
  let i = 0;

  while (i < lines.length) {
    // Match headings that indicate a file
    const headingMatch = lines[i].match(/^#{2,3}\s+file:\s*(.+)/i);
    if (headingMatch) {
      const filePath = headingMatch[1].trim();
      i++;
      let content = '';

      // Check if next line is a fenced code block
      if (i < lines.length && lines[i].startsWith('```')) {
        const fence = lines[i];
        i++; // skip opening fence
        while (i < lines.length && !lines[i].startsWith('```')) {
          content += (content ? '\n' : '') + lines[i];
          i++;
        }
        if (i < lines.length && lines[i].startsWith('```')) {
          i++; // skip closing fence
        }
      } else {
        // Collect lines until next heading or end
        while (i < lines.length && !lines[i].match(/^#{2,3}\s+/)) {
          content += (content ? '\n' : '') + lines[i];
          i++;
        }
      }

      files.push({ filePath, content });
    } else {
      i++;
    }
  }

  return files;
}

/**
 * Write all files from the plan to the target directory (default: current working dir).
 * @param {string} planPath - path to PLAN.md
 * @param {string} [outDir] - base directory for output
 */
function assemble(planPath, outDir = process.cwd()) {
  if (!fs.existsSync(planPath)) {
    throw new Error(`PLAN.md not found at ${planPath}`);
  }

  const planContent = fs.readFileSync(planPath, 'utf-8');
  const files = parsePlan(planContent);

  files.forEach(({ filePath, content }) => {
    const fullPath = path.resolve(outDir, filePath);
    const dir = path.dirname(fullPath);

    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    fs.writeFileSync(fullPath, content, 'utf-8');
    console.log(`Created: ${fullPath}`);
  });

  console.log(`DevOpsAssembler completed: ${files.length} file(s) assembled.`);
}

// If invoked directly, read PLAN.md from cwd
if (require.main === module) {
  const planPath = path.resolve(process.cwd(), 'PLAN.md');
  try {
    assemble(planPath);
  } catch (err) {
    console.error('DevOpsAssembler error:', err.message);
    process.exit(1);
  }
}

module.exports = { assemble, parsePlan };
