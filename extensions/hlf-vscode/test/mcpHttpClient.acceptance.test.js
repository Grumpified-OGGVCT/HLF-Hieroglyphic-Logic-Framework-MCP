const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const { loadWithMocks } = require('./helpers/loadWithMocks');

test('mcp http client acceptance: parses SSE-framed MCP messages', () => {
  const { parseEventStreamMessages } = loadWithMocks(path.join(__dirname, '..', 'src', 'mcpHttpClient.js'), {
    './config': {
      getEndpointUrl() {
        return 'http://127.0.0.1:8000/mcp';
      },
    },
  });

  const messages = parseEventStreamMessages(
    'event: message\n' +
    'data: {"jsonrpc":"2.0","id":"3","result":{"ok":true}}\n\n',
  );

  assert.deepEqual(messages, [
    {
      jsonrpc: '2.0',
      id: '3',
      result: { ok: true },
    },
  ]);
});