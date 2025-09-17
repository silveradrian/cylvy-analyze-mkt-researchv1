import asyncio
from app.core.database import db_pool
import uuid
from datetime import datetime

async def check():
    pipeline_id = uuid.UUID("1a1bac89-8056-41ff-8f20-8e82ec67999f")
    
    async with db_pool.acquire() as conn:
        # Check when content scraping last started for this pipeline
        last_scraping = await conn.fetchrow("""
            SELECT phase_name, status, started_at, completed_at
            FROM pipeline_phase_status
            WHERE pipeline_execution_id = $1
            AND phase_name = 'content_scraping'
            ORDER BY started_at DESC
            LIMIT 1
        """, pipeline_id)
        
        print(f"Last content scraping phase:")
        if last_scraping:
            print(f"  Status: {last_scraping['status']}")
            print(f"  Started: {last_scraping['started_at']}")
            print(f"  Completed: {last_scraping['completed_at']}")
        else:
            print("  No previous content scraping phase found")
        
        # Check when SERP results were added
        serp_times = await conn.fetchrow("""
            SELECT 
                MIN(created_at) as earliest,
                MAX(created_at) as latest,
                COUNT(*) as total_count
            FROM serp_results
            WHERE pipeline_execution_id = $1
        """, pipeline_id)
        
        print(f"\nSERP results for this pipeline:")
        print(f"  Total count: {serp_times['total_count']}")
        print(f"  Earliest: {serp_times['earliest']}")
        print(f"  Latest: {serp_times['latest']}")
        
        # Check how many URLs are from this pipeline vs previous ones
        url_sources = await conn.fetch("""
            SELECT 
                sr.pipeline_execution_id,
                COUNT(DISTINCT sr.url) as url_count,
                MIN(sr.created_at) as earliest,
                MAX(sr.created_at) as latest
            FROM serp_results sr
            WHERE sr.url IN (
                SELECT DISTINCT url 
                FROM serp_results 
                WHERE pipeline_execution_id = $1
                AND serp_type IN ('organic', 'news')
            )
            AND sr.serp_type IN ('organic', 'news')
            GROUP BY sr.pipeline_execution_id
            ORDER BY MIN(sr.created_at) DESC
            LIMIT 5
        """, pipeline_id)
        
        print(f"\nURL sources (which pipelines have these URLs):")
        for source in url_sources:
            pipeline_str = str(source['pipeline_execution_id'])
            is_current = " (CURRENT)" if source['pipeline_execution_id'] == pipeline_id else ""
            print(f"  Pipeline {pipeline_str[:8]}...{is_current}: {source['url_count']} URLs")
            print(f"    Added: {source['earliest']} to {source['latest']}")
        
        # Check already scraped content across all pipelines
        already_scraped = await conn.fetchrow("""
            SELECT COUNT(DISTINCT sc.url) as scraped_count
            FROM scraped_content sc
            WHERE sc.url IN (
                SELECT DISTINCT url 
                FROM serp_results 
                WHERE pipeline_execution_id = $1
                AND serp_type IN ('organic', 'news')
            )
            AND sc.status = 'completed'
        """, pipeline_id)
        
        print(f"\nAlready scraped URLs (from any pipeline): {already_scraped['scraped_count']}")

asyncio.run(check())
