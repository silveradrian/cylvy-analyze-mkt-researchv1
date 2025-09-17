"""
Pipeline Scheduling Service
Handles automated pipeline execution based on configured schedules
"""

import asyncio
from datetime import datetime, timedelta, time
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from enum import Enum
import json
import cron_descriptor

from loguru import logger
from pydantic import BaseModel
from croniter import croniter

from app.core.database import db_pool
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig, PipelineMode


class ScheduleFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly" 
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    CUSTOM_CRON = "custom_cron"


class ContentTypeSchedule(BaseModel):
    """Schedule configuration for a content type"""
    content_type: str  # organic, news, video
    enabled: bool = True
    frequency: ScheduleFrequency
    
    # Time settings
    time_of_day: time = time(2, 0)  # 2 AM default
    timezone: str = "UTC"
    
    # Weekly settings
    days_of_week: Optional[List[int]] = None  # 1=Monday, 7=Sunday
    
    # Monthly settings
    day_of_month: Optional[int] = None  # 1-31, or -1 for last day
    
    # Custom cron
    cron_expression: Optional[str] = None
    
    # Execution settings
    max_retries: int = 3
    retry_delay_minutes: int = 30
    timeout_hours: int = 6


class PipelineSchedule(BaseModel):
    """Pipeline schedule configuration"""
    id: Optional[UUID] = None
    name: str
    description: Optional[str] = None
    
    # Schedule status
    is_active: bool = True
    
    # Content type schedules
    content_schedules: List[ContentTypeSchedule] = []
    
    # Pipeline configuration
    keywords: Optional[List[str]] = None  # If None, uses all keywords
    regions: List[str] = ["US", "UK"]
    
    # Execution settings
    max_concurrent_executions: int = 1
    
    # Notifications
    notification_emails: Optional[List[str]] = None
    notify_on_completion: bool = True
    notify_on_error: bool = True
    
    # Metadata
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_executed_at: Optional[datetime] = None
    next_execution_at: Optional[datetime] = None


class ScheduleExecution(BaseModel):
    """Schedule execution record"""
    id: UUID
    schedule_id: UUID
    pipeline_id: Optional[UUID] = None
    
    # Execution details
    content_types: List[str]
    scheduled_for: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Status
    status: str = "pending"  # pending, running, completed, failed, cancelled
    error_message: Optional[str] = None
    retry_count: int = 0
    
    # Results
    results_summary: Optional[Dict[str, Any]] = None


class SchedulingService:
    """Service for managing pipeline schedules and execution"""
    
    def __init__(self, settings, db, pipeline_service: PipelineService):
        self.settings = settings
        self.db = db
        self.pipeline_service = pipeline_service
        
        # Scheduler state
        self._scheduler_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        self._active_executions: Dict[UUID, ScheduleExecution] = {}
    
    async def create_schedule(self, schedule: PipelineSchedule) -> UUID:
        """Create a new pipeline schedule"""
        if not schedule.id:
            schedule.id = uuid4()
        
        schedule.created_at = datetime.utcnow()
        schedule.updated_at = datetime.utcnow()
        
        # Calculate next execution
        schedule.next_execution_at = await self._calculate_next_execution(schedule)
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO pipeline_schedules (
                    id, name, description, is_active, content_schedules,
                    custom_keywords, regions, max_concurrent_executions,
                    notification_emails, notify_on_completion, notify_on_error,
                    created_at, updated_at, next_execution_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """,
                schedule.id,
                schedule.name,
                schedule.description,
                schedule.is_active,
                json.dumps([self._content_schedule_to_dict(cs) for cs in schedule.content_schedules]),
                json.dumps(schedule.keywords) if schedule.keywords else None,
                schedule.regions,  # Pass as array, not JSON string
                schedule.max_concurrent_executions,
                schedule.notification_emails,  # Pass as array, not JSON string
                schedule.notify_on_completion,
                schedule.notify_on_error,
                schedule.created_at,
                schedule.updated_at,
                schedule.next_execution_at
            )
        
        logger.info(f"Created pipeline schedule: {schedule.name} ({schedule.id})")
        return schedule.id
    
    async def update_schedule(self, schedule_id: UUID, updates: Dict[str, Any]) -> PipelineSchedule:
        """Update an existing schedule"""
        # Get current schedule
        current = await self.get_schedule(schedule_id)
        if not current:
            raise ValueError(f"Schedule {schedule_id} not found")
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(current, key):
                # Special handling for content_schedules
                if key == 'content_schedules' and isinstance(value, list):
                    # Convert dicts to ContentTypeSchedule objects
                    value = [ContentTypeSchedule(**cs) if isinstance(cs, dict) else cs for cs in value]
                setattr(current, key, value)
        
        current.updated_at = datetime.utcnow()
        
        # Recalculate next execution if schedule changed
        if any(key in ['content_schedules', 'is_active'] for key in updates.keys()):
            current.next_execution_at = await self._calculate_next_execution(current)
        
        # Save to database
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_schedules SET
                    name = $2, description = $3, is_active = $4,
                    content_schedules = $5, custom_keywords = $6, regions = $7,
                    max_concurrent_executions = $8, notification_emails = $9,
                    notify_on_completion = $10, notify_on_error = $11,
                    updated_at = $12, next_execution_at = $13
                WHERE id = $1
                """,
                schedule_id,
                current.name,
                current.description,
                current.is_active,
                json.dumps([self._content_schedule_to_dict(cs) for cs in current.content_schedules]),
                json.dumps(current.keywords) if current.keywords else None,
                current.regions,  # Pass as array, not JSON string
                current.max_concurrent_executions,
                current.notification_emails,  # Pass as array, not JSON string
                current.notify_on_completion,
                current.notify_on_error,
                current.updated_at,
                current.next_execution_at
            )
        
        logger.info(f"Updated pipeline schedule: {current.name} ({schedule_id})")
        return current
    
    async def get_schedule(self, schedule_id: UUID) -> Optional[PipelineSchedule]:
        """Get a schedule by ID"""
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pipeline_schedules WHERE id = $1",
                schedule_id
            )
            
            if not row:
                return None
            
            return self._row_to_schedule(row)
    
    async def get_all_schedules(self, active_only: bool = False) -> List[PipelineSchedule]:
        """Get all schedules"""
        async with db_pool.acquire() as conn:
            query = "SELECT * FROM pipeline_schedules"
            if active_only:
                query += " WHERE is_active = true"
            query += " ORDER BY name"
            
            rows = await conn.fetch(query)
            return [self._row_to_schedule(row) for row in rows]
    
    async def delete_schedule(self, schedule_id: UUID) -> bool:
        """Delete a schedule"""
        async with db_pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM pipeline_schedules WHERE id = $1",
                schedule_id
            )
            
            if result == "DELETE 1":
                logger.info(f"Deleted pipeline schedule: {schedule_id}")
                return True
            return False
    
    async def start_scheduler(self):
        """Start the background scheduler"""
        if self._scheduler_running:
            logger.warning("Scheduler already running")
            return
        
        self._scheduler_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Pipeline scheduler started")
    
    async def stop_scheduler(self):
        """Stop the background scheduler"""
        if not self._scheduler_running:
            return
        
        self._scheduler_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Pipeline scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop"""
        while self._scheduler_running:
            try:
                await self._check_and_execute_schedules()
                await asyncio.sleep(60)  # Check every minute
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduler loop error: {e}")
                await asyncio.sleep(60)
    
    async def _check_and_execute_schedules(self):
        """Check for schedules that need to be executed"""
        now = datetime.utcnow()
        
        # Get schedules due for execution
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM pipeline_schedules 
                WHERE is_active = true 
                AND next_execution_at <= $1
                """,
                now
            )
        
        for row in rows:
            schedule = self._row_to_schedule(row)
            
            # Check if we can execute (concurrent execution limits)
            active_count = await self._count_active_executions(schedule.id)
            if active_count >= schedule.max_concurrent_executions:
                logger.info(f"Schedule {schedule.name} hit concurrent execution limit")
                continue
            
            # Determine which content types to run
            content_types_due = await self._get_content_types_due(schedule, now)
            if not content_types_due:
                continue
            
            # Execute schedule
            await self._execute_schedule(schedule, content_types_due, now)
    
    async def _execute_schedule(
        self, 
        schedule: PipelineSchedule, 
        content_types: List[str], 
        scheduled_for: datetime
    ):
        """Execute a scheduled pipeline"""
        execution_id = uuid4()
        
        # Create execution record
        execution = ScheduleExecution(
            id=execution_id,
            schedule_id=schedule.id,
            content_types=content_types,
            scheduled_for=scheduled_for,
            started_at=datetime.utcnow()
        )
        
        self._active_executions[execution_id] = execution
        
        try:
            # Save execution record
            await self._save_execution(execution)
            
            # Check if this is the first run for this schedule
            is_initial_run = schedule.last_executed_at is None
            
            # Create pipeline config with robustness features
            config = PipelineConfig(
                keywords=schedule.keywords,
                regions=schedule.regions,
                content_types=content_types,
                schedule_id=schedule.id,
                is_initial_run=is_initial_run,
                scheduled_for=scheduled_for,
                # Enable robust execution for scheduled runs
                force_refresh=True,  # Always refresh data for scheduled runs
                enable_historical_tracking=True
            )
            
            # Start pipeline with robust orchestration
            pipeline_id = await self.pipeline_service.start_pipeline(
                config, 
                mode=PipelineMode.SCHEDULED
            )
            
            execution.pipeline_id = pipeline_id
            execution.status = "running"
            await self._save_execution(execution)
            
            # Wait for completion (with timeout)
            timeout_seconds = max(cs.timeout_hours for cs in schedule.content_schedules) * 3600
            
            try:
                await self._wait_for_pipeline_completion(
                    pipeline_id, 
                    timeout_seconds
                )
                
                # Get pipeline result
                result = await self.pipeline_service.get_pipeline_status(pipeline_id)
                
                execution.status = "completed" if result and result.status.value == "completed" else "failed"
                execution.completed_at = datetime.utcnow()
                execution.results_summary = {
                    "keywords_processed": result.keywords_processed if result else 0,
                    "serp_results_collected": result.serp_results_collected if result else 0,
                    "content_analyzed": result.content_analyzed if result else 0
                }
                
                if execution.status == "completed" and schedule.notify_on_completion:
                    await self._send_notification(schedule, execution, "completed")
                
            except asyncio.TimeoutError:
                execution.status = "failed"
                execution.error_message = "Pipeline execution timed out"
                execution.completed_at = datetime.utcnow()
                
                # Cancel the pipeline
                await self.pipeline_service.cancel_pipeline(pipeline_id)
                
                if schedule.notify_on_error:
                    await self._send_notification(schedule, execution, "timeout")
            
            await self._save_execution(execution)
            
            # Update schedule's last execution and next execution time
            await self._update_schedule_execution_time(schedule.id)
            
            logger.info(f"Scheduled execution {execution_id} completed with status: {execution.status}")
            
        except Exception as e:
            execution.status = "failed"
            execution.error_message = str(e)
            execution.completed_at = datetime.utcnow()
            await self._save_execution(execution)
            
            if schedule.notify_on_error:
                await self._send_notification(schedule, execution, "error")
            
            logger.error(f"Scheduled execution {execution_id} failed: {e}")
        
        finally:
            # Remove from active executions
            if execution_id in self._active_executions:
                del self._active_executions[execution_id]
    
    async def _calculate_next_execution(self, schedule: PipelineSchedule) -> Optional[datetime]:
        """Calculate the next execution time for a schedule"""
        if not schedule.is_active or not schedule.content_schedules:
            return None
        
        now = datetime.utcnow()
        next_times = []
        
        for cs in schedule.content_schedules:
            if not cs.enabled:
                continue
            
            if cs.frequency == ScheduleFrequency.DAILY:
                next_time = now.replace(
                    hour=cs.time_of_day.hour,
                    minute=cs.time_of_day.minute,
                    second=0,
                    microsecond=0
                )
                if next_time <= now:
                    next_time += timedelta(days=1)
                next_times.append(next_time)
            
            elif cs.frequency == ScheduleFrequency.WEEKLY:
                # Find next occurrence of specified days
                if cs.days_of_week:
                    for day_of_week in cs.days_of_week:
                        days_ahead = day_of_week - now.isoweekday()
                        if days_ahead <= 0:
                            days_ahead += 7
                        
                        next_time = now.replace(
                            hour=cs.time_of_day.hour,
                            minute=cs.time_of_day.minute,
                            second=0,
                            microsecond=0
                        ) + timedelta(days=days_ahead)
                        
                        next_times.append(next_time)
            
            elif cs.frequency == ScheduleFrequency.MONTHLY:
                # Monthly execution
                if cs.day_of_month:
                    target_day = cs.day_of_month if cs.day_of_month > 0 else 1  # TODO: Handle last day
                    
                    next_time = now.replace(
                        day=min(target_day, 28),  # Safe day
                        hour=cs.time_of_day.hour,
                        minute=cs.time_of_day.minute,
                        second=0,
                        microsecond=0
                    )
                    
                    if next_time <= now:
                        # Next month
                        if next_time.month == 12:
                            next_time = next_time.replace(year=next_time.year + 1, month=1)
                        else:
                            next_time = next_time.replace(month=next_time.month + 1)
                    
                    next_times.append(next_time)
            
            elif cs.frequency == ScheduleFrequency.QUARTERLY:
                # Quarterly execution (every 3 months)
                if cs.day_of_month:
                    target_day = cs.day_of_month if cs.day_of_month > 0 else 1
                    
                    next_time = now.replace(
                        day=min(target_day, 28),  # Safe day
                        hour=cs.time_of_day.hour,
                        minute=cs.time_of_day.minute,
                        second=0,
                        microsecond=0
                    )
                    
                    if next_time <= now:
                        # Next quarter (add 3 months)
                        month = next_time.month + 3
                        year = next_time.year
                        if month > 12:
                            month = month - 12
                            year = year + 1
                        next_time = next_time.replace(year=year, month=month)
                    
                    next_times.append(next_time)
            
            elif cs.frequency == ScheduleFrequency.CUSTOM_CRON and cs.cron_expression:
                # Use croniter for custom expressions
                try:
                    cron = croniter(cs.cron_expression, now)
                    next_times.append(cron.get_next(datetime))
                except Exception as e:
                    logger.error(f"Invalid cron expression '{cs.cron_expression}': {e}")
        
        return min(next_times) if next_times else None
    
    async def _get_content_types_due(
        self, 
        schedule: PipelineSchedule, 
        current_time: datetime
    ) -> List[str]:
        """Get content types that are due for execution"""
        due_types = []
        
        for cs in schedule.content_schedules:
            if not cs.enabled:
                continue
            
            # Check if this content type is due
            if await self._is_content_type_due(cs, current_time):
                due_types.append(cs.content_type)
        
        return due_types
    
    async def _is_content_type_due(
        self, 
        content_schedule: ContentTypeSchedule, 
        current_time: datetime
    ) -> bool:
        """Check if a specific content type is due for execution"""
        # This would implement the logic to check if execution is due
        # based on the frequency and last execution time
        # For now, simplified implementation
        return True
    
    async def _count_active_executions(self, schedule_id: UUID) -> int:
        """Count active executions for a schedule"""
        async with db_pool.acquire() as conn:
            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM schedule_executions 
                WHERE schedule_id = $1 AND status IN ('pending', 'running')
                """,
                schedule_id
            )
            return count or 0
    
    async def _save_execution(self, execution: ScheduleExecution):
        """Save execution record to database"""
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO schedule_executions (
                    id, schedule_id, pipeline_id, content_types,
                    scheduled_for, started_at, completed_at, status,
                    error_message, retry_count, results_summary
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (id) DO UPDATE SET
                    pipeline_id = EXCLUDED.pipeline_id,
                    started_at = EXCLUDED.started_at,
                    completed_at = EXCLUDED.completed_at,
                    status = EXCLUDED.status,
                    error_message = EXCLUDED.error_message,
                    retry_count = EXCLUDED.retry_count,
                    results_summary = EXCLUDED.results_summary
                """,
                execution.id,
                execution.schedule_id,
                execution.pipeline_id,
                json.dumps(execution.content_types),
                execution.scheduled_for,
                execution.started_at,
                execution.completed_at,
                execution.status,
                execution.error_message,
                execution.retry_count,
                json.dumps(execution.results_summary) if execution.results_summary else None
            )
    
    async def _wait_for_pipeline_completion(self, pipeline_id: UUID, timeout_seconds: int):
        """Wait for pipeline to complete with timeout"""
        start_time = datetime.utcnow()
        
        while True:
            result = await self.pipeline_service.get_pipeline_status(pipeline_id)
            if not result:
                break
            
            if result.status.value in ["completed", "failed", "cancelled"]:
                break
            
            # Check timeout
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                raise asyncio.TimeoutError()
            
            await asyncio.sleep(30)  # Check every 30 seconds
    
    async def _update_schedule_execution_time(self, schedule_id: UUID):
        """Update schedule's last execution and next execution time"""
        schedule = await self.get_schedule(schedule_id)
        if not schedule:
            return
        
        next_execution = await self._calculate_next_execution(schedule)
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE pipeline_schedules 
                SET last_executed_at = $2, next_execution_at = $3
                WHERE id = $1
                """,
                schedule_id,
                datetime.utcnow(),
                next_execution
            )
    
    async def _send_notification(
        self, 
        schedule: PipelineSchedule, 
        execution: ScheduleExecution, 
        event_type: str
    ):
        """Send notification about execution"""
        # TODO: Implement email/webhook notifications
        logger.info(f"Notification: Schedule '{schedule.name}' execution {event_type}")
    
    def _content_schedule_to_dict(self, cs: ContentTypeSchedule) -> dict:
        """Convert ContentTypeSchedule to dict with proper serialization"""
        data = cs.dict()
        # Convert time object to string
        if 'time_of_day' in data and data['time_of_day'] is not None:
            data['time_of_day'] = data['time_of_day'].isoformat()
        return data
    
    def _row_to_schedule(self, row) -> PipelineSchedule:
        """Convert database row to PipelineSchedule"""
        data = dict(row)
        
        # Parse JSON fields
        content_schedules_data = json.loads(data['content_schedules'] or '[]')
        # Convert time strings back to time objects
        for cs_data in content_schedules_data:
            if 'time_of_day' in cs_data and isinstance(cs_data['time_of_day'], str):
                # Parse time string (HH:MM:SS)
                time_parts = cs_data['time_of_day'].split(':')
                cs_data['time_of_day'] = time(
                    int(time_parts[0]), 
                    int(time_parts[1]), 
                    int(time_parts[2]) if len(time_parts) > 2 else 0
                )
        data['content_schedules'] = [
            ContentTypeSchedule(**cs_data) for cs_data in content_schedules_data
        ]
        
        # Handle keywords from keywords_set and custom_keywords columns
        if data.get('custom_keywords'):
            data['keywords'] = json.loads(data['custom_keywords'])
        else:
            data['keywords'] = None
        
        # Regions is already an array from the database, no need to parse JSON
        data['regions'] = data['regions'] or ["US", "UK"]
        
        # notification_emails is already an array from the database
        # No need to parse JSON
        
        return PipelineSchedule(**data)

