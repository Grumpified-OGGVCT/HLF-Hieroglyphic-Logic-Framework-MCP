"""
Response models for API endpoints.

These models define the exact schema for outgoing responses,
matching the AgentsKB compatibility contract with enhancements.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class AnswerResponse(BaseModel):
    """
    Response model for successful /ask queries (hits).
    
    Returns when confidence >= 0.80 (configurable threshold).
    """
    
    question: str = Field(
        ...,
        description="Complete verbatim restatement of the original query"
    )
    answer: str = Field(
        ...,
        description="The full detailed grounded response"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.00 to 1.00)"
    )
    tier: Optional[str] = Field(
        default=None,
        description="Quality tier (GOLD, SILVER, BRONZE)"
    )
    sources: List[str] = Field(
        default_factory=list,
        description="List of source URLs"
    )
    related_questions: Optional[List[str]] = Field(
        default=None,
        description="3-5 related questions from KB"
    )
    reasoning_summary: Optional[str] = Field(
        default=None,
        description="Reasoning summary (only for complex queries)"
    )
    
    # Enhancement fields
    cache_hit: bool = Field(
        default=False,
        description="Whether this was served from cache"
    )
    entry_id: Optional[str] = Field(
        default=None,
        description="KB entry ID used (for lockfiles)"
    )
    entry_ids: Optional[List[str]] = Field(
        default=None,
        description="All KB entry IDs used (for synthesis)"
    )
    entry_hashes_sha256: Optional[Dict[str, str]] = Field(
        default=None,
        description="SHA256 hashes per entry (for lockfiles)"
    )
    software_version_resolved: Optional[str] = Field(
        default=None,
        description="Resolved version used for answering"
    )
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "What is the default max_connections in PostgreSQL 16?",
                "answer": "The default value for max_connections in PostgreSQL 16 is 100...",
                "confidence": 0.98,
                "tier": "GOLD",
                "sources": ["https://www.postgresql.org/docs/16/runtime-config-connection.html"],
                "related_questions": [
                    "How do I increase max_connections in PostgreSQL?",
                    "What happens when max_connections is exceeded?"
                ],
                "cache_hit": False,
                "entry_id": "postgresql-max-connections-0001",
                "software_version_resolved": "16"
            }
        }


class MissResponse(BaseModel):
    """
    Response model for /ask queries that miss (confidence < 0.80).
    
    Includes the exact miss phrase and queue information.
    """
    
    question: str = Field(
        ...,
        description="The original question"
    )
    answer: str = Field(
        default="No verified high-confidence answer found in the knowledge base.",
        description="The exact miss phrase"
    )
    confidence: float = Field(
        ...,
        lt=0.80,
        description="Confidence score (< 0.80)"
    )
    queued: bool = Field(
        default=True,
        description="Whether the question was queued for research"
    )
    queue_id: Optional[str] = Field(
        default=None,
        description="Queue item ID for provenance tracking"
    )
    related_questions: Optional[List[str]] = Field(
        default=None,
        description="Closest related questions found"
    )
    meta: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "How do I configure advanced caching in PostgreSQL 17?",
                "answer": "No verified high-confidence answer found in the knowledge base.",
                "confidence": 0.45,
                "queued": True,
                "queue_id": "550e8400-e29b-41d4-a716-446655440000",
                "related_questions": [
                    "How do I configure shared_buffers in PostgreSQL?",
                    "What caching mechanisms does PostgreSQL use?"
                ]
            }
        }


class BatchAnswerItem(BaseModel):
    """Single answer item in a batch response."""
    
    question: str
    answer: Optional[str] = None
    confidence: float
    tier: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    entry_id: Optional[str] = None
    queued: bool = False
    queue_id: Optional[str] = None


class BatchResponse(BaseModel):
    """
    Response model for /ask-batch endpoint.
    """
    
    total: int = Field(
        ...,
        description="Total questions submitted"
    )
    unique: int = Field(
        ...,
        description="Unique questions after deduplication"
    )
    found: int = Field(
        default=0,
        description="Questions with high-confidence answers"
    )
    not_found: int = Field(
        default=0,
        description="Questions queued for research"
    )
    answers: List[BatchAnswerItem] = Field(
        default_factory=list,
        description="Array of answer items"
    )
    processing_time_ms: Optional[float] = Field(
        default=None,
        description="Total processing time in milliseconds"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "total": 3,
                "unique": 2,
                "found": 2,
                "not_found": 0,
                "answers": [
                    {
                        "question": "What is PostgreSQL?",
                        "answer": "PostgreSQL is...",
                        "confidence": 0.98,
                        "tier": "GOLD"
                    }
                ],
                "processing_time_ms": 125.5
            }
        }


class LockEntryInfo(BaseModel):
    """Information about a locked KB entry."""
    
    sha256: str
    version: Optional[str] = None


class LockResponse(BaseModel):
    """
    Response model for /lock endpoint.
    """
    
    lockfile_version: str = Field(default="1")
    generated_at: datetime
    entries: Dict[str, LockEntryInfo]

    class Config:
        json_schema_extra = {
            "example": {
                "lockfile_version": "1",
                "generated_at": "2024-01-15T10:30:00Z",
                "entries": {
                    "postgresql-max-connections-0001": {
                        "sha256": "abc123...",
                        "version": "16"
                    }
                }
            }
        }


class VerifyLockResponse(BaseModel):
    """
    Response model for /verify-lock endpoint.
    """
    
    valid: bool = Field(
        ...,
        description="Whether all entries match their locked hashes"
    )
    checked: int = Field(
        ...,
        description="Number of entries checked"
    )
    mismatches: List[str] = Field(
        default_factory=list,
        description="List of entry IDs that don't match"
    )
    missing: List[str] = Field(
        default_factory=list,
        description="List of entry IDs not found in KB"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "valid": True,
                "checked": 5,
                "mismatches": [],
                "missing": []
            }
        }


class ServiceHealth(BaseModel):
    """Health status for a single service."""
    
    status: str
    response_time_ms: Optional[float] = None
    error: Optional[str] = None


class HealthMetrics(BaseModel):
    """Metrics included in health response."""
    
    hit_rate: Optional[float] = None
    avg_confidence: Optional[float] = None
    entries_total: Optional[int] = None
    entries_by_domain: Optional[Dict[str, int]] = None


class HealthResponse(BaseModel):
    """
    Response model for /health endpoint.
    """
    
    status: str = Field(
        ...,
        description="Overall status: healthy, degraded, or unhealthy"
    )
    timestamp: datetime
    checks: Dict[str, Union[str, ServiceHealth]] = Field(
        default_factory=dict,
        description="Individual service health checks"
    )
    metrics: Optional[HealthMetrics] = None
    emergency_stop: bool = Field(
        default=False,
        description="Whether emergency stop is active"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "checks": {
                    "api": "healthy",
                    "database": "healthy",
                    "redis": "healthy",
                    "google_file_search": "healthy"
                },
                "emergency_stop": False
            }
        }


class StatsResponse(BaseModel):
    """
    Response model for /stats endpoint.
    """
    
    total_entries: int
    domains: int
    avg_confidence: float
    entries_by_domain: Dict[str, int]
    entries_by_tier: Dict[str, int]
    queue_depth: int
    queue_by_status: Dict[str, int]
    hit_rate_24h: Optional[float] = None
    miss_rate_24h: Optional[float] = None

    class Config:
        json_schema_extra = {
            "example": {
                "total_entries": 1500,
                "domains": 15,
                "avg_confidence": 0.95,
                "entries_by_domain": {
                    "postgresql": 150,
                    "nextjs": 120
                },
                "entries_by_tier": {
                    "GOLD": 1200,
                    "SILVER": 250,
                    "BRONZE": 50
                },
                "queue_depth": 25,
                "queue_by_status": {
                    "pending": 20,
                    "researching": 3,
                    "needs_review": 2
                }
            }
        }


class QueueItemStatus(str, Enum):
    """Possible queue item statuses."""
    
    PENDING = "pending"
    RESEARCHING = "researching"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    FAILED = "failed"
    DISCARDED = "discarded"


class QueueStatusItem(BaseModel):
    """Single queue item for status response."""
    
    id: str
    question: str
    domain: Optional[str]
    status: QueueItemStatus
    reference_count: int
    created_at: datetime
    claimed_at: Optional[datetime] = None
    worker_id: Optional[str] = None
    retry_count: int = 0


class QueueStatusResponse(BaseModel):
    """
    Response model for /queue-status endpoint.
    """
    
    total: int
    by_status: Dict[str, int]
    items: List[QueueStatusItem] = Field(default_factory=list)
    workers_active: int
    oldest_pending: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "total": 25,
                "by_status": {
                    "pending": 20,
                    "researching": 3,
                    "needs_review": 2
                },
                "workers_active": 2,
                "oldest_pending": "2024-01-15T08:00:00Z"
            }
        }

