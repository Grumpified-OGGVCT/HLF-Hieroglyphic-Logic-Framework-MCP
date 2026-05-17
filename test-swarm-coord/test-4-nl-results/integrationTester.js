const http = require('http');
const https = require('https');
const fs = require('fs');
const path = require('path');
const urlModule = require('url');

class IntegrationTester {
  constructor(configPath = path.join(__dirname, 'testScenarios.json')) {
    this.configPath = configPath;
    this.scenarios = [];
  }

  loadScenarios() {
    if (fs.existsSync(this.configPath)) {
      const raw = fs.readFileSync(this.configPath, 'utf8');
      this.scenarios = JSON.parse(raw);
    } else {
      // default scenarios for testing
      this.scenarios = [
        {
          name: "Orchestrator Health Check",
          method: "GET",
          url: "http://localhost:3000/health",
          expectedStatus: 200,
          expectedBodyContains: "OK"
        },
        {
          name: "Integration Agent Registration",
          method: "POST",
          url: "http://localhost:3000/agent/register",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ agentId: "IntegrationTester", role: "tester" }),
          expectedStatus: 200,
          expectedBodyContains: "registered"
        }
      ];
    }
  }

  async runTests() {
    this.loadScenarios();
    const results = [];
    for (const scenario of this.scenarios) {
      const result = await this.runScenario(scenario);
      results.push(result);
    }
    return results;
  }

  runScenario(scenario) {
    return new Promise((resolve) => {
      const parsed = urlModule.parse(scenario.url);
      const isHttps = parsed.protocol === 'https:';
      const transport = isHttps ? https : http;
      const options = {
        hostname: parsed.hostname,
        port: parsed.port || (isHttps ? 443 : 80),
        path: parsed.path,
        method: scenario.method,
        headers: scenario.headers || {}
      };
      const req = transport.request(options, (res) => {
        let data = '';
        res.on('data', chunk => data += chunk);
        res.on('end', () => {
          const statusMatch = res.statusCode === scenario.expectedStatus;
          const bodyMatch = scenario.expectedBodyContains ? data.includes(scenario.expectedBodyContains) : true;
          resolve({
            name: scenario.name,
            status: statusMatch && bodyMatch ? "PASS" : "FAIL",
            details: {
              expectedStatus: scenario.expectedStatus,
              actualStatus: res.statusCode,
              expectedBodyContains: scenario.expectedBodyContains || null,
              bodyContains: scenario.expectedBodyContains ? data.includes(scenario.expectedBodyContains) : null
            }
          });
        });
      });
      req.on('error', (e) => {
        resolve({
          name: scenario.name,
          status: "ERROR",
          details: { error: e.message }
        });
      });
      if (scenario.body) {
        req.write(scenario.body);
      }
      req.end();
    });
  }
}

// If run directly, execute tests and output results
if (require.main === module) {
  const tester = new IntegrationTester();
  tester.runTests().then(results => {
    console.log(JSON.stringify(results, null, 2));
    const failed = results.filter(r => r.status !== "PASS");
    process.exit(failed.length > 0 ? 1 : 0);
  }).catch(err => {
    console.error(err);
    process.exit(1);
  });
} else {
  module.exports = IntegrationTester;
}