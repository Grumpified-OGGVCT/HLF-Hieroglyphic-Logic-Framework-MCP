/**
 * AgentsKB API Client
 * Handles all HTTP requests to the AgentsKB API with proper error handling
 */

import { getConfig } from './config.js';
import { logger } from './logger.js';
import type {
  AgentsKBAskResponse,
  AgentsKBBatchResponse,
  AgentsKBErrorResponse,
  AgentsKBHealthResponse,
  AgentsKBSearchResponse,
  AgentsKBStatsResponse,
} from './types.js';

export class AgentsKBClient {
  private apiKey: string;
  private baseUrl: string;

  constructor() {
    const config = getConfig();
    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = new Headers(options.headers);
    
    // Add AgentsKB API key header (Pro/Scale tier)
    // Pro tier requires: Authorization: Bearer <key> or X-API-Key header
    if (this.apiKey) {
      if (this.apiKey.startsWith('ak_pro_') || this.apiKey.startsWith('ak_scale_')) {
        // Pro/Scale tier: Use Authorization Bearer (primary) and X-API-Key (fallback)
        headers.set('Authorization', `Bearer ${this.apiKey}`);
        headers.set('X-API-Key', this.apiKey);
        // Also try X-AgentsKB-Key for compatibility
        headers.set('X-AgentsKB-Key', this.apiKey);
      } else if (this.apiKey.startsWith('ak_')) {
        // Free tier key format - may not need auth
        headers.set('X-AgentsKB-Key', this.apiKey);
      } else {
        // Legacy format or custom key
        headers.set('Authorization', `Bearer ${this.apiKey}`);
        headers.set('X-API-Key', this.apiKey);
        headers.set('X-AgentsKB-Key', this.apiKey);
      }
    }

    headers.set('Content-Type', 'application/json');
    headers.set('Accept', 'application/json');

    const requestOptions: RequestInit = {
      ...options,
      headers,
    };

    logger.debug(`Making request to ${url}`, { method: options.method || 'GET' });

    try {
      const response = await fetch(url, requestOptions);
      const responseText = await response.text();

      if (!response.ok) {
        let errorData: AgentsKBErrorResponse | null = null;
        try {
          errorData = JSON.parse(responseText) as AgentsKBErrorResponse;
        } catch {
          // If response is not JSON, create error from text
        }

        const errorMessage =
          errorData?.error?.message ||
          `HTTP ${response.status}: ${response.statusText}`;
        const errorCode = errorData?.error?.code || `HTTP_${response.status}`;

        logger.error(`API request failed: ${errorMessage}`, null, {
          url,
          status: response.status,
          code: errorCode,
        });

        throw new Error(`AgentsKB API error: ${errorMessage} (${errorCode})`);
      }

      const data = JSON.parse(responseText) as T;
      logger.debug(`API request successful`, { url, status: response.status });
      return data;
    } catch (error) {
      if (error instanceof Error && error.message.includes('AgentsKB API error')) {
        throw error;
      }

      logger.error(`Network error during API request`, error, { url });
      throw new Error(
        `Failed to connect to AgentsKB API: ${error instanceof Error ? error.message : 'Unknown error'}`
      );
    }
  }

  /**
   * Ask a technical question and receive a researched answer
   */
  async askQuestion(params: {
    question: string;
    domain?: string;
    tier?: 'GOLD' | 'SILVER' | 'BRONZE';
  }): Promise<AgentsKBAskResponse> {
    if (!params.question || params.question.trim().length === 0) {
      throw new Error('Question is required and cannot be empty');
    }

    return this.request<AgentsKBAskResponse>('/ask', {
      method: 'POST',
      body: JSON.stringify({
        question: params.question.trim(),
        ...(params.domain && { domain: params.domain }),
        ...(params.tier && { tier: params.tier }),
      }),
    });
  }

  /**
   * Ask multiple questions in a single batch request
   */
  async askBatch(questions: string[]): Promise<AgentsKBBatchResponse> {
    if (!Array.isArray(questions) || questions.length === 0) {
      throw new Error('Questions array is required and cannot be empty');
    }

    if (questions.length > 100) {
      throw new Error('Maximum 100 questions allowed per batch request');
    }

    const validQuestions = questions
      .map((q) => (typeof q === 'string' ? q.trim() : ''))
      .filter((q) => q.length > 0);

    if (validQuestions.length === 0) {
      throw new Error('At least one valid question is required');
    }

    return this.request<AgentsKBBatchResponse>('/ask-batch', {
      method: 'POST',
      body: JSON.stringify({ questions: validQuestions }),
    });
  }

  /**
   * Search the Q&A database for relevant questions and answers
   */
  async searchQuestions(params: {
    query: string;
    domain?: string;
    limit?: number;
  }): Promise<AgentsKBSearchResponse> {
    if (!params.query || params.query.trim().length === 0) {
      throw new Error('Search query is required and cannot be empty');
    }

    const limit = Math.min(Math.max(1, params.limit || 10), 50);

    return this.request<AgentsKBSearchResponse>('/search', {
      method: 'POST',
      body: JSON.stringify({
        query: params.query.trim(),
        ...(params.domain && { domain: params.domain }),
        limit: limit,
      }),
    });
  }

  /**
   * Get knowledge base statistics
   */
  async getStats(): Promise<AgentsKBStatsResponse> {
    return this.request<AgentsKBStatsResponse>('/stats');
  }

  /**
   * Get API health status
   */
  async getHealth(): Promise<AgentsKBHealthResponse> {
    // Health endpoint doesn't use /api/free prefix
    const healthUrl = this.baseUrl.replace('/api/free', '').replace('/api/pro', '');
    return fetch(`${healthUrl}/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        ...(this.apiKey && {
          'Authorization': `Bearer ${this.apiKey}`,
          'X-API-Key': this.apiKey,
        }),
      },
    }).then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      return response.json() as Promise<AgentsKBHealthResponse>;
    });
  }
}

