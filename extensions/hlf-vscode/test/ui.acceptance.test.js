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