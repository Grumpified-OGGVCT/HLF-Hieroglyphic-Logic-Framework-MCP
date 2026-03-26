"""
SQLAlchemy ORM models.

Database models matching the schema defined in the blueprint.
Uses pgvector for semantic deduplication.
"""

from sqlalchemy import (
    Column,
    String,
    Text,
    Integer,
    Float,
    Boolean,
    DateTime,
    JSON,
    Index,
    CheckConstraint,
    ForeignKey,
    DECIMAL,
)
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

# Try to import pgvector, fall back to generic if not available
try:
    from pgvector.sqlalchemy import Vector
    VECTOR_AVAILABLE = True
except ImportError:
    # Fallback for environments without pgvector
    Vector = None
    VECTOR_AVAILABLE = False


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


class QueueItemDB(Base):
    """
    Research queue table.
    
    Stores questions that need to be researched and added to the KB.
    Includes semantic deduplication via vector embeddings.
    """
    
    __tablename__ = "queue"
    
    # Primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True
    )
    
    # Question data
    question = Column(Text, nullable=False)
    normalized_question = Column(Text, nullable=False)
    
    # Vector embedding for semantic dedup (768 dimensions for Gemini embeddings)
    # Only create if pgvector is available
    if VECTOR_AVAILABLE:
        question_embedding = Column(Vector(768), nullable=True)
    else:
        question_embedding = Column(Text, nullable=True)  # Fallback
    
    # Request context
    domain = Column(String(50), nullable=True, index=True)
    software_version = Column(String(20), nullable=True)
    stack_pack = Column(String(50), nullable=True)
    
    # Status tracking
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        index=True
    )
    
    # Deduplication
    reference_count = Column(Integer, nullable=False, default=1)
    requester_session_ids = Column(JSON, nullable=False, default=list)
    
    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Worker tracking
    worker_id = Column(String(100), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_log = Column(JSON, nullable=True)
    
    # Result tracking
    result_entry_id = Column(String(200), nullable=True)
    needs_review_reason = Column(Text, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            status.in_([
                'pending', 'researching', 'needs_review',
                'completed', 'failed', 'discarded'
            ]),
            name='status_check'
        ),
        # Partial index for pending items (most common query)
        Index('idx_queue_status_pending', status, postgresql_where=(status == 'pending')),
        # Index for created_at ordering
        Index('idx_queue_created', created_at.desc()),
    )
    
    def __repr__(self) -> str:
        return f"<QueueItem(id={self.id}, status={self.status}, question={self.question[:50]}...)>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": str(self.id),
            "question": self.question,
            "normalized_question": self.normalized_question,
            "domain": self.domain,
            "software_version": self.software_version,
            "stack_pack": self.stack_pack,
            "status": self.status,
            "reference_count": self.reference_count,
            "requester_session_ids": self.requester_session_ids,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "worker_id": self.worker_id,
            "retry_count": self.retry_count,
            "error_log": self.error_log,
            "result_entry_id": self.result_entry_id,
            "needs_review_reason": self.needs_review_reason,
        }


class DeadLetterQueueDB(Base):
    """
    Dead letter queue for failed research items.
    
    Items moved here after max retries for manual review.
    """
    
    __tablename__ = "dead_letter_queue"
    
    # Same fields as queue
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question = Column(Text, nullable=False)
    normalized_question = Column(Text, nullable=False)
    domain = Column(String(50), nullable=True)
    software_version = Column(String(20), nullable=True)
    stack_pack = Column(String(50), nullable=True)
    status = Column(String(20), nullable=False)
    reference_count = Column(Integer, nullable=False, default=1)
    requester_session_ids = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False)
    claimed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    worker_id = Column(String(100), nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)
    error_log = Column(JSON, nullable=True)
    
    # DLQ-specific fields
    moved_to_dlq_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    final_error = Column(JSON, nullable=True)
    
    def __repr__(self) -> str:
        return f"<DeadLetterItem(id={self.id}, question={self.question[:50]}...)>"


class WorkerHeartbeatDB(Base):
    """
    Worker heartbeat tracking table.
    
    Workers must update their heartbeat regularly.
    Stale heartbeats indicate dead workers.
    """
    
    __tablename__ = "worker_heartbeats"
    
    worker_id = Column(String(100), primary_key=True)
    last_heartbeat = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    current_task_id = Column(UUID(as_uuid=True), nullable=True)
    tasks_completed = Column(Integer, nullable=False, default=0)
    tasks_failed = Column(Integer, nullable=False, default=0)
    started_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    status = Column(String(20), nullable=False, default="active")
    
    def __repr__(self) -> str:
        return f"<WorkerHeartbeat(worker_id={self.worker_id}, last={self.last_heartbeat})>"
    
    def is_stale(self, threshold_seconds: int = 60) -> bool:
        """Check if heartbeat is stale."""
        if self.last_heartbeat is None:
            return True
        elapsed = (datetime.utcnow() - self.last_heartbeat.replace(tzinfo=None)).total_seconds()
        return elapsed > threshold_seconds


class EntryProvenanceDB(Base):
    """
    Entry provenance tracking table.
    
    Links KB entries back to the queue items that triggered their creation.
    Includes cost tracking for research operations.
    """
    
    __tablename__ = "entry_provenance"
    
    entry_id = Column(String(200), primary_key=True)
    source_queue_ids = Column(ARRAY(UUID(as_uuid=True)), nullable=False)
    research_cost_usd = Column(DECIMAL(10, 4), nullable=True)
    tokens_consumed = Column(JSON, nullable=True)  # {"input": 1000, "output": 500}
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )
    promoted_at = Column(DateTime(timezone=True), nullable=True)
    
    def __repr__(self) -> str:
        return f"<EntryProvenance(entry_id={self.entry_id})>"


class MetricsLogDB(Base):
    """
    Metrics logging table.
    
    Stores structured logs for metrics collection and analysis.
    """
    
    __tablename__ = "metrics_log"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True
    )
    event_type = Column(String(50), nullable=False, index=True)  # ask, miss, hit, research
    domain = Column(String(50), nullable=True)
    entry_id = Column(String(200), nullable=True)
    software_version = Column(String(20), nullable=True)
    queue_id = Column(UUID(as_uuid=True), nullable=True)
    stack_pack = Column(String(50), nullable=True)
    is_cached_hit = Column(Boolean, nullable=False, default=False)
    model_name = Column(String(100), nullable=True)
    confidence = Column(Float, nullable=True)
    latency_ms = Column(Float, nullable=True)
    tokens_input = Column(Integer, nullable=True)
    tokens_output = Column(Integer, nullable=True)
    extra_data = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_metrics_timestamp', timestamp.desc()),
        Index('idx_metrics_event_type', event_type),
    )
    
    def __repr__(self) -> str:
        return f"<MetricsLog(id={self.id}, event={self.event_type})>"


# Add vector index if pgvector is available
if VECTOR_AVAILABLE:
    # This index is created separately after table creation
    # CREATE INDEX idx_queue_embedding ON queue USING ivfflat (question_embedding vector_cosine_ops);
    pass

