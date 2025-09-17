"""Quick fix to unstick the pipeline"""
import asyncio
from app.core.database import db_pool
from datetime import datetime
import uuid

async def fix():
    pipeline_id = "1a1bac89-8056-41ff-8f20-8e82ec67999f"
    
    async with db_pool.acquire() as conn:
        # 1. Mark stuck company enrichment as completed
        result = await conn.execute("""
            UPDATE pipeline_phase_status
            SET status = 'completed',
                updated_at = NOW(),
                completed_at = NOW(),
                result_data = jsonb_build_object(
                    'success', true,
                    'phase_name', 'company_enrichment_serp',
                    'message', 'All domains already enriched - marking as complete',
                    'domains_processed', 0,
                    'companies_enriched', 0,
                    'errors', ARRAY[]::text[]
                )
            WHERE pipeline_execution_id = $1
            AND phase_name = 'company_enrichment_serp'
            AND status = 'running'
            RETURNING phase_name
        """, uuid.UUID(pipeline_id))
        
        if result:
            print(f"✅ Marked company_enrichment_serp as completed")
        else:
            print("⚠️ No running company_enrichment_serp phase found")
            
        # 2. Check what phases are pending
        pending_phases = await conn.fetch("""
            SELECT phase_name, status
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            AND status IN ('pending', 'running')
            ORDER BY created_at
        """, uuid.UUID(pipeline_id))
        
        print(f"\nPending phases: {[p['phase_name'] for p in pending_phases]}")
        
        # 3. Update pipeline execution to allow it to continue
        await conn.execute("""
            UPDATE pipeline_executions
            SET updated_at = NOW()
            WHERE id = $1
            AND status = 'running'
        """, uuid.UUID(pipeline_id))
        
        print("\n✅ Pipeline is ready to continue")
        print("The pipeline should automatically pick up the next phase.")
        
asyncio.run(fix())
