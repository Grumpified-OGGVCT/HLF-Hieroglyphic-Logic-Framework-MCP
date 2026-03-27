"""
Queue management service.

Handles research queue operations including semantic deduplication
and reference counting.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
import json

from sqlalchemy import select, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QueueItemDB, DeadLetterQueueDB, WorkerHeartbeatDB
from app.db.connection import get_async_session
from app.services.embedding import EmbeddingService
from app.config import get_settings
from app.models.queue import QueueItem, QueueStatus

logger = logging.getLogger(__name__)


class QueueService:
    """
    Research queue management service.
    
    Implements:
    - Semantic deduplication before enqueue
    - Reference counting for duplicate questions
    - Worker task claiming
    - Dead letter queue management
    - Worker heartbeat tracking
    """
    
    # Similarity threshold for semantic dedup
    DEDUP_THRESHOLD = 0.9
    
    def __init__(self, embedding_service: Optional[EmbeddingService] = None):
        """
        Initialize the queue service.
        
        Args:
            embedding_service: Optional embedding service for semantic dedup
        """
        self.settings = get_settings()
        self.embedding_service = embedding_service or EmbeddingService()
    
    async def initialize(self) -> None:
        """Initialize the embedding service."""
        await self.embedding_service.initialize()
    
    def _normalize_question(self, question: str) -> str:
        """Normalize question for deduplication."""
        # Import from retrieval to reuse abbreviation expansion
        from app.services.retrieval import IntelligentRetriever
        retriever = IntelligentRetriever()
        return retriever._normalize_question(question)
    
    async def enqueue(
        self,
        question: str,
        domain: Optional[str] = None,
        software_version: Optional[str] = None,
        stack_pack: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Enqueue a question for research with semantic deduplication.
        
        If a semantically similar question already exists in the queue,
        increments its reference count instead of creating a new item.
        
        Args:
            question: The question to enqueue
            domain: Optional domain filter
            software_version: Optional version filter
            stack_pack: Optional stack pack filter
            session_id: Optional requester session ID
            
        Returns:
            Queue item ID (new or existing)
        """
        normalized = self._normalize_question(question)
        
        # Get embedding for semantic dedup
        embedding = await self.embedding_service.embed(normalized)
        
        async with get_async_session() as db:
            # Check for existing similar items
            existing = await self._find_similar(db, embedding, normalized)
            
            if existing:
                # Increment reference count
                await self._increment_reference(db, existing.id, session_id)
                logger.info(f"Found similar queue item, incremented reference: {existing.id}")
                return str(existing.id)
            
            # Create new queue item
            item = QueueItemDB(
                question=question,
                normalized_question=normalized,
                question_embedding=embedding,
                domain=domain,
                software_version=software_version,
                stack_pack=stack_pack,
                status="pending",
                reference_count=1,
                requester_session_ids=[session_id] if session_id else []
            )
            
            db.add(item)
            await db.flush()
            
            queue_id = str(item.id)
            logger.info(f"Created new queue item: {queue_id}")
            
            return queue_id
    
    async def _find_similar(
        self,
        db: AsyncSession,
        embedding: Optional[List[float]],
        normalized: str
    ) -> Optional[QueueItemDB]:
        """
        Find a similar existing queue item.
        
        Uses vector similarity if embeddings available,
        falls back to exact match.
        
        Args:
            db: Database session
            embedding: Question embedding
            normalized: Normalized question text
            
        Returns:
            Existing queue item or None
        """
        # First try exact match on normalized question
        stmt = select(QueueItemDB).where(
            and_(
                QueueItemDB.normalized_question == normalized,
                QueueItemDB.status.in_(["pending", "researching"])
            )
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        
        if existing:
            return existing
        
        # TODO: Implement vector similarity search when pgvector is available
        # For now, exact match is the fallback
        
        return None
    
    async def _increment_reference(
        self,
        db: AsyncSession,
        queue_id: UUID,
        session_id: Optional[str]
    ) -> None:
        """
        Increment reference count on an existing queue item.
        
        Args:
            db: Database session
            queue_id: Queue item ID
            session_id: Session ID to add
        """
        stmt = (
            update(QueueItemDB)
            .where(QueueItemDB.id == queue_id)
            .values(
                reference_count=QueueItemDB.reference_count + 1
            )
        )
        await db.execute(stmt)
        
        # Add session ID to array (PostgreSQL specific)
        if session_id:
            item = await db.get(QueueItemDB, queue_id)
            if item:
                session_ids = item.requester_session_ids or []
                if session_id not in session_ids:
                    session_ids.append(session_id)
                    item.requester_session_ids = session_ids
    
    async def claim_task(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """
        Claim a pending task for processing.
        
        Args:
            worker_id: The worker's ID
            
        Returns:
            Task dict or None if no tasks available
        """
        async with get_async_session() as db:
            # Get oldest pending task that isn't being processed
            stmt = (
                select(QueueItemDB)
                .where(QueueItemDB.status == "pending")
                .order_by(QueueItemDB.created_at)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            result = await db.execute(stmt)
            item = result.scalar_one_or_none()
            
            if not item:
                return None
            
            # Claim it
            item.status = "researching"
            item.worker_id = worker_id
            item.claimed_at = datetime.utcnow()
            
            await db.flush()
            
            return item.to_dict()
    
    async def complete_task(
        self,
        queue_id: str,
        entry_id: str,
        success: bool = True
    ) -> None:
        """
        Mark a task as completed.
        
        Args:
            queue_id: Queue item ID
            entry_id: Created KB entry ID (if successful)
            success: Whether research was successful
        """
        async with get_async_session() as db:
            item = await db.get(QueueItemDB, UUID(queue_id))
            
            if not item:
                logger.warning(f"Queue item not found: {queue_id}")
                return
            
            if success:
                item.status = "needs_review"  # Needs human review before promotion
                item.result_entry_id = entry_id
            else:
                item.status = "failed"
            
            item.completed_at = datetime.utcnow()
    
    async def mark_needs_review(
        self,
        queue_id: str,
        reason: str
    ) -> None:
        """
        Mark a task as needing human review.
        
        Args:
            queue_id: Queue item ID
            reason: Reason for review
        """
        async with get_async_session() as db:
            item = await db.get(QueueItemDB, UUID(queue_id))
            
            if item:
                item.status = "needs_review"
                item.needs_review_reason = reason
    
    async def discard_task(self, queue_id: str) -> None:
        """
        Mark a task as discarded (no authoritative sources found).
        
        Args:
            queue_id: Queue item ID
        """
        async with get_async_session() as db:
            item = await db.get(QueueItemDB, UUID(queue_id))
            
            if item:
                item.status = "discarded"
                item.completed_at = datetime.utcnow()
    
    async def fail_task(
        self,
        queue_id: str,
        error: Dict[str, Any]
    ) -> None:
        """
        Record a task failure.
        
        Args:
            queue_id: Queue item ID
            error: Error details
        """
        async with get_async_session() as db:
            item = await db.get(QueueItemDB, UUID(queue_id))
            
            if not item:
                return
            
            item.retry_count += 1
            item.error_log = error
            
            if item.retry_count >= self.settings.worker.max_retries:
                # Move to DLQ
                await self._move_to_dlq(db, item)
            else:
                # Reset for retry
                item.status = "pending"
                item.worker_id = None
                item.claimed_at = None
    
    async def _move_to_dlq(self, db: AsyncSession, item: QueueItemDB) -> None:
        """Move an item to the dead letter queue."""
        dlq_item = DeadLetterQueueDB(
            id=item.id,
            question=item.question,
            normalized_question=item.normalized_question,
            domain=item.domain,
            software_version=item.software_version,
            stack_pack=item.stack_pack,
            status=item.status,
            reference_count=item.reference_count,
            requester_session_ids=item.requester_session_ids,
            created_at=item.created_at,
            claimed_at=item.claimed_at,
            completed_at=item.completed_at,
            worker_id=item.worker_id,
            retry_count=item.retry_count,
            error_log=item.error_log,
            final_error=item.error_log
        )
        
        db.add(dlq_item)
        await db.delete(item)
        
        logger.warning(f"Moved queue item to DLQ: {item.id}")
    
    async def update_heartbeat(
        self,
        worker_id: str,
        current_task_id: Optional[str] = None
    ) -> None:
        """
        Update worker heartbeat.
        
        Args:
            worker_id: Worker ID
            current_task_id: Currently processing task ID
        """
        async with get_async_session() as db:
            # Upsert heartbeat
            existing = await db.get(WorkerHeartbeatDB, worker_id)
            
            if existing:
                existing.last_heartbeat = datetime.utcnow()
                existing.current_task_id = UUID(current_task_id) if current_task_id else None
            else:
                heartbeat = WorkerHeartbeatDB(
                    worker_id=worker_id,
                    current_task_id=UUID(current_task_id) if current_task_id else None
                )
                db.add(heartbeat)
    
    async def record_worker_completion(
        self,
        worker_id: str,
        success: bool = True
    ) -> None:
        """
        Record task completion for a worker.
        
        Args:
            worker_id: Worker ID
            success: Whether the task was successful
        """
        async with get_async_session() as db:
            existing = await db.get(WorkerHeartbeatDB, worker_id)
            
            if existing:
                existing.current_task_id = None
                if success:
                    existing.tasks_completed += 1
                else:
                    existing.tasks_failed += 1
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics.
        
        Returns:
            Stats dict with counts by status
        """
        async with get_async_session() as db:
            # Count by status
            stmt = (
                select(QueueItemDB.status, func.count(QueueItemDB.id))
                .group_by(QueueItemDB.status)
            )
            result = await db.execute(stmt)
            by_status = {row[0]: row[1] for row in result}
            
            # Get oldest pending
            stmt = (
                select(func.min(QueueItemDB.created_at))
                .where(QueueItemDB.status == "pending")
            )
            result = await db.execute(stmt)
            oldest = result.scalar()
            
            # Count active workers
            stmt = (
                select(func.count(WorkerHeartbeatDB.worker_id))
                .where(
                    WorkerHeartbeatDB.last_heartbeat > 
                    func.now() - func.cast('60 seconds', type_=func.literal_column('interval'))
                )
            )
            # Fallback count without interval for SQLite compatibility
            try:
                result = await db.execute(stmt)
                active_workers = result.scalar() or 0
            except:
                active_workers = 0
            
            total = sum(by_status.values())
            
            return {
                "total": total,
                "by_status": by_status,
                "oldest_pending": oldest.isoformat() if oldest else None,
                "active_workers": active_workers
            }
    
    async def get_stale_workers(self, threshold_seconds: int = 60) -> List[str]:
        """
        Get list of stale workers.
        
        Args:
            threshold_seconds: Seconds before considered stale
            
        Returns:
            List of stale worker IDs
        """
        async with get_async_session() as db:
            cutoff = datetime.utcnow()
            
            stmt = select(WorkerHeartbeatDB)
            result = await db.execute(stmt)
            workers = result.scalars().all()
            
            stale = []
            for worker in workers:
                if worker.is_stale(threshold_seconds):
                    stale.append(worker.worker_id)
            
            return stale

