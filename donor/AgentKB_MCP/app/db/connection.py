"""
Database connection and session management.

Provides async database connections using SQLAlchemy 2.0 patterns.
"""

from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
)
from sqlalchemy.pool import NullPool
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional
import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

# Global engine instance (initialized lazily)
_engine: Optional[AsyncEngine] = None
_async_session_maker: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """
    Get or create the database engine.
    
    Returns:
        The SQLAlchemy async engine instance.
    """
    global _engine
    
    if _engine is None:
        settings = get_settings()
        
        # Convert standard PostgreSQL URL to async
        db_url = settings.database.url
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        
        _engine = create_async_engine(
            db_url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_timeout=settings.database.pool_timeout,
            echo=settings.database.echo,
            # Use NullPool for testing to avoid connection issues
            poolclass=NullPool if settings.environment == "testing" else None,
        )
        
        logger.info(f"Database engine created for {db_url.split('@')[-1]}")
    
    return _engine


def get_session_maker() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the session maker.
    
    Returns:
        The SQLAlchemy async session maker.
    """
    global _async_session_maker
    
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    
    return _async_session_maker


# Convenience aliases
engine = property(lambda: get_engine())
async_session_maker = property(lambda: get_session_maker())


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions.
    
    Handles session lifecycle including commit/rollback on errors.
    
    Usage:
        async with get_async_session() as session:
            result = await session.execute(...)
    """
    session_maker = get_session_maker()
    session = session_maker()
    
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection function for FastAPI.
    
    Usage:
        @app.get("/")
        async def endpoint(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with get_async_session() as session:
        yield session


async def init_db() -> None:
    """
    Initialize the database.
    
    Creates all tables if they don't exist.
    Should be called during application startup.
    """
    from app.db.models import Base
    
    engine = get_engine()
    
    async with engine.begin() as conn:
        # Create pgvector extension if not exists
        await conn.execute(
            "CREATE EXTENSION IF NOT EXISTS vector"
        )
        
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database initialized")


async def close_db() -> None:
    """
    Close the database connection.
    
    Should be called during application shutdown.
    """
    global _engine, _async_session_maker
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        
    logger.info("Database connection closed")


async def check_db_health() -> dict:
    """
    Check database health.
    
    Returns:
        Health check result with status and response time.
    """
    import time
    
    start = time.time()
    
    try:
        async with get_async_session() as session:
            result = await session.execute("SELECT 1")
            result.scalar()
            
        elapsed_ms = (time.time() - start) * 1000
        
        return {
            "status": "healthy",
            "response_time_ms": round(elapsed_ms, 2)
        }
    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        
        return {
            "status": "unhealthy",
            "response_time_ms": round(elapsed_ms, 2),
            "error": str(e)
        }

