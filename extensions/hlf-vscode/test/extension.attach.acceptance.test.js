const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { loadWithMocks } = require('./helpers/loadWithMocks');

test('extension attach acceptance: streamable-http attach mode proxies packaged actions', () => {
  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {},
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {},
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './operatorPanel': { OperatorPanelProvider: class {} },
    './packagedActions': {},
    './secrets': {},
    './trustPanel': { TrustPanel: class {} },
  });

  assert.equal(extensionModule.canRunLocalPackagedActions({ attachMode: 'attach' }), false);
  assert.equal(extensionModule.canUseLiveMcpActions({ attachMode: 'attach', transport: 'streamable-http' }), true);
  assert.equal(extensionModule.getPackagedActionUnavailableReason({ attachMode: 'attach', transport: 'streamable-http' }), undefined);
  assert.deepEqual(extensionModule.buildAttachModeActionRequest(['resource', '--uri', 'hlf://status/formal_verifier', '--json']), {
    kind: 'resource',
    uri: 'hlf://status/formal_verifier',
  });
  assert.deepEqual(extensionModule.buildAttachModeActionRequest(['test-summary', '--json']), {
    kind: 'tool',
    name: 'hlf_test_suite_summary',
    arguments: {},
  });
  assert.deepEqual(extensionModule.buildAttachModeActionRequest(['weekly-evidence-summary', '--json']), {
    kind: 'tool',
    name: 'hlf_weekly_evidence_summary',
    arguments: {},
  });
  assert.deepEqual(extensionModule.buildAttachModeActionRequest(['provenance-summary', '--json']), {
    kind: 'resource',
    uri: 'hlf://status/provenance_contract',
  });
  assert.deepEqual(extensionModule.buildAttachModeActionRequest(['memory-govern', '--action', 'revoke', '--fact-id', '7', '--operator-summary', 'revoked', '--reason', 'operator_ui_revoke', '--operator-id', 'alice', '--operator-display-name', 'Alice Example', '--operator-channel', 'vscode.desktop.operator_panel', '--json']), {
    kind: 'tool',
    name: 'hlf_memory_govern',
    arguments: {
      action: 'revoke',
      fact_id: 7,
      sha256: undefined,
      operator_summary: 'revoked',
      reason: 'operator_ui_revoke',
      operator_id: 'alice',
      operator_display_name: 'Alice Example',
      operator_channel: 'vscode.desktop.operator_panel',
    },
  });
  assert.deepEqual(extensionModule.buildAttachModeActionRequest(['do', '--intent', 'review', '--tier', 'forge', '--dry-run', '--show-hlf', '--json']), {
    kind: 'tool',
    name: 'hlf_do',
    arguments: {
      intent: 'review',
      tier: 'forge',
      dry_run: true,
      show_hlf: true,
    },
  });
});

test('extension attach acceptance: sse attach mode still reports packaged action unavailability', () => {
  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {},
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {},
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './operatorPanel': { OperatorPanelProvider: class {} },
    './packagedActions': {},
    './secrets': {},
    './trustPanel': { TrustPanel: class {} },
  });

  assert.equal(extensionModule.canUseLiveMcpActions({ attachMode: 'attach', transport: 'sse' }), false);
  assert.match(
    extensionModule.getPackagedActionUnavailableReason({ attachMode: 'attach', transport: 'sse' }),
    /require streamable-http transport/i,
  );
  assert.equal(extensionModule.canRunLocalPackagedActions({ attachMode: 'launch' }), true);
});

test('extension attach acceptance: live MCP action retries after stale session failure', async () => {
  let createdClients = 0;
  let readCalls = 0;
  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {},
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
      getSettings() {
        return { transport: 'streamable-http', attachMode: 'attach' };
      },
      getWorkspaceRoot() {
        return 'C:\\repo';
      },
    },
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': {
      StreamableHttpMcpClient: class {
        constructor() {
          createdClients += 1;
        }

        async readResource() {
          readCalls += 1;
          if (readCalls === 1) {
            throw new Error('stale session');
          }
          return {
            contents: [{ text: JSON.stringify({ status: 'ok', source: 'live' }) }],
          };
        }
      },
    },
    './operatorPanel': { OperatorPanelProvider: class {}, interventionMatchesTarget() { return false; } },
    './packagedActions': {},
    './secrets': {},
    './trustPanel': { TrustPanel: class {} },
  });

  extensionModule.resetLiveMcpClient();
  const result = await extensionModule.runLiveMcpPackagedAction({
    settings: { transport: 'streamable-http', attachMode: 'attach' },
    outputChannel: { appendLine() {} },
    args: ['resource', '--uri', 'hlf://status/provenance_contract', '--json'],
    title: 'HLF Provenance Contract',
    secretHeaders: {},
  });

  assert.equal(result.ok, true);
  assert.deepEqual(result.parsed, { status: 'ok', source: 'live' });
  assert.equal(createdClients, 2);
  assert.equal(readCalls, 2);
});

test('extension attach acceptance: trust panel failure section shapes partial-error payloads', () => {
  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {},
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {},
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './operatorPanel': { OperatorPanelProvider: class {}, interventionMatchesTarget() { return false; } },
    './packagedActions': {},
    './secrets': {},
    './trustPanel': { TrustPanel: class {} },
  });

  const section = extensionModule.buildTrustPanelFailureSection(
    'Memory Provenance',
    'Packaged provenance contract across memory, governance, witness, and evidence surfaces.',
    new Error('timeout'),
  );

  assert.equal(section.title, 'Memory Provenance');
  assert.equal(section.body.status, 'unavailable');
  assert.equal(section.body.error, 'timeout');
});

test('extension attach acceptance: provenance trust sections expose pointer and supersession subsections', () => {
  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {},
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {},
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './operatorPanel': { OperatorPanelProvider: class {} },
    './packagedActions': {},
    './secrets': {},
    './trustPanel': { TrustPanel: class {} },
  });

  const sections = extensionModule.buildProvenanceTrustSections({
    provenance_contract: {
      summary: { memory_fact_count: 4 },
      memory_state_counts: { active: 2, revoked: 1 },
      pointer_chain_summary: {
        recent_pointers: [
          { pointer: '&topic-1:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', supersedes: '', superseded: false },
          { pointer: '&topic-2:SHA256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', supersedes: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', superseded: false },
        ],
      },
    },
  });

  assert.equal(sections[0].title, 'Memory Provenance');
  assert.equal(sections[1].title, 'Pointer Chains');
  assert.equal(sections[2].title, 'Supersession Lineage');
  assert.equal(sections[2].body.length, 1);
});

test('extension attach acceptance: governance intervention trust section exposes recent interventions', () => {
  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {},
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {},
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './memoryGovernance': {
      getAllowedGovernanceActions() { return ['revoke', 'tombstone']; },
      isGovernanceActionAllowed() { return true; },
    },
    './operatorPanel': {
      OperatorPanelProvider: class {},
      interventionMatchesTarget(intervention, target) {
        const targetId = target?.id ?? target?.factId;
        if (targetId !== undefined && targetId !== null && String(intervention?.subject_id || '') === String(targetId)) {
          return true;
        }
        if (target?.sha256 && intervention?.sha256 && String(target.sha256) === String(intervention.sha256)) {
          return true;
        }
        if (target?.pointer && intervention?.pointer && String(target.pointer) === String(intervention.pointer)) {
          return true;
        }
        return false;
      },
    },
    './packagedActions': {},
    './secrets': {},
    './trustPanel': { TrustPanel: class {} },
  });

  const sections = extensionModule.buildGovernanceInterventionTrustSections({
    memory_governance: {
      memory_state_counts: { active: 2, revoked: 1 },
      recent_interventions: [
        {
          action: 'memory_revoke',
          kind: 'memory_governance',
          subject_id: '7',
          pointer: '&governance-7:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          sha256: 'a'.repeat(64),
        },
      ],
      recent_targets: [
        {
          id: 7,
          topic: 'governance',
          state: 'revoked',
          pointer: '&governance-7:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
          sha256: 'a'.repeat(64),
          operator_identity: {
            operator_id: 'alice',
            operator_display_name: 'Alice Example',
            operator_channel: 'vscode.desktop.operator_panel',
          },
        },
      ],
    },
  });

  assert.equal(sections[0].title, 'Latest Governance Interventions');
  assert.equal(sections[0].body.recent_interventions.length, 1);
  assert.equal(sections[0].body.recent_interventions[0].action, 'memory_revoke');
  assert.equal(sections[1].title, 'Target Intervention History: &governance-7:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa');
  assert.equal(sections[1].body.target.id, 7);
  assert.equal(sections[1].body.recent_interventions.length, 1);
});