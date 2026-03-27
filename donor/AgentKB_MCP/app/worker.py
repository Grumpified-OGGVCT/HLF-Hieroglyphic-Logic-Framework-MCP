"""
Research worker process.

Consumes research queue and expands the KB using the Research Agent.
"""

import asyncio
import logging
import time
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

from app.config import get_settings
from app.services.queue_service import QueueService
from app.services.research import ResearchAgentService
from app.services.sanitizer import PIISanitizer
from app.db.connection import init_db, close_db
from app.monitoring import (
    record_research_task,
    update_worker_heartbeat,
    record_llm_usage,
    get_logger,
)

logger = get_logger(__name__)


class ResearchWorker:
    """
    Research worker that processes the queue.
    
    Implements:
    - Heartbeat tracking
    - PII sanitization
    - Emergency stop detection
    - Retry logic with DLQ
    - Cost tracking
    """
    
    def __init__(self, worker_id: Optional[str] = None):
        """
        Initialize the research worker.
        
        Args:
            worker_id: Unique worker identifier (generated if not provided)
        """
        self.settings = get_settings()
        self.worker_id = worker_id or self.settings.worker.worker_id
        
        self.queue_service = QueueService()
        self.research_agent = ResearchAgentService()
        self.sanitizer = PIISanitizer()
        
        self.shutdown = False
        self.emergency_stop = False
        self.consecutive_failures = 0
        self.tasks_completed = 0
        self.tasks_failed = 0
    
    async def initialize(self) -> None:
        """Initialize worker services."""
        await init_db()
        await self.queue_service.initialize()
        await self.research_agent.initialize()
        
        logger.info(
            "worker_initialized",
            worker_id=self.worker_id
        )
    
    async def shutdown_worker(self) -> None:
        """Shutdown worker gracefully."""
        self.shutdown = True
        await close_db()
        
        logger.info(
            "worker_shutdown",
            worker_id=self.worker_id,
            tasks_completed=self.tasks_completed,
            tasks_failed=self.tasks_failed
        )
    
    async def check_emergency_stop(self) -> bool:
        """Check if emergency stop flag is set."""
        flag_path = Path(self.settings.kb.alerts_path) / "EMERGENCY_STOP.flag"
        
        if flag_path.exists():
            if not self.emergency_stop:
                logger.warning(
                    "emergency_stop_detected",
                    worker_id=self.worker_id
                )
                self.emergency_stop = True
            return True
        
        self.emergency_stop = False
        return False
    
    async def update_heartbeat(self, task_id: Optional[str] = None) -> None:
        """Update worker heartbeat."""
        await self.queue_service.update_heartbeat(self.worker_id, task_id)
        update_worker_heartbeat(self.worker_id, time.time())
    
    async def claim_task(self) -> Optional[Dict[str, Any]]:
        """Claim the next pending task."""
        return await self.queue_service.claim_task(self.worker_id)
    
    async def process_task(self, task: Dict[str, Any]) -> bool:
        """
        Process a single research task.
        
        Args:
            task: The task dict from the queue
            
        Returns:
            True if successful, False otherwise
        """
        task_id = task["id"]
        question = task["question"]
        domain = task.get("domain")
        software_version = task.get("software_version")
        
        start_time = time.time()
        
        logger.info(
            "task_started",
            worker_id=self.worker_id,
            task_id=task_id,
            question=question[:50] + "..." if len(question) > 50 else question
        )
        
        try:
            # Sanitization check
            if self.sanitizer.contains_sensitive(question):
                logger.warning(
                    "task_sensitive_content",
                    worker_id=self.worker_id,
                    task_id=task_id
                )
                await self.queue_service.mark_needs_review(
                    task_id,
                    reason="PII/secrets detected in question"
                )
                return True  # Not a failure, just needs review
            
            # Perform research
            entry = await self.research_agent.research(
                question,
                domain,
                software_version
            )
            
            duration = time.time() - start_time
            
            if entry:
                # Write to staging
                success = await self.research_agent.write_to_staging(entry)
                
                if success:
                    await self.queue_service.complete_task(task_id, entry.id, success=True)
                    
                    record_research_task("completed", domain or "unknown", duration)
                    
                    logger.info(
                        "task_completed",
                        worker_id=self.worker_id,
                        task_id=task_id,
                        entry_id=entry.id,
                        duration_seconds=duration
                    )
                    
                    self.consecutive_failures = 0
                    return True
                else:
                    reason = getattr(self.research_agent, "last_qa_audit_message", None) or "Failed to write entry to staging"
                    raise Exception(reason)
            else:
                # Research returned None - discard
                await self.queue_service.discard_task(task_id)
                
                record_research_task("discarded", domain or "unknown", duration)
                
                logger.info(
                    "task_discarded",
                    worker_id=self.worker_id,
                    task_id=task_id,
                    reason="No authoritative sources found"
                )
                
                return True  # Discard is not a failure
                
        except Exception as e:
            duration = time.time() - start_time
            
            logger.error(
                "task_failed",
                worker_id=self.worker_id,
                task_id=task_id,
                error=str(e),
                duration_seconds=duration
            )
            
            await self.queue_service.fail_task(task_id, {
                "error": str(e),
                "worker_id": self.worker_id,
                "timestamp": datetime.utcnow().isoformat()
            })
            
            record_research_task("failed", domain or "unknown", duration)
            
            self.consecutive_failures += 1
            return False
    
    async def check_consecutive_failures(self) -> None:
        """Check for too many consecutive failures and trigger emergency stop."""
        threshold = self.settings.worker.emergency_stop_threshold
        
        if self.consecutive_failures >= threshold:
            logger.critical(
                "emergency_stop_triggered",
                worker_id=self.worker_id,
                consecutive_failures=self.consecutive_failures
            )
            
            # Create emergency stop flag
            alerts_path = Path(self.settings.kb.alerts_path)
            alerts_path.mkdir(parents=True, exist_ok=True)
            
            flag_path = alerts_path / "EMERGENCY_STOP.flag"
            flag_path.write_text(
                f"Emergency stop triggered by worker {self.worker_id}\n"
                f"Consecutive failures: {self.consecutive_failures}\n"
                f"Timestamp: {datetime.utcnow().isoformat()}\n"
            )
            
            self.emergency_stop = True
    
    async def run(self) -> None:
        """
        Main worker loop.
        
        Processes tasks until shutdown or emergency stop.
        """
        logger.info(
            "worker_starting",
            worker_id=self.worker_id
        )
        
        poll_interval = self.settings.worker.poll_interval
        heartbeat_interval = self.settings.worker.heartbeat_interval
        last_heartbeat = 0
        
        while not self.shutdown:
            try:
                # Check emergency stop
                if await self.check_emergency_stop():
                    logger.warning(
                        "worker_paused_emergency",
                        worker_id=self.worker_id
                    )
                    await asyncio.sleep(60)  # Wait before rechecking
                    continue
                
                # Heartbeat
                current_time = time.time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    await self.update_heartbeat()
                    last_heartbeat = current_time
                
                # Claim a task
                task = await self.claim_task()
                
                if task is None:
                    # No tasks available, wait
                    await asyncio.sleep(poll_interval)
                    continue
                
                # Update heartbeat with current task
                await self.update_heartbeat(task["id"])
                
                # Process the task
                success = await self.process_task(task)
                
                if success:
                    self.tasks_completed += 1
                else:
                    self.tasks_failed += 1
                    await self.check_consecutive_failures()
                
                # Clear task from heartbeat
                await self.update_heartbeat()
                
                # Record completion
                await self.queue_service.record_worker_completion(
                    self.worker_id,
                    success=success
                )
                
            except Exception as e:
                logger.error(
                    "worker_loop_error",
                    worker_id=self.worker_id,
                    error=str(e)
                )
                await asyncio.sleep(poll_interval)
        
        await self.shutdown_worker()


async def main():
    """Main entry point for worker process."""
    import signal
    
    worker = ResearchWorker()
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal")
        worker.shutdown = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    await worker.initialize()
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())

