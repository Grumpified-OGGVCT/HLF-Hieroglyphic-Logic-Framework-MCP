const path = require('node:path');
const vscode = require('vscode');

const EXTENSION_SECTION = 'hlf';
const SUPPORTED_TRANSPORTS = ['stdio', 'sse', 'streamable-http'];
const SUPPORTED_ATTACH_MODES = ['launch', 'attach'];
const SUPPORTED_HTTP_AUTH_MODES = ['none', 'bearer'];

function getWorkspaceRoot() {
  return vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
}

function resolveWorkspaceTokens(value) {
  if (typeof value !== 'string') {
    return value;
  }

  const workspaceRoot = getWorkspaceRoot();
  if (!workspaceRoot) {
    return value;
  }

  return value.replaceAll('${workspaceFolder}', workspaceRoot);
}

function normalizeStringArray(value) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item));
  }

  if (typeof value === 'string' && value.trim()) {
    return value.split(' ').map((item) => item.trim()).filter(Boolean);
  }

  return [];
}

function normalizeEnvironment(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(value).map(([key, entryValue]) => [key, resolveWorkspaceTokens(String(entryValue))]),
  );
}

function normalizePath(value) {
  if (typeof value !== 'string' || !value.trim()) {
    return undefined;
  }

  const resolved = resolveWorkspaceTokens(value.trim());
  return path.normalize(resolved);
}

function getSettings() {
  const configuration = vscode.workspace.getConfiguration(EXTENSION_SECTION);
  const transport = String(configuration.get('transport', 'stdio')).trim();
  const attachMode = String(configuration.get('attachMode', 'launch')).trim();
  const httpAuthMode = String(configuration.get('http.authMode', 'none')).trim();
  const httpEndpoint = String(configuration.get('http.endpoint', '/mcp')).trim() || '/mcp';
  const httpHealthPath = String(configuration.get('http.healthPath', '/health')).trim() || '/health';

  return {
    transport,
    attachMode,
    httpAuthMode,
    serverCommand: String(configuration.get('server.command', 'uv')).trim(),
    serverArgs: normalizeStringArray(configuration.get('server.args', [])),
    serverCwd: normalizePath(configuration.get('server.cwd', '${workspaceFolder}')),
    serverEnv: normalizeEnvironment(configuration.get('server.env', {})),
    httpHost: String(configuration.get('http.host', '127.0.0.1')).trim(),
    httpPort: Number(configuration.get('http.port', 8000)),
    httpEndpoint: httpEndpoint.startsWith('/') ? httpEndpoint : `/${httpEndpoint}`,
    httpHealthPath: httpHealthPath.startsWith('/') ? httpHealthPath : `/${httpHealthPath}`,
    httpHealthTimeoutMs: Number(configuration.get('http.healthTimeoutMs', 3000)),
    evidencePath: normalizePath(configuration.get('evidence.path', '${workspaceFolder}/observability')),
  };
}

function getBaseHttpUrl(settings) {
  return `http://${settings.httpHost}:${settings.httpPort}`;
}

function getHealthUrl(settings) {
  return `${getBaseHttpUrl(settings)}${settings.httpHealthPath}`;
}

function getEndpointUrl(settings) {
  if (settings.transport === 'sse') {
    return `${getBaseHttpUrl(settings)}/sse`;
  }

  return `${getBaseHttpUrl(settings)}${settings.httpEndpoint}`;
}

function validateSettings(settings) {
  const problems = [];

  if (!SUPPORTED_TRANSPORTS.includes(settings.transport)) {
    problems.push({ severity: 'error', message: `Unsupported transport '${settings.transport}'.` });
  }

  if (!SUPPORTED_ATTACH_MODES.includes(settings.attachMode)) {
    problems.push({ severity: 'error', message: `Unsupported attach mode '${settings.attachMode}'.` });
  }

  if (!SUPPORTED_HTTP_AUTH_MODES.includes(settings.httpAuthMode)) {
    problems.push({ severity: 'error', message: `Unsupported HTTP auth mode '${settings.httpAuthMode}'.` });
  }

  if (settings.transport === 'stdio' && settings.attachMode === 'attach') {
    problems.push({ severity: 'error', message: 'stdio requires attach mode `launch`; attach mode is only valid for HTTP transports.' });
  }

  if (settings.attachMode === 'launch' && !settings.serverCommand) {
    problems.push({ severity: 'error', message: 'A server command is required when attach mode is `launch`.' });
  }

  if (settings.transport !== 'stdio') {
    if (!settings.httpHost) {
      problems.push({ severity: 'error', message: 'An HTTP host is required for SSE and streamable HTTP transports.' });
    }
    if (!Number.isInteger(settings.httpPort) || settings.httpPort < 1 || settings.httpPort > 65535) {
      problems.push({ severity: 'error', message: 'HTTP port must be an integer between 1 and 65535.' });
    }
    if (!settings.httpEndpoint.startsWith('/')) {
      problems.push({ severity: 'error', message: 'HTTP endpoint must start with `/`.' });
    }
    if (!settings.httpHealthPath.startsWith('/')) {
      problems.push({ severity: 'error', message: 'Health path must start with `/`.' });
    }
  }

  return problems;
}

module.exports = {
  EXTENSION_SECTION,
  SUPPORTED_ATTACH_MODES,
  SUPPORTED_HTTP_AUTH_MODES,
  SUPPORTED_TRANSPORTS,
  getBaseHttpUrl,
  getEndpointUrl,
  getHealthUrl,
  getSettings,
  getWorkspaceRoot,
  resolveWorkspaceTokens,
  validateSettings,
};