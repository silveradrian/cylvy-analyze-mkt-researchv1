"""
Keyword Metrics Scheduling Service
Handles automated monthly keyword metrics updates from Google Ads
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from loguru import logger

from app.core.database import db_pool
from app.services.keywords.simplified_google_ads_service import SimplifiedGoogleAdsService as GoogleAdsService


class KeywordMetricsScheduler:
    """Service for scheduling and running keyword metrics updates"""
    
    def __init__(self, settings, ads_service: GoogleAdsService):
        self.settings = settings
        self.ads_service = ads_service
        self._scheduler_running = False
        self._scheduler_task: Optional[asyncio.Task] = None
        
    async def start_scheduler(self):
        """Start the keyword metrics scheduler"""
        if self._scheduler_running:
            logger.warning("Keyword metrics scheduler already running")
            return
            
        self._scheduler_running = True
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())
        logger.info("🔍 Keyword metrics scheduler started")
        
    async def stop_scheduler(self):
        """Stop the keyword metrics scheduler"""
        if not self._scheduler_running:
            return
            
        self._scheduler_running = False
        if self._scheduler_task:
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
                
        logger.info("🔍 Keyword metrics scheduler stopped")
        
    async def _scheduler_loop(self):
        """Main scheduler loop - runs monthly checks"""
        while self._scheduler_running:
            try:
                # Check if metrics update is due
                is_due = await self._is_metrics_update_due()
                if is_due:
                    logger.info("📊 Monthly keyword metrics update is due")
                    await self.update_all_keyword_metrics()
                    
                # Sleep for 1 hour between checks
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Keyword metrics scheduler error: {e}")
                await asyncio.sleep(3600)
                
    async def _is_metrics_update_due(self) -> bool:
        """Check if monthly metrics update is due"""
        async with db_pool.acquire() as conn:
            # Get last metrics update timestamp
            last_update = await conn.fetchval(
                """
                SELECT MAX(created_at) 
                FROM keyword_metrics_jobs 
                WHERE status = 'completed' AND job_type = 'scheduled_monthly'
                """
            )
            
            if not last_update:
                # No previous update, it's due
                return True
                
            # Check if it's been at least 30 days
            days_since_update = (datetime.utcnow() - last_update).days
            
            # Also check if it's the preferred day of month (e.g., 1st)
            now = datetime.utcnow()
            is_preferred_day = now.day == 1  # Run on the 1st of each month
            
            return days_since_update >= 30 and is_preferred_day
            
    async def update_all_keyword_metrics(self, force: bool = False) -> Dict[str, Any]:
        """
        Update metrics for all keywords
        
        Args:
            force: Force update even if recently updated
            
        Returns:
            Results summary
        """
        job_id = f"metrics_scheduled_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            # Record job start
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO keyword_metrics_jobs (
                        id, job_type, status, started_at, total_keywords
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    job_id, 'scheduled_monthly', 'running', datetime.utcnow(), 0
                )
                
            logger.info(f"🚀 Starting monthly keyword metrics update job: {job_id}")
            
            # Get all active keywords
            keywords = await self._get_all_keywords()
            total_keywords = len(keywords)
            
            logger.info(f"📊 Found {total_keywords} keywords to update")
            
            # Update job with total count
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE keyword_metrics_jobs 
                    SET total_keywords = $2 
                    WHERE id = $1
                    """,
                    job_id, total_keywords
                )
                
            # Process keywords in batches
            batch_size = 10  # Google Ads API limit
            total_processed = 0
            total_errors = 0
            
            for i in range(0, len(keywords), batch_size):
                batch = keywords[i:i + batch_size]
                batch_keywords = [kw['keyword'] for kw in batch]
                
                try:
                    # Fetch metrics from Google Ads
                    logger.info(f"🔍 Fetching metrics for batch {i//batch_size + 1}/{(len(keywords) + batch_size - 1)//batch_size}")
                    metrics = await self.ads_service.get_keyword_metrics(
                        batch_keywords,
                        location_id="2840"  # US by default
                    )
                    
                    # Store metrics in database
                    await self._store_keyword_metrics(metrics)
                    
                    total_processed += len(metrics)
                    
                    # Update job progress
                    async with db_pool.acquire() as conn:
                        await conn.execute(
                            """
                            UPDATE keyword_metrics_jobs 
                            SET keywords_processed = $2, last_updated = NOW()
                            WHERE id = $1
                            """,
                            job_id, total_processed
                        )
                        
                except Exception as e:
                    logger.error(f"❌ Error processing batch {i//batch_size + 1}: {e}")
                    total_errors += len(batch)
                    
                # Rate limiting delay
                await asyncio.sleep(1)
                
            # Complete job
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE keyword_metrics_jobs 
                    SET status = $2, completed_at = $3, keywords_processed = $4, errors = $5
                    WHERE id = $1
                    """,
                    job_id, 'completed', datetime.utcnow(), total_processed, total_errors
                )
                
            logger.info(f"✅ Monthly keyword metrics update completed: {total_processed}/{total_keywords} processed")
            
            return {
                'job_id': job_id,
                'status': 'completed',
                'total_keywords': total_keywords,
                'keywords_processed': total_processed,
                'errors': total_errors
            }
            
        except Exception as e:
            logger.error(f"❌ Keyword metrics job {job_id} failed: {e}")
            
            # Mark job as failed
            async with db_pool.acquire() as conn:
                await conn.execute(
                    """
                    UPDATE keyword_metrics_jobs 
                    SET status = 'failed', error_message = $2, completed_at = NOW()
                    WHERE id = $1
                    """,
                    job_id, str(e)
                )
                
            return {
                'job_id': job_id,
                'status': 'failed',
                'error': str(e)
            }
            
    async def _get_all_keywords(self) -> List[Dict[str, Any]]:
        """Get all active keywords from database"""
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, keyword, category, jtbd_stage
                FROM keywords
                WHERE is_active = TRUE
                ORDER BY keyword
                """
            )
            
            return [dict(row) for row in rows]
            
    async def _store_keyword_metrics(self, metrics: List[Any]):
        """Store keyword metrics in database"""
        if not metrics:
            return
            
        async with db_pool.acquire() as conn:
            # Update keywords table with latest metrics
            for metric in metrics:
                await conn.execute(
                    """
                    UPDATE keywords 
                    SET 
                        avg_monthly_searches = $2,
                        competition_level = $3,
                        competition_index = $4,
                        low_bid_micros = $5,
                        high_bid_micros = $6,
                        metrics_updated_at = NOW()
                    WHERE keyword = $1
                    """,
                    metric.keyword,
                    metric.avg_monthly_searches,
                    metric.competition_level,
                    metric.competition_index,
                    metric.low_bid_micros,
                    metric.high_bid_micros
                )
                
                # Also store in historical metrics table
                await conn.execute(
                    """
                    INSERT INTO historical_keyword_metrics (
                        keyword_id,
                        avg_monthly_searches,
                        competition,
                        competition_index,
                        low_top_of_page_bid_micros,
                        high_top_of_page_bid_micros,
                        metric_date
                    ) 
                    SELECT 
                        id, $2, $3, $4, $5, $6, CURRENT_DATE
                    FROM keywords 
                    WHERE keyword = $1
                    """,
                    metric.keyword,
                    metric.avg_monthly_searches,
                    metric.competition_level,
                    metric.competition_index,
                    metric.low_bid_micros,
                    metric.high_bid_micros
                )
                
    async def get_metrics_status(self) -> Dict[str, Any]:
        """Get current status of keyword metrics"""
        async with db_pool.acquire() as conn:
            # Get last update info
            last_job = await conn.fetchrow(
                """
                SELECT * FROM keyword_metrics_jobs 
                WHERE job_type = 'scheduled_monthly'
                ORDER BY created_at DESC 
                LIMIT 1
                """
            )
            
            # Get keywords with/without metrics
            metrics_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_keywords,
                    COUNT(CASE WHEN avg_monthly_searches IS NOT NULL THEN 1 END) as keywords_with_metrics,
                    COUNT(CASE WHEN avg_monthly_searches IS NULL THEN 1 END) as keywords_without_metrics,
                    MIN(metrics_updated_at) as oldest_metrics_date,
                    MAX(metrics_updated_at) as newest_metrics_date
                FROM keywords
                WHERE is_active = TRUE
                """
            )
            
            return {
                'last_job': dict(last_job) if last_job else None,
                'metrics_coverage': {
                    'total_keywords': metrics_stats['total_keywords'],
                    'with_metrics': metrics_stats['keywords_with_metrics'],
                    'without_metrics': metrics_stats['keywords_without_metrics'],
                    'coverage_percentage': round(
                        (metrics_stats['keywords_with_metrics'] / metrics_stats['total_keywords'] * 100)
                        if metrics_stats['total_keywords'] > 0 else 0,
                        2
                    )
                },
                'date_range': {
                    'oldest_metrics': metrics_stats['oldest_metrics_date'],
                    'newest_metrics': metrics_stats['newest_metrics_date']
                },
                'next_update_due': await self._get_next_update_date()
            }
            
    async def _get_next_update_date(self) -> datetime:
        """Calculate when the next metrics update is due"""
        async with db_pool.acquire() as conn:
            last_update = await conn.fetchval(
                """
                SELECT MAX(created_at) 
                FROM keyword_metrics_jobs 
                WHERE status = 'completed' AND job_type = 'scheduled_monthly'
                """
            )
            
            if not last_update:
                # No previous update, due immediately
                return datetime.utcnow()
                
            # Next update is on the 1st of next month
            next_month = last_update.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=1)