from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, date, timezone
from typing import Optional, Dict, Any, List
from uuid import UUID

from loguru import logger
from asyncpg.pool import Pool

from app.core.config import settings
from app.core.database import db_pool
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig


class SerpBatchCoordinator:
    """Coordinates SERP batch webhooks and starts a single pipeline per project/day when complete."""

    def __init__(self, db: Pool, pipeline_service: PipelineService):
        self.db = db
        self.pipeline_service = pipeline_service

    async def record_batch_completion(
        self,
        project_id: UUID,
        content_type: str,
        period_date: date,
        batch_id: str,
        result_set_id: Optional[str],
        download_links: Optional[Dict[str, Any]]
    ) -> None:
        async with self.db.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO serp_batch_expectations (
                    project_id, period_date, content_type, expected, received, received_at,
                    batch_id, result_set_id, download_links
                ) VALUES ($1, $2, $3, TRUE, TRUE, NOW(), $4, $5, $6)
                ON CONFLICT (project_id, period_date, content_type)
                DO UPDATE SET received = TRUE, received_at = NOW(),
                              batch_id = EXCLUDED.batch_id,
                              result_set_id = EXCLUDED.result_set_id,
                              download_links = EXCLUDED.download_links,
                              updated_at = NOW()
                """,
                project_id, period_date, content_type, batch_id, result_set_id, download_links
            )

    async def try_start_pipeline(self, project_id: UUID, period_date: date) -> Optional[UUID]:
        """If all required expectations are received or cutoff reached, start exactly one pipeline."""
        cutoff_minutes = settings.SERP_COORDINATOR_CUTOFF_MINUTES
        # Use timezone-aware UTC to compare with timestamptz from DB
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=cutoff_minutes)

        async with self.db.acquire() as conn:
            # Check if already started
            existing = await conn.fetchrow(
                "SELECT pipeline_execution_id FROM serp_batch_coordinator_runs WHERE project_id = $1 AND period_date = $2",
                project_id, period_date
            )
            if existing and existing['pipeline_execution_id']:
                return existing['pipeline_execution_id']

            # Load expectations
            rows = await conn.fetch(
                """
                SELECT content_type, expected, received, received_at, batch_id, result_set_id, download_links
                FROM serp_batch_expectations
                WHERE project_id = $1 AND period_date = $2
                """,
                project_id, period_date
            )
            if not rows:
                return None

            received_all = all(r['received'] for r in rows if r['expected'])
            any_received_recent = any((r['received_at'] and r['received_at'] > cutoff_time) for r in rows)

            if not received_all and any_received_recent:
                # Wait for more until cutoff expires
                return None

            # Acquire lock (one row per day/project)
            try:
                await conn.execute(
                    "INSERT INTO serp_batch_coordinator_runs (project_id, period_date) VALUES ($1, $2)",
                    project_id, period_date
                )
            except Exception:
                # Another coordinator acquired it
                existing = await conn.fetchrow(
                    "SELECT pipeline_execution_id FROM serp_batch_coordinator_runs WHERE project_id = $1 AND period_date = $2",
                    project_id, period_date
                )
                return existing['pipeline_execution_id'] if existing else None

        # Build pipeline config to consume batches
        # For now, just disable serp collection and let pipeline fetch via UnifiedSERPCollector.process_webhook_batch
        config = PipelineConfig(
            enable_serp_collection=False,
            enable_company_enrichment=True,
            enable_video_enrichment=True,
            enable_content_analysis=True,
        )

        pipeline_id = await self.pipeline_service.start_pipeline(config)

        async with self.db.acquire() as conn:
            await conn.execute(
                "UPDATE serp_batch_coordinator_runs SET pipeline_execution_id = $3 WHERE project_id = $1 AND period_date = $2",
                project_id, period_date, str(pipeline_id)
            )

        logger.info(f"Coordinator started pipeline {pipeline_id} for project {project_id} period {period_date}")
        return pipeline_id


