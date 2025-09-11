"""
Persistent Job Queue Management
Provides reliable background job processing with retry capabilities
"""

import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Callable, TypeVar, Generic
from uuid import UUID, uuid4
from enum import Enum
import asyncpg
from loguru import logger
from pydantic import BaseModel

from app.core.database import DatabasePool


T = TypeVar('T', bound=BaseModel)


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


class JobPriority:
    """Standard job priority levels"""
    CRITICAL = 1000
    HIGH = 100
    NORMAL = 0
    LOW = -100
    

class Job(BaseModel):
    """Job representation"""
    id: UUID
    queue_name: str
    job_type: str
    payload: Dict[str, Any]
    priority: int = JobPriority.NORMAL
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    scheduled_for: datetime
    locked_at: Optional[datetime] = None
    locked_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    last_error: Optional[str] = None
    error_count: int = 0
    dead_letter: bool = False
    metadata: Dict[str, Any] = {}
    

class JobQueue:
    """
    Persistent job queue with retry capabilities
    
    Features:
    - Persistent storage in database
    - Priority-based processing
    - Automatic retry with exponential backoff
    - Dead letter queue for failed jobs
    - Worker locking to prevent duplicate processing
    """
    
    def __init__(
        self,
        queue_name: str,
        db_pool: DatabasePool,
        worker_id: Optional[str] = None,
        lock_timeout_seconds: int = 300,
        visibility_timeout_seconds: int = 300
    ):
        self.queue_name = queue_name
        self.db_pool = db_pool
        self.worker_id = worker_id or f"worker-{uuid4()}"
        self.lock_timeout_seconds = lock_timeout_seconds
        self.visibility_timeout_seconds = visibility_timeout_seconds
        self._handlers: Dict[str, Callable] = {}
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        
    def register_handler(self, job_type: str, handler: Callable[[Dict[str, Any]], Any]):
        """Register a handler for a specific job type"""
        self._handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")
        
    async def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        priority: int = JobPriority.NORMAL,
        delay_seconds: int = 0,
        max_attempts: int = 3,
        metadata: Optional[Dict[str, Any]] = None
    ) -> UUID:
        """
        Add a job to the queue
        
        Args:
            job_type: Type of job to process
            payload: Job data
            priority: Job priority (higher = processed first)
            delay_seconds: Delay before job becomes available
            max_attempts: Maximum retry attempts
            metadata: Additional job metadata
            
        Returns:
            Job ID
        """
        job_id = uuid4()
        scheduled_for = datetime.utcnow() + timedelta(seconds=delay_seconds)
        
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO job_queue (
                    id, queue_name, job_type, payload, priority,
                    scheduled_for, max_attempts, metadata
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                job_id,
                self.queue_name,
                job_type,
                json.dumps(payload),
                priority,
                scheduled_for,
                max_attempts,
                json.dumps(metadata or {})
            )
            
        logger.info(f"Enqueued job {job_id} of type {job_type} to {self.queue_name}")
        return job_id
        
    async def bulk_enqueue(
        self,
        jobs: List[Dict[str, Any]],
        priority: int = JobPriority.NORMAL,
        max_attempts: int = 3
    ) -> List[UUID]:
        """Enqueue multiple jobs efficiently"""
        job_ids = []
        scheduled_for = datetime.utcnow()
        
        async with self.db_pool.acquire() as conn:
            # Use COPY for efficient bulk insert
            records = []
            for job in jobs:
                job_id = uuid4()
                job_ids.append(job_id)
                records.append((
                    job_id,
                    self.queue_name,
                    job['job_type'],
                    json.dumps(job['payload']),
                    priority,
                    scheduled_for,
                    max_attempts,
                    json.dumps(job.get('metadata', {}))
                ))
                
            await conn.copy_records_to_table(
                'job_queue',
                records=records,
                columns=['id', 'queue_name', 'job_type', 'payload', 'priority',
                        'scheduled_for', 'max_attempts', 'metadata']
            )
            
        logger.info(f"Bulk enqueued {len(jobs)} jobs to {self.queue_name}")
        return job_ids
        
    async def _acquire_job(self, conn: asyncpg.Connection) -> Optional[Job]:
        """Acquire next available job from queue"""
        # Release expired locks
        await conn.execute(
            """
            UPDATE job_queue 
            SET locked_at = NULL, locked_by = NULL
            WHERE queue_name = $1
            AND locked_at < $2
            AND status = 'processing'
            """,
            self.queue_name,
            datetime.utcnow() - timedelta(seconds=self.lock_timeout_seconds)
        )
        
        # Acquire next job
        row = await conn.fetchrow(
            """
            UPDATE job_queue
            SET 
                locked_at = NOW(),
                locked_by = $2,
                status = 'processing',
                started_at = COALESCE(started_at, NOW()),
                attempts = attempts + 1
            WHERE id = (
                SELECT id FROM job_queue
                WHERE queue_name = $1
                AND status = 'pending'
                AND NOT dead_letter
                AND scheduled_for <= NOW()
                AND (locked_at IS NULL OR locked_at < $3)
                ORDER BY priority DESC, scheduled_for ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
            """,
            self.queue_name,
            self.worker_id,
            datetime.utcnow() - timedelta(seconds=self.lock_timeout_seconds)
        )
        
        if row:
            job_data = dict(row)
            job_data['payload'] = json.loads(job_data['payload'])
            job_data['metadata'] = json.loads(job_data['metadata'])
            return Job(**job_data)
        return None
        
    async def _complete_job(self, job_id: UUID):
        """Mark job as completed"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE job_queue
                SET 
                    status = 'completed',
                    completed_at = NOW(),
                    locked_at = NULL,
                    locked_by = NULL
                WHERE id = $1
                """,
                job_id
            )
            
    async def _fail_job(self, job_id: UUID, error: str, max_attempts: int):
        """Mark job as failed and schedule retry if applicable"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE job_queue
                SET 
                    status = CASE 
                        WHEN attempts >= $3 THEN 'failed'
                        ELSE 'pending'
                    END,
                    failed_at = CASE
                        WHEN attempts >= $3 THEN NOW()
                        ELSE NULL
                    END,
                    dead_letter = CASE
                        WHEN attempts >= $3 THEN TRUE
                        ELSE FALSE
                    END,
                    last_error = $2,
                    error_count = error_count + 1,
                    locked_at = NULL,
                    locked_by = NULL,
                    scheduled_for = CASE
                        WHEN attempts < $3 THEN NOW() + INTERVAL '1 second' * POWER(2, attempts)
                        ELSE scheduled_for
                    END
                WHERE id = $1
                RETURNING status, attempts, scheduled_for
                """,
                job_id,
                error[:1000],  # Truncate error message
                max_attempts
            )
            
            if row:
                if row['status'] == 'failed':
                    logger.error(f"Job {job_id} failed after {row['attempts']} attempts")
                else:
                    logger.warning(f"Job {job_id} failed, retry scheduled for {row['scheduled_for']}")
                    
    async def _process_job(self, job: Job) -> bool:
        """Process a single job"""
        handler = self._handlers.get(job.job_type)
        if not handler:
            logger.error(f"No handler registered for job type: {job.job_type}")
            await self._fail_job(job.id, f"No handler for job type: {job.job_type}", job.max_attempts)
            return False
            
        try:
            logger.info(f"Processing job {job.id} of type {job.job_type}")
            
            # Execute handler
            if asyncio.iscoroutinefunction(handler):
                result = await handler(job.payload)
            else:
                result = handler(job.payload)
                
            # Mark as completed
            await self._complete_job(job.id)
            logger.info(f"Job {job.id} completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Job {job.id} failed: {str(e)}")
            await self._fail_job(job.id, str(e), job.max_attempts)
            return False
            
    async def process_jobs(self, batch_size: int = 10):
        """Process jobs in batches"""
        self._running = True
        logger.info(f"Starting job processor for queue {self.queue_name}")
        
        while self._running:
            try:
                jobs_processed = 0
                
                # Process batch
                async with self.db_pool.acquire() as conn:
                    for _ in range(batch_size):
                        job = await self._acquire_job(conn)
                        if not job:
                            break
                            
                        await self._process_job(job)
                        jobs_processed += 1
                        
                # If no jobs processed, wait before checking again
                if jobs_processed == 0:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                logger.error(f"Error in job processor: {e}")
                await asyncio.sleep(5)
                
    async def start(self, batch_size: int = 10):
        """Start background job processing"""
        if self._processing_task:
            logger.warning(f"Job processor already running for {self.queue_name}")
            return
            
        self._processing_task = asyncio.create_task(self.process_jobs(batch_size))
        logger.info(f"Started job processor for {self.queue_name}")
        
    async def stop(self):
        """Stop job processing"""
        self._running = False
        if self._processing_task:
            await self._processing_task
            self._processing_task = None
        logger.info(f"Stopped job processor for {self.queue_name}")
        
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics"""
        async with self.db_pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'pending') as pending_count,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing_count,
                    COUNT(*) FILTER (WHERE status = 'completed') as completed_count,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed_count,
                    COUNT(*) FILTER (WHERE dead_letter = TRUE) as dead_letter_count,
                    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) 
                        FILTER (WHERE completed_at IS NOT NULL) as avg_processing_time_seconds
                FROM job_queue
                WHERE queue_name = $1
                """,
                self.queue_name
            )
            
            return dict(stats)
            
    async def retry_dead_letter_jobs(self, job_ids: Optional[List[UUID]] = None):
        """Retry jobs from dead letter queue"""
        async with self.db_pool.acquire() as conn:
            query = """
                UPDATE job_queue
                SET 
                    status = 'pending',
                    dead_letter = FALSE,
                    attempts = 0,
                    scheduled_for = NOW(),
                    last_error = NULL,
                    error_count = 0
                WHERE queue_name = $1
                AND dead_letter = TRUE
            """
            params = [self.queue_name]
            
            if job_ids:
                query += " AND id = ANY($2)"
                params.append(job_ids)
                
            result = await conn.execute(query, *params)
            count = int(result.split()[-1])
            logger.info(f"Retrying {count} dead letter jobs in {self.queue_name}")
            return count


class JobQueueManager:
    """Manages multiple job queues"""
    
    def __init__(self, db_pool: DatabasePool, worker_id: Optional[str] = None):
        self.db_pool = db_pool
        self.worker_id = worker_id or f"worker-{uuid4()}"
        self._queues: Dict[str, JobQueue] = {}
        
    def get_queue(self, queue_name: str) -> JobQueue:
        """Get or create a job queue"""
        if queue_name not in self._queues:
            self._queues[queue_name] = JobQueue(
                queue_name=queue_name,
                db_pool=self.db_pool,
                worker_id=self.worker_id
            )
        return self._queues[queue_name]
        
    async def start_all(self, batch_size: int = 10):
        """Start all job queues"""
        for queue in self._queues.values():
            await queue.start(batch_size)
            
    async def stop_all(self):
        """Stop all job queues"""
        for queue in self._queues.values():
            await queue.stop()
            
    async def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all queues"""
        stats = {}
        for name, queue in self._queues.items():
            stats[name] = await queue.get_queue_stats()
        return stats
