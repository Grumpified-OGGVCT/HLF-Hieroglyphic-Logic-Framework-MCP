const childProcess = require('node:child_process');

class HlfServerController {
  constructor(outputChannel, onStateChanged) {
    this.outputChannel = outputChannel;
    this.onStateChanged = onStateChanged;
    this.process = undefined;
    this.lastLaunchSettings = undefined;
  }

  isRunning() {
    return Boolean(this.process && !this.process.killed);
  }

  getState() {
    return {
      running: this.isRunning(),
      pid: this.process?.pid,
      transport: this.lastLaunchSettings?.transport,
      attachMode: this.lastLaunchSettings?.attachMode,
    };
  }

  async start(settings) {
    this.lastLaunchSettings = settings;

    if (settings.attachMode === 'attach') {
      this.outputChannel.appendLine(`[hlf-vscode] attach mode enabled for ${settings.transport}; no managed process started.`);
      this.onStateChanged?.();
      return { started: false, attached: true };
    }

    if (this.isRunning()) {
      this.outputChannel.appendLine('[hlf-vscode] managed HLF process already running.');
      return { started: false, attached: false, pid: this.process?.pid };
    }

    const environment = {
      ...process.env,
      ...settings.serverEnv,
      HLF_TRANSPORT: settings.transport,
    };

    if (settings.transport !== 'stdio') {
      environment.HLF_HOST = settings.httpHost;
      environment.HLF_PORT = String(settings.httpPort);
    }

    this.outputChannel.appendLine(
      `[hlf-vscode] starting managed HLF process: ${settings.serverCommand} ${settings.serverArgs.join(' ')}`,
    );

    const child = childProcess.spawn(settings.serverCommand, settings.serverArgs, {
      cwd: settings.serverCwd,
      env: environment,
      shell: false,
      windowsHide: true,
    });

    child.stdout?.on('data', (chunk) => {
      this.outputChannel.appendLine(`[hlf stdout] ${String(chunk).trimEnd()}`);
    });

    child.stderr?.on('data', (chunk) => {
      this.outputChannel.appendLine(`[hlf stderr] ${String(chunk).trimEnd()}`);
    });

    child.on('error', (error) => {
      this.outputChannel.appendLine(`[hlf-vscode] launch error: ${error.message}`);
      this.process = undefined;
      this.onStateChanged?.();
    });

    child.on('exit', (code, signal) => {
      this.outputChannel.appendLine(`[hlf-vscode] managed process exited with code=${code ?? 'null'} signal=${signal ?? 'null'}`);
      this.process = undefined;
      this.onStateChanged?.();
    });

    this.process = child;
    this.onStateChanged?.();
    return { started: true, attached: false, pid: child.pid };
  }

  async stop() {
    if (!this.process) {
      return false;
    }

    const runningProcess = this.process;
    this.process = undefined;
    this.outputChannel.appendLine(`[hlf-vscode] stopping managed HLF process ${runningProcess.pid}.`);
    runningProcess.kill();
    this.onStateChanged?.();
    return true;
  }

  async restart(settings) {
    await this.stop();
    return this.start(settings);
  }
}

module.exports = {
  HlfServerController,
};