import asyncio
from app.core.database import db_pool

async def check_pipeline():
    async with db_pool.acquire() as conn:
        # Check pipeline execution status
        pipeline = await conn.fetchrow("""
            SELECT id, status, error_message, created_at, updated_at 
            FROM pipeline_executions 
            WHERE id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        """)
        
        if pipeline:
            print(f"Pipeline ID: {pipeline['id']}")
            print(f"Status: {pipeline['status']}")
            print(f"Error: {pipeline['error_message']}")
            print(f"Created: {pipeline['created_at']}")
            print(f"Updated: {pipeline['updated_at']}")
        else:
            print("Pipeline not found")
            
        # Check phase status
        phases = await conn.fetch("""
            SELECT phase_name, status, error_message, attempt_count, created_at, updated_at
            FROM pipeline_phase_status 
            WHERE pipeline_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f' 
            ORDER BY created_at
        """)
        
        print("\nPhase Status:")
        for phase in phases:
            print(f"\n  Phase: {phase['phase_name']}")
            print(f"    Status: {phase['status']}")
            print(f"    Attempts: {phase['attempt_count']}")
            print(f"    Updated: {phase['updated_at']}")
            if phase['error_message']:
                print(f"    Error: {phase['error_message']}")

if __name__ == "__main__":
    asyncio.run(check_pipeline())
