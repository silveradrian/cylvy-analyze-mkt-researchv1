import asyncio
from app.core.database import db_pool
import uuid

async def check():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Check all phase statuses
        phases = await conn.fetch("""
            SELECT phase_name, status, started_at, completed_at
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            ORDER BY created_at
        """, pipeline_id)
        
        print("Pipeline phase statuses:")
        for phase in phases:
            print(f"  {phase['phase_name']}: {phase['status']}")
            if phase['started_at']:
                print(f"    Started: {phase['started_at']}")
            if phase['completed_at']:
                print(f"    Completed: {phase['completed_at']}")

asyncio.run(check())
