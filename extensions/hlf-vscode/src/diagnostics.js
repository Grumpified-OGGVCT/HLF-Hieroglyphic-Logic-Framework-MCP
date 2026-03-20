const http = require('node:http');
const https = require('node:https');
const vscode = require('vscode');

const { getEndpointUrl, getHealthUrl, validateSettings } = require('./config');

const DIAGNOSTIC_URI = vscode.Uri.parse('hlf:/bridge-configuration');

function makeDiagnostic(message, severity) {
  const range = new vscode.Range(0, 0, 0, 1);
  const mappedSeverity = severity === 'warning'
    ? vscode.DiagnosticSeverity.Warning
    : severity === 'info'
      ? vscode.DiagnosticSeverity.Information
      : vscode.DiagnosticSeverity.Error;

  return new vscode.Diagnostic(range, message, mappedSeverity);
}

function httpRequest(urlString, timeoutMs, headers = {}) {
  return new Promise((resolve) => {
    const target = new URL(urlString);
    const client = target.protocol === 'https:' ? https : http;

    const request = client.request(
      target,
      {
        method: 'GET',
        headers,
        timeout: timeoutMs,
      },
      (response) => {
        let body = '';
        response.setEncoding('utf8');
        response.on('data', (chunk) => {
          body += chunk;
        });
        response.on('end', () => {
          resolve({ ok: true, statusCode: response.statusCode ?? 0, body });
        });
      },
    );

    request.on('timeout', () => {
      request.destroy(new Error(`Health probe timed out after ${timeoutMs}ms.`));
    });

    request.on('error', (error) => {
      resolve({ ok: false, statusCode: 0, error: error.message });
    });

    request.end();
  });
}

async function runBridgeDiagnostics(settings, controller, diagnosticCollection, outputChannel, options = {}) {
  const diagnostics = [];
  const findings = [];
  const authConfigured = Boolean(options.hasBearerToken);

  for (const problem of validateSettings(settings)) {
    diagnostics.push(makeDiagnostic(problem.message, problem.severity));
    findings.push(problem.message);
  }

  if (settings.httpAuthMode === 'bearer' && !authConfigured) {
    const message = 'HTTP auth mode is `bearer` but no bearer token is stored in VS Code secret storage.';
    diagnostics.push(makeDiagnostic(message, 'warning'));
    findings.push(message);
  }

  if (settings.transport === 'stdio' && settings.attachMode === 'launch' && !controller.isRunning()) {
    const message = 'Managed stdio launch is configured but no HLF process is currently running.';
    diagnostics.push(makeDiagnostic(message, 'warning'));
    findings.push(message);
  }

  if (settings.transport !== 'stdio') {
    const endpointUrl = getEndpointUrl(settings);
    const healthUrl = getHealthUrl(settings);
    findings.push(`Endpoint: ${endpointUrl}`);
    findings.push(`Health: ${healthUrl}`);

    if (settings.attachMode === 'launch' && !controller.isRunning()) {
      const message = 'Managed HTTP launch is configured but no HLF process is currently running, so live health probing was skipped.';
      diagnostics.push(makeDiagnostic(message, 'warning'));
      findings.push(message);
    } else {
      const result = await httpRequest(healthUrl, settings.httpHealthTimeoutMs, options.httpHeaders ?? {});
      if (!result.ok) {
        const message = `Health probe failed for ${healthUrl}: ${result.error}`;
        diagnostics.push(makeDiagnostic(message, 'warning'));
        findings.push(message);
      } else if (result.statusCode < 200 || result.statusCode >= 300) {
        const message = `Health probe returned HTTP ${result.statusCode} for ${healthUrl}.`;
        diagnostics.push(makeDiagnostic(message, 'warning'));
        findings.push(message);
      } else {
        findings.push(`Health probe succeeded with HTTP ${result.statusCode}.`);
      }
    }
  }

  diagnosticCollection.set(DIAGNOSTIC_URI, diagnostics);
  outputChannel.appendLine(`[hlf-vscode] diagnostics completed with ${diagnostics.length} issue(s).`);

  return {
    diagnostics,
    findings,
    summary: diagnostics.length === 0
      ? 'HLF bridge diagnostics passed.'
      : `HLF bridge diagnostics reported ${diagnostics.length} issue(s).`,
  };
}

module.exports = {
  DIAGNOSTIC_URI,
  runBridgeDiagnostics,
};