#!/usr/bin/env python3
"""
Clear all pipeline execution history
"""
import asyncio
import asyncpg
from app.core.database import db_pool
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def clear_pipeline_history():
    """Clear all pipeline execution history from the database"""
    try:
        # Initialize database pool
        if not db_pool.pool:
            await db_pool.initialize()
        
        async with db_pool.acquire() as conn:
            # Get count of pipeline executions
            count_result = await conn.fetchval("SELECT COUNT(*) FROM pipeline_executions")
            logger.info(f"Found {count_result} pipeline executions to clear")
            
            if count_result == 0:
                logger.info("No pipeline executions to clear")
                return
            
            # Confirm deletion
            confirm = input(f"Are you sure you want to delete {count_result} pipeline executions? (yes/no): ")
            if confirm.lower() != 'yes':
                logger.info("Deletion cancelled")
                return
            
            # Delete all pipeline executions
            await conn.execute("DELETE FROM pipeline_executions")
            logger.info(f"✅ Deleted {count_result} pipeline executions")
            
            # Also clear related phase status if table exists
            try:
                phase_count = await conn.fetchval("SELECT COUNT(*) FROM pipeline_phase_status")
                if phase_count > 0:
                    await conn.execute("DELETE FROM pipeline_phase_status")
                    logger.info(f"✅ Deleted {phase_count} pipeline phase status records")
            except asyncpg.UndefinedTableError:
                logger.info("No pipeline_phase_status table found (this is normal)")
            
            # Clear any orphaned SERP results (optional - be careful with this)
            # Uncomment only if you want to clear ALL data
            # await conn.execute("DELETE FROM serp_results")
            # await conn.execute("DELETE FROM content_analysis")
            # logger.info("✅ Cleared all SERP and content analysis data")
            
    except Exception as e:
        logger.error(f"Failed to clear pipeline history: {e}")
        raise
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(clear_pipeline_history())
