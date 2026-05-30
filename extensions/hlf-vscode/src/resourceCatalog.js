const fs = require('node:fs');
const path = require('node:path');

const { getWorkspaceRoot } = require('./config');

const RESOURCE_PATTERN = /@mcp\.resource\("([^"]+)"\)/g;

const SG_URI_PATTERN = /sg:\/\/[a-zA-Z0-9._\/{}\-]+/g;

const FALLBACK_RESOURCES = [
  // ── hlf:// (backward-compat) ──────────────────────────────
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
  'hlf://status/provenance_contract',
  'hlf://status/memory_governance',
  // ── sg:// (SwarmGlass canonical) ──────────────────────────
  'sg://status/benchmark_artifacts',
  'sg://status/active_profiles',
  'sg://status/profile_evidence/{profile_name}',
  'sg://status/profile_capability_catalog',
  'sg://status/model_catalog',
  'sg://status/model_catalog/{agent_id}',
  'sg://status/align',
  'sg://status/formal_verifier',
  'sg://status/governed_route',
  'sg://status/governed_route/{agent_id}',
  'sg://status/instinct',
  'sg://status/instinct/{mission_id}',
  'sg://status/witness_governance',
  'sg://status/witness_governance/{subject_agent_id}',
  'sg://status/provenance_contract',
  'sg://status/memory_governance',
];

const SG_TOOL_NAMES = [
  'sg_orchestrate',
  'sg_memory_store',
  'sg_memory_governed_recall',
  'sg_memory_query',
  'sg_memory_dream_run',
  'sg_memory_register_evidence_bundle',
  'sg_memory_hks_research',
  'sg_overwatch_scan',
  'sg_overwatch_health',
  'sg_overwatch_status',
  'sg_overwatch_terminate',
  'sg_secure_secret_store',
  'sg_secure_secret_retrieve',
  'sg_secure_secret_rotate',
  'sg_coordinate_orchestration_contract',
  'sg_coordinate_handoff_chain',
  'sg_audit_event_log',
  'sg_audit_merkle_verify',
  'sg_audit_evidence_show',
  'sg_model_version_check',
  'sg_observe_drift',
];

function getServerResourcesPath() {
  const workspaceRoot = getWorkspaceRoot();
  if (!workspaceRoot) {
    return undefined;
  }

  return path.join(workspaceRoot, 'hlf_mcp', 'server_resources.py');
}

function classifyResource(uri) {
  if (uri.startsWith('hlf://status/') || uri.startsWith('sg://status/')) {
    return 'status';
  }
  if (uri.startsWith('hlf://governance/') || uri.startsWith('sg://governance/')) {
    return 'governance';
  }
  if (uri.startsWith('sg://')) {
    return 'sg-core';
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

function getSgToolCatalog() {
  return SG_TOOL_NAMES.map((name) => ({
    uri: `sg://tool/${name}`,
    category: 'sg-tool',
  }));
}

function getSgUriCatalog() {
  return FALLBACK_RESOURCES
    .filter((uri) => uri.startsWith('sg://'))
    .map((uri) => ({ uri, category: classifyResource(uri) }))
    .sort((left, right) => left.uri.localeCompare(right.uri));
}

module.exports = {
  getPackagedResourceCatalog,
  getSgToolCatalog,
  getSgUriCatalog,
  getServerResourcesPath,
  SG_TOOL_NAMES,
};