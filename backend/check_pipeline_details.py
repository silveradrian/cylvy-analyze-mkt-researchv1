import asyncio
from app.core.database import db_pool
import uuid

async def check():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Check pipeline execution status
        pipeline = await conn.fetchrow("""
            SELECT status, started_at, completed_at, mode, errors
            FROM pipeline_executions
            WHERE id = $1
        """, pipeline_id)
        
        print(f"Pipeline Status: {pipeline['status']}")
        print(f"Mode: {pipeline['mode']}")
        print(f"Started: {pipeline['started_at']}")
        print(f"Completed: {pipeline['completed_at']}")
        if pipeline['errors']:
            print(f"Errors: {pipeline['errors']}")

asyncio.run(check())
