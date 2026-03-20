const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');

const { getClaimLanePanelEntries, getClaimLanesDocPath } = require('./claimLanes');
const { getEndpointUrl, getHealthUrl, getSettings } = require('./config');
const { getPackagedResourceCatalog, getServerResourcesPath } = require('./resourceCatalog');

class PanelItem extends vscode.TreeItem {
  constructor(label, options = {}) {
    super(label, options.collapsibleState ?? vscode.TreeItemCollapsibleState.None);
    this.children = options.children ?? [];
    this.description = options.description;
    this.tooltip = options.tooltip;
    this.command = options.command;
    this.contextValue = options.contextValue;
    this.resourceUri = options.resourceUri;
    this.iconPath = options.iconPath;
  }
}

function makeValueItem(label, description, tooltip, iconId = 'info') {
  return new PanelItem(label, {
    description,
    tooltip,
    iconPath: new vscode.ThemeIcon(iconId),
  });
}

function makeCommandItem(label, command, tooltip, iconId = 'play') {
  return new PanelItem(label, {
    tooltip,
    command,
    iconPath: new vscode.ThemeIcon(iconId),
  });
}

function getEvidenceSnapshot(evidencePath) {
  if (!evidencePath) {
    return { exists: false, files: [] };
  }

  if (!fs.existsSync(evidencePath)) {
    return { exists: false, files: [] };
  }

  const entries = fs.readdirSync(evidencePath, { withFileTypes: true })
    .filter((entry) => entry.isFile())
    .map((entry) => {
      const filePath = path.join(evidencePath, entry.name);
      const stat = fs.statSync(filePath);
      return {
        name: entry.name,
        path: filePath,
        modifiedMs: stat.mtimeMs,
      };
    })
    .sort((left, right) => right.modifiedMs - left.modifiedMs)
    .slice(0, 5);

  return { exists: true, files: entries };
}

class OperatorPanelProvider {
  constructor(controller, getSecretStatus) {
    this.controller = controller;
    this.getSecretStatus = getSecretStatus;
    this._onDidChangeTreeData = new vscode.EventEmitter();
    this.onDidChangeTreeData = this._onDidChangeTreeData.event;
  }

  refresh() {
    this._onDidChangeTreeData.fire(undefined);
  }

  getTreeItem(element) {
    return element;
  }

  async getChildren(element) {
    if (element) {
      return element.children;
    }

    const settings = getSettings();
    const state = this.controller?.getState?.() ?? { running: false };
    const evidence = getEvidenceSnapshot(settings.evidencePath);
    const resources = getPackagedResourceCatalog().filter((resource) => resource.category === 'status');
    const serverResourcesPath = getServerResourcesPath();
    const secretStatus = this.getSecretStatus ? await this.getSecretStatus() : { hasBearerToken: false };
    const claimLaneDocPath = getClaimLanesDocPath(vscode.workspace.workspaceFolders?.[0]?.uri.fsPath);

    const bridgeChildren = [
      makeValueItem('Transport', settings.transport, `Current bridge transport: ${settings.transport}.`, 'radio-tower'),
      makeValueItem('Mode', settings.attachMode, `Bridge mode is ${settings.attachMode}.`, 'plug'),
      makeValueItem('Managed Process', state.running ? 'running' : 'stopped', state.running ? `Managed HLF process PID ${state.pid}.` : 'No managed HLF process is currently running.', state.running ? 'pass' : 'warning'),
      makeValueItem('HTTP Auth', settings.httpAuthMode, `HTTP auth mode is ${settings.httpAuthMode}.`, settings.httpAuthMode === 'bearer' ? 'lock' : 'unlock'),
      makeValueItem('Bearer Token', secretStatus.hasBearerToken ? 'configured' : 'not configured', secretStatus.hasBearerToken ? 'A bearer token is stored in VS Code secret storage.' : 'No bearer token is currently stored.', secretStatus.hasBearerToken ? 'key' : 'warning'),
    ];

    if (settings.transport === 'stdio') {
      bridgeChildren.push(
        makeValueItem('Launch Command', `${settings.serverCommand} ${settings.serverArgs.join(' ')}`.trim(), 'Managed stdio launch command for the packaged HLF server.', 'terminal'),
      );
    } else {
      bridgeChildren.push(
        makeValueItem('Endpoint', getEndpointUrl(settings), 'Configured MCP endpoint for HTTP transport.', 'link'),
        makeValueItem('Health', getHealthUrl(settings), 'Configured health endpoint for HTTP transport.', 'heart'),
      );
    }

    const evidenceChildren = [
      makeValueItem('Evidence Path', settings.evidencePath ?? 'not configured', settings.evidencePath ?? 'No evidence path is configured.', evidence.exists ? 'folder-library' : 'warning'),
      makeValueItem('Path State', evidence.exists ? 'present' : 'missing', evidence.exists ? 'The configured evidence directory exists.' : 'The configured evidence directory does not exist yet.', evidence.exists ? 'pass' : 'warning'),
      makeCommandItem('Open Evidence Path', { command: 'hlf.openEvidencePath' }, 'Open the configured evidence directory in VS Code.', 'folder-opened'),
    ];

    const claimLaneChildren = [
      ...getClaimLanePanelEntries().map((lane) => makeValueItem(lane.label, lane.description, lane.tooltip, 'tag')),
      makeCommandItem('Show Claim-Lane Context', { command: 'hlf.showClaimLanes', title: 'Show Claim-Lane Context' }, 'Open the extension claim-lane summary in the trust panel.', 'layers'),
    ];

    if (claimLaneDocPath) {
      claimLaneChildren.push(new PanelItem('Open Claim-Lane Doctrine', {
        description: 'docs/HLF_CLAIM_LANES.md',
        tooltip: claimLaneDocPath,
        resourceUri: vscode.Uri.file(claimLaneDocPath),
        command: {
          command: 'hlf.openClaimLaneDoctrine',
          title: 'Open Claim-Lane Doctrine',
        },
        iconPath: new vscode.ThemeIcon('book'),
      }));
    }

    if (evidence.files.length === 0) {
      evidenceChildren.push(
        makeValueItem('Recent Evidence', 'none detected', 'No recent evidence files were found in the configured directory.', 'circle-slash'),
      );
    } else {
      for (const file of evidence.files) {
        evidenceChildren.push(new PanelItem(file.name, {
          description: new Date(file.modifiedMs).toLocaleString(),
          tooltip: file.path,
          resourceUri: vscode.Uri.file(file.path),
          command: {
            command: 'vscode.open',
            title: 'Open Evidence File',
            arguments: [vscode.Uri.file(file.path)],
          },
          iconPath: new vscode.ThemeIcon('file'),
        }));
      }
    }

    const resourceChildren = resources.length > 0
      ? resources.map((resource) => new PanelItem(resource.uri, {
        description: 'status resource',
        tooltip: `${resource.uri}\nDerived from packaged resource declarations in ${serverResourcesPath ?? 'workspace-unavailable'}.`,
        command: {
          command: 'hlf.inspectResource',
          title: 'Inspect Packaged Resource',
          arguments: [resource.uri],
        },
        iconPath: new vscode.ThemeIcon('symbol-key'),
        contextValue: 'hlfResource',
      }))
      : [makeValueItem('Packaged Status Resources', 'unavailable', 'No packaged status resources could be derived from the workspace.', 'warning')];

    const actionsChildren = [
      makeCommandItem('Run First-Run Validation', { command: 'hlf.runFirstRunValidation', title: 'Run First-Run Validation' }, 'Validate current bridge configuration and secret state.', 'check-all'),
      makeCommandItem('Run Bridge Diagnostics', { command: 'hlf.runDiagnostics', title: 'Run Bridge Diagnostics' }, 'Run bridge diagnostics now.', 'pulse'),
      makeCommandItem('Set HTTP Bearer Token', { command: 'hlf.setHttpBearerToken', title: 'Set HTTP Bearer Token' }, 'Store or replace the HTTP bearer token in VS Code secret storage.', 'key'),
      makeCommandItem('Clear HTTP Bearer Token', { command: 'hlf.clearHttpBearerToken', title: 'Clear HTTP Bearer Token' }, 'Delete the stored HTTP bearer token from VS Code secret storage.', 'trash'),
      makeCommandItem('Start Bridge', { command: 'hlf.startServer', title: 'Start Bridge' }, 'Start the managed HLF bridge process.', 'play'),
      makeCommandItem('Stop Bridge', { command: 'hlf.stopServer', title: 'Stop Bridge' }, 'Stop the managed HLF bridge process.', 'debug-stop'),
      makeCommandItem('Restart Bridge', { command: 'hlf.restartServer', title: 'Restart Bridge' }, 'Restart the managed HLF bridge process.', 'debug-restart'),
      makeCommandItem('Copy Connection Details', { command: 'hlf.copyConnectionDetails', title: 'Copy Connection Details' }, 'Copy the current bridge connection details to the clipboard.', 'copy'),
      makeCommandItem('Run HLF Do', { command: 'hlf.runHlfDo', title: 'Run HLF Do' }, 'Invoke the packaged governed build-assist front door.', 'sparkle'),
      makeCommandItem('Show Test Summary', { command: 'hlf.showTestSuiteSummary', title: 'Show Test Summary' }, 'Show the latest packaged pytest summary.', 'beaker'),
      makeCommandItem('Show Weekly Evidence Summary', { command: 'hlf.showWeeklyEvidenceSummary', title: 'Show Weekly Evidence Summary' }, 'Show the governed weekly evidence summary.', 'graph'),
      makeCommandItem('Show Profile Capability Catalog', { command: 'hlf.showProfileCapabilityCatalog', title: 'Show Profile Capability Catalog' }, 'Show the packaged governed profile catalog.', 'organization'),
      makeCommandItem('Open Trust Panel', { command: 'hlf.openTrustPanel', title: 'Open Trust Panel' }, 'Open the webview trust panel for route, verifier, and memory evidence.', 'preview'),
    ];

    if (settings.transport !== 'stdio') {
      actionsChildren.push(
        makeCommandItem('Open Health Endpoint', { command: 'hlf.openHealthEndpoint', title: 'Open Health Endpoint' }, 'Open the configured HTTP health endpoint.', 'globe'),
      );
    }

    return [
      new PanelItem('Bridge State', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: bridgeChildren,
        iconPath: new vscode.ThemeIcon('radio-tower'),
      }),
      new PanelItem('Claim Lanes', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: claimLaneChildren,
        iconPath: new vscode.ThemeIcon('layers'),
      }),
      new PanelItem('Evidence Snapshot', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: evidenceChildren,
        iconPath: new vscode.ThemeIcon('history'),
      }),
      new PanelItem('Packaged Status Resources', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: resourceChildren,
        iconPath: new vscode.ThemeIcon('symbol-namespace'),
      }),
      new PanelItem('Quick Actions', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: actionsChildren,
        iconPath: new vscode.ThemeIcon('tools'),
      }),
    ];
  }
}

module.exports = {
  OperatorPanelProvider,
};