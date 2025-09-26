"""Database connection management for Dominion"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import asyncpg
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from ..config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages database connections and sessions"""

    def __init__(self):
        self.engine = None
        self.async_session_maker = None
        self._redis_pool = None
        self._pg_pool = None

    async def initialize(self):
        """Initialize database connections"""
        try:
            # Initialize PostgreSQL async engine
            self.engine = create_async_engine(
                settings.DATABASE_URL,
                poolclass=NullPool,  # Use asyncpg's built-in pooling
                echo=settings.ENVIRONMENT == "development",
                future=True
            )

            # Create session maker
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

            # Initialize asyncpg connection pool for raw SQL
            self._pg_pool = await asyncpg.create_pool(
                settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"),
                min_size=2,
                max_size=10,
                max_queries=50000,
                max_inactive_connection_lifetime=300.0,
                command_timeout=30.0
            )

            # Initialize Redis connection pool
            self._redis_pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
                max_connections=20,
                retry_on_timeout=True,
                retry_on_error=[redis.ConnectionError, redis.TimeoutError]
            )

            logger.info("Database connections initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database connections: {e}")
            raise

    async def close(self):
        """Close all database connections"""
        try:
            if self.engine:
                await self.engine.dispose()
                logger.info("SQLAlchemy engine disposed")

            if self._pg_pool:
                await self._pg_pool.close()
                logger.info("AsyncPG pool closed")

            if self._redis_pool:
                await self._redis_pool.disconnect()
                logger.info("Redis pool disconnected")

        except Exception as e:
            logger.error(f"Error closing database connections: {e}")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get SQLAlchemy async session"""
        if not self.async_session_maker:
            raise RuntimeError("Database not initialized")

        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception as e:
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                await session.close()

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Get raw asyncpg connection for complex queries"""
        if not self._pg_pool:
            raise RuntimeError("Database pool not initialized")

        async with self._pg_pool.acquire() as connection:
            try:
                yield connection
            except Exception as e:
                logger.error(f"Database connection error: {e}")
                raise

    @asynccontextmanager
    async def get_redis(self) -> AsyncGenerator[redis.Redis, None]:
        """Get Redis connection"""
        if not self._redis_pool:
            raise RuntimeError("Redis pool not initialized")

        redis_client = redis.Redis(connection_pool=self._redis_pool)
        try:
            yield redis_client
        except Exception as e:
            logger.error(f"Redis connection error: {e}")
            raise
        finally:
            await redis_client.close()

    async def health_check(self) -> dict:
        """Check health of all database connections"""
        health_status = {
            "postgres": False,
            "redis": False,
            "overall": False
        }

        # Check PostgreSQL
        try:
            async with self.get_connection() as conn:
                result = await conn.fetchval("SELECT 1")
                health_status["postgres"] = result == 1
        except Exception as e:
            logger.error(f"PostgreSQL health check failed: {e}")

        # Check Redis
        try:
            async with self.get_redis() as redis_client:
                result = await redis_client.ping()
                health_status["redis"] = result
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")

        health_status["overall"] = health_status["postgres"] and health_status["redis"]
        return health_status

# Global database manager instance
db_manager = DatabaseManager()

# Convenience functions for dependency injection
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency function to get database session"""
    async with db_manager.get_session() as session:
        yield session

async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Dependency function to get raw database connection"""
    async with db_manager.get_connection() as connection:
        yield connection

async def get_redis_connection() -> AsyncGenerator[redis.Redis, None]:
    """Dependency function to get Redis connection"""
    async with db_manager.get_redis() as redis_client:
        yield redis_client

# Transaction utilities
@asynccontextmanager
async def transaction():
    """Context manager for database transactions"""
    async with db_manager.get_connection() as conn:
        async with conn.transaction():
            yield conn

class DatabaseUtils:
    """Utility functions for database operations"""

    @staticmethod
    async def execute_sql_file(file_path: str):
        """Execute SQL file (for schema initialization)"""
        try:
            with open(file_path, 'r') as f:
                sql_content = f.read()

            async with db_manager.get_connection() as conn:
                await conn.execute(sql_content)
                logger.info(f"Successfully executed SQL file: {file_path}")

        except Exception as e:
            logger.error(f"Failed to execute SQL file {file_path}: {e}")
            raise

    @staticmethod
    async def check_table_exists(table_name: str) -> bool:
        """Check if a table exists"""
        try:
            async with db_manager.get_connection() as conn:
                result = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_schema = 'public'
                        AND table_name = $1
                    );
                """, table_name)
                return result
        except Exception as e:
            logger.error(f"Error checking if table {table_name} exists: {e}")
            return False

    @staticmethod
    async def get_table_row_count(table_name: str) -> int:
        """Get row count for a table"""
        try:
            async with db_manager.get_connection() as conn:
                result = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                return result
        except Exception as e:
            logger.error(f"Error getting row count for {table_name}: {e}")
            return 0

# Content hash utilities for change detection
class ContentHashManager:
    """Manages content hashing for change detection"""

    @staticmethod
    async def get_last_hash(source_name: str) -> Optional[str]:
        """Get the last content hash for a source"""
        try:
            async with db_manager.get_redis() as redis_client:
                hash_value = await redis_client.get(f"content_hash:{source_name}")
                return hash_value.decode('utf-8') if hash_value else None
        except Exception as e:
            logger.error(f"Error getting content hash for {source_name}: {e}")
            return None

    @staticmethod
    async def set_hash(source_name: str, content_hash: str, expire_seconds: int = 86400):
        """Set content hash for a source with expiration"""
        try:
            async with db_manager.get_redis() as redis_client:
                await redis_client.setex(
                    f"content_hash:{source_name}",
                    expire_seconds,
                    content_hash
                )
        except Exception as e:
            logger.error(f"Error setting content hash for {source_name}: {e}")

    @staticmethod
    async def has_content_changed(source_name: str, new_hash: str) -> bool:
        """Check if content has changed by comparing hashes"""
        last_hash = await ContentHashManager.get_last_hash(source_name)
        return last_hash != new_hash