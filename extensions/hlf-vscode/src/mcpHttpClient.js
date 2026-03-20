const http = require('node:http');
const https = require('node:https');

const { getEndpointUrl } = require('./config');

const MCP_PROTOCOL_VERSION = '2025-03-26';

function parseEventStreamMessages(body) {
  const messages = [];
  const lines = String(body).split(/\r?\n/);
  let dataLines = [];

  for (const line of lines) {
    if (!line.trim()) {
      if (dataLines.length > 0) {
        const payload = dataLines.join('\n');
        messages.push(JSON.parse(payload));
        dataLines = [];
      }
      continue;
    }

    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }

  if (dataLines.length > 0) {
    messages.push(JSON.parse(dataLines.join('\n')));
  }

  return messages;
}

class StreamableHttpMcpClient {
  constructor({ settings, outputChannel, secretHeaders = {} }) {
    this.settings = settings;
    this.outputChannel = outputChannel;
    this.secretHeaders = secretHeaders;
    this.sessionId = undefined;
    this.initialized = false;
  }

  async ensureInitialized() {
    if (this.initialized && this.sessionId) {
      return;
    }

    const initializeMessage = {
      jsonrpc: '2.0',
      id: 'hlf-vscode-initialize',
      method: 'initialize',
      params: {
        protocolVersion: MCP_PROTOCOL_VERSION,
        capabilities: {},
        clientInfo: {
          name: 'hlf-vscode',
          version: '0.1.0',
        },
      },
    };

    const initializeResponse = await this._postMessage(initializeMessage, { requireResponse: true });
    if (!initializeResponse.sessionId) {
      throw new Error('MCP initialize response did not include mcp-session-id.');
    }
    this.sessionId = initializeResponse.sessionId;
    this._assertResponseOk(initializeResponse.message, 'initialize');

    await this._postMessage(
      {
        jsonrpc: '2.0',
        method: 'notifications/initialized',
        params: {},
      },
      { requireResponse: false },
    );
    this.initialized = true;
  }

  async callTool(name, args) {
    await this.ensureInitialized();
    const response = await this._postMessage(
      {
        jsonrpc: '2.0',
        id: `tool:${name}`,
        method: 'tools/call',
        params: {
          name,
          arguments: args,
        },
      },
      { requireResponse: true },
    );
    this._assertResponseOk(response.message, `tools/call ${name}`);
    return response.message.result;
  }

  async readResource(uri) {
    await this.ensureInitialized();
    const response = await this._postMessage(
      {
        jsonrpc: '2.0',
        id: `resource:${uri}`,
        method: 'resources/read',
        params: { uri },
      },
      { requireResponse: true },
    );
    this._assertResponseOk(response.message, `resources/read ${uri}`);
    return response.message.result;
  }

  _assertResponseOk(message, context) {
    if (!message) {
      throw new Error(`Missing MCP response for ${context}.`);
    }
    if (message.error) {
      throw new Error(`${context} failed: ${message.error.message}`);
    }
  }

  async _postMessage(message, { requireResponse }) {
    const endpoint = new URL(getEndpointUrl(this.settings));
    const transport = endpoint.protocol === 'https:' ? https : http;
    const body = JSON.stringify(message);

    const headers = {
      Accept: 'application/json, text/event-stream',
      'Content-Type': 'application/json',
      ...this.secretHeaders,
    };

    if (this.sessionId) {
      headers['mcp-session-id'] = this.sessionId;
    }

    this.outputChannel?.appendLine(
      `[hlf-vscode] MCP HTTP ${message.method}${this.sessionId ? ` session=${this.sessionId}` : ''}`,
    );

    return new Promise((resolve, reject) => {
      const request = transport.request(
        endpoint,
        {
          method: 'POST',
          headers,
        },
        (response) => {
          let responseBody = '';
          response.setEncoding('utf8');
          response.on('data', (chunk) => {
            responseBody += chunk;
          });
          response.on('end', () => {
            const sessionId = response.headers['mcp-session-id'];
            const statusCode = response.statusCode ?? 0;
            if (statusCode < 200 || statusCode >= 300) {
              reject(new Error(`MCP HTTP request failed with status ${statusCode}.`));
              return;
            }

            if (!requireResponse && !responseBody.trim()) {
              resolve({ message: undefined, sessionId });
              return;
            }

            const contentType = String(response.headers['content-type'] || '');
            try {
              let parsedMessage;
              if (contentType.includes('text/event-stream')) {
                const messages = parseEventStreamMessages(responseBody);
                parsedMessage = messages[messages.length - 1];
              } else {
                parsedMessage = JSON.parse(responseBody);
              }
              resolve({ message: parsedMessage, sessionId });
            } catch (error) {
              reject(new Error(`Failed to parse MCP HTTP response: ${error.message}`));
            }
          });
        },
      );

      request.on('error', (error) => {
        reject(error);
      });

      request.write(body);
      request.end();
    });
  }
}

module.exports = {
  MCP_PROTOCOL_VERSION,
  StreamableHttpMcpClient,
  parseEventStreamMessages,
};