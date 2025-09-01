"""
Database connection and session management
"""
import asyncio
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

import asyncpg
from loguru import logger

from app.core.config import settings


class DatabasePool:
    """Manages database connection pool"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize the connection pool"""
        async with self._lock:
            if self.pool is None:
                logger.info("Initializing database connection pool...")
                self.pool = await asyncpg.create_pool(
                    settings.DATABASE_URL,
                    min_size=10,
                    max_size=settings.DB_POOL_SIZE,
                    command_timeout=60,
                    server_settings={
                        'application_name': settings.APP_NAME,
                        'jit': 'off'
                    }
                )
                logger.info("Database pool initialized successfully")
    
    async def close(self):
        """Close the connection pool"""
        async with self._lock:
            if self.pool:
                await self.pool.close()
                self.pool = None
                logger.info("Database pool closed")
    
    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Acquire a connection from the pool"""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as connection:
            # Set tenant context for RLS if needed
            yield connection
    
    async def execute(self, query: str, *args, timeout: float = None):
        """Execute a query"""
        async with self.acquire() as conn:
            return await conn.execute(query, *args, timeout=timeout)
    
    async def fetch(self, query: str, *args, timeout: float = None):
        """Fetch multiple rows"""
        async with self.acquire() as conn:
            return await conn.fetch(query, *args, timeout=timeout)
    
    async def fetchrow(self, query: str, *args, timeout: float = None):
        """Fetch a single row"""
        async with self.acquire() as conn:
            return await conn.fetchrow(query, *args, timeout=timeout)
    
    async def fetchval(self, query: str, *args, timeout: float = None):
        """Fetch a single value"""
        async with self.acquire() as conn:
            return await conn.fetchval(query, *args, timeout=timeout)


# Global database pool instance
db_pool = DatabasePool()


async def get_db() -> DatabasePool:
    """Dependency to get database pool"""
    return db_pool


class AsyncConnection:
    """Async database connection wrapper for compatibility"""
    
    def __init__(self, connection):
        self._connection = connection
    
    async def fetch(self, query: str, *args):
        return await self._connection.fetch(query, *args)
    
    async def fetchrow(self, query: str, *args):
        return await self._connection.fetchrow(query, *args)
    
    async def fetchval(self, query: str, *args):
        return await self._connection.fetchval(query, *args)
    
    async def execute(self, query: str, *args):
        return await self._connection.execute(query, *args)

