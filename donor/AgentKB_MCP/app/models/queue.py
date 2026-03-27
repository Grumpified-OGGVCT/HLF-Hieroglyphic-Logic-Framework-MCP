"""
Queue and worker models.

Models for the research queue and worker heartbeat tracking.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class QueueStatus(str, Enum):
    """Possible statuses for a queue item."""
    
    PENDING = "pending"
    RESEARCHING = "researching"
    NEEDS_REVIEW = "needs_review"
    COMPLETED = "completed"
    FAILED = "failed"
    DISCARDED = "discarded"


class QueueItem(BaseModel):
    """
    Model for a research queue item.
    
    Represents a question that needs to be researched and
    added to the knowledge base.
    """
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique queue item ID"
    )
    question: str = Field(
        ...,
        description="The original question"
    )
    normalized_question: str = Field(
        ...,
        description="Question after abbreviation expansion"
    )
    question_embedding: Optional[List[float]] = Field(
        default=None,
        description="Vector embedding for semantic dedup"
    )
    domain: Optional[str] = Field(
        default=None,
        description="Domain filter from request"
    )
    software_version: Optional[str] = Field(
        default=None,
        description="Software version from request"
    )
    stack_pack: Optional[str] = Field(
        default=None,
        description="Stack pack ID from request"
    )
    status: QueueStatus = Field(
        default=QueueStatus.PENDING,
        description="Current status"
    )
    reference_count: int = Field(
        default=1,
        ge=1,
        description="Number of times this question was asked"
    )
    requester_session_ids: List[str] = Field(
        default_factory=list,
        description="Session IDs of requesters (for provenance)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the item was created"
    )
    claimed_at: Optional[datetime] = Field(
        default=None,
        description="When a worker claimed this item"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When processing completed"
    )
    worker_id: Optional[str] = Field(
        default=None,
        description="ID of worker processing this item"
    )
    retry_count: int = Field(
        default=0,
        ge=0,
        description="Number of retry attempts"
    )
    error_log: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Error information from failed attempts"
    )
    result_entry_id: Optional[str] = Field(
        default=None,
        description="ID of the KB entry created (if successful)"
    )
    needs_review_reason: Optional[str] = Field(
        default=None,
        description="Reason for needs_review status"
    )

    def increment_reference(self, session_id: Optional[str] = None) -> None:
        """Increment reference count and add session ID."""
        self.reference_count += 1
        if session_id and session_id not in self.requester_session_ids:
            self.requester_session_ids.append(session_id)

    def claim(self, worker_id: str) -> None:
        """Mark as claimed by a worker."""
        self.status = QueueStatus.RESEARCHING
        self.worker_id = worker_id
        self.claimed_at = datetime.utcnow()

    def complete(self, entry_id: str) -> None:
        """Mark as completed with result entry."""
        self.status = QueueStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result_entry_id = entry_id

    def fail(self, error: Dict[str, Any]) -> None:
        """Mark as failed with error info."""
        self.status = QueueStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_log = error
        self.retry_count += 1

    def mark_needs_review(self, reason: str) -> None:
        """Mark as needing human review."""
        self.status = QueueStatus.NEEDS_REVIEW
        self.needs_review_reason = reason

    def discard(self) -> None:
        """Mark as discarded (no authoritative sources found)."""
        self.status = QueueStatus.DISCARDED
        self.completed_at = datetime.utcnow()

    def reset_for_retry(self) -> None:
        """Reset for another attempt (within retry limit)."""
        self.status = QueueStatus.PENDING
        self.worker_id = None
        self.claimed_at = None


class DeadLetterItem(QueueItem):
    """
    Extended queue item for dead letter queue.
    
    Items moved to DLQ after max retries.
    """
    
    moved_to_dlq_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When moved to DLQ"
    )
    final_error: Optional[Dict[str, Any]] = Field(
        default=None,
        description="The final error that caused DLQ move"
    )


class WorkerHeartbeat(BaseModel):
    """
    Model for worker heartbeat tracking.
    
    Workers must update their heartbeat regularly to indicate
    they are still alive and processing.
    """
    
    worker_id: str = Field(
        ...,
        description="Unique worker identifier"
    )
    last_heartbeat: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last heartbeat timestamp"
    )
    current_task_id: Optional[str] = Field(
        default=None,
        description="ID of task currently being processed"
    )
    tasks_completed: int = Field(
        default=0,
        ge=0,
        description="Total tasks completed by this worker"
    )
    tasks_failed: int = Field(
        default=0,
        ge=0,
        description="Total tasks failed by this worker"
    )
    started_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the worker started"
    )
    status: str = Field(
        default="active",
        description="Worker status: active, idle, stopping"
    )

    def is_stale(self, threshold_seconds: int = 60) -> bool:
        """Check if heartbeat is stale (worker may be dead)."""
        elapsed = (datetime.utcnow() - self.last_heartbeat).total_seconds()
        return elapsed > threshold_seconds

    def update(self, task_id: Optional[str] = None) -> None:
        """Update heartbeat timestamp."""
        self.last_heartbeat = datetime.utcnow()
        self.current_task_id = task_id

    def record_completion(self, success: bool = True) -> None:
        """Record task completion."""
        self.current_task_id = None
        if success:
            self.tasks_completed += 1
        else:
            self.tasks_failed += 1


class WorkerStats(BaseModel):
    """Aggregated worker statistics."""
    
    total_workers: int
    active_workers: int
    stale_workers: int
    total_tasks_completed: int
    total_tasks_failed: int
    average_tasks_per_worker: float


class QueueStats(BaseModel):
    """Queue statistics for monitoring."""
    
    total_items: int
    by_status: Dict[str, int]
    oldest_pending: Optional[datetime]
    avg_time_to_research_seconds: Optional[float]
    research_success_rate: Optional[float]
    discard_rate: Optional[float]

