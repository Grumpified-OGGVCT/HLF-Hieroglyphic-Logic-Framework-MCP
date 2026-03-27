/**
 * Configuration management for AgentsKB MCP Server
 */

import dotenv from 'dotenv';
import { z } from 'zod';

// Load environment variables
dotenv.config();

const ConfigSchema = z.object({
  apiKey: z.string().min(1, 'AGENTSKB_API_KEY is required'),
  baseUrl: z
    .string()
    .url()
    .default('https://agentskb-api.agentskb.com/api/free')
    .describe('API base URL - use /api/free for free tier, /api/pro for Pro tier'),
  useProEndpoint: z
    .string()
    .optional()
    .transform((val) => val === 'true' || val === '1')
    .describe('Use Pro tier endpoint (/api/pro) instead of free tier'),
  debug: z
    .string()
    .optional()
    .transform((val) => val === 'true' || val === '1'),
  rateLimit: z
    .string()
    .optional()
    .transform((val) => (val ? parseInt(val, 10) : 10000))
    .pipe(z.number().int().min(1).max(1000000)),
});

export type Config = z.infer<typeof ConfigSchema>;

let config: Config | null = null;

/**
 * Get application configuration
 * Validates environment variables and returns typed config
 */
export function getConfig(): Config {
  if (config) {
    return config;
  }

  const apiKey = process.env.AGENTSKB_API_KEY;
  if (!apiKey) {
    throw new Error(
      'AGENTSKB_API_KEY environment variable is required. Please set it in your .env file.'
    );
  }

  // Determine base URL based on API key and config
  const useProEndpoint = process.env.AGENTSKB_USE_PRO_ENDPOINT === 'true' || 
                         process.env.AGENTSKB_USE_PRO_ENDPOINT === '1' ||
                         (apiKey && (apiKey.startsWith('ak_pro_') || apiKey.startsWith('ak_scale_')));
  
  const defaultBaseUrl = useProEndpoint 
    ? 'https://agentskb-api.agentskb.com/api/pro'
    : 'https://agentskb-api.agentskb.com/api/free';

  const result = ConfigSchema.safeParse({
    apiKey,
    baseUrl: process.env.AGENTSKB_BASE_URL || defaultBaseUrl,
    useProEndpoint: process.env.AGENTSKB_USE_PRO_ENDPOINT,
    debug: process.env.DEBUG,
    rateLimit: process.env.AGENTSKB_RATE_LIMIT,
  });

  if (!result.success) {
    const errors = result.error.errors.map((e) => `${e.path.join('.')}: ${e.message}`).join(', ');
    throw new Error(`Configuration error: ${errors}`);
  }

  config = result.data;
  return config;
}

/**
 * Reset configuration (useful for testing)
 */
export function resetConfig(): void {
  config = null;
}

