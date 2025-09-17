import asyncio
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from uuid import UUID

from loguru import logger
from asyncpg.pool import Pool

from app.core.config import settings
from app.core.database import db_pool
from app.services.serp.unified_serp_collector import UnifiedSERPCollector
from app.services.serp.serp_batch_coordinator import SerpBatchCoordinator
from app.services.pipeline.pipeline_service import PipelineService


class SerpBatchScheduler:
    """Creates due ScaleSERP batches per schedule and polls for readiness."""

    def __init__(self, db: Pool, pipeline_service: PipelineService):
        self.db = db
        self.pipeline_service = pipeline_service
        self.collector = UnifiedSERPCollector(settings, db)
        self.coordinator = SerpBatchCoordinator(db, pipeline_service)
        self._task = None
        self._running = False

    async def start(self):
        if self._running or not settings.SERP_SCHEDULER_ENABLED:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("SerpBatchScheduler started")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SerpBatchScheduler stopped")

    async def _loop(self):
        interval = max(15, settings.SERP_SCHEDULER_POLL_INTERVAL_S)
        while self._running:
            try:
                await self._tick()
            except Exception as e:
                logger.error(f"SerpBatchScheduler tick error: {e}")
            await asyncio.sleep(interval)

    async def _tick(self):
        today = date.today()
        # Load active schedule: keywords, regions, enabled content types
        schedule = await self._load_active_schedule()
        if not schedule:
            return
        project_id = str(schedule['id'])
        content_types = schedule['content_types']
        if not content_types:
            return

        # Ensure expectations exist
        async with self.db.acquire() as conn:
            for ct in content_types:
                await conn.execute(
                    """
                    INSERT INTO serp_batch_expectations (project_id, period_date, content_type, expected)
                    VALUES ($1, $2, $3, TRUE)
                    ON CONFLICT (project_id, period_date, content_type)
                    DO NOTHING
                    """,
                    project_id, today, ct
                )

        # Create missing batches and record their IDs
        for ct in content_types:
            already_have = await self._has_received_or_recorded(project_id, today, ct)
            if already_have:
                continue
            try:
                create = await self.collector.create_batch_only(
                    keywords=schedule['keywords'],
                    keyword_ids=[],
                    regions=schedule['regions'],
                    content_type=ct,
                    include_html=False,
                )
                batch_id = create.get('batch_id')
                if batch_id:
                    await self.coordinator.record_batch_completion(
                        project_id=UUID(project_id),
                        content_type=ct,
                        period_date=today,
                        batch_id=batch_id,
                        result_set_id=None,
                        download_links=None,
                    )
                    logger.info(f"Scheduled and recorded batch {batch_id} for {ct}")
            except Exception as e:
                logger.error(f"Failed to create batch for {ct}: {e}")

        # Try start pipeline if possible
        await self.coordinator.try_start_pipeline(UUID(project_id), today)

    async def _load_active_schedule(self) -> Optional[Dict[str, Any]]:
        """Return active schedule with id, keywords, regions, enabled content types."""
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, content_schedules, regions, custom_keywords
                FROM pipeline_schedules
                WHERE is_active = TRUE
                LIMIT 1
                """
            )
        if not row:
            return None
        # Parse content_schedules
        content_types: List[str] = []
        try:
            import json
            cs = row['content_schedules']
            cs_list = json.loads(cs) if isinstance(cs, str) else cs
            for item in cs_list or []:
                if item.get('enabled', True) and item.get('content_type') in ("organic", "news", "video"):
                    content_types.append(item['content_type'])
        except Exception:
            content_types = ["organic", "news", "video"]

        # Regions
        regions = row['regions'] or []
        # Keywords from custom_keywords JSON
        keywords: List[str] = []
        try:
            import json
            ck = row['custom_keywords']
            ck_list = json.loads(ck) if isinstance(ck, str) else ck
            if isinstance(ck_list, list):
                for k in ck_list:
                    if isinstance(k, dict) and k.get('keyword'):
                        keywords.append(k['keyword'])
                    elif isinstance(k, str):
                        keywords.append(k)
        except Exception:
            pass

        return {
            'id': row['id'],
            'content_types': content_types,
            'regions': regions,
            'keywords': keywords,
        }

    async def _has_received_or_recorded(self, project_id: str, period_date: date, content_type: str) -> bool:
        async with self.db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT received, batch_id FROM serp_batch_expectations
                WHERE project_id = $1 AND period_date = $2 AND content_type = $3
                """,
                project_id, period_date, content_type
            )
            return bool(row and (row['received'] or row['batch_id']))

