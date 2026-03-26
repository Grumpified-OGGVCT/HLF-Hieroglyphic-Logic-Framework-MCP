/**
 * Structured logging utility for AgentsKB MCP Server
 */

import { getConfig } from './config.js';

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

class Logger {
  private debugEnabled: boolean;

  constructor() {
    try {
      const config = getConfig();
      this.debugEnabled = config.debug ?? false;
    } catch {
      this.debugEnabled = false;
    }
  }

  private formatMessage(level: string, message: string, data?: unknown): string {
    const timestamp = new Date().toISOString();
    const dataStr = data ? ` ${JSON.stringify(data)}` : '';
    return `[${timestamp}] [${level}] ${message}${dataStr}`;
  }

  debug(message: string, data?: unknown): void {
    if (this.debugEnabled) {
      console.error(this.formatMessage('DEBUG', message, data));
    }
  }

  info(message: string, data?: unknown): void {
    console.error(this.formatMessage('INFO', message, data));
  }

  warn(message: string, data?: unknown): void {
    console.error(this.formatMessage('WARN', message, data));
  }

  error(message: string, error?: Error | unknown, data?: unknown): void {
    const errorData = error instanceof Error ? { message: error.message, stack: error.stack } : error;
    console.error(this.formatMessage('ERROR', message, { ...errorData, ...data }));
  }
}

export const logger = new Logger();

