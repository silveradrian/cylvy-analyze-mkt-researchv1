import asyncio
from app.core.database import db_pool
import uuid

async def fix():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Fix the inconsistent phase status
        result = await conn.execute("""
            UPDATE pipeline_phase_status
            SET status = 'completed'
            WHERE pipeline_execution_id = $1
            AND phase_name = 'company_enrichment_serp'
            AND completed_at IS NOT NULL
            RETURNING phase_name
        """, pipeline_id)
        
        print(f"✅ Fixed company_enrichment_serp phase status")
        
        # Verify the fix
        phases = await conn.fetch("""
            SELECT phase_name, status
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            ORDER BY created_at
        """, pipeline_id)
        
        print("\nUpdated phase statuses:")
        for phase in phases:
            print(f"  {phase['phase_name']}: {phase['status']}")

asyncio.run(fix())
