import asyncio
from app.core.database import db_pool
import uuid
import json

async def reset():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Reset pipeline to running state and clear errors
        await conn.execute("""
            UPDATE pipeline_executions
            SET status = 'running',
                completed_at = NULL,
                errors = '[]'::jsonb
            WHERE id = $1
        """, pipeline_id)
        
        print(f"✅ Reset pipeline to running state")
        
        # Verify the update
        pipeline = await conn.fetchrow("""
            SELECT status, errors
            FROM pipeline_executions
            WHERE id = $1
        """, pipeline_id)
        
        print(f"\nUpdated pipeline status: {pipeline['status']}")
        print(f"Errors cleared: {json.loads(pipeline['errors'])}")

asyncio.run(reset())
