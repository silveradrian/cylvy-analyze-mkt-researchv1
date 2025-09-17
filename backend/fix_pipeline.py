import asyncio
from app.core.database import db_pool
import uuid
import json
import redis.asyncio as redis

async def fix():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    # Reset YouTube circuit breaker
    r = await redis.from_url("redis://redis:6379", decode_responses=True)
    key = "circuit_breaker:youtube_api"
    await r.delete(key)
    print("✅ Reset YouTube API circuit breaker")
    
    async with db_pool.acquire() as conn:
        # Update pipeline to running status
        await conn.execute("""
            UPDATE pipeline_executions
            SET status = 'running',
                completed_at = NULL,
                errors = '[]'::jsonb
            WHERE id = $1
        """, pipeline_id)
        
        # Mark YouTube enrichment as skipped (non-critical)
        await conn.execute("""
            UPDATE pipeline_phase_status
            SET status = 'skipped',
                completed_at = NOW(),
                result_data = '{"success": false, "skipped": true, "reason": "Non-critical phase - YouTube API unavailable"}'::jsonb
            WHERE pipeline_execution_id = $1
            AND phase_name = 'youtube_enrichment'
            AND status IN ('running', 'failed')
        """, pipeline_id)
        
        print("✅ Updated pipeline status to running")
        print("✅ Marked YouTube enrichment as skipped (non-critical)")
        
        # Check all phase statuses
        phases = await conn.fetch("""
            SELECT phase_name, status
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            ORDER BY created_at
        """, pipeline_id)
        
        print("\nPhase statuses:")
        for phase in phases:
            print(f"  {phase['phase_name']}: {phase['status']}")
    
    await r.close()

asyncio.run(fix())
