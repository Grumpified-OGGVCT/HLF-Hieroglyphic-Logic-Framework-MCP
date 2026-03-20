const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { loadWithMocks } = require('./helpers/loadWithMocks');

function loadConfigWithConfiguration(configurationValues, workspaceRoot = 'C:\\repo') {
  return loadWithMocks(path.join(__dirname, '..', 'src', 'config.js'), {
    vscode: {
      workspace: {
        workspaceFolders: [{ uri: { fsPath: workspaceRoot } }],
        getConfiguration() {
          return {
            get(key, fallback) {
              return Object.prototype.hasOwnProperty.call(configurationValues, key)
                ? configurationValues[key]
                : fallback;
            },
          };
        },
      },
    },
  });
}

test('config acceptance: normalizes workspace tokens and HTTP paths', () => {
  const config = loadConfigWithConfiguration({
    transport: 'streamable-http',
    attachMode: 'attach',
    'http.authMode': 'bearer',
    'server.cwd': '${workspaceFolder}\\runtime',
    'http.endpoint': 'mcp',
    'http.healthPath': 'healthz',
    'server.env': {
      HLF_HOME: '${workspaceFolder}\\artifacts',
    },
  });

  const settings = config.getSettings();

  assert.equal(settings.transport, 'streamable-http');
  assert.equal(settings.attachMode, 'attach');
  assert.equal(settings.httpAuthMode, 'bearer');
  assert.equal(settings.serverCwd, path.normalize('C:\\repo\\runtime'));
  assert.equal(settings.httpEndpoint, '/mcp');
  assert.equal(settings.httpHealthPath, '/healthz');
  assert.equal(settings.serverEnv.HLF_HOME, path.normalize('C:\\repo\\artifacts'));
  assert.equal(config.getEndpointUrl(settings), 'http://127.0.0.1:8000/mcp');
  assert.equal(config.getHealthUrl(settings), 'http://127.0.0.1:8000/healthz');
});

test('config acceptance: rejects stdio attach mode and invalid ports', () => {
  const config = loadConfigWithConfiguration({
    transport: 'stdio',
    attachMode: 'attach',
    'http.port': 70000,
  });

  const problems = config.validateSettings(config.getSettings());
  const messages = problems.map((problem) => problem.message);

  assert.ok(messages.includes('stdio requires attach mode `launch`; attach mode is only valid for HTTP transports.'));
});