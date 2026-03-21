const os = require('node:os');
const vscode = require('vscode');

const { getClaimLaneSections, getClaimLanesDocPath } = require('./claimLanes');
const { getEndpointUrl, getHealthUrl, getSettings, getWorkspaceRoot } = require('./config');
const { runBridgeDiagnostics } = require('./diagnostics');
const { HlfServerController } = require('./launcher');
const { getAllowedGovernanceActions, isGovernanceActionAllowed } = require('./memoryGovernance');
const { StreamableHttpMcpClient } = require('./mcpHttpClient');
const { OperatorPanelProvider, interventionMatchesTarget } = require('./operatorPanel');
const { runOperatorAction } = require('./packagedActions');
const { applyResourceUriValues, getResourceUriPlaceholders } = require('./resourceUriTemplate');
const { buildHttpHeaders, deleteHttpBearerToken, hasHttpBearerToken, storeHttpBearerToken } = require('./secrets');
const { TrustPanel } = require('./trustPanel');

let controller;
let statusBar;
let outputChannel;
let diagnosticCollection;
let operatorPanelProvider;
let trustPanel;
let extensionContext;
const PROVENANCE_PANEL_CACHE_TTL_MS = 5000;
let provenancePanelCache = {
  expiresAt: 0,
  payload: undefined,
};
let liveMcpClient;
let liveMcpClientSignature;

function getEnvironmentOperatorIdentityDefaults() {
  let username = '';
  try {
    username = os.userInfo().username || '';
  } catch {
    username = '';
  }

  const normalizedUsername = String(username || process.env.USERNAME || process.env.USER || 'operator').trim() || 'operator';
  const appHost = String(vscode.env?.appHost || 'desktop').trim() || 'desktop';
  return {
    operatorId: normalizedUsername,
    operatorDisplayName: normalizedUsername,
    operatorChannel: `vscode.${appHost}.operator_panel`,
  };
}

function getStoredOperatorIdentityDefaults() {
  const stored = extensionContext?.globalState?.get('hlf.operatorIdentityDefaults');
  if (!stored || typeof stored !== 'object') {
    return {};
  }
  return stored;
}

function getDefaultOperatorIdentity() {
  const environmentDefaults = getEnvironmentOperatorIdentityDefaults();
  const storedDefaults = getStoredOperatorIdentityDefaults();
  return {
    operatorId: String(storedDefaults.operatorId || environmentDefaults.operatorId || 'operator'),
    operatorDisplayName: String(
      storedDefaults.operatorDisplayName
      || environmentDefaults.operatorDisplayName
      || environmentDefaults.operatorId
      || ''
    ),
    operatorChannel: String(storedDefaults.operatorChannel || environmentDefaults.operatorChannel || 'vscode.desktop.operator_panel'),
  };
}

async function persistOperatorIdentityDefaults(identity) {
  if (!extensionContext?.globalState) {
    return;
  }
  await extensionContext.globalState.update('hlf.operatorIdentityDefaults', {
    operatorId: String(identity.operatorId || ''),
    operatorDisplayName: String(identity.operatorDisplayName || ''),
    operatorChannel: String(identity.operatorChannel || ''),
  });
}

async function manageOperatorIdentityDefaults() {
  const currentDefaults = getDefaultOperatorIdentity();
  const environmentDefaults = getEnvironmentOperatorIdentityDefaults();
  const selection = await vscode.window.showQuickPick([
    {
      label: 'Update Stored Defaults',
      value: 'update',
      description: `${currentDefaults.operatorId}${currentDefaults.operatorDisplayName ? ` (${currentDefaults.operatorDisplayName})` : ''}`,
      detail: `Current channel: ${currentDefaults.operatorChannel}`,
    },
    {
      label: 'Reset To Environment Defaults',
      value: 'reset',
      description: `${environmentDefaults.operatorId}${environmentDefaults.operatorDisplayName ? ` (${environmentDefaults.operatorDisplayName})` : ''}`,
      detail: `Reset channel to ${environmentDefaults.operatorChannel}`,
    },
  ], {
    placeHolder: 'Choose how to manage stored operator identity defaults.',
    ignoreFocusOut: true,
  });

  if (!selection) {
    return;
  }

  if (selection.value === 'reset') {
    await persistOperatorIdentityDefaults(environmentDefaults);
    operatorPanelProvider?.refresh();
    vscode.window.showInformationMessage('HLF operator identity defaults reset to environment-derived values.');
    return;
  }

  const operatorId = await vscode.window.showInputBox({
    prompt: 'Enter the stored default operator id.',
    placeHolder: 'alice, gerry, oncall-operator, or other durable operator id.',
    value: currentDefaults.operatorId,
    ignoreFocusOut: true,
  });
  if (operatorId === undefined) {
    return;
  }
  if (!operatorId.trim()) {
    vscode.window.showWarningMessage('A stored default operator id is required.');
    return;
  }

  const operatorDisplayName = await vscode.window.showInputBox({
    prompt: 'Enter the stored default operator display name.',
    placeHolder: 'Optional human-readable operator name.',
    value: currentDefaults.operatorDisplayName,
    ignoreFocusOut: true,
  });
  if (operatorDisplayName === undefined) {
    return;
  }

  const operatorChannel = await vscode.window.showInputBox({
    prompt: 'Enter the stored default operator channel.',
    placeHolder: 'vscode.desktop.operator_panel or other governed operator channel.',
    value: currentDefaults.operatorChannel,
    ignoreFocusOut: true,
  });
  if (operatorChannel === undefined) {
    return;
  }
  if (!operatorChannel.trim()) {
    vscode.window.showWarningMessage('A stored default operator channel is required.');
    return;
  }

  await persistOperatorIdentityDefaults({
    operatorId: operatorId.trim(),
    operatorDisplayName: operatorDisplayName.trim(),
    operatorChannel: operatorChannel.trim(),
  });
  operatorPanelProvider?.refresh();
  vscode.window.showInformationMessage('HLF operator identity defaults updated.');
}

function canRunLocalPackagedActions(settings) {
  return settings.attachMode !== 'attach';
}

function canUseLiveMcpActions(settings) {
  return settings.transport === 'streamable-http' && (settings.attachMode === 'attach' || controller?.isRunning());
}

function parseAttachModeArgs(args) {
  if (args[0] === 'resource') {
    const uriIndex = args.indexOf('--uri');
    if (uriIndex === -1 || !args[uriIndex + 1]) {
      throw new Error('Attach-mode resource requests require --uri.');
    }
    return {
      kind: 'resource',
      uri: args[uriIndex + 1],
    };
  }

  if (args[0] === 'provenance-summary') {
    return {
      kind: 'resource',
      uri: 'hlf://status/provenance_contract',
    };
  }

  if (args[0] === 'memory-govern') {
    const actionIndex = args.indexOf('--action');
    const factIdIndex = args.indexOf('--fact-id');
    const shaIndex = args.indexOf('--sha256');
    const operatorSummaryIndex = args.indexOf('--operator-summary');
    const reasonIndex = args.indexOf('--reason');
    const operatorIdIndex = args.indexOf('--operator-id');
    const operatorDisplayNameIndex = args.indexOf('--operator-display-name');
    const operatorChannelIndex = args.indexOf('--operator-channel');
    if (actionIndex === -1 || !args[actionIndex + 1]) {
      throw new Error('Attach-mode memory governance requests require --action.');
    }

    return {
      kind: 'tool',
      name: 'hlf_memory_govern',
      arguments: {
        action: args[actionIndex + 1],
        fact_id: factIdIndex === -1 || !args[factIdIndex + 1] ? undefined : Number(args[factIdIndex + 1]),
        sha256: shaIndex === -1 ? undefined : args[shaIndex + 1],
        operator_summary: operatorSummaryIndex === -1 ? '' : args[operatorSummaryIndex + 1],
        reason: reasonIndex === -1 ? '' : args[reasonIndex + 1],
        operator_id: operatorIdIndex === -1 ? '' : args[operatorIdIndex + 1],
        operator_display_name: operatorDisplayNameIndex === -1 ? '' : args[operatorDisplayNameIndex + 1],
        operator_channel: operatorChannelIndex === -1 ? '' : args[operatorChannelIndex + 1],
      },
    };
  }

  if (args[0] === 'test-summary') {
    return {
      kind: 'tool',
      name: 'hlf_test_suite_summary',
      arguments: {},
    };
  }

  if (args[0] === 'weekly-evidence-summary') {
    return {
      kind: 'tool',
      name: 'hlf_weekly_evidence_summary',
      arguments: {},
    };
  }

  if (args[0] === 'do') {
    const intentIndex = args.indexOf('--intent');
    const tierIndex = args.indexOf('--tier');
    return {
      kind: 'tool',
      name: 'hlf_do',
      arguments: {
        intent: intentIndex === -1 ? '' : args[intentIndex + 1],
        tier: tierIndex === -1 ? 'forge' : args[tierIndex + 1],
        dry_run: args.includes('--dry-run'),
        show_hlf: args.includes('--show-hlf'),
      },
    };
  }

  throw new Error(`Attach-mode MCP proxy does not support action '${args[0]}'.`);
}

function getPackagedActionUnavailableReason(settings) {
  if (canRunLocalPackagedActions(settings) || canUseLiveMcpActions(settings)) {
    return undefined;
  }

  return 'Attach-mode packaged operator actions currently require streamable-http transport. SSE attach mode still exposes diagnostics and connection state only.';
}

function getLiveMcpClientCacheSignature(settings, secretHeaders = {}) {
  return JSON.stringify({
    endpointUrl: getEndpointUrl(settings),
    attachMode: settings.attachMode,
    authorization: secretHeaders.Authorization || '',
  });
}

function resetLiveMcpClient() {
  liveMcpClient = undefined;
  liveMcpClientSignature = undefined;
}

function getLiveMcpClient({ settings, outputChannel, secretHeaders = {} }) {
  const signature = getLiveMcpClientCacheSignature(settings, secretHeaders);
  if (!liveMcpClient || liveMcpClientSignature !== signature) {
    liveMcpClient = new StreamableHttpMcpClient({ settings, outputChannel, secretHeaders });
    liveMcpClientSignature = signature;
  }
  return liveMcpClient;
}

function invalidateProvenancePanelCache() {
  provenancePanelCache = {
    expiresAt: 0,
    payload: undefined,
  };
}

function extractProvenanceContractPayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  if (payload.provenance_contract && typeof payload.provenance_contract === 'object') {
    return payload.provenance_contract;
  }

  return payload;
}

function extractMemoryGovernancePayload(payload) {
  if (!payload || typeof payload !== 'object') {
    return undefined;
  }

  if (payload.memory_governance && typeof payload.memory_governance === 'object') {
    return payload.memory_governance;
  }

  return payload;
}

function buildProvenanceTrustSections(payload) {
  const contract = extractProvenanceContractPayload(payload);
  if (!contract) {
    return [{
      title: 'Memory Provenance',
      subtitle: 'Packaged provenance contract across memory, governance, witness, and evidence surfaces.',
      body: payload,
    }];
  }

  const lineageEntries = Array.isArray(contract.pointer_chain_summary?.recent_pointers)
    ? contract.pointer_chain_summary.recent_pointers
    : [];
  const supersessionLineage = lineageEntries.filter((entry) => entry.supersedes || entry.superseded);

  return [
    {
      title: 'Memory Provenance',
      subtitle: 'Summary counts and governed state from the packaged provenance contract.',
      body: {
        summary: contract.summary ?? {},
        memory_state_counts: contract.memory_state_counts ?? {},
      },
    },
    {
      title: 'Pointer Chains',
      subtitle: 'Recent pointer-chain entries with governed state and freshness status.',
      body: lineageEntries,
    },
    {
      title: 'Supersession Lineage',
      subtitle: 'Recent superseding and superseded pointer relationships from governed memory.',
      body: supersessionLineage,
    },
  ];
}

function buildGovernanceInterventionTrustSections(payload) {
  const governance = extractMemoryGovernancePayload(payload);
  if (!governance) {
    return [{
      title: 'Latest Governance Interventions',
      subtitle: 'Packaged intervention history for governed memory actions.',
      body: payload,
    }];
  }

  const recentInterventions = Array.isArray(governance.recent_interventions) ? governance.recent_interventions : [];
  const recentTargets = Array.isArray(governance.recent_targets) ? governance.recent_targets : [];
  const sections = [{
    title: 'Latest Governance Interventions',
    subtitle: 'Recent memory governance interventions recorded by the packaged governance spine.',
    body: {
      recent_interventions: recentInterventions,
      memory_state_counts: governance.memory_state_counts ?? {},
    },
  }];

  for (const target of recentTargets) {
    sections.push({
      title: `Target Intervention History: ${describeGovernanceTarget(target)}`,
      subtitle: 'Current packaged target state aligned with intervention history filtered to that target only.',
      body: {
        target,
        recent_interventions: recentInterventions.filter((intervention) => interventionMatchesTarget(intervention, target)),
      },
    });
  }

  return sections;
}

function updateStatusBar() {
  const settings = getSettings();
  const state = controller?.getState() ?? { running: false };

  if (!statusBar) {
    return;
  }

  if (state.running) {
    statusBar.text = `$(radio-tower) HLF ${settings.transport}`;
    statusBar.tooltip = `HLF managed bridge running via ${settings.transport}.`;
    statusBar.backgroundColor = undefined;
  } else if (settings.attachMode === 'attach') {
    statusBar.text = `$(plug) HLF ${settings.transport}`;
    statusBar.tooltip = `HLF attach mode configured for ${getEndpointUrl(settings)}.`;
    statusBar.backgroundColor = undefined;
  } else {
    statusBar.text = `$(warning) HLF stopped`;
    statusBar.tooltip = 'HLF bridge is configured for managed launch but is not running.';
    statusBar.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
  }
}

async function runDiagnostics(showMessage = false) {
  const settings = getSettings();
  const hasBearerToken = extensionContext ? await hasHttpBearerToken(extensionContext.secrets) : false;
  const httpHeaders = extensionContext
    ? await buildHttpHeaders(extensionContext.secrets, settings)
    : {};
  const result = await runBridgeDiagnostics(settings, controller, diagnosticCollection, outputChannel, {
    hasBearerToken,
    httpHeaders,
  });
  updateStatusBar();

  if (showMessage) {
    if (result.diagnostics.length === 0) {
      vscode.window.showInformationMessage(result.summary);
    } else {
      vscode.window.showWarningMessage(result.summary);
    }
  }

  return result;
}

async function startServer() {
  const settings = getSettings();
  resetLiveMcpClient();
  const result = await controller.start(settings);
  updateStatusBar();
  operatorPanelProvider?.refresh();
  await runDiagnostics(false);

  if (result.attached) {
    vscode.window.showInformationMessage(`HLF bridge configured to attach via ${settings.transport}.`);
  } else if (result.started) {
    vscode.window.showInformationMessage(`HLF bridge started with ${settings.transport}.`);
  }
}

async function stopServer() {
  const stopped = await controller.stop();
  resetLiveMcpClient();
  updateStatusBar();
  operatorPanelProvider?.refresh();
  await runDiagnostics(false);

  if (stopped) {
    vscode.window.showInformationMessage('HLF bridge stopped.');
  }
}

async function restartServer() {
  const settings = getSettings();
  await controller.restart(settings);
  resetLiveMcpClient();
  updateStatusBar();
  operatorPanelProvider?.refresh();
  await runDiagnostics(false);
  vscode.window.showInformationMessage(`HLF bridge restarted with ${settings.transport}.`);
}

async function openHealthEndpoint() {
  const settings = getSettings();
  if (settings.transport === 'stdio') {
    vscode.window.showWarningMessage('Health endpoints are only available for SSE and streamable HTTP transports.');
    return;
  }

  await vscode.env.openExternal(vscode.Uri.parse(getHealthUrl(settings)));
}

async function copyConnectionDetails() {
  const settings = getSettings();
  const hasBearerToken = extensionContext ? await hasHttpBearerToken(extensionContext.secrets) : false;
  const details = {
    transport: settings.transport,
    attachMode: settings.attachMode,
    httpAuthMode: settings.httpAuthMode,
    bearerTokenConfigured: hasBearerToken,
    endpoint: settings.transport === 'stdio' ? null : getEndpointUrl(settings),
    health: settings.transport === 'stdio' ? null : getHealthUrl(settings),
    evidencePath: settings.evidencePath ?? null,
  };

  await vscode.env.clipboard.writeText(JSON.stringify(details, null, 2));
  vscode.window.showInformationMessage('HLF connection details copied to the clipboard.');
}

async function openEvidencePath() {
  const settings = getSettings();
  if (!settings.evidencePath) {
    vscode.window.showWarningMessage('No HLF evidence path is configured.');
    return;
  }

  await vscode.commands.executeCommand('revealFileInOS', vscode.Uri.file(settings.evidencePath));
}

async function copyResourceUri(resourceUri) {
  await vscode.env.clipboard.writeText(String(resourceUri));
  vscode.window.showInformationMessage(`Copied ${resourceUri} to the clipboard.`);
}

async function resolveResourceUri(resourceUri) {
  const placeholders = getResourceUriPlaceholders(resourceUri);
  if (placeholders.length === 0) {
    return resourceUri;
  }

  const values = {};
  for (const placeholder of placeholders) {
    const value = await vscode.window.showInputBox({
      prompt: `Enter a value for ${placeholder}.`,
      ignoreFocusOut: true,
    });
    if (!value) {
      return undefined;
    }
    values[placeholder] = value.trim();
  }

  return applyResourceUriValues(resourceUri, values);
}

async function inspectResource(resourceUri) {
  const resolvedUri = await resolveResourceUri(String(resourceUri));
  if (!resolvedUri) {
    return undefined;
  }

  const result = await runPackagedAction(
    ['resource', '--uri', resolvedUri, '--json'],
    'HLF Resource Inspector',
    `Packaged resource payload for ${resolvedUri}.`,
  );
  if (!result) {
    return undefined;
  }

  trustPanel.show(`HLF Resource: ${resolvedUri}`, [
    {
      title: resolvedUri,
      subtitle: 'Packaged MCP resource payload grounded in current server resources.',
      body: result.parsed ?? result.stdout,
    },
  ]);

  return result;
}

function refreshOperatorPanel() {
  operatorPanelProvider?.refresh();
}

async function setHttpBearerToken() {
  if (!extensionContext) {
    return;
  }

  const token = await vscode.window.showInputBox({
    prompt: 'Store the HTTP bearer token for HLF bridge requests.',
    password: true,
    ignoreFocusOut: true,
  });
  if (!token) {
    return;
  }

  await storeHttpBearerToken(extensionContext.secrets, token.trim());
  outputChannel.appendLine('[hlf-vscode] stored HTTP bearer token in VS Code secret storage.');
  operatorPanelProvider?.refresh();
  await runDiagnostics(false);
  vscode.window.showInformationMessage('HLF bearer token stored in VS Code secret storage.');
}

async function clearHttpBearerToken() {
  if (!extensionContext) {
    return;
  }

  await deleteHttpBearerToken(extensionContext.secrets);
  outputChannel.appendLine('[hlf-vscode] cleared HTTP bearer token from VS Code secret storage.');
  operatorPanelProvider?.refresh();
  await runDiagnostics(false);
  vscode.window.showInformationMessage('HLF bearer token removed from VS Code secret storage.');
}

async function renderCommandResult(title, subtitle, result) {
  if (!trustPanel) {
    return;
  }

  trustPanel.show(title, [
    {
      title,
      subtitle,
      body: result.parsed ?? result.stdout ?? result.stderr ?? 'No output returned.',
    },
  ]);
}

async function runLiveMcpPackagedAction({ settings, outputChannel, args, title, secretHeaders = {} }) {
  const request = parseAttachModeArgs(args);
  const execute = async () => {
    const client = getLiveMcpClient({ settings, outputChannel, secretHeaders });

    if (request.kind === 'resource') {
      const result = await client.readResource(request.uri);
      const content = result.contents?.[0]?.text ?? '';
      let parsed;
      try {
        parsed = JSON.parse(content);
      } catch {
        parsed = content;
      }

      return {
        ok: true,
        exitCode: 0,
        stdout: typeof parsed === 'string' ? parsed : JSON.stringify(parsed, null, 2),
        stderr: '',
        parsed,
        invocation: {
          command: 'mcp-http',
          args,
        },
      };
    }

    const result = await client.callTool(request.name, request.arguments);
    const contentText = result.content?.[0]?.text;
    let parsed = result.structuredContent;
    if (parsed === undefined && contentText) {
      try {
        parsed = JSON.parse(contentText);
      } catch {
        parsed = contentText;
      }
    }

    return {
      ok: result.isError !== true,
      exitCode: result.isError ? 1 : 0,
      stdout: typeof parsed === 'string' ? parsed : JSON.stringify(parsed, null, 2),
      stderr: '',
      parsed,
      invocation: {
        command: 'mcp-http',
        args,
      },
    };
  };

  try {
    return await execute();
  } catch (error) {
    outputChannel?.appendLine(`[hlf-vscode] live MCP action failed for ${title}: ${error.message}`);
    resetLiveMcpClient();
    return await execute();
  }
}

async function runPackagedAction(args, title, subtitle) {
  const settings = getSettings();
  const unavailableReason = getPackagedActionUnavailableReason(settings);
  if (unavailableReason) {
    outputChannel.appendLine(`[hlf-vscode] skipped ${title}: ${unavailableReason}`);
    vscode.window.showWarningMessage(unavailableReason);
    return undefined;
  }

  const secretHeaders = extensionContext
    ? await buildHttpHeaders(extensionContext.secrets, settings)
    : {};
  let result;
  if (canUseLiveMcpActions(settings)) {
    result = await runLiveMcpPackagedAction({
      settings,
      outputChannel,
      args,
      title,
      secretHeaders,
    });
  } else {
    result = await runOperatorAction({
      settings,
      outputChannel,
      args,
      title,
      secretHeaders,
    });
  }

  if (!result.ok) {
    vscode.window.showErrorMessage(`${title} failed with exit code ${result.exitCode}. Check the HLF MCP Bridge output channel.`);
  }

  await renderCommandResult(title, subtitle, result);
  return result;
}

async function readPanelPayload(args, title) {
  const settings = getSettings();
  const unavailableReason = getPackagedActionUnavailableReason(settings);
  if (unavailableReason) {
    outputChannel.appendLine(`[hlf-vscode] skipped ${title} for operator panel: ${unavailableReason}`);
    return undefined;
  }

  const secretHeaders = extensionContext
    ? await buildHttpHeaders(extensionContext.secrets, settings)
    : {};
  let result;
  if (canUseLiveMcpActions(settings)) {
    result = await runLiveMcpPackagedAction({
      settings,
      outputChannel,
      args,
      title,
      secretHeaders,
    });
  } else {
    result = await runOperatorAction({
      settings,
      outputChannel,
      args,
      title,
      secretHeaders,
    });
  }

  if (!result.ok) {
    return undefined;
  }

  return result.parsed;
}

async function readProvenanceContractForPanel() {
  if (provenancePanelCache.payload && Date.now() < provenancePanelCache.expiresAt) {
    return provenancePanelCache.payload;
  }

  const payload = await readPanelPayload(['provenance-summary', '--json'], 'HLF Provenance Summary');
  if (!payload) {
    return undefined;
  }

  provenancePanelCache = {
    expiresAt: Date.now() + PROVENANCE_PANEL_CACHE_TTL_MS,
    payload,
  };
  return payload;
}

async function readMemoryGovernanceStatusForPanel() {
  return readPanelPayload(
    ['resource', '--uri', 'hlf://status/memory_governance', '--json'],
    'HLF Memory Governance',
  );
}

async function runHlfDo() {
  const intent = await vscode.window.showInputBox({
    prompt: 'Enter the governed build-assist intent to translate through HLF.',
    ignoreFocusOut: true,
  });
  if (!intent) {
    return;
  }

  const tier = await vscode.window.showQuickPick(['hearth', 'forge', 'sovereign'], {
    placeHolder: 'Choose the HLF execution tier.',
    ignoreFocusOut: true,
  });
  if (!tier) {
    return;
  }

  await runPackagedAction(
    ['do', '--intent', intent, '--tier', tier, '--dry-run', '--show-hlf', '--json'],
    'HLF Do',
    'Packaged governed front door result rendered from hlf-operator.',
  );
}

async function showTestSuiteSummary() {
  await runPackagedAction(
    ['test-summary', '--json'],
    'HLF Test Suite Summary',
    'Latest packaged pytest metrics summary.',
  );
}

async function showWeeklyEvidenceSummary() {
  await runPackagedAction(
    ['weekly-evidence-summary', '--json'],
    'HLF Weekly Evidence Summary',
    'Governed weekly evidence summary from the packaged artifact history.',
  );
}

async function showProfileCapabilityCatalog() {
  await runPackagedAction(
    ['resource', '--uri', 'hlf://status/profile_capability_catalog', '--json'],
    'HLF Profile Capability Catalog',
    'Packaged governed profile capability catalog.',
  );
}

async function showProvenanceContract() {
  await runPackagedAction(
    ['provenance-summary', '--json'],
    'HLF Provenance Contract',
    'Packaged provenance contract across memory, governance, witness, and weekly evidence.',
  );
}

function describeGovernanceTarget(target) {
  return target.pointer || `${target.topic || 'memory'}#${target.factId || target.id || 'unknown'}`;
}

async function promptForGovernanceInterventionDetails(targetLabel, action) {
  const identityDefaults = getDefaultOperatorIdentity();
  const operatorSummary = await vscode.window.showInputBox({
    prompt: `Enter the operator summary to record for ${action} on ${targetLabel}.`,
    placeHolder: 'Brief summary of what you are changing and why.',
    ignoreFocusOut: true,
  });
  if (operatorSummary === undefined) {
    return undefined;
  }
  if (!operatorSummary.trim()) {
    vscode.window.showWarningMessage('An operator summary is required for governed memory interventions.');
    return undefined;
  }

  const reason = await vscode.window.showInputBox({
    prompt: `Enter the reason to record for ${action} on ${targetLabel}.`,
    placeHolder: 'Reason code or operator explanation for the intervention.',
    ignoreFocusOut: true,
  });
  if (reason === undefined) {
    return undefined;
  }
  if (!reason.trim()) {
    vscode.window.showWarningMessage('A reason is required for governed memory interventions.');
    return undefined;
  }

  const operatorId = await vscode.window.showInputBox({
    prompt: `Enter the operator id to record for ${action} on ${targetLabel}.`,
    placeHolder: 'alice, gerry, oncall-operator, or other durable operator id.',
    value: identityDefaults.operatorId,
    ignoreFocusOut: true,
  });
  if (operatorId === undefined) {
    return undefined;
  }
  if (!operatorId.trim()) {
    vscode.window.showWarningMessage('An operator id is required for governed memory interventions.');
    return undefined;
  }

  const operatorDisplayName = await vscode.window.showInputBox({
    prompt: `Enter the operator display name to record for ${action} on ${targetLabel}.`,
    placeHolder: 'Optional human-readable operator name.',
    value: identityDefaults.operatorDisplayName,
    ignoreFocusOut: true,
  });
  if (operatorDisplayName === undefined) {
    return undefined;
  }

  const resolvedIdentity = {
    operatorId: operatorId.trim(),
    operatorDisplayName: operatorDisplayName.trim(),
    operatorChannel: identityDefaults.operatorChannel,
  };
  await persistOperatorIdentityDefaults(resolvedIdentity);

  return {
    operatorSummary: operatorSummary.trim(),
    reason: reason.trim(),
    operatorId: resolvedIdentity.operatorId,
    operatorDisplayName: resolvedIdentity.operatorDisplayName,
    operatorChannel: resolvedIdentity.operatorChannel,
  };
}

async function governMemoryTarget(target, requestedAction) {
  const allowedActions = getAllowedGovernanceActions(target || {});
  const action = requestedAction || await vscode.window.showQuickPick(allowedActions, {
    placeHolder: 'Choose the governed memory intervention to apply.',
    ignoreFocusOut: true,
  });
  if (!action) {
    return;
  }

  if (!isGovernanceActionAllowed(target || {}, action)) {
    vscode.window.showWarningMessage(
      `${action} is not a valid governed memory action for ${describeGovernanceTarget(target || {})} in state ${String(target?.state || 'unknown')}.`,
    );
    return;
  }

  const factId = target?.factId ?? target?.id;
  const sha256 = target?.sha256;
  if (!factId && !sha256) {
    vscode.window.showWarningMessage('The selected memory target does not expose a fact id or SHA256 identifier.');
    return;
  }

  const targetLabel = describeGovernanceTarget(target || {});
  const interventionDetails = await promptForGovernanceInterventionDetails(targetLabel, action);
  if (!interventionDetails) {
    return;
  }

  if (action === 'revoke' || action === 'tombstone') {
    const confirmation = await vscode.window.showWarningMessage(
      `${action === 'revoke' ? 'Revoke' : 'Tombstone'} ${targetLabel}?

Summary: ${interventionDetails.operatorSummary}
Reason: ${interventionDetails.reason}
Operator: ${interventionDetails.operatorId}${interventionDetails.operatorDisplayName ? ` (${interventionDetails.operatorDisplayName})` : ''}

This changes governed memory state and will be recorded in audit/governance history.`,
      { modal: true },
      'Confirm',
    );
    if (confirmation !== 'Confirm') {
      return;
    }
  }

  const args = [
    'memory-govern',
    '--action', action,
    '--operator-summary', interventionDetails.operatorSummary,
    '--reason', interventionDetails.reason,
    '--operator-id', interventionDetails.operatorId,
    '--operator-display-name', interventionDetails.operatorDisplayName,
    '--operator-channel', interventionDetails.operatorChannel,
    '--json',
  ];
  if (factId) {
    args.push('--fact-id', String(factId));
  }
  if (sha256) {
    args.push('--sha256', String(sha256));
  }

  const result = await runPackagedAction(
    args,
    `HLF Memory ${action[0].toUpperCase()}${action.slice(1)}`,
    `Governed memory intervention for ${targetLabel}.`,
  );
  if (!result?.ok) {
    return;
  }

  invalidateProvenancePanelCache();
  operatorPanelProvider?.refresh();
}

async function showClaimLanes() {
  trustPanel.show('HLF Claim Lanes', getClaimLaneSections());
}

function buildTrustPanelFailureSection(title, subtitle, error) {
  return {
    title,
    subtitle,
    body: {
      status: 'unavailable',
      error: error instanceof Error ? error.message : String(error || 'unknown_error'),
    },
  };
}

async function readTrustSectionPayload(args, title) {
  try {
    return await readPanelPayload(args, title);
  } catch (error) {
    outputChannel?.appendLine(`[hlf-vscode] trust panel section failed for ${title}: ${error.message}`);
    return error;
  }
}

async function openClaimLaneDoctrine() {
  const claimLaneDocPath = getClaimLanesDocPath(getWorkspaceRoot());
  if (!claimLaneDocPath) {
    vscode.window.showWarningMessage('HLF claim-lane doctrine is unavailable because no workspace folder is open.');
    return;
  }

  await vscode.commands.executeCommand('vscode.open', vscode.Uri.file(claimLaneDocPath));
}

async function openTrustPanel() {
  const sections = [...getClaimLaneSections()];
  const routeResult = await readTrustSectionPayload(
    ['resource', '--uri', 'hlf://status/governed_route', '--json'],
    'HLF Trust Panel: Governed Route',
  );
  sections.push(routeResult instanceof Error
    ? buildTrustPanelFailureSection('Governed Route', 'Latest packaged route rationale and selected lane.', routeResult)
    : {
      title: 'Governed Route',
      subtitle: 'Latest packaged route rationale and selected lane.',
      body: routeResult ?? { status: 'unavailable', error: 'no_payload_returned' },
    });

  const verifierResult = await readTrustSectionPayload(
    ['resource', '--uri', 'hlf://status/formal_verifier', '--json'],
    'HLF Trust Panel: Formal Verifier',
  );
  sections.push(verifierResult instanceof Error
    ? buildTrustPanelFailureSection('Formal Verifier', 'Packaged verifier status surface.', verifierResult)
    : {
      title: 'Formal Verifier',
      subtitle: 'Packaged verifier status surface.',
      body: verifierResult ?? { status: 'unavailable', error: 'no_payload_returned' },
    });

  const witnessResult = await readTrustSectionPayload(
    ['resource', '--uri', 'hlf://status/witness_governance', '--json'],
    'HLF Trust Panel: Witness Governance',
  );
  sections.push(witnessResult instanceof Error
    ? buildTrustPanelFailureSection('Witness Governance', 'Current witness governance trust surface.', witnessResult)
    : {
      title: 'Witness Governance',
      subtitle: 'Current witness governance trust surface.',
      body: witnessResult ?? { status: 'unavailable', error: 'no_payload_returned' },
    });

  const memoryGovernanceResult = await readTrustSectionPayload(
    ['resource', '--uri', 'hlf://status/memory_governance', '--json'],
    'HLF Trust Panel: Memory Governance',
  );
  if (memoryGovernanceResult instanceof Error) {
    sections.push(buildTrustPanelFailureSection(
      'Latest Governance Interventions',
      'Recent memory governance interventions recorded by the packaged governance spine.',
      memoryGovernanceResult,
    ));
  } else {
    sections.push(...buildGovernanceInterventionTrustSections(
      memoryGovernanceResult ?? { status: 'unavailable', error: 'no_payload_returned' },
    ));
  }

  const memoryResult = await readTrustSectionPayload(
    ['provenance-summary', '--json'],
    'HLF Trust Panel: Provenance Contract',
  );
  if (memoryResult instanceof Error) {
    sections.push(buildTrustPanelFailureSection(
      'Memory Provenance',
      'Packaged provenance contract across memory, governance, witness, and evidence surfaces.',
      memoryResult,
    ));
  } else {
    sections.push(...buildProvenanceTrustSections(
      memoryResult ?? { status: 'unavailable', error: 'no_payload_returned' },
    ));
  }

  trustPanel.show('HLF Trust Panel', sections);
}

async function runFirstRunValidation() {
  const settings = getSettings();
  const diagnostics = await runDiagnostics(false);
  const hasBearerToken = extensionContext ? await hasHttpBearerToken(extensionContext.secrets) : false;
  const findings = [...diagnostics.findings];
  findings.push(`Transport: ${settings.transport}`);
  findings.push(`Attach mode: ${settings.attachMode}`);
  findings.push(`HTTP auth mode: ${settings.httpAuthMode}`);
  findings.push(`Bearer token configured: ${hasBearerToken ? 'yes' : 'no'}`);

  trustPanel.show('HLF First-Run Validation', [
    {
      title: 'Validation Summary',
      subtitle: diagnostics.summary,
      body: findings,
    },
  ]);

  if (diagnostics.diagnostics.length === 0) {
    vscode.window.showInformationMessage('HLF first-run validation passed.');
  } else {
    vscode.window.showWarningMessage('HLF first-run validation reported issues. Review the trust panel and diagnostics.');
  }
}

function activate(context) {
  extensionContext = context;
  outputChannel = vscode.window.createOutputChannel('HLF MCP Bridge');
  diagnosticCollection = vscode.languages.createDiagnosticCollection('hlf-bridge');
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
  statusBar.command = 'hlf.runDiagnostics';
  statusBar.show();

  controller = new HlfServerController(outputChannel, updateStatusBar);
  trustPanel = new TrustPanel(context.extensionUri);
  operatorPanelProvider = new OperatorPanelProvider(controller, async () => ({
    hasBearerToken: await hasHttpBearerToken(context.secrets),
  }), readProvenanceContractForPanel, readMemoryGovernanceStatusForPanel);

  context.subscriptions.push(outputChannel, diagnosticCollection, statusBar);
  context.subscriptions.push(vscode.window.registerTreeDataProvider('hlf.operatorPanel', operatorPanelProvider));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.startServer', startServer));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.stopServer', stopServer));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.restartServer', restartServer));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.runDiagnostics', () => runDiagnostics(true)));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.openHealthEndpoint', openHealthEndpoint));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.copyConnectionDetails', copyConnectionDetails));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.openEvidencePath', openEvidencePath));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.copyResourceUri', copyResourceUri));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.inspectResource', inspectResource));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.refreshOperatorPanel', refreshOperatorPanel));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.manageOperatorIdentityDefaults', manageOperatorIdentityDefaults));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.setHttpBearerToken', setHttpBearerToken));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.clearHttpBearerToken', clearHttpBearerToken));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.runFirstRunValidation', runFirstRunValidation));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.runHlfDo', runHlfDo));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showTestSuiteSummary', showTestSuiteSummary));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showWeeklyEvidenceSummary', showWeeklyEvidenceSummary));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showProvenanceContract', showProvenanceContract));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.governMemoryTarget', governMemoryTarget));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showProfileCapabilityCatalog', showProfileCapabilityCatalog));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showClaimLanes', showClaimLanes));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.openClaimLaneDoctrine', openClaimLaneDoctrine));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.openTrustPanel', openTrustPanel));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
    if (event.affectsConfiguration('hlf')) {
      outputChannel.appendLine('[hlf-vscode] configuration changed; rerunning diagnostics.');
      invalidateProvenancePanelCache();
      resetLiveMcpClient();
      updateStatusBar();
      operatorPanelProvider?.refresh();
      void runDiagnostics(false);
    }
  }));

  updateStatusBar();
  operatorPanelProvider.refresh();
  void runDiagnostics(false);
}

async function deactivate() {
  if (controller) {
    await controller.stop();
  }
}

module.exports = {
  activate,
  buildAttachModeActionRequest: parseAttachModeArgs,
  buildGovernanceInterventionTrustSections,
  buildProvenanceTrustSections,
  buildTrustPanelFailureSection,
  canRunLocalPackagedActions,
  canUseLiveMcpActions,
  deactivate,
  extractProvenanceContractPayload,
  getDefaultOperatorIdentity,
  getLiveMcpClientCacheSignature,
  manageOperatorIdentityDefaults,
  governMemoryTarget,
  getPackagedActionUnavailableReason,
  readTrustSectionPayload,
  resetLiveMcpClient,
  runLiveMcpPackagedAction,
};