"""
Monitoring and observability module.

Provides Prometheus metrics, structured logging, and health checking.
"""

import time
import logging
from typing import Callable
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from app.config import get_settings

# Configure structured logging
def configure_logging():
    """Configure structured logging based on settings."""
    settings = get_settings()
    
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if settings.monitoring.log_format == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Set log level
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.monitoring.log_level.upper()),
    )


# Prometheus Metrics
kb_hits = Counter(
    'kb_hits_total',
    'Total KB cache/retrieval hits',
    ['domain', 'tier', 'cache_hit']
)

kb_misses = Counter(
    'kb_misses_total',
    'Total KB misses requiring research',
    ['domain']
)

research_tasks = Counter(
    'research_tasks_total',
    'Total research tasks',
    ['status', 'domain']
)

research_duration = Histogram(
    'research_duration_seconds',
    'Time to complete research',
    ['domain'],
    buckets=[1, 5, 10, 30, 60, 120, 300]
)

queue_depth = Gauge(
    'queue_depth',
    'Current queue depth',
    ['status']
)

worker_heartbeat_gauge = Gauge(
    'worker_last_heartbeat_timestamp',
    'Last worker heartbeat timestamp',
    ['worker_id']
)

api_requests = Counter(
    'api_requests_total',
    'Total API requests',
    ['endpoint', 'method', 'status_code']
)

api_latency = Histogram(
    'api_latency_seconds',
    'API response time',
    ['endpoint', 'method'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

confidence_distribution = Histogram(
    'confidence_scores',
    'Distribution of confidence scores',
    ['domain'],
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 1.0]
)

llm_costs = Counter(
    'llm_costs_usd',
    'LLM API costs in USD',
    ['model', 'domain', 'operation']
)

llm_tokens = Counter(
    'llm_tokens_total',
    'Total LLM tokens consumed',
    ['model', 'domain', 'direction']  # direction: input/output
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tracking API metrics.
    
    Records request counts, latency, and status codes.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and record metrics."""
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        endpoint = request.url.path
        method = request.method
        status_code = str(response.status_code)
        
        api_requests.labels(
            endpoint=endpoint,
            method=method,
            status_code=status_code
        ).inc()
        
        api_latency.labels(
            endpoint=endpoint,
            method=method
        ).observe(duration)
        
        # Add timing header
        response.headers["X-Response-Time"] = f"{duration:.4f}s"
        
        return response


def record_kb_hit(
    domain: str,
    tier: str,
    confidence: float,
    cache_hit: bool = False
):
    """Record a KB hit metric."""
    kb_hits.labels(
        domain=domain,
        tier=tier,
        cache_hit=str(cache_hit).lower()
    ).inc()
    
    confidence_distribution.labels(domain=domain).observe(confidence)


def record_kb_miss(domain: str, confidence: float):
    """Record a KB miss metric."""
    kb_misses.labels(domain=domain or "unknown").inc()
    
    if domain:
        confidence_distribution.labels(domain=domain).observe(confidence)


def record_research_task(status: str, domain: str, duration: float = None):
    """Record a research task metric."""
    research_tasks.labels(status=status, domain=domain or "unknown").inc()
    
    if duration is not None:
        research_duration.labels(domain=domain or "unknown").observe(duration)


def record_llm_usage(
    model: str,
    domain: str,
    operation: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float
):
    """Record LLM usage metrics."""
    llm_tokens.labels(model=model, domain=domain, direction="input").inc(input_tokens)
    llm_tokens.labels(model=model, domain=domain, direction="output").inc(output_tokens)
    llm_costs.labels(model=model, domain=domain, operation=operation).inc(cost_usd)


def update_queue_metrics(by_status: dict):
    """Update queue depth metrics."""
    for status, count in by_status.items():
        queue_depth.labels(status=status).set(count)


def update_worker_heartbeat(worker_id: str, timestamp: float):
    """Update worker heartbeat metric."""
    worker_heartbeat_gauge.labels(worker_id=worker_id).set(timestamp)


async def metrics_endpoint(request: Request) -> Response:
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


def get_logger(name: str = None):
    """Get a structured logger."""
    return structlog.get_logger(name)


class LogContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding request context to logs.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add request context to logs."""
        import uuid
        
        # Generate request ID
        request_id = str(uuid.uuid4())[:8]
        
        # Bind context to logger
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            path=request.url.path,
            method=request.method,
        )
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response

