const fs = require('node:fs');
const path = require('node:path');
const vscode = require('vscode');

const { getClaimLanePanelEntries, getClaimLanesDocPath } = require('./claimLanes');
const { getEndpointUrl, getHealthUrl, getSettings } = require('./config');
const { getAllowedGovernanceActions } = require('./memoryGovernance');
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

function extractProvenanceContract(payload) {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  if (payload.provenance_contract && typeof payload.provenance_contract === 'object') {
    return payload.provenance_contract;
  }

  return payload;
}

function extractMemoryGovernanceStatus(payload) {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  if (payload.memory_governance && typeof payload.memory_governance === 'object') {
    return payload.memory_governance;
  }

  return payload;
}

function buildMemoryGovernanceTargetItem(target) {
  const identity = target.operator_identity || {};
  const label = target.pointer || `${target.topic || 'memory'}#${target.id || 'unknown'}`;
  const tooltip = target.operator_summary || target.sha256 || label;
  const commandTarget = {
    factId: target.id ?? null,
    sha256: target.sha256 ?? '',
    topic: target.topic ?? '',
    pointer: target.pointer ?? '',
    state: target.state ?? '',
    operatorSummary: target.operator_summary ?? '',
  };
  const children = [
    makeValueItem('State', target.state || 'unknown', 'Current governed memory state for this target.', 'shield'),
    makeValueItem('Topic', target.topic || 'general', 'Memory topic associated with this governed target.', 'tag'),
    makeValueItem('Pointer', target.pointer || 'unavailable', 'Canonical pointer reference for this target.', 'link'),
  ];

  if (identity.operator_id || identity.operator_display_name) {
    const operatorLabel = identity.operator_display_name
      ? `${identity.operator_display_name} (${identity.operator_id || 'unknown'})`
      : identity.operator_id;
    children.push(makeValueItem('Operator', operatorLabel, 'Latest operator identity aligned to this target state.', 'account'));
  }
  if (identity.operator_channel) {
    children.push(makeValueItem('Channel', identity.operator_channel, 'Latest operator channel aligned to this target state.', 'plug'));
  }

  if (target.sha256) {
    children.push(makeValueItem('SHA256', target.sha256, 'Content hash for the governed target.', 'key'));
  }
  if (target.operator_summary) {
    children.push(makeValueItem('Summary', target.operator_summary, 'Latest operator summary attached to this target.', 'note'));
  }
  if (target.id || target.sha256) {
    const allowedActions = getAllowedGovernanceActions(target);
    if (allowedActions.includes('revoke')) {
      children.push(makeCommandItem('Revoke', {
        command: 'hlf.governMemoryTarget',
        title: 'Revoke Memory Target',
        arguments: [commandTarget, 'revoke'],
      }, 'Mark this governed memory target as revoked.', 'warning'));
    }
    if (allowedActions.includes('tombstone')) {
      children.push(makeCommandItem('Tombstone', {
        command: 'hlf.governMemoryTarget',
        title: 'Tombstone Memory Target',
        arguments: [commandTarget, 'tombstone'],
      }, 'Mark this governed memory target as tombstoned.', 'trash'));
    }
    if (allowedActions.includes('reinstate')) {
      children.push(makeCommandItem('Reinstate', {
        command: 'hlf.governMemoryTarget',
        title: 'Reinstate Memory Target',
        arguments: [commandTarget, 'reinstate'],
      }, 'Reinstate this governed memory target.', 'history'));
    }
  }

  return new PanelItem(label, {
    collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
    children,
    description: target.state || 'unknown',
    tooltip,
    iconPath: new vscode.ThemeIcon('shield'),
  });
}

function buildMemoryGovernanceInterventionItem(intervention) {
  const label = intervention.pointer || `${intervention.action || 'intervention'}#${intervention.subject_id || 'unknown'}`;
  const identity = intervention.operator_identity || {};
  const operatorLabel = identity.operator_display_name
    ? `${identity.operator_display_name} (${identity.operator_id || 'unknown'})`
    : (identity.operator_id || 'unknown');
  const children = [
    makeValueItem('Action', intervention.action || 'unknown', 'Governance action recorded for this intervention.', 'history'),
    makeValueItem('State', intervention.state || 'unknown', 'Governed state after this intervention.', 'shield'),
    makeValueItem('Operator', operatorLabel, 'Operator identity recorded for this intervention.', 'account'),
    makeValueItem('Channel', identity.operator_channel || 'unknown', 'Origin channel recorded for this intervention.', 'plug'),
    makeValueItem('Reason', intervention.reason || 'none', 'Governance reason recorded for this intervention.', 'note'),
  ];

  if (intervention.operator_summary) {
    children.push(makeValueItem('Summary', intervention.operator_summary, 'Operator summary recorded for this intervention.', 'comment'));
  }
  if (intervention.timestamp) {
    children.push(makeValueItem('Timestamp', String(intervention.timestamp), 'Recorded governance intervention timestamp.', 'clock'));
  }
  if (intervention.sha256) {
    children.push(makeValueItem('SHA256', intervention.sha256, 'Target content hash associated with this intervention.', 'key'));
  }

  return new PanelItem(label, {
    collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
    children,
    description: intervention.action || 'unknown',
    tooltip: intervention.operator_summary || intervention.reason || label,
    iconPath: new vscode.ThemeIcon('history'),
  });
}

function interventionMatchesTarget(intervention, target) {
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
}

function buildTargetInterventionHistoryItem(target, interventions) {
  const matching = interventions.filter((intervention) => interventionMatchesTarget(intervention, target));
  return new PanelItem('Intervention History', {
    collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
    children: matching.length > 0
      ? matching.map((intervention) => buildMemoryGovernanceInterventionItem(intervention))
      : [makeValueItem('Interventions', 'none recorded', 'No recent governed memory interventions match this target.', 'circle-slash')],
    iconPath: new vscode.ThemeIcon('history'),
  });
}

class OperatorPanelProvider {
  constructor(controller, getSecretStatus, readProvenanceContract, readMemoryGovernanceStatus) {
    this.controller = controller;
    this.getSecretStatus = getSecretStatus;
    this.readProvenanceContract = readProvenanceContract;
    this.readMemoryGovernanceStatus = readMemoryGovernanceStatus;
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
    let provenanceContract;
    let memoryGovernance;
    if (this.readProvenanceContract) {
      try {
        provenanceContract = extractProvenanceContract(await this.readProvenanceContract());
      } catch {
        provenanceContract = undefined;
      }
    }
    if (this.readMemoryGovernanceStatus) {
      try {
        memoryGovernance = extractMemoryGovernanceStatus(await this.readMemoryGovernanceStatus());
      } catch {
        memoryGovernance = undefined;
      }
    }

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

    const provenanceSummary = provenanceContract?.summary;
    const pointerSummary = provenanceContract?.pointer_chain_summary;
    const stateCounts = provenanceContract?.memory_state_counts;
    const provenanceChildren = provenanceSummary
      ? [
        makeValueItem('Memory Facts', String(provenanceSummary.memory_fact_count ?? 0), 'Total memory facts included in the packaged provenance contract.', 'database'),
        makeValueItem('Governance Events', String(provenanceSummary.governance_event_count ?? 0), 'Governance events observed in the current packaged session context.', 'history'),
        makeValueItem('Witness Subjects', String(provenanceSummary.witness_subject_count ?? 0), 'Witness-governed subjects currently tracked in the packaged context.', 'eye'),
        makeValueItem('Active Pointers', String(pointerSummary?.active_pointer_count ?? provenanceSummary.active_pointer_count ?? 0), 'Pointers whose governed memory state is currently active.', 'link'),
        makeValueItem('Revoked', String(stateCounts?.revoked ?? provenanceSummary.revoked_pointer_count ?? 0), 'Pointers or facts marked revoked by governed memory evidence.', 'warning'),
        makeValueItem('Tombstoned', String(stateCounts?.tombstoned ?? provenanceSummary.tombstoned_pointer_count ?? 0), 'Pointers or facts marked tombstoned by governed memory evidence.', 'trash'),
        makeValueItem('Superseded', String(stateCounts?.superseded ?? provenanceSummary.superseded_pointer_count ?? 0), 'Pointers or facts superseded by newer governed memory entries.', 'git-commit'),
        makeValueItem('Stale', String(stateCounts?.stale ?? provenanceSummary.stale_pointer_count ?? 0), 'Pointers or facts whose freshness window has expired.', 'clock'),
        makeCommandItem('Show Provenance Contract', { command: 'hlf.showProvenanceContract', title: 'Show Provenance Contract' }, 'Open the full packaged provenance contract in the trust panel.', 'shield'),
      ]
      : [
        makeValueItem('Provenance Summary', 'unavailable', 'The operator panel could not load the packaged provenance contract summary.', 'warning'),
        makeCommandItem('Show Provenance Contract', { command: 'hlf.showProvenanceContract', title: 'Show Provenance Contract' }, 'Open the full packaged provenance contract in the trust panel.', 'shield'),
      ];

    const governanceTargets = Array.isArray(memoryGovernance?.recent_targets)
      ? memoryGovernance.recent_targets
      : [];
    const governanceInterventions = Array.isArray(memoryGovernance?.recent_interventions)
      ? memoryGovernance.recent_interventions
      : [];
    const governanceCounts = memoryGovernance?.memory_state_counts ?? {};
    const memoryGovernanceChildren = memoryGovernance
      ? [
        makeValueItem('Active', String(governanceCounts.active ?? 0), 'Governed memory facts currently considered active.', 'pass'),
        makeValueItem('Revoked', String(governanceCounts.revoked ?? 0), 'Governed memory facts currently marked revoked.', 'warning'),
        makeValueItem('Tombstoned', String(governanceCounts.tombstoned ?? 0), 'Governed memory facts currently marked tombstoned.', 'trash'),
        makeValueItem('Superseded', String(governanceCounts.superseded ?? 0), 'Governed memory facts superseded by newer entries.', 'git-commit'),
        new PanelItem('Recent Interventions', {
          collapsibleState: vscode.TreeItemCollapsibleState.Collapsed,
          children: governanceInterventions.length > 0
            ? governanceInterventions.map((intervention) => buildMemoryGovernanceInterventionItem(intervention))
            : [makeValueItem('Interventions', 'none recorded', 'No recent governed memory interventions are available.', 'circle-slash')],
          iconPath: new vscode.ThemeIcon('history'),
        }),
        ...governanceTargets.map((target) => {
          const targetItem = buildMemoryGovernanceTargetItem(target);
          targetItem.children.push(buildTargetInterventionHistoryItem(target, governanceInterventions));
          return targetItem;
        }),
      ]
      : [
        makeValueItem('Memory Governance', 'unavailable', 'The operator panel could not load the packaged memory governance resource.', 'warning'),
      ];

    const actionsChildren = [
      makeCommandItem('Run First-Run Validation', { command: 'hlf.runFirstRunValidation', title: 'Run First-Run Validation' }, 'Validate current bridge configuration and secret state.', 'check-all'),
      makeCommandItem('Manage Operator Identity Defaults', { command: 'hlf.manageOperatorIdentityDefaults', title: 'Manage Operator Identity Defaults' }, 'Set or reset stored operator identity defaults without waiting for an intervention prompt.', 'account'),
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
      makeCommandItem('Show Provenance Contract', { command: 'hlf.showProvenanceContract', title: 'Show Provenance Contract' }, 'Show the packaged provenance contract across memory, governance, witness, and evidence.', 'shield'),
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
      new PanelItem('Provenance Summary', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: provenanceChildren,
        iconPath: new vscode.ThemeIcon('shield'),
      }),
      new PanelItem('Memory Governance', {
        collapsibleState: vscode.TreeItemCollapsibleState.Expanded,
        children: memoryGovernanceChildren,
        iconPath: new vscode.ThemeIcon('law'),
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
  buildMemoryGovernanceInterventionItem,
  buildTargetInterventionHistoryItem,
  buildMemoryGovernanceTargetItem,
  interventionMatchesTarget,
};