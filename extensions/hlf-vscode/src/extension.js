const vscode = require('vscode');

const { getClaimLaneSections, getClaimLanesDocPath } = require('./claimLanes');
const { getEndpointUrl, getHealthUrl, getSettings, getWorkspaceRoot } = require('./config');
const { runBridgeDiagnostics } = require('./diagnostics');
const { HlfServerController } = require('./launcher');
const { StreamableHttpMcpClient } = require('./mcpHttpClient');
const { OperatorPanelProvider } = require('./operatorPanel');
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

function canRunLocalPackagedActions(settings) {
  return settings.attachMode !== 'attach';
}

function canProxyPackagedActions(settings) {
  return settings.attachMode === 'attach' && settings.transport === 'streamable-http';
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
  if (canRunLocalPackagedActions(settings) || canProxyPackagedActions(settings)) {
    return undefined;
  }

  return 'Attach-mode packaged operator actions currently require streamable-http transport. SSE attach mode still exposes diagnostics and connection state only.';
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

async function runAttachModePackagedAction({ settings, outputChannel, args, title, secretHeaders = {} }) {
  const request = parseAttachModeArgs(args);
  const client = new StreamableHttpMcpClient({ settings, outputChannel, secretHeaders });

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
  const result = canProxyPackagedActions(settings)
    ? await runAttachModePackagedAction({
      settings,
      outputChannel,
      args,
      title,
      secretHeaders,
    })
    : await runOperatorAction({
      settings,
      outputChannel,
      args,
      title,
      secretHeaders,
    });

  if (!result.ok) {
    vscode.window.showErrorMessage(`${title} failed with exit code ${result.exitCode}. Check the HLF MCP Bridge output channel.`);
  }

  await renderCommandResult(title, subtitle, result);
  return result;
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

async function showClaimLanes() {
  trustPanel.show('HLF Claim Lanes', getClaimLaneSections());
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
  const routeResult = await runPackagedAction(
    ['resource', '--uri', 'hlf://status/governed_route', '--json'],
    'HLF Trust Panel',
    'Combined trust surfaces from packaged status resources.',
  );
  if (!routeResult) {
    return;
  }
  sections.push({
    title: 'Governed Route',
    subtitle: 'Latest packaged route rationale and selected lane.',
    body: routeResult.parsed ?? routeResult.stdout,
  });

  const verifierResult = await runPackagedAction(
    ['resource', '--uri', 'hlf://status/formal_verifier', '--json'],
    'HLF Trust Panel',
    'Combined trust surfaces from packaged status resources.',
  );
  sections.push({
    title: 'Formal Verifier',
    subtitle: 'Packaged verifier status surface.',
    body: verifierResult.parsed ?? verifierResult.stdout,
  });

  const witnessResult = await runPackagedAction(
    ['resource', '--uri', 'hlf://status/witness_governance', '--json'],
    'HLF Trust Panel',
    'Combined trust surfaces from packaged status resources.',
  );
  sections.push({
    title: 'Witness Governance',
    subtitle: 'Current witness governance trust surface.',
    body: witnessResult.parsed ?? witnessResult.stdout,
  });

  const memoryResult = await runPackagedAction(
    ['resource', '--uri', 'hlf://status/benchmark_artifacts', '--json'],
    'HLF Trust Panel',
    'Combined trust surfaces from packaged status resources.',
  );
  sections.push({
    title: 'Memory Provenance',
    subtitle: 'Benchmark artifacts and memory evidence references from packaged truth.',
    body: memoryResult.parsed ?? memoryResult.stdout,
  });

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
  }));

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
  context.subscriptions.push(vscode.commands.registerCommand('hlf.setHttpBearerToken', setHttpBearerToken));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.clearHttpBearerToken', clearHttpBearerToken));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.runFirstRunValidation', runFirstRunValidation));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.runHlfDo', runHlfDo));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showTestSuiteSummary', showTestSuiteSummary));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showWeeklyEvidenceSummary', showWeeklyEvidenceSummary));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showProfileCapabilityCatalog', showProfileCapabilityCatalog));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.showClaimLanes', showClaimLanes));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.openClaimLaneDoctrine', openClaimLaneDoctrine));
  context.subscriptions.push(vscode.commands.registerCommand('hlf.openTrustPanel', openTrustPanel));
  context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((event) => {
    if (event.affectsConfiguration('hlf')) {
      outputChannel.appendLine('[hlf-vscode] configuration changed; rerunning diagnostics.');
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
  canRunLocalPackagedActions,
  canProxyPackagedActions,
  deactivate,
  getPackagedActionUnavailableReason,
  runAttachModePackagedAction,
};