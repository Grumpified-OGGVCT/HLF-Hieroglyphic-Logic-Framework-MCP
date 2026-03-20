const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { EventEmitter } = require('node:events');

const { loadWithMocks } = require('./helpers/loadWithMocks');

function createChildProcess(pid = 4242) {
  const processHandle = new EventEmitter();
  processHandle.pid = pid;
  processHandle.killed = false;
  processHandle.stdout = new EventEmitter();
  processHandle.stderr = new EventEmitter();
  processHandle.kill = () => {
    processHandle.killed = true;
  };
  return processHandle;
}

test('launcher acceptance: attach mode reports attached without spawning', async () => {
  let spawnCalled = false;
  const { HlfServerController } = loadWithMocks(path.join(__dirname, '..', 'src', 'launcher.js'), {
    'node:child_process': {
      spawn() {
        spawnCalled = true;
        return createChildProcess();
      },
    },
  });

  const output = [];
  const controller = new HlfServerController({ appendLine: (line) => output.push(line) }, () => {});
  const result = await controller.start({ transport: 'sse', attachMode: 'attach' });

  assert.deepEqual(result, { started: false, attached: true });
  assert.equal(spawnCalled, false);
  assert.match(output[0], /attach mode enabled/);
});

test('launcher acceptance: launch mode spawns managed process with transport env', async () => {
  let spawnArgs;
  const child = createChildProcess(8181);
  const { HlfServerController } = loadWithMocks(path.join(__dirname, '..', 'src', 'launcher.js'), {
    'node:child_process': {
      spawn(command, args, options) {
        spawnArgs = { command, args, options };
        return child;
      },
    },
  });

  let stateChanges = 0;
  const controller = new HlfServerController({ appendLine() {} }, () => {
    stateChanges += 1;
  });

  const result = await controller.start({
    transport: 'streamable-http',
    attachMode: 'launch',
    serverCommand: 'uv',
    serverArgs: ['run', 'python', '-m', 'hlf_mcp.server'],
    serverCwd: 'C:\\repo',
    serverEnv: { EXTRA_FLAG: '1' },
    httpHost: '127.0.0.1',
    httpPort: 9000,
  });

  assert.equal(result.started, true);
  assert.equal(result.pid, 8181);
  assert.equal(spawnArgs.command, 'uv');
  assert.deepEqual(spawnArgs.args, ['run', 'python', '-m', 'hlf_mcp.server']);
  assert.equal(spawnArgs.options.cwd, 'C:\\repo');
  assert.equal(spawnArgs.options.env.HLF_TRANSPORT, 'streamable-http');
  assert.equal(spawnArgs.options.env.HLF_HOST, '127.0.0.1');
  assert.equal(spawnArgs.options.env.HLF_PORT, '9000');
  assert.equal(spawnArgs.options.env.EXTRA_FLAG, '1');
  assert.ok(stateChanges >= 1);

  const stopped = await controller.stop();
  assert.equal(stopped, true);
  assert.equal(child.killed, true);
});