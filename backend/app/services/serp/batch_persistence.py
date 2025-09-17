"""
SERP Batch Persistence Service
Stores batch details for recovery after restarts
"""

import json
from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime
from loguru import logger

from app.core.database import db_pool


class BatchPersistenceService:
    """
    Persists SERP batch details to enable recovery after backend restarts
    """
    
    @staticmethod
    async def store_batch_details(
        pipeline_id: UUID,
        batch_id: str,
        content_type: str,
        batch_requests: List[Dict[str, Any]],
        batch_config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Store batch details for later recovery"""
        try:
            async with db_pool.acquire() as conn:
                # Store in serp_batch_coordinator_runs with extended metadata
                await conn.execute("""
                    UPDATE serp_batch_coordinator_runs
                    SET 
                        batch_requests = $4::jsonb,
                        batch_config = $5::jsonb,
                        updated_at = NOW()
                    WHERE pipeline_execution_id = $1
                    AND batch_id = $2
                    AND content_type = $3
                """, 
                pipeline_id, 
                batch_id, 
                content_type,
                json.dumps(batch_requests),
                json.dumps(batch_config or {})
                )
                
                logger.info(f"Stored batch details for {batch_id} ({content_type})")
                return True
                
        except Exception as e:
            logger.error(f"Failed to store batch details: {e}")
            return False
    
    @staticmethod
    async def retrieve_batch_details(
        pipeline_id: UUID,
        batch_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve batch details for recovery"""
        try:
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT 
                        batch_id,
                        content_type,
                        status,
                        batch_size,
                        batch_requests,
                        batch_config,
                        created_at,
                        updated_at
                    FROM serp_batch_coordinator_runs
                    WHERE pipeline_execution_id = $1
                    AND batch_id = $2
                """, pipeline_id, batch_id)
                
                if row:
                    return {
                        'batch_id': row['batch_id'],
                        'content_type': row['content_type'],
                        'status': row['status'],
                        'batch_size': row['batch_size'],
                        'batch_requests': row['batch_requests'] or [],
                        'batch_config': row['batch_config'] or {},
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at']
                    }
                    
        except Exception as e:
            logger.error(f"Failed to retrieve batch details: {e}")
            
        return None
    
    @staticmethod
    async def get_incomplete_batches(pipeline_id: UUID) -> List[Dict[str, Any]]:
        """Get all incomplete batches for a pipeline"""
        try:
            async with db_pool.acquire() as conn:
                rows = await conn.fetch("""
                    SELECT 
                        batch_id,
                        content_type,
                        status,
                        batch_size,
                        batch_requests,
                        batch_config,
                        created_at
                    FROM serp_batch_coordinator_runs
                    WHERE pipeline_execution_id = $1
                    AND status IN ('created', 'running')
                    AND created_at > NOW() - INTERVAL '24 hours'
                    ORDER BY created_at
                """, pipeline_id)
                
                return [dict(row) for row in rows]
                
        except Exception as e:
            logger.error(f"Failed to get incomplete batches: {e}")
            return []
