"""
Pipeline State Tracking Service
Provides granular tracking and resume capabilities for pipeline execution
"""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID
from enum import Enum
import asyncpg
from loguru import logger

from app.core.database import DatabasePool
from app.core.robustness_logging import get_logger, log_performance


class StateStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    QUEUED = "queued"


class StateTracker:
    """
    Tracks pipeline execution state at a granular level
    Enables resume from any point and provides detailed progress tracking
    """
    
    def __init__(self, db_pool: DatabasePool):
        self.db_pool = db_pool
        self.logger = get_logger("state_tracker")
        
    @log_performance("state_tracker", "initialize_pipeline")
    async def initialize_pipeline(
        self,
        pipeline_execution_id: UUID,
        phases: List[str],
        items: List[Dict[str, Any]]
    ) -> int:
        """
        Initialize state tracking for a pipeline execution
        
        Args:
            pipeline_execution_id: Pipeline execution ID
            phases: List of pipeline phases
            items: List of items to process (keywords, domains, etc.)
            
        Returns:
            Number of states created
        """
        states_created = 0

        async with self.db_pool.acquire() as conn:
            # Load existing (phase, item_identifier) pairs to ensure idempotency without relying on DB constraints
            existing_pairs_rows = await conn.fetch(
                """
                SELECT phase, item_identifier
                FROM pipeline_state
                WHERE pipeline_execution_id = $1
                """,
                pipeline_execution_id
            )
            existing_pairs = {(r['phase'], r['item_identifier']) for r in existing_pairs_rows}

            # Prepare deduplicated state records
            records = []
            for phase in phases:
                for item in items:
                    item_id = self._generate_item_identifier(phase, item)
                    key = (phase, item_id)
                    if key in existing_pairs:
                        continue
                    records.append((
                        pipeline_execution_id,
                        phase,
                        item.get('type', 'unknown'),
                        item_id,
                        StateStatus.PENDING,
                        json.dumps(item.get('metadata', {}))
                    ))

            # Bulk insert only new records
            if records:
                await conn.copy_records_to_table(
                    'pipeline_state',
                    records=records,
                    columns=['pipeline_execution_id', 'phase', 'item_type', 
                            'item_identifier', 'status', 'progress_data']
                )
                states_created = len(records)
                
        self.logger.info(
            f"Initialized pipeline state tracking",
            pipeline_execution_id=str(pipeline_execution_id),
            phases=phases,
            items_count=len(items),
            states_created=states_created
        )
        
        return states_created
    
    def _generate_item_identifier(self, phase: str, item: Dict[str, Any]) -> str:
        """Generate unique identifier for an item"""
        if phase in ['keyword_metrics', 'serp_collection']:
            # For keyword-based phases
            return f"{item['keyword']}:{item.get('region', 'global')}:{item.get('type', 'web')}"
        elif phase in ['company_enrichment']:
            # For domain-based phases
            return item['domain']
        elif phase in ['content_scraping', 'content_analysis']:
            # For URL-based phases
            return item['url']
        elif phase in ['video_enrichment', 'youtube_enrichment']:
            # For video-based phases
            return item.get('url', item.get('video_id', str(hash(json.dumps(item, sort_keys=True)))))
        else:
            # Generic fallback
            return json.dumps(item, sort_keys=True)
    
    @log_performance("state_tracker", "get_pending_items")
    async def get_pending_items(
        self,
        pipeline_execution_id: UUID,
        phase: str,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get pending items for a phase"""
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    id,
                    item_type,
                    item_identifier,
                    progress_data,
                    attempt_count
                FROM pipeline_state
                WHERE pipeline_execution_id = $1
                AND phase = $2
                AND status = 'pending'
                ORDER BY attempt_count ASC, created_at ASC
                LIMIT $3
                """,
                pipeline_execution_id,
                phase,
                limit
            )
            
            items = []
            for row in rows:
                item_data = json.loads(row['progress_data'] or '{}')
                item_data.update({
                    'state_id': row['id'],
                    'item_type': row['item_type'],
                    'item_identifier': row['item_identifier'],
                    'attempt_count': row['attempt_count']
                })
                items.append(item_data)
                
        self.logger.debug(
            f"Retrieved pending items",
            pipeline_execution_id=str(pipeline_execution_id),
            phase=phase,
            count=len(items)
        )
        
        return items
    
    @log_performance("state_tracker", "update_state")
    async def update_state(
        self,
        state_id: UUID,
        status: StateStatus,
        progress_data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        error_category: Optional[str] = None
    ):
        """Update state for an item"""
        async with self.db_pool.acquire() as conn:
            query_parts = [
                "UPDATE pipeline_state SET",
                f"status = $2",
                f"updated_at = NOW()"
            ]
            params = [state_id, status]
            param_count = 3
            
            if status == StateStatus.PROCESSING:
                query_parts.append(f"last_attempt_at = NOW()")
                query_parts.append(f"attempt_count = attempt_count + 1")
            elif status == StateStatus.COMPLETED:
                query_parts.append(f"completed_at = NOW()")
            
            if progress_data:
                query_parts.append(f"progress_data = ${param_count}")
                params.append(json.dumps(progress_data))
                param_count += 1
                
            if error:
                query_parts.append(f"last_error = ${param_count}")
                params.append(error[:1000])  # Truncate
                param_count += 1
                
            if error_category:
                query_parts.append(f"error_category = ${param_count}")
                params.append(error_category)
                param_count += 1
            
            query_parts.append("WHERE id = $1")
            query = ", ".join(query_parts[:-1]) + " " + query_parts[-1]
            
            await conn.execute(query, *params)
            
        self.logger.state_transition(
            entity=f"state_{state_id}",
            from_state="unknown",
            to_state=status,
            reason=error
        )
    
    async def bulk_update_states(
        self,
        updates: List[Tuple[UUID, StateStatus, Optional[Dict[str, Any]]]]
    ):
        """Update multiple states efficiently"""
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                for state_id, status, progress_data in updates:
                    await self.update_state(state_id, status, progress_data)
                    
    @log_performance("state_tracker", "get_phase_progress")
    async def get_phase_progress(
        self,
        pipeline_execution_id: UUID,
        phase: str
    ) -> Dict[str, Any]:
        """Get progress statistics for a phase"""
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    COUNT(*) FILTER (WHERE status = 'skipped') as skipped,
                    AVG(attempt_count) as avg_attempts,
                    MAX(attempt_count) as max_attempts
                FROM pipeline_state
                WHERE pipeline_execution_id = $1
                AND phase = $2
                """,
                pipeline_execution_id,
                phase
            )
            
            progress = dict(stats) if stats else {}
            progress['completion_percentage'] = (
                (progress.get('completed', 0) / progress.get('total', 1)) * 100
                if progress.get('total', 0) > 0 else 0
            )
            
        self.logger.debug(
            f"Phase progress",
            pipeline_execution_id=str(pipeline_execution_id),
            phase=phase,
            **progress
        )
        
        return progress
    
    @log_performance("state_tracker", "get_pipeline_progress")
    async def get_pipeline_progress(
        self,
        pipeline_execution_id: UUID
    ) -> Dict[str, Any]:
        """Get overall pipeline progress"""
        async with self.db_pool.acquire() as conn:
            # Overall stats
            overall_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(DISTINCT phase) as total_phases,
                    COUNT(*) as total_items,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_items,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_items,
                    COUNT(DISTINCT phase) FILTER (
                        WHERE phase IN (
                            SELECT DISTINCT phase 
                            FROM pipeline_state 
                            WHERE pipeline_execution_id = $1 
                            AND status != 'completed'
                        )
                    ) as incomplete_phases
                FROM pipeline_state
                WHERE pipeline_execution_id = $1
                """,
                pipeline_execution_id
            )
            
            # Phase breakdown
            phase_stats = await conn.fetch(
                """
                SELECT 
                    phase,
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed
                FROM pipeline_state
                WHERE pipeline_execution_id = $1
                GROUP BY phase
                ORDER BY 
                    CASE phase
                        WHEN 'keyword_metrics' THEN 1
                        WHEN 'serp_collection' THEN 2
                        WHEN 'company_enrichment' THEN 3
                        WHEN 'video_enrichment' THEN 4
                        WHEN 'content_scraping' THEN 5
                        WHEN 'content_analysis' THEN 6
                        WHEN 'dsi_calculation' THEN 7
                        WHEN 'historical_snapshot' THEN 8
                        WHEN 'landscape_dsi' THEN 9
                        ELSE 10
                    END
                """,
                pipeline_execution_id
            )
            
            progress = dict(overall_stats) if overall_stats else {}
            progress['phases'] = [dict(row) for row in phase_stats]
            progress['overall_completion_percentage'] = (
                (progress.get('completed_items', 0) / progress.get('total_items', 1)) * 100
                if progress.get('total_items', 0) > 0 else 0
            )
            
        return progress
    
    async def create_checkpoint(
        self,
        pipeline_execution_id: UUID,
        phase: str,
        checkpoint_name: str,
        state_data: Dict[str, Any]
    ):
        """Create a checkpoint for resume capability"""
        async with self.db_pool.acquire() as conn:
            # Get current progress
            progress = await self.get_phase_progress(pipeline_execution_id, phase)
            
            await conn.execute(
                """
                INSERT INTO pipeline_checkpoints (
                    pipeline_execution_id,
                    phase,
                    checkpoint_name,
                    state_data,
                    items_processed,
                    items_total
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (pipeline_execution_id, phase, checkpoint_name)
                DO UPDATE SET 
                    state_data = $4,
                    items_processed = $5,
                    items_total = $6,
                    created_at = NOW()
                """,
                pipeline_execution_id,
                phase,
                checkpoint_name,
                json.dumps(state_data),
                progress.get('completed', 0),
                progress.get('total', 0)
            )
            
        self.logger.info(
            f"Created checkpoint",
            pipeline_execution_id=str(pipeline_execution_id),
            phase=phase,
            checkpoint_name=checkpoint_name
        )
    
    async def get_checkpoint(
        self,
        pipeline_execution_id: UUID,
        phase: str,
        checkpoint_name: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a checkpoint"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM pipeline_checkpoints
                WHERE pipeline_execution_id = $1
                AND phase = $2
                AND checkpoint_name = $3
                """,
                pipeline_execution_id,
                phase,
                checkpoint_name
            )
            
            if row:
                return {
                    'state_data': json.loads(row['state_data']),
                    'items_processed': row['items_processed'],
                    'items_total': row['items_total'],
                    'created_at': row['created_at']
                }
        return None
    
    async def get_failed_items(
        self,
        pipeline_execution_id: UUID,
        phase: Optional[str] = None,
        error_category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get failed items for analysis or retry"""
        query = """
            SELECT 
                id,
                phase,
                item_type,
                item_identifier,
                attempt_count,
                last_error,
                error_category,
                progress_data
            FROM pipeline_state
            WHERE pipeline_execution_id = $1
            AND status = 'failed'
        """
        params = [pipeline_execution_id]
        param_count = 2
        
        if phase:
            query += f" AND phase = ${param_count}"
            params.append(phase)
            param_count += 1
            
        if error_category:
            query += f" AND error_category = ${param_count}"
            params.append(error_category)
            
        query += " ORDER BY last_attempt_at DESC"
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, *params)
            
        return [dict(row) for row in rows]
    
    async def reset_failed_items(
        self,
        pipeline_execution_id: UUID,
        phase: Optional[str] = None,
        max_items: Optional[int] = None
    ) -> int:
        """Reset failed items to pending for retry"""
        query = """
            UPDATE pipeline_state
            SET 
                status = 'pending',
                last_error = NULL,
                error_category = NULL,
                attempt_count = 0
            WHERE pipeline_execution_id = $1
            AND status = 'failed'
        """
        params = [pipeline_execution_id]
        
        if phase:
            query += " AND phase = $2"
            params.append(phase)
            
        if max_items:
            query += f" AND id IN (SELECT id FROM pipeline_state WHERE pipeline_execution_id = $1 AND status = 'failed' LIMIT {max_items})"
            
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(query, *params)
            count = int(result.split()[-1])
            
        self.logger.info(
            f"Reset failed items",
            pipeline_execution_id=str(pipeline_execution_id),
            phase=phase,
            count=count
        )
        
        return count
