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
  assert.equal(extensionModule.canProxyPackagedActions({ attachMode: 'attach', transport: 'streamable-http' }), true);
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

  assert.equal(extensionModule.canProxyPackagedActions({ attachMode: 'attach', transport: 'sse' }), false);
  assert.match(
    extensionModule.getPackagedActionUnavailableReason({ attachMode: 'attach', transport: 'sse' }),
    /require streamable-http transport/i,
  );
  assert.equal(extensionModule.canRunLocalPackagedActions({ attachMode: 'launch' }), true);
});