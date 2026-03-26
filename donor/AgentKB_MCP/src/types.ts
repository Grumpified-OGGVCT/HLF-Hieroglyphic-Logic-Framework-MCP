/**
 * Type definitions for AgentsKB API responses
 */

export interface AgentsKBAskResponse {
  question: string;
  answer: string; // API returns answer as a string, not an object
  confidence: number;
  sources?: string[];
  source_count?: number;
  researched?: boolean;
  match_score?: number;
  matched_question?: string | null;
  auth_level?: string;
  quota_used?: number;
  quota_limit?: number;
  is_authenticated?: boolean;
  is_rehit?: boolean;
  below_threshold?: boolean | null;
  meta?: {
    domain?: string;
    search_time_ms?: number;
    model?: string;
  };
}

export interface AgentsKBBatchResponse {
  total: number;
  found: number;
  not_found: number;
  answers: Array<{
    question: string;
    answer: string;
    confidence: number;
    sources?: string[];
    topic?: string;
  }>;
  processing_time_ms: number;
}

export interface AgentsKBSearchResult {
  id: string;
  question: string;
  answer: string;
  domain: string;
  confidence: number;
  tier?: 'GOLD' | 'SILVER' | 'BRONZE';
  similarity: number;
}

export interface AgentsKBSearchResponse {
  query: string;
  results: AgentsKBSearchResult[];
  meta: {
    total: number;
    returned: number;
    search_time_ms: number;
  };
}

export interface AgentsKBStatsResponse {
  total_questions: number;
  domains: number;
  avg_confidence: number;
  curated_by?: string;
  verification_rate?: number;
  domains_list?: string[];
  domain_breakdown?: Record<string, number>;
}

export interface AgentsKBHealthResponse {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
  uptime: number;
  services: {
    api: {
      status: string;
      response_time_ms: number;
    };
    database: {
      status: string;
      type: string;
      response_time_ms: number;
    };
    vector_search?: {
      status: string;
      dimension: number;
      model: string;
    };
  };
}

export interface AgentsKBErrorResponse {
  error: {
    code: string;
    message: string;
  };
  meta?: {
    responseTimeMs?: number;
  };
}

