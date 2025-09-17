import asyncio
import httpx

async def force_restart():
    pipeline_id = "1a1bac89-8056-41ff-8f20-8e82ec67999f"
    
    async with httpx.AsyncClient() as client:
        # Update pipeline status to allow restart
        try:
            # First, let's mark the running phase as failed to force a restart
            from app.core.database import db_pool
            async with db_pool.acquire() as conn:
                # Mark the stuck phase as failed
                await conn.execute("""
                    UPDATE pipeline_phase_status 
                    SET status = 'failed', 
                        error_message = 'Container restart interrupted phase',
                        updated_at = NOW()
                    WHERE pipeline_execution_id = $1 
                    AND phase_name = 'company_enrichment_serp' 
                    AND status = 'running'
                """, pipeline_id)
                
                # Mark pipeline as failed to allow resume
                await conn.execute("""
                    UPDATE pipeline_executions
                    SET status = 'failed',
                        updated_at = NOW()
                    WHERE id = $1
                    AND status = 'running'
                """, pipeline_id)
                
                print("Pipeline status updated to allow restart")
        except Exception as e:
            print(f"Error updating pipeline status: {e}")
            
        # Now resume the pipeline
        try:
            resume_resp = await client.post(f"http://localhost:8000/api/v1/pipeline/{pipeline_id}/resume", json={})
            if resume_resp.status_code == 200:
                print("Pipeline resumed successfully!")
            else:
                print(f"Failed to resume: {resume_resp.status_code} - {resume_resp.text}")
        except Exception as e:
            print(f"Error resuming pipeline: {e}")

if __name__ == "__main__":
    import sys
    import os
    sys.path.append('/app')
    asyncio.run(force_restart())
