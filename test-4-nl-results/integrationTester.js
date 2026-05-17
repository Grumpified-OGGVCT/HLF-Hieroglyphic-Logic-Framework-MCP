const http = require('http');
const assert = require('assert');

class IntegrationTester {
  constructor(options = {}) {
    this.baseUrl = options.baseUrl || 'http://localhost:3000';
    this.tests = [];
    this.beforeAllFns = [];
    this.afterAllFns = [];
    this.results = [];
  }

  beforeAll(fn) {
    this.beforeAllFns.push(fn);
  }

  afterAll(fn) {
    this.afterAllFns.push(fn);
  }

  test(name, fn) {
    this.tests.push({ name, fn });
  }

  async run() {
    console.log('Running integration tests...');
    for (const fn of this.beforeAllFns) {
      await fn();
    }

    for (const { name, fn } of this.tests) {
      try {
        await fn();
        console.log(`  ✓ ${name}`);
        this.results.push({ name, status: 'pass' });
      } catch (err) {
        console.log(`  ✗ ${name}`);
        console.log(`    ${err.message}`);
        this.results.push({ name, status: 'fail', error: err.message });
      }
    }

    for (const fn of this.afterAllFns) {
      await fn();
    }

    const failed = this.results.filter(r => r.status === 'fail').length;
    console.log(`\nResults: ${this.results.length - failed} passed, ${failed} failed.`);
    return this.results;
  }

  // Helper to make HTTP requests
  request(method, path, body) {
    return new Promise((resolve, reject) => {
      const url = new URL(path, this.baseUrl);
      const options = {
        method,
        hostname: url.hostname,
        port: url.port,
        path: url.pathname + url.search,
        headers: { 'Content-Type': 'application/json' }
      };

      const req = http.request(options, res => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          try {
            const parsed = JSON.parse(data);
            resolve({ status: res.statusCode, body: parsed });
          } catch {
            resolve({ status: res.statusCode, body: data });
          }
        });
      });

      req.on('error', reject);
      if (body) {
        req.write(JSON.stringify(body));
      }
      req.end();
    });
  }

  // Built-in assertions
  assertStatus(response, expectedStatus) {
    assert.strictEqual(response.status, expectedStatus, `Expected status ${expectedStatus} but got ${response.status}`);
  }

  assertBodyContains(response, expectedKey) {
    assert.ok(response.body && response.body[expectedKey] !== undefined, `Response body missing key "${expectedKey}"`);
  }
}

module.exports = IntegrationTester;
