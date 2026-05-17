const http = require('http');
const { strictEqual, ok } = require('assert');

const BASE_URL = process.env.TEST_BASE_URL || 'http://localhost:3000';

function fetch(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        resolve({ status: res.statusCode, headers: res.headers, body: data });
      });
    }).on('error', reject);
  });
}

async function runTests() {
  let passed = 0;
  let failed = 0;
  const test = async (name, fn) => {
    try {
      await fn();
      console.log(`✓ ${name}`);
      passed++;
    } catch (err) {
      console.log(`✗ ${name}: ${err.message}`);
      failed++;
    }
  };

  await test('GET /health returns 200', async () => {
    const res = await fetch(`${BASE_URL}/health`);
    strictEqual(res.status, 200, 'Status should be 200');
  });

  await test('GET /health returns JSON with status ok', async () => {
    const res = await fetch(`${BASE_URL}/health`);
    const json = JSON.parse(res.body);
    ok(json.status === 'ok', 'Expected status ok');
  });

  console.log(`\nTests completed: ${passed} passed, ${failed} failed`);
  if (failed > 0) process.exit(1);
}

module.exports = { runTests };
