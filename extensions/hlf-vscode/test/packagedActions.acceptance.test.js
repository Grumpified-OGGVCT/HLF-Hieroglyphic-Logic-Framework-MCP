const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { EventEmitter } = require('node:events');

const { loadWithMocks } = require('./helpers/loadWithMocks');

function createSpawnBehavior(steps) {
  let index = 0;
  return function spawn(command, args) {
    const step = steps[index] ?? steps[steps.length - 1];
    index += 1;

    const handle = new EventEmitter();
    handle.stdout = new EventEmitter();
    handle.stderr = new EventEmitter();

    process.nextTick(() => {
      if (step.type === 'error') {
        handle.emit('error', new Error(step.message));
        return;
      }

      if (step.stdout) {
        handle.stdout.emit('data', step.stdout);
      }
      if (step.stderr) {
        handle.stderr.emit('data', step.stderr);
      }
      handle.emit('close', step.code ?? 0);
    });

    handle.command = command;
    handle.args = args;
    return handle;
  };
}

test('packaged actions acceptance: non-python server commands use uv/python operator fallbacks', () => {
  const { buildOperatorInvocationCandidates } = loadWithMocks(path.join(__dirname, '..', 'src', 'packagedActions.js'), {
    vscode: {},
  });

  const candidates = buildOperatorInvocationCandidates({ serverCommand: 'hlf-mcp' }, ['resource', '--json']);

  assert.deepEqual(candidates, [
    { command: 'uv', args: ['run', 'hlf-operator', 'resource', '--json'] },
    { command: 'python', args: ['-m', 'hlf_mcp.operator_cli', 'resource', '--json'] },
  ]);
});

test('packaged actions acceptance: runOperatorAction falls back after launch failure', async () => {
  const attempts = [];
  const { runOperatorAction } = loadWithMocks(path.join(__dirname, '..', 'src', 'packagedActions.js'), {
    vscode: {
      window: {
        withProgress(_options, callback) {
          return callback();
        },
      },
      ProgressLocation: { Notification: 15 },
    },
    'node:child_process': {
      spawn: createSpawnBehavior([
        { type: 'error', message: 'uv not found' },
        { type: 'close', code: 0, stdout: '{"status":"ok"}' },
      ]),
    },
  });

  const output = {
    appendLine(line) {
      attempts.push(line);
    },
  };

  const result = await runOperatorAction({
    settings: {
      serverCommand: 'hlf-mcp',
      serverCwd: 'C:\\repo',
      serverEnv: {},
    },
    outputChannel: output,
    args: ['resource', '--uri', 'hlf://status/formal_verifier', '--json'],
    title: 'HLF Resource',
  });

  assert.equal(result.ok, true);
  assert.equal(result.invocation.command, 'python');
  assert.deepEqual(result.parsed, { status: 'ok' });
  assert.ok(attempts.some((line) => line.includes('operator command fallback after launch failure')));
});