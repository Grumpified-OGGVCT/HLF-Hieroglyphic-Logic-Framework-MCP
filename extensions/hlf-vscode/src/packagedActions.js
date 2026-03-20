const childProcess = require('node:child_process');
const path = require('node:path');
const vscode = require('vscode');

function buildOperatorInvocationCandidates(settings, args) {
  const command = settings.serverCommand;
  const executableName = path.basename(command).toLowerCase();

  if (executableName === 'uv' || executableName === 'uv.exe') {
    return [{
      command,
      args: ['run', 'hlf-operator', ...args],
    }];
  }

  if (executableName.includes('python')) {
    return [{
      command,
      args: ['-m', 'hlf_mcp.operator_cli', ...args],
    }];
  }

  if (executableName === 'hlf-operator' || executableName === 'hlf-operator.exe') {
    return [{
      command,
      args,
    }];
  }

  return [
    {
      command: 'uv',
      args: ['run', 'hlf-operator', ...args],
    },
    {
      command: 'python',
      args: ['-m', 'hlf_mcp.operator_cli', ...args],
    },
  ];
}

function runProcess(command, args, options) {
  return new Promise((resolve) => {
    const process = childProcess.spawn(command, args, options);
    let stdout = '';
    let stderr = '';

    process.stdout?.on('data', (chunk) => {
      stdout += String(chunk);
    });

    process.stderr?.on('data', (chunk) => {
      stderr += String(chunk);
    });

    process.on('error', (error) => {
      resolve({ ok: false, exitCode: -1, stdout, stderr: `${stderr}${error.message}` });
    });

    process.on('close', (code) => {
      resolve({ ok: code === 0, exitCode: code ?? -1, stdout, stderr });
    });
  });
}

async function runOperatorAction({ settings, outputChannel, args, title, secretHeaders = {} }) {
  const candidates = buildOperatorInvocationCandidates(settings, args);
  const environment = {
    ...process.env,
    ...settings.serverEnv,
  };

  if (Object.keys(secretHeaders).length > 0) {
    const authHeader = secretHeaders.Authorization;
    if (authHeader) {
      environment.HLF_HTTP_AUTHORIZATION = authHeader;
    }
  }

  let result;
  let invocation;

  for (const candidate of candidates) {
    invocation = candidate;
    outputChannel.appendLine(`[hlf-vscode] running ${title}: ${invocation.command} ${invocation.args.join(' ')}`);

    result = await vscode.window.withProgress(
      {
        location: vscode.ProgressLocation.Notification,
        title,
        cancellable: false,
      },
      async () => runProcess(invocation.command, invocation.args, {
        cwd: settings.serverCwd,
        env: environment,
        shell: false,
        windowsHide: true,
      }),
    );

    if (result.ok || result.exitCode !== -1) {
      break;
    }

    outputChannel.appendLine(`[hlf-vscode] operator command fallback after launch failure from ${invocation.command}.`);
  }

  if (result.stdout.trim()) {
    outputChannel.appendLine(`[hlf action stdout]\n${result.stdout.trimEnd()}`);
  }
  if (result.stderr.trim()) {
    outputChannel.appendLine(`[hlf action stderr]\n${result.stderr.trimEnd()}`);
  }

  let parsed;
  if (result.stdout.trim()) {
    try {
      parsed = JSON.parse(result.stdout);
    } catch {
      parsed = undefined;
    }
  }

  return {
    ...result,
    parsed,
    invocation,
  };
}

module.exports = {
  buildOperatorInvocationCandidates,
  runOperatorAction,
};