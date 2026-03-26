"""
Pydantic models for request/response schemas.

All models are organized by purpose:
- requests: Incoming API request models
- responses: Outgoing API response models
- kb: Knowledge base entry models
- queue: Queue and worker models
"""

from app.models.requests import (
    AskRequest,
    AskBatchRequest,
    LockRequest,
    VerifyLockRequest,
)
from app.models.responses import (
    AnswerResponse,
    MissResponse,
    BatchResponse,
    LockResponse,
    VerifyLockResponse,
    HealthResponse,
    StatsResponse,
    QueueStatusResponse,
)
from app.models.kb import (
    KBEntry,
    KBEntryMetadata,
    ParsedKBEntry,
)
from app.models.queue import (
    QueueItem,
    QueueStatus,
    WorkerHeartbeat,
)

__all__ = [
    # Requests
    "AskRequest",
    "AskBatchRequest",
    "LockRequest",
    "VerifyLockRequest",
    # Responses
    "AnswerResponse",
    "MissResponse",
    "BatchResponse",
    "LockResponse",
    "VerifyLockResponse",
    "HealthResponse",
    "StatsResponse",
    "QueueStatusResponse",
    # KB
    "KBEntry",
    "KBEntryMetadata",
    "ParsedKBEntry",
    # Queue
    "QueueItem",
    "QueueStatus",
    "WorkerHeartbeat",
]

