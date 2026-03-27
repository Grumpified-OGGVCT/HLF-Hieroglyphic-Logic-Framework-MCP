/**
 * Rate Limiter for AgentsKB API
 * Tracks usage and enforces monthly limits
 */

import { readFileSync, writeFileSync, existsSync } from 'fs';
import { join } from 'path';
import { logger } from './logger.js';

interface UsageData {
  month: string; // YYYY-MM format
  requests: number;
  limit: number;
  resetDate: string; // ISO date string for next reset
}

export class RateLimiter {
  private usageFile: string;
  private currentUsage: UsageData;
  private limit: number;

  constructor(limit: number = 10000) {
    // Store usage in user's home directory or project root
    const homeDir = process.env.HOME || process.env.USERPROFILE || process.cwd();
    this.usageFile = join(homeDir, '.agentskb-usage.json');
    this.limit = limit;
    this.currentUsage = this.loadUsage();
  }

  private getCurrentMonth(): string {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`;
  }

  private getNextResetDate(): Date {
    const now = new Date();
    const nextMonth = new Date(now.getFullYear(), now.getMonth() + 1, 1);
    return nextMonth;
  }

  private loadUsage(): UsageData {
    if (!existsSync(this.usageFile)) {
      const initial: UsageData = {
        month: this.getCurrentMonth(),
        requests: 0,
        limit: this.limit,
        resetDate: this.getNextResetDate().toISOString(),
      };
      this.saveUsage(initial);
      return initial;
    }

    try {
      const data = JSON.parse(readFileSync(this.usageFile, 'utf-8')) as UsageData;
      const currentMonth = this.getCurrentMonth();

      // Check if we need to reset (new month or limit changed)
      if (data.month !== currentMonth || data.limit !== this.limit) {
        const reset: UsageData = {
          month: currentMonth,
          requests: 0,
          limit: this.limit,
          resetDate: this.getNextResetDate().toISOString(),
        };
        this.saveUsage(reset);
        return reset;
      }

      // Check if reset date has passed
      const resetDate = new Date(data.resetDate);
      if (new Date() >= resetDate) {
        const reset: UsageData = {
          month: currentMonth,
          requests: 0,
          limit: this.limit,
          resetDate: this.getNextResetDate().toISOString(),
        };
        this.saveUsage(reset);
        return reset;
      }

      return data;
    } catch (error) {
      logger.error('Failed to load usage data', error);
      const initial: UsageData = {
        month: this.getCurrentMonth(),
        requests: 0,
        limit: this.limit,
        resetDate: this.getNextResetDate().toISOString(),
      };
      this.saveUsage(initial);
      return initial;
    }
  }

  private saveUsage(usage: UsageData): void {
    try {
      writeFileSync(this.usageFile, JSON.stringify(usage, null, 2), 'utf-8');
    } catch (error) {
      logger.error('Failed to save usage data', error);
    }
  }

  /**
   * Check if a request can be made
   * @returns true if allowed, false if limit exceeded
   */
  canMakeRequest(): boolean {
    this.currentUsage = this.loadUsage(); // Reload to check for resets
    return this.currentUsage.requests < this.currentUsage.limit;
  }

  /**
   * Record a request
   * @returns true if successful, false if limit exceeded
   */
  recordRequest(): boolean {
    this.currentUsage = this.loadUsage();

    if (this.currentUsage.requests >= this.currentUsage.limit) {
      return false;
    }

    this.currentUsage.requests++;
    this.saveUsage(this.currentUsage);
    
    logger.debug('Request recorded', {
      requests: this.currentUsage.requests,
      limit: this.currentUsage.limit,
      remaining: this.currentUsage.limit - this.currentUsage.requests,
    });

    return true;
  }

  /**
   * Get current usage statistics
   */
  getUsage(): {
    requests: number;
    limit: number;
    remaining: number;
    percentage: number;
    resetDate: string;
    month: string;
  } {
    this.currentUsage = this.loadUsage();
    return {
      requests: this.currentUsage.requests,
      limit: this.currentUsage.limit,
      remaining: Math.max(0, this.currentUsage.limit - this.currentUsage.requests),
      percentage: (this.currentUsage.requests / this.currentUsage.limit) * 100,
      resetDate: this.currentUsage.resetDate,
      month: this.currentUsage.month,
    };
  }

  /**
   * Update the limit dynamically
   */
  setLimit(newLimit: number): void {
    this.limit = newLimit;
    this.currentUsage.limit = newLimit;
    this.saveUsage(this.currentUsage);
    logger.info('Rate limit updated', { newLimit });
  }

  /**
   * Reset usage (for testing or manual reset)
   */
  reset(): void {
    const reset: UsageData = {
      month: this.getCurrentMonth(),
      requests: 0,
      limit: this.limit,
      resetDate: this.getNextResetDate().toISOString(),
    };
    this.saveUsage(reset);
    this.currentUsage = reset;
    logger.info('Usage reset', { month: reset.month });
  }
}

