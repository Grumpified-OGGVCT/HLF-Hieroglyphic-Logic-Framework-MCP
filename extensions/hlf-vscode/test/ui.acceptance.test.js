const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { loadWithMocks } = require('./helpers/loadWithMocks');

test('ui acceptance: claim-lane sections expose current bridge and vision context', () => {
  const claimLanes = require(path.join(__dirname, '..', 'src', 'claimLanes.js'));
  const sections = claimLanes.getClaimLaneSections();

  assert.equal(sections[0].title, 'Current-True');
  assert.equal(sections[1].title, 'Bridge-True');
  assert.equal(sections[2].title, 'Vision-True');
  assert.ok(sections[3].body.some((entry) => entry.includes('second HLF implementation line')));
});

test('ui acceptance: trust panel escapes markup in rendered evidence', () => {
  const createdPanels = [];
  const { TrustPanel } = loadWithMocks(path.join(__dirname, '..', 'src', 'trustPanel.js'), {
    vscode: {
      window: {
        createWebviewPanel() {
          const panel = {
            webview: { html: '' },
            onDidDispose() {},
            reveal() {},
          };
          createdPanels.push(panel);
          return panel;
        },
      },
      ViewColumn: { Beside: 2 },
    },
  });

  const trustPanel = new TrustPanel({});
  trustPanel.show('Trust', [{ title: 'Route <Lane>', subtitle: 'unsafe & raw', body: '<script>alert(1)</script>' }]);

  const html = createdPanels[0].webview.html;
  assert.match(html, /Route &lt;Lane&gt;/);
  assert.match(html, /unsafe &amp; raw/);
  assert.doesNotMatch(html, /<script>alert\(1\)<\/script>/);
});

test('ui acceptance: operator panel exposes claim-lane section', async () => {
  class MockTreeItem {
    constructor(label, collapsibleState) {
      this.label = label;
      this.collapsibleState = collapsibleState;
    }
  }

  class MockThemeIcon {
    constructor(id) {
      this.id = id;
    }
  }

  class MockEventEmitter {
    constructor() {
      this.event = () => {};
    }

    fire() {}
  }

  const vscodeMock = {
    TreeItem: MockTreeItem,
    ThemeIcon: MockThemeIcon,
    EventEmitter: MockEventEmitter,
    TreeItemCollapsibleState: {
      None: 0,
      Expanded: 2,
    },
    Uri: {
      file(filePath) {
        return { fsPath: filePath };
      },
    },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: 'C:\\repo' } }],
    },
  };

  const { OperatorPanelProvider } = loadWithMocks(path.join(__dirname, '..', 'src', 'operatorPanel.js'), {
    vscode: vscodeMock,
    './config': {
      getSettings() {
        return {
          transport: 'stdio',
          attachMode: 'launch',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
    },
    './resourceCatalog': {
      getPackagedResourceCatalog() {
        return [];
      },
      getServerResourcesPath() {
        return 'C:\\repo\\hlf_mcp\\server_resources.py';
      },
    },
  });

  const provider = new OperatorPanelProvider({ getState: () => ({ running: false }) }, async () => ({ hasBearerToken: false }));
  const children = await provider.getChildren();

  assert.ok(children.some((item) => item.label === 'Claim Lanes'));
  const claimLaneSection = children.find((item) => item.label === 'Claim Lanes');
  assert.ok(claimLaneSection.children.some((item) => item.label === 'current-true'));
  assert.ok(claimLaneSection.children.some((item) => item.label === 'Show Claim-Lane Context'));
});

test('ui acceptance: operator panel resource entries inspect packaged resources', async () => {
  class MockTreeItem {
    constructor(label, collapsibleState) {
      this.label = label;
      this.collapsibleState = collapsibleState;
    }
  }

  class MockThemeIcon {
    constructor(id) {
      this.id = id;
    }
  }

  class MockEventEmitter {
    constructor() {
      this.event = () => {};
    }

    fire() {}
  }

  const vscodeMock = {
    TreeItem: MockTreeItem,
    ThemeIcon: MockThemeIcon,
    EventEmitter: MockEventEmitter,
    TreeItemCollapsibleState: {
      None: 0,
      Expanded: 2,
    },
    Uri: {
      file(filePath) {
        return { fsPath: filePath };
      },
    },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: 'C:\\repo' } }],
    },
  };

  const { OperatorPanelProvider } = loadWithMocks(path.join(__dirname, '..', 'src', 'operatorPanel.js'), {
    vscode: vscodeMock,
    './config': {
      getSettings() {
        return {
          transport: 'stdio',
          attachMode: 'launch',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
    },
    './resourceCatalog': {
      getPackagedResourceCatalog() {
        return [{ uri: 'hlf://status/formal_verifier', category: 'status' }];
      },
      getServerResourcesPath() {
        return 'C:\\repo\\hlf_mcp\\server_resources.py';
      },
    },
  });

  const provider = new OperatorPanelProvider({ getState: () => ({ running: false }) }, async () => ({ hasBearerToken: false }));
  const children = await provider.getChildren();
  const resourceSection = children.find((item) => item.label === 'Packaged Status Resources');
  const resourceItem = resourceSection.children.find((item) => item.label === 'hlf://status/formal_verifier');

  assert.equal(resourceItem.command.command, 'hlf.inspectResource');
  assert.deepEqual(resourceItem.command.arguments, ['hlf://status/formal_verifier']);
  assert.equal(resourceItem.contextValue, 'hlfResource');
});

test('ui acceptance: operator panel quick actions expose provenance contract command', async () => {
  class MockTreeItem {
    constructor(label, collapsibleState) {
      this.label = label;
      this.collapsibleState = collapsibleState;
    }
  }

  class MockThemeIcon {
    constructor(id) {
      this.id = id;
    }
  }

  class MockEventEmitter {
    constructor() {
      this.event = () => {};
    }

    fire() {}
  }

  const vscodeMock = {
    TreeItem: MockTreeItem,
    ThemeIcon: MockThemeIcon,
    EventEmitter: MockEventEmitter,
    TreeItemCollapsibleState: {
      None: 0,
      Expanded: 2,
    },
    Uri: {
      file(filePath) {
        return { fsPath: filePath };
      },
    },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: 'C:\\repo' } }],
    },
  };

  const { OperatorPanelProvider } = loadWithMocks(path.join(__dirname, '..', 'src', 'operatorPanel.js'), {
    vscode: vscodeMock,
    './config': {
      getSettings() {
        return {
          transport: 'stdio',
          attachMode: 'launch',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
    },
    './resourceCatalog': {
      getPackagedResourceCatalog() {
        return [{ uri: 'hlf://status/provenance_contract', category: 'status' }];
      },
      getServerResourcesPath() {
        return 'C:\\repo\\hlf_mcp\\server_resources.py';
      },
    },
  });

  const provider = new OperatorPanelProvider({ getState: () => ({ running: false }) }, async () => ({ hasBearerToken: false }));
  const children = await provider.getChildren();
  const quickActions = children.find((item) => item.label === 'Quick Actions');

  assert.ok(quickActions.children.some((item) => item.label === 'Show Provenance Contract'));
  assert.ok(quickActions.children.some((item) => item.label === 'Manage Operator Identity Defaults'));
  const provenanceAction = quickActions.children.find((item) => item.label === 'Show Provenance Contract');
  assert.equal(provenanceAction.command.command, 'hlf.showProvenanceContract');
  const identityAction = quickActions.children.find((item) => item.label === 'Manage Operator Identity Defaults');
  assert.equal(identityAction.command.command, 'hlf.manageOperatorIdentityDefaults');
});

test('ui acceptance: operator panel renders provenance summary section from packaged contract', async () => {
  class MockTreeItem {
    constructor(label, collapsibleState) {
      this.label = label;
      this.collapsibleState = collapsibleState;
    }
  }

  class MockThemeIcon {
    constructor(id) {
      this.id = id;
    }
  }

  class MockEventEmitter {
    constructor() {
      this.event = () => {};
    }

    fire() {}
  }

  const vscodeMock = {
    TreeItem: MockTreeItem,
    ThemeIcon: MockThemeIcon,
    EventEmitter: MockEventEmitter,
    TreeItemCollapsibleState: {
      None: 0,
      Expanded: 2,
    },
    Uri: {
      file(filePath) {
        return { fsPath: filePath };
      },
    },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: 'C:\\repo' } }],
    },
  };

  const { OperatorPanelProvider } = loadWithMocks(path.join(__dirname, '..', 'src', 'operatorPanel.js'), {
    vscode: vscodeMock,
    './config': {
      getSettings() {
        return {
          transport: 'stdio',
          attachMode: 'launch',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
    },
    './resourceCatalog': {
      getPackagedResourceCatalog() {
        return [{ uri: 'hlf://status/provenance_contract', category: 'status' }];
      },
      getServerResourcesPath() {
        return 'C:\\repo\\hlf_mcp\\server_resources.py';
      },
    },
  });

  const provider = new OperatorPanelProvider(
    { getState: () => ({ running: false }) },
    async () => ({ hasBearerToken: false }),
    async () => ({
      status: 'ok',
      provenance_contract: {
        summary: {
          memory_fact_count: 9,
          governance_event_count: 4,
          witness_subject_count: 2,
          active_pointer_count: 6,
          revoked_pointer_count: 1,
          tombstoned_pointer_count: 1,
          superseded_pointer_count: 1,
          stale_pointer_count: 0,
        },
        memory_state_counts: {
          active: 6,
          revoked: 1,
          tombstoned: 1,
          superseded: 1,
          stale: 0,
        },
        pointer_chain_summary: {
          active_pointer_count: 6,
        },
      },
    }),
  );

  const children = await provider.getChildren();
  const provenanceSection = children.find((item) => item.label === 'Provenance Summary');

  assert.ok(provenanceSection);
  assert.ok(provenanceSection.children.some((item) => item.label === 'Memory Facts' && item.description === '9'));
  assert.ok(provenanceSection.children.some((item) => item.label === 'Revoked' && item.description === '1'));
  assert.ok(provenanceSection.children.some((item) => item.label === 'Show Provenance Contract'));
});

test('ui acceptance: operator panel renders dedicated memory governance targets with intervention actions', async () => {
  class MockTreeItem {
    constructor(label, collapsibleState) {
      this.label = label;
      this.collapsibleState = collapsibleState;
    }
  }

  class MockThemeIcon {
    constructor(id) {
      this.id = id;
    }
  }

  class MockEventEmitter {
    constructor() {
      this.event = () => {};
    }

    fire() {}
  }

  const vscodeMock = {
    TreeItem: MockTreeItem,
    ThemeIcon: MockThemeIcon,
    EventEmitter: MockEventEmitter,
    TreeItemCollapsibleState: {
      None: 0,
      Collapsed: 1,
      Expanded: 2,
    },
    Uri: {
      file(filePath) {
        return { fsPath: filePath };
      },
    },
    workspace: {
      workspaceFolders: [{ uri: { fsPath: 'C:\\repo' } }],
    },
  };

  const { OperatorPanelProvider } = loadWithMocks(path.join(__dirname, '..', 'src', 'operatorPanel.js'), {
    vscode: vscodeMock,
    './config': {
      getSettings() {
        return {
          transport: 'stdio',
          attachMode: 'launch',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
    },
    './resourceCatalog': {
      getPackagedResourceCatalog() {
        return [{ uri: 'hlf://status/memory_governance', category: 'status' }];
      },
      getServerResourcesPath() {
        return 'C:\\repo\\hlf_mcp\\server_resources.py';
      },
    },
  });

  const provider = new OperatorPanelProvider(
    { getState: () => ({ running: false }) },
    async () => ({ hasBearerToken: false }),
    async () => undefined,
    async () => ({
      status: 'ok',
      memory_governance: {
        memory_state_counts: {
          active: 3,
          revoked: 1,
          tombstoned: 1,
          superseded: 0,
        },
        recent_interventions: [
          {
            action: 'memory_revoke',
            subject_id: '11',
            state: 'revoked',
            pointer: '&governance-11:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            reason: 'policy_review',
            operator_summary: 'Revoked after operator review',
            operator_identity: {
              operator_id: 'alice',
              operator_display_name: 'Alice Example',
              operator_channel: 'vscode.desktop.operator_panel',
            },
          },
        ],
        recent_targets: [
          {
            id: 11,
            topic: 'governance',
            sha256: 'a'.repeat(64),
            pointer: '&governance-11:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
            state: 'active',
            operator_summary: 'Candidate governance target',
            operator_identity: {
              operator_id: 'alice',
              operator_display_name: 'Alice Example',
              operator_channel: 'vscode.desktop.operator_panel',
            },
          },
          {
            id: 12,
            topic: 'governance',
            sha256: 'b'.repeat(64),
            pointer: '&governance-12:SHA256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
            state: 'revoked',
            operator_summary: 'Previously revoked target',
            operator_identity: {
              operator_id: 'bob',
              operator_display_name: 'Bob Example',
              operator_channel: 'vscode.desktop.operator_panel',
            },
          },
        ],
      },
    }),
  );

  const children = await provider.getChildren();
  const governanceSection = children.find((item) => item.label === 'Memory Governance');
  assert.ok(governanceSection);
  assert.ok(governanceSection.children.some((item) => item.label === 'Revoked' && item.description === '1'));
  const interventionSection = governanceSection.children.find((item) => item.label === 'Recent Interventions');
  assert.ok(interventionSection);
  const interventionItem = interventionSection.children.find((item) => item.label.includes('&governance-11:SHA256:'));
  assert.ok(interventionItem);
  assert.ok(interventionItem.children.some((item) => item.label === 'Operator' && item.description === 'Alice Example (alice)'));

  const targetItem = governanceSection.children.find((item) => item.label.includes('&governance-11:SHA256:'));
  assert.ok(targetItem);
  assert.ok(targetItem.children.some((item) => item.label === 'Operator' && item.description === 'Alice Example (alice)'));
  assert.ok(targetItem.children.some((item) => item.label === 'Revoke'));
  assert.ok(targetItem.children.some((item) => item.label === 'Tombstone'));
  assert.ok(!targetItem.children.some((item) => item.label === 'Reinstate'));
  const targetHistory = targetItem.children.find((item) => item.label === 'Intervention History');
  assert.ok(targetHistory);
  assert.equal(targetHistory.children.length, 1);
  assert.ok(targetHistory.children[0].label.includes('&governance-11:SHA256:'));
  const revokeAction = targetItem.children.find((item) => item.label === 'Revoke');
  assert.equal(revokeAction.command.command, 'hlf.governMemoryTarget');
  assert.deepEqual(revokeAction.command.arguments[1], 'revoke');

  const revokedTargetItem = governanceSection.children.find((item) => item.label.includes('&governance-12:SHA256:'));
  assert.ok(revokedTargetItem);
  assert.ok(!revokedTargetItem.children.some((item) => item.label === 'Revoke'));
  assert.ok(!revokedTargetItem.children.some((item) => item.label === 'Tombstone'));
  assert.ok(revokedTargetItem.children.some((item) => item.label === 'Reinstate'));
});

test('ui acceptance: governMemoryTarget prepopulates operator identity defaults from local environment', async () => {
  const inputValues = ['Revoke stale claim', 'operator_review_required', 'alice', 'Alice Example'];
  const inputOptions = [];

  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {
      env: { appHost: 'desktop' },
      window: {
        showInputBox: async (options) => {
          inputOptions.push(options);
          return inputValues.shift();
        },
        showQuickPick: async () => undefined,
        showWarningMessage: async () => 'Confirm',
      },
    },
    'node:os': {
      userInfo() {
        return { username: 'alice' };
      },
    },
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {
      getSettings() {
        return {
          attachMode: 'launch',
          transport: 'stdio',
        };
      },
      getWorkspaceRoot() {
        return 'C:\\repo';
      },
    },
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './memoryGovernance': require(path.join(__dirname, '..', 'src', 'memoryGovernance.js')),
    './operatorPanel': { OperatorPanelProvider: class {} },
    './packagedActions': { runOperatorAction: async () => ({ ok: true, parsed: { status: 'ok' } }) },
    './secrets': {},
    './trustPanel': { TrustPanel: class { show() {} } },
  });

  await extensionModule.governMemoryTarget({
    id: 11,
    topic: 'governance',
    state: 'active',
    pointer: '&governance-11:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  }, 'revoke');

  assert.equal(inputOptions[2].value, 'alice');
  assert.equal(inputOptions[3].value, 'alice');
});

test('ui acceptance: manageOperatorIdentityDefaults updates and resets stored defaults explicitly', async () => {
  const infoMessages = [];
  const store = new Map();
  const quickPickValues = [
    { value: 'update' },
    { value: 'reset' },
  ];
  const inputValues = ['stored-operator', 'Stored Operator', 'vscode.desktop.custom_operator'];

  const vscodeMock = {
    env: { appHost: 'desktop' },
    ThemeColor: class {
      constructor(id) {
        this.id = id;
      }
    },
    window: {
      createOutputChannel() {
        return { appendLine() {}, dispose() {} };
      },
      createStatusBarItem() {
        return { show() {}, hide() {}, dispose() {} };
      },
      registerTreeDataProvider() {
        return { dispose() {} };
      },
      showQuickPick: async () => quickPickValues.shift(),
      showInputBox: async () => inputValues.shift(),
      showInformationMessage: async (message) => {
        infoMessages.push(message);
        return undefined;
      },
      showWarningMessage: async () => undefined,
    },
    commands: {
      registerCommand() {
        return { dispose() {} };
      },
    },
    languages: {
      createDiagnosticCollection() {
        return { clear() {}, dispose() {} };
      },
    },
    workspace: {
      onDidChangeConfiguration() {
        return { dispose() {} };
      },
    },
    StatusBarAlignment: { Left: 1 },
  };

  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: vscodeMock,
    'node:os': {
      userInfo() {
        return { username: 'env-user' };
      },
    },
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {
      getSettings() {
        return {
          attachMode: 'launch',
          transport: 'stdio',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
      getWorkspaceRoot() {
        return 'C:\\repo';
      },
    },
    './diagnostics': {
      runBridgeDiagnostics: async () => ({ summary: 'ok', diagnostics: [], findings: [] }),
    },
    './launcher': {
      HlfServerController: class {
        getState() {
          return { running: false };
        }
        async stop() {
          return true;
        }
      },
    },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './memoryGovernance': require(path.join(__dirname, '..', 'src', 'memoryGovernance.js')),
    './operatorPanel': { OperatorPanelProvider: class { refresh() {} } },
    './packagedActions': { runOperatorAction: async () => ({ ok: true, parsed: { status: 'ok' } }) },
    './secrets': {
      buildHttpHeaders: async () => ({}),
      deleteHttpBearerToken: async () => {},
      hasHttpBearerToken: async () => false,
      storeHttpBearerToken: async () => {},
    },
    './trustPanel': { TrustPanel: class { show() {} } },
  });

  const context = {
    extensionUri: { fsPath: 'C:\\repo\\extensions\\hlf-vscode' },
    subscriptions: [],
    secrets: {},
    globalState: {
      get(key) {
        return store.get(key);
      },
      async update(key, value) {
        store.set(key, value);
      },
    },
  };

  extensionModule.activate(context);
  await extensionModule.manageOperatorIdentityDefaults();
  assert.deepEqual(store.get('hlf.operatorIdentityDefaults'), {
    operatorId: 'stored-operator',
    operatorDisplayName: 'Stored Operator',
    operatorChannel: 'vscode.desktop.custom_operator',
  });

  await extensionModule.manageOperatorIdentityDefaults();
  assert.deepEqual(store.get('hlf.operatorIdentityDefaults'), {
    operatorId: 'env-user',
    operatorDisplayName: 'env-user',
    operatorChannel: 'vscode.desktop.operator_panel',
  });
  assert.deepEqual(infoMessages, [
    'HLF operator identity defaults updated.',
    'HLF operator identity defaults reset to environment-derived values.',
  ]);
});

test('ui acceptance: stored operator identity defaults override environment defaults on next intervention', async () => {
  const store = new Map();
  const inputOptions = [];
  const quickPickValues = [{ value: 'update' }];
  const inputValues = [
    'stored-operator',
    'Stored Operator',
    'vscode.desktop.custom_operator',
    'Revoke stale claim',
    'operator_review_required',
    'stored-operator',
    'Stored Operator',
  ];
  const runCalls = [];

  const vscodeMock = {
    env: { appHost: 'desktop' },
    ThemeColor: class {
      constructor(id) {
        this.id = id;
      }
    },
    window: {
      createOutputChannel() {
        return { appendLine() {}, dispose() {} };
      },
      createStatusBarItem() {
        return { show() {}, hide() {}, dispose() {} };
      },
      registerTreeDataProvider() {
        return { dispose() {} };
      },
      showQuickPick: async () => quickPickValues.shift(),
      showInputBox: async (options) => {
        inputOptions.push(options);
        return inputValues.shift();
      },
      showInformationMessage: async () => undefined,
      showWarningMessage: async () => 'Confirm',
    },
    commands: {
      registerCommand() {
        return { dispose() {} };
      },
    },
    languages: {
      createDiagnosticCollection() {
        return { clear() {}, dispose() {} };
      },
    },
    workspace: {
      onDidChangeConfiguration() {
        return { dispose() {} };
      },
    },
    StatusBarAlignment: { Left: 1 },
  };

  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: vscodeMock,
    'node:os': {
      userInfo() {
        return { username: 'env-user' };
      },
    },
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {
      getSettings() {
        return {
          attachMode: 'launch',
          transport: 'stdio',
          httpAuthMode: 'none',
          evidencePath: undefined,
          serverCommand: 'uv',
          serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
        };
      },
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
      getHealthUrl() {
        return 'http://127.0.0.1:8000/health';
      },
      getWorkspaceRoot() {
        return 'C:\\repo';
      },
    },
    './diagnostics': {
      runBridgeDiagnostics: async () => ({ summary: 'ok', diagnostics: [], findings: [] }),
    },
    './launcher': {
      HlfServerController: class {
        getState() {
          return { running: false };
        }
        async stop() {
          return true;
        }
      },
    },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './memoryGovernance': require(path.join(__dirname, '..', 'src', 'memoryGovernance.js')),
    './operatorPanel': { OperatorPanelProvider: class { refresh() {} } },
    './packagedActions': {
      runOperatorAction: async (payload) => {
        runCalls.push(payload);
        return { ok: true, parsed: { status: 'ok' } };
      },
    },
    './secrets': {
      buildHttpHeaders: async () => ({}),
      deleteHttpBearerToken: async () => {},
      hasHttpBearerToken: async () => false,
      storeHttpBearerToken: async () => {},
    },
    './trustPanel': { TrustPanel: class { show() {} } },
  });

  const context = {
    extensionUri: { fsPath: 'C:\\repo\\extensions\\hlf-vscode' },
    subscriptions: [],
    secrets: {},
    globalState: {
      get(key) {
        return store.get(key);
      },
      async update(key, value) {
        store.set(key, value);
      },
    },
  };

  extensionModule.activate(context);
  await extensionModule.manageOperatorIdentityDefaults();
  await extensionModule.governMemoryTarget({
    id: 11,
    topic: 'governance',
    state: 'active',
    pointer: '&governance-11:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  }, 'revoke');

  assert.equal(inputOptions[5].value, 'stored-operator');
  assert.equal(inputOptions[6].value, 'Stored Operator');
  assert.deepEqual(runCalls[0].args, [
    'memory-govern',
    '--action', 'revoke',
    '--operator-summary', 'Revoke stale claim',
    '--reason', 'operator_review_required',
    '--operator-id', 'stored-operator',
    '--operator-display-name', 'Stored Operator',
    '--operator-channel', 'vscode.desktop.custom_operator',
    '--json',
    '--fact-id', '11',
  ]);
});

test('ui acceptance: governMemoryTarget prompts for summary, reason, and operator identity before destructive confirmation', async () => {
  const inputValues = ['Revoke stale claim', 'operator_review_required', 'alice', 'Alice Example'];
  const warningMessages = [];
  const runCalls = [];

  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {
      env: { appHost: 'desktop' },
      window: {
        showInputBox: async () => inputValues.shift(),
        showQuickPick: async () => undefined,
        showWarningMessage: async (message, options) => {
          warningMessages.push({ message, options });
          return 'Confirm';
        },
      },
    },
    'node:os': {
      userInfo() {
        return { username: 'alice' };
      },
    },
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {
      getSettings() {
        return {
          attachMode: 'launch',
          transport: 'stdio',
        };
      },
    },
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './memoryGovernance': require(path.join(__dirname, '..', 'src', 'memoryGovernance.js')),
    './operatorPanel': { OperatorPanelProvider: class {} },
    './packagedActions': {
      runOperatorAction: async (payload) => {
        runCalls.push(payload);
        return { ok: true, parsed: { status: 'ok' } };
      },
    },
    './secrets': {},
    './trustPanel': { TrustPanel: class { show() {} } },
  });

  await extensionModule.governMemoryTarget({
    id: 11,
    topic: 'governance',
    state: 'active',
    pointer: '&governance-11:SHA256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
  }, 'revoke');

  assert.equal(runCalls.length, 1);
  assert.deepEqual(runCalls[0].args, [
    'memory-govern',
    '--action', 'revoke',
    '--operator-summary', 'Revoke stale claim',
    '--reason', 'operator_review_required',
    '--operator-id', 'alice',
    '--operator-display-name', 'Alice Example',
    '--operator-channel', 'vscode.desktop.operator_panel',
    '--json',
    '--fact-id', '11',
  ]);
  assert.match(warningMessages[0].message, /Summary: Revoke stale claim/);
  assert.match(warningMessages[0].message, /Reason: operator_review_required/);
  assert.match(warningMessages[0].message, /Operator: alice \(Alice Example\)|Operator: alice/);
  assert.deepEqual(warningMessages[0].options, { modal: true });
});

test('ui acceptance: governMemoryTarget blocks invalid state-action combinations', async () => {
  const warningMessages = [];
  let runCount = 0;

  const extensionModule = loadWithMocks(path.join(__dirname, '..', 'src', 'extension.js'), {
    vscode: {
      window: {
        showInputBox: async () => undefined,
        showQuickPick: async () => undefined,
        showWarningMessage: async (message) => {
          warningMessages.push(message);
          return undefined;
        },
      },
    },
    './claimLanes': { getClaimLaneSections() { return []; }, getClaimLanesDocPath() { return undefined; } },
    './config': {
      getSettings() {
        return {
          attachMode: 'launch',
          transport: 'stdio',
        };
      },
    },
    './diagnostics': {},
    './launcher': { HlfServerController: class {} },
    './mcpHttpClient': { StreamableHttpMcpClient: class {} },
    './memoryGovernance': require(path.join(__dirname, '..', 'src', 'memoryGovernance.js')),
    './operatorPanel': { OperatorPanelProvider: class {} },
    './packagedActions': {
      runOperatorAction: async () => {
        runCount += 1;
        return { ok: true, parsed: { status: 'ok' } };
      },
    },
    './secrets': {},
    './trustPanel': { TrustPanel: class { show() {} } },
  });

  await extensionModule.governMemoryTarget({
    id: 12,
    topic: 'governance',
    state: 'revoked',
    pointer: '&governance-12:SHA256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb',
  }, 'revoke');

  assert.equal(runCount, 0);
  assert.match(warningMessages[0], /not a valid governed memory action/i);
});