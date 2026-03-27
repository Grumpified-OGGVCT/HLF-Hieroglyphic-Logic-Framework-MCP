"""
API endpoint definitions.

Implements all REST endpoints for the Verified Developer KB Pro.
"""

import time
import logging
import hashlib
from typing import Union, List
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.api import AskRequest
from app.models.requests import (
    AskBatchRequest,
    LockRequest,
    VerifyLockRequest,
    SearchRequest,
)
from app.models.responses import (
    AnswerResponse,
    MissResponse,
    BatchResponse,
    BatchAnswerItem,
    LockResponse,
    LockEntryInfo,
    VerifyLockResponse,
    HealthResponse,
    StatsResponse,
    QueueStatusResponse,
)
from app.db.connection import get_db
from app.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


# Dependency injection for services
async def get_retriever():
    """Get the retrieval service."""
    from app.services.retrieval import IntelligentRetriever
    retriever = IntelligentRetriever()
    await retriever.initialize()
    return retriever


async def get_kb_model():
    """Get the KB model service."""
    from app.services.kb_model import KBModelService
    service = KBModelService()
    await service.initialize()
    return service


async def get_queue_service():
    """Get the queue service."""
    from app.services.queue_service import QueueService
    service = QueueService()
    await service.initialize()
    return service


async def get_kb_parser():
    """Get the KB parser."""
    from app.services.kb_parser import KBParser
    return KBParser()


@router.get("/")
async def root():
    """
    API root endpoint.
    
    Returns API information and status.
    """
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "Verified developer knowledge base with self-expanding research",
        "status": "production",
        "endpoints": [
            "/health",
            "/stats",
            "/ask",
            "/ask-batch",
            "/search",
            "/lock",
            "/verify-lock",
            "/queue-status"
        ]
    }


@router.post("/ask", response_model=Union[AnswerResponse, MissResponse])
async def ask_question(
    request: AskRequest,
    background_tasks: BackgroundTasks,
    http_request: Request
):
    """
    Ask a technical question.
    
    Returns a grounded answer if confidence >= threshold,
    otherwise queues the question for research.
    """
    start_time = time.time()
    settings = get_settings()
    
    try:
        # Get services
        retriever = await get_retriever()
        kb_model = await get_kb_model()
        queue_service = await get_queue_service()
        
        # 1. Retrieve relevant chunks
        chunks, cache_hit = await retriever.retrieve(
            request.question,
            request.domain,
            request.software_version,
            request.stack_pack
        )
        
        # 2. Check for high-confidence exact match (fast path)
        if cache_hit and chunks and chunks[0].adjusted_confidence >= 0.95:
            top_chunk = chunks[0]
            
            # Get entry hash for lockfile support
            entry_hashes = {top_chunk.entry.id: top_chunk.entry.sha256}
            
            return AnswerResponse(
                question=request.question,
                answer=top_chunk.entry.answer,
                confidence=top_chunk.adjusted_confidence,
                tier=top_chunk.entry.tier,
                sources=top_chunk.entry.sources,
                related_questions=top_chunk.entry.related_questions,
                cache_hit=True,
                entry_id=top_chunk.entry.id,
                entry_ids=[top_chunk.entry.id],
                entry_hashes_sha256=entry_hashes,
                software_version_resolved=top_chunk.entry.software_version,
                meta={
                    "response_time_ms": round((time.time() - start_time) * 1000, 2)
                }
            )
        
        # 3. Query KB model
        model_response = await kb_model.query(
            request.question,
            chunks,
            request.software_version
        )
        
        # 4. Determine hit or miss
        if model_response.is_hit:
            # Get entry hashes for lockfile support
            entry_hashes = {}
            parser = await get_kb_parser()
            for entry_id in model_response.entry_ids:
                entry_hash = parser.get_entry_hash(entry_id)
                if entry_hash:
                    entry_hashes[entry_id] = entry_hash
            
            response_obj = kb_model.to_answer_response(
                model_response,
                cache_hit=cache_hit,
                entry_hashes=entry_hashes if entry_hashes else None
            )
            # Final QA pass (skip cached fast path; only for non-cached LLM answers)
            if not cache_hit:
                from app.services.final_qa import FinalQAPassService
                qa = FinalQAPassService()
                try:
                    response_obj.answer = await qa.maybe_apply(
                        question=request.question,
                        answer=response_obj.answer,
                        sources=response_obj.sources,
                    )
                finally:
                    await qa.close()
            return response_obj
        
        # 5. Miss - queue for research
        queue_id = await queue_service.enqueue(
            request.question,
            request.domain,
            request.software_version,
            request.stack_pack,
            request.session_id
        )
        
        # 6. Optional realtime research
        if request.realtime_research:
            background_tasks.add_task(
                run_realtime_research,
                queue_id,
                request.question,
                request.domain,
                request.software_version
            )
        
        return kb_model.to_miss_response(model_response, queue_id)
        
    except Exception as e:
        logger.error(f"Error processing /ask request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def run_realtime_research(
    queue_id: str,
    question: str,
    domain: str,
    software_version: str
):
    """Background task for realtime research."""
    from app.services.research import ResearchAgentService
    from app.services.queue_service import QueueService
    
    research = ResearchAgentService()
    await research.initialize()
    
    queue_service = QueueService()
    
    try:
        entry = await research.research(question, domain, software_version)
        
        if entry:
            # Write to staging
            ok = await research.write_to_staging(entry)

            # Update queue
            if ok:
                await queue_service.complete_task(queue_id, entry.id, success=True)
            else:
                reason = getattr(research, "last_qa_audit_message", None) or "QA audit failed"
                await queue_service.fail_task(queue_id, {"error": reason})
        else:
            await queue_service.discard_task(queue_id)
            
    except Exception as e:
        logger.error(f"Realtime research failed: {e}")
        await queue_service.fail_task(queue_id, {"error": str(e)})


@router.post("/ask-batch", response_model=BatchResponse)
async def ask_batch(request: AskBatchRequest):
    """
    Ask multiple questions in a single request.
    
    Supports semantic deduplication for efficiency.
    """
    start_time = time.time()
    
    try:
        retriever = await get_retriever()
        kb_model = await get_kb_model()
        queue_service = await get_queue_service()
        
        questions = request.questions
        unique_questions = questions
        
        # Semantic deduplication if requested
        if request.dedupe and len(questions) > 1:
            # TODO: Implement semantic dedup
            # For now, just remove exact duplicates
            seen = set()
            unique_questions = []
            for q in questions:
                normalized = q.lower().strip()
                if normalized not in seen:
                    seen.add(normalized)
                    unique_questions.append(q)
        
        # Process each question
        answers = []
        found = 0
        not_found = 0
        
        for question in unique_questions:
            chunks, cache_hit = await retriever.retrieve(
                question,
                request.domain,
                request.software_version,
                request.stack_pack
            )
            
            model_response = await kb_model.query(
                question,
                chunks,
                request.software_version
            )
            
            if model_response.is_hit:
                found += 1
                answers.append(BatchAnswerItem(
                    question=question,
                    answer=model_response.answer,
                    confidence=model_response.confidence,
                    tier=model_response.tier,
                    sources=model_response.sources,
                    entry_id=model_response.entry_ids[0] if model_response.entry_ids else None,
                    queued=False
                ))
            else:
                not_found += 1
                queue_id = await queue_service.enqueue(
                    question,
                    request.domain,
                    request.software_version,
                    request.stack_pack
                )
                answers.append(BatchAnswerItem(
                    question=question,
                    answer=None,
                    confidence=model_response.confidence,
                    queued=True,
                    queue_id=queue_id
                ))
        
        return BatchResponse(
            total=len(request.questions),
            unique=len(unique_questions),
            found=found,
            not_found=not_found,
            answers=answers,
            processing_time_ms=round((time.time() - start_time) * 1000, 2)
        )
        
    except Exception as e:
        logger.error(f"Error processing /ask-batch request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_questions(
    q: str,
    domain: str = None,
    limit: int = 10,
    tier: str = None
):
    """
    Search the Q&A database.
    
    Returns matching questions and answers ranked by relevance.
    """
    start_time = time.time()
    
    try:
        retriever = await get_retriever()
        
        chunks, _ = await retriever.retrieve(
            q,
            domain,
            top_k=limit
        )
        
        results = []
        for chunk in chunks:
            results.append({
                "id": chunk.entry.id,
                "question": chunk.entry.question,
                "answer": chunk.entry.answer[:500] + "..." if len(chunk.entry.answer) > 500 else chunk.entry.answer,
                "domain": chunk.entry.domain,
                "confidence": chunk.adjusted_confidence,
                "tier": chunk.entry.tier,
                "similarity": chunk.similarity
            })
        
        return {
            "query": q,
            "results": results,
            "meta": {
                "total": len(chunks),
                "returned": len(results),
                "search_time_ms": round((time.time() - start_time) * 1000, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Error processing /search request: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lock", response_model=LockResponse)
async def generate_lockfile(request: LockRequest):
    """
    Generate SHA-256 hashes for specific KB entries.
    
    Used for reproducible builds and version pinning.
    """
    try:
        parser = await get_kb_parser()
        
        entries = {}
        for entry_id in request.entry_ids:
            entry = parser.get_entry_by_id(entry_id)
            if entry:
                entries[entry_id] = LockEntryInfo(
                    sha256=entry.sha256,
                    version=entry.software_version
                )
            else:
                logger.warning(f"Entry not found for lock: {entry_id}")
        
        return LockResponse(
            lockfile_version="1",
            generated_at=datetime.utcnow(),
            entries=entries
        )
        
    except Exception as e:
        logger.error(f"Error generating lockfile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/verify-lock", response_model=VerifyLockResponse)
async def verify_lockfile(request: VerifyLockRequest):
    """
    Verify KB entries haven't drifted from locked hashes.
    """
    try:
        parser = await get_kb_parser()
        
        mismatches = []
        missing = []
        checked = 0
        
        for entry_id, expected in request.entries.items():
            checked += 1
            entry = parser.get_entry_by_id(entry_id)
            
            if not entry:
                missing.append(entry_id)
                continue
            
            expected_hash = expected.get("sha256") if isinstance(expected, dict) else expected
            
            if entry.sha256 != expected_hash:
                mismatches.append(entry_id)
        
        return VerifyLockResponse(
            valid=len(mismatches) == 0 and len(missing) == 0,
            checked=checked,
            mismatches=mismatches,
            missing=missing
        )
        
    except Exception as e:
        logger.error(f"Error verifying lockfile: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Checks all service dependencies and returns overall status.
    """
    from pathlib import Path
    import os
    
    settings = get_settings()
    checks = {}
    
    # Check API (always healthy if responding)
    checks["api"] = "healthy"
    
    # Check database
    try:
        from app.db.connection import check_db_health
        db_health = await check_db_health()
        checks["database"] = db_health
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
    
    # Check Redis
    try:
        from app.services.cache import CacheService
        cache = CacheService()
        await cache.connect()
        redis_health = await cache.health_check()
        checks["redis"] = redis_health
        await cache.close()
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
    
    # Check KB files
    kb_path = Path(settings.kb.kb_files_path)
    checks["kb_files"] = "healthy" if kb_path.exists() else "missing"
    
    # Check worker heartbeats
    try:
        queue_service = await get_queue_service()
        stale_workers = await queue_service.get_stale_workers()
        if stale_workers:
            checks["workers"] = {"status": "degraded", "stale_workers": stale_workers}
        else:
            checks["workers"] = "healthy"
    except Exception as e:
        checks["workers"] = {"status": "unknown", "error": str(e)}
    
    # Check emergency stop flag
    emergency_stop = Path(settings.kb.alerts_path) / "EMERGENCY_STOP.flag"
    is_emergency = emergency_stop.exists()
    
    # Determine overall status
    all_healthy = all(
        (c == "healthy" or (isinstance(c, dict) and c.get("status") == "healthy"))
        for k, c in checks.items()
        if k != "kb_files"  # KB files can be missing initially
    )
    
    status = "healthy" if all_healthy and not is_emergency else "degraded"
    if is_emergency:
        status = "emergency_stop"
    
    return HealthResponse(
        status=status,
        timestamp=datetime.utcnow(),
        checks=checks,
        emergency_stop=is_emergency
    )


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get knowledge base statistics.
    """
    try:
        parser = await get_kb_parser()
        queue_service = await get_queue_service()
        
        kb_stats = parser.get_stats()
        queue_stats = await queue_service.get_queue_stats()
        
        return StatsResponse(
            total_entries=kb_stats["total_entries"],
            domains=kb_stats["domains"],
            avg_confidence=kb_stats["avg_confidence"],
            entries_by_domain=kb_stats["entries_by_domain"],
            entries_by_tier=kb_stats["entries_by_tier"],
            queue_depth=queue_stats["total"],
            queue_by_status=queue_stats["by_status"]
        )
        
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue-status", response_model=QueueStatusResponse)
async def get_queue_status():
    """
    Get research queue status.
    """
    try:
        queue_service = await get_queue_service()
        stats = await queue_service.get_queue_stats()
        
        return QueueStatusResponse(
            total=stats["total"],
            by_status=stats["by_status"],
            workers_active=stats.get("active_workers", 0),
            oldest_pending=datetime.fromisoformat(stats["oldest_pending"]) if stats.get("oldest_pending") else None
        )
        
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

