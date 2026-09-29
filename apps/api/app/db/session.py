"""
NEXUS - DB Session - Phase 2B Persistence Foundation
Async engine + sessionmaker, get_session dependency
"""

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings
from app.db.base import Base

# Async engine - uses DATABASE_URL from settings
# For tests, can override via env or direct engine creation
engine = create_async_engine(
    settings.database_url,
    echo=settings.is_development,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for DB session
    Usage: Depends(get_session)
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    Init DB - create all tables (for dev only, use Alembic for prod)
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """
    Close engine
    """
    await engine.dispose()
