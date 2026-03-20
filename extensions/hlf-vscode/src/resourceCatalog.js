const fs = require('node:fs');
const path = require('node:path');

const { getWorkspaceRoot } = require('./config');

const RESOURCE_PATTERN = /@mcp\.resource\("([^"]+)"\)/g;

const FALLBACK_RESOURCES = [
  'hlf://status/benchmark_artifacts',
  'hlf://status/active_profiles',
  'hlf://status/profile_evidence/{profile_name}',
  'hlf://status/profile_capability_catalog',
  'hlf://status/model_catalog',
  'hlf://status/model_catalog/{agent_id}',
  'hlf://status/align',
  'hlf://status/formal_verifier',
  'hlf://status/governed_route',
  'hlf://status/governed_route/{agent_id}',
  'hlf://status/instinct',
  'hlf://status/instinct/{mission_id}',
  'hlf://status/witness_governance',
  'hlf://status/witness_governance/{subject_agent_id}',
];

function getServerResourcesPath() {
  const workspaceRoot = getWorkspaceRoot();
  if (!workspaceRoot) {
    return undefined;
  }

  return path.join(workspaceRoot, 'hlf_mcp', 'server_resources.py');
}

function classifyResource(uri) {
  if (uri.startsWith('hlf://status/')) {
    return 'status';
  }
  if (uri.startsWith('hlf://governance/')) {
    return 'governance';
  }
  return 'core';
}

function extractResourceUris(sourceText) {
  const resources = [];
  for (const match of sourceText.matchAll(RESOURCE_PATTERN)) {
    resources.push(match[1]);
  }
  return resources;
}

function getPackagedResourceCatalog() {
  const serverResourcesPath = getServerResourcesPath();
  let resourceUris = [...FALLBACK_RESOURCES];

  if (serverResourcesPath && fs.existsSync(serverResourcesPath)) {
    try {
      const sourceText = fs.readFileSync(serverResourcesPath, 'utf8');
      const extracted = extractResourceUris(sourceText);
      if (extracted.length > 0) {
        resourceUris = extracted;
      }
    } catch {
      // Fall back to the baked-in status resources when the workspace file cannot be read.
    }
  }

  return resourceUris
    .map((uri) => ({ uri, category: classifyResource(uri) }))
    .sort((left, right) => left.uri.localeCompare(right.uri));
}

module.exports = {
  getPackagedResourceCatalog,
  getServerResourcesPath,
};