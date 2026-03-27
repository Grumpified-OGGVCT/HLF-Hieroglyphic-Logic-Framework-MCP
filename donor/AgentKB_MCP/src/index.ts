#!/usr/bin/env node
/**
 * AgentsKB MCP Server
 * Model Context Protocol server providing access to AgentsKB knowledge base
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import * as z from 'zod';
import { AgentsKBClient } from './api-client.js';
import { logger } from './logger.js';
import { getConfig } from './config.js';
import { RateLimiter } from './rate-limiter.js';

// Initialize configuration
let config;
try {
  config = getConfig();
  logger.info('AgentsKB MCP Server starting...', {
    baseUrl: config.baseUrl,
    debug: config.debug,
  });
} catch (error) {
  logger.error('Failed to initialize configuration', error);
  process.exit(1);
}

// Create MCP server instance
const server = new McpServer({
  name: 'agentskb',
  version: '1.0.0',
});

// Initialize API client
const apiClient = new AgentsKBClient();

// Initialize rate limiter with dynamic limit from config
const rateLimiter = new RateLimiter(config.rateLimit || 10000);

/**
 * Tool: ask_question
 * Get researched answers to technical questions
 */
server.registerTool(
  'ask_question',
  {
    title: 'Ask Question',
    description:
      'Ask a technical question and receive a researched answer with confidence score and sources. Supports optional domain filtering and quality tier selection.',
    inputSchema: {
      question: z
        .string()
        .min(1, 'Question cannot be empty')
        .describe('The technical question to ask'),
      domain: z
        .string()
        .optional()
        .describe('Optional domain filter (e.g., "python", "aws", "postgresql")'),
      tier: z
        .enum(['GOLD', 'SILVER', 'BRONZE'])
        .optional()
        .describe('Quality tier filter: GOLD (highest quality), SILVER, or BRONZE'),
    },
    outputSchema: {
      question: z.string(),
      answer: z.string(), // API returns answer as string
      confidence: z.number(),
      sources: z.array(z.string()).optional(),
      source_count: z.number().optional(),
      researched: z.boolean().optional(),
      match_score: z.number().optional(),
      matched_question: z.string().nullable().optional(),
      auth_level: z.string().optional(),
      quota_used: z.number().optional(),
      quota_limit: z.number().optional(),
      is_authenticated: z.boolean().optional(),
      is_rehit: z.boolean().optional(),
      below_threshold: z.boolean().nullable().optional(),
    },
  },
  async ({ question, domain, tier }) => {
    try {
      // Check rate limit before making request
      if (!rateLimiter.canMakeRequest()) {
        const usage = rateLimiter.getUsage();
        throw new Error(
          `Rate limit exceeded: ${usage.requests}/${usage.limit} requests used this month. Reset date: ${new Date(usage.resetDate).toLocaleDateString()}`
        );
      }

      logger.debug('ask_question called', { question, domain, tier });
      const response = await apiClient.askQuestion({ question, domain, tier });
      
      // Record the request
      rateLimiter.recordRequest();
      
      // Log usage info
      const usage = rateLimiter.getUsage();
      logger.info('Request completed', {
        usage: {
          requests: usage.requests,
          limit: usage.limit,
          remaining: usage.remaining,
        },
      });
      
      // Filter response to only include schema-defined fields
      const filteredResponse = {
        question: response.question,
        answer: response.answer,
        confidence: response.confidence,
        ...(response.sources && { sources: response.sources }),
        ...(response.source_count !== undefined && { source_count: response.source_count }),
        ...(response.researched !== undefined && { researched: response.researched }),
        ...(response.match_score !== undefined && { match_score: response.match_score }),
        ...(response.matched_question !== undefined && { matched_question: response.matched_question }),
        ...(response.auth_level && { auth_level: response.auth_level }),
        ...(response.quota_used !== undefined && { quota_used: response.quota_used }),
        ...(response.quota_limit !== undefined && { quota_limit: response.quota_limit }),
        ...(response.is_authenticated !== undefined && { is_authenticated: response.is_authenticated }),
        ...(response.is_rehit !== undefined && { is_rehit: response.is_rehit }),
        ...(response.below_threshold !== undefined && { below_threshold: response.below_threshold }),
      };
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify({
              ...filteredResponse,
              _usage: {
                requests: usage.requests,
                limit: usage.limit,
                remaining: usage.remaining,
                resetDate: usage.resetDate,
              },
            }, null, 2),
          },
        ],
        structuredContent: filteredResponse,
      };
    } catch (error) {
      logger.error('Error in ask_question tool', error, { question, domain, tier });
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      throw new Error(`Failed to get answer: ${errorMessage}`);
    }
  }
);

/**
 * Tool: search_questions
 * Search the Q&A database for relevant questions and answers
 */
server.registerTool(
  'search_questions',
  {
    title: 'Search Questions',
    description:
      'Search the AgentsKB Q&A database for questions and answers relevant to your query. Returns ranked results based on relevance.',
    inputSchema: {
      query: z
        .string()
        .min(1, 'Search query cannot be empty')
        .describe('The search query to find relevant Q&As'),
      domain: z
        .string()
        .optional()
        .describe('Optional domain filter (e.g., "python", "aws", "postgresql")'),
      limit: z
        .number()
        .int()
        .min(1)
        .max(50)
        .optional()
        .default(10)
        .describe('Maximum number of results to return (1-50, default: 10)'),
    },
    outputSchema: {
      query: z.string(),
      results: z.array(
        z.object({
          id: z.string(),
          question: z.string(),
          answer: z.string(),
          domain: z.string(),
          confidence: z.number(),
          tier: z.enum(['GOLD', 'SILVER', 'BRONZE']).optional(),
          similarity: z.number(),
        })
      ),
      meta: z.object({
        total: z.number(),
        returned: z.number(),
        search_time_ms: z.number(),
      }),
    },
  },
  async ({ query, domain, limit }) => {
    try {
      logger.debug('search_questions called', { query, domain, limit });
      const response = await apiClient.searchQuestions({ query, domain, limit });
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response, null, 2),
          },
        ],
        structuredContent: response,
      };
    } catch (error) {
      logger.error('Error in search_questions tool', error, { query, domain, limit });
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      throw new Error(`Failed to search questions: ${errorMessage}`);
    }
  }
);

/**
 * Tool: get_usage
 * Get current rate limit usage statistics
 */
server.registerTool(
  'get_usage',
  {
    title: 'Get Usage Statistics',
    description:
      'Get current rate limit usage statistics including requests used, remaining, and reset date.',
    inputSchema: {},
    outputSchema: {
      requests: z.number(),
      limit: z.number(),
      remaining: z.number(),
      percentage: z.number(),
      resetDate: z.string(),
      month: z.string(),
    },
  },
  async () => {
    try {
      logger.debug('get_usage called');
      const usage = rateLimiter.getUsage();
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(usage, null, 2),
          },
        ],
        structuredContent: usage,
      };
    } catch (error) {
      logger.error('Error in get_usage tool', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      throw new Error(`Failed to get usage: ${errorMessage}`);
    }
  }
);

/**
 * Tool: get_stats
 * Get knowledge base statistics and metrics
 */
server.registerTool(
  'get_stats',
  {
    title: 'Get Statistics',
    description:
      'Get comprehensive statistics about the AgentsKB knowledge base including total questions, domain breakdown, accuracy metrics, and coverage.',
    inputSchema: {},
    outputSchema: {
      total_questions: z.number(),
      domains: z.number(),
      avg_confidence: z.number(),
      curated_by: z.string().optional(),
      verification_rate: z.number().optional(),
      domains_list: z.array(z.string()).optional(),
      domain_breakdown: z.record(z.string(), z.number()).optional(),
    },
  },
  async () => {
    try {
      logger.debug('get_stats called');
      const response = await apiClient.getStats();
      
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(response, null, 2),
          },
        ],
        structuredContent: response,
      };
    } catch (error) {
      logger.error('Error in get_stats tool', error);
      const errorMessage =
        error instanceof Error ? error.message : 'Unknown error occurred';
      throw new Error(`Failed to get statistics: ${errorMessage}`);
    }
  }
);

/**
 * Main server startup
 */
async function main() {
  try {
    const transport = new StdioServerTransport();
    await server.connect(transport);
    
    logger.info('AgentsKB MCP Server connected and ready', {
      tools: ['ask_question', 'search_questions', 'get_stats', 'get_usage'],
      rateLimit: rateLimiter.getUsage().limit,
    });
  } catch (error) {
    logger.error('Failed to start MCP server', error);
    process.exit(1);
  }
}

// Handle uncaught errors
process.on('uncaughtException', (error) => {
  logger.error('Uncaught exception', error);
  process.exit(1);
});

process.on('unhandledRejection', (reason, promise) => {
  logger.error('Unhandled rejection', reason, { promise });
  process.exit(1);
});

// Start the server
main().catch((error) => {
  logger.error('Fatal error during server startup', error);
  process.exit(1);
});

