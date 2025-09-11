"""
Script to monitor database writes during pipeline execution
"""
import asyncio
import asyncpg
from datetime import datetime, timedelta
import json
from loguru import logger

DATABASE_URL = "postgresql://cylvy:cylvy123@localhost:5433/cylvy_analyzer"

async def check_database_writes(pipeline_id: str):
    """Check what's been written to database for a specific pipeline"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        print(f"\n{'='*80}")
        print(f"DATABASE WRITE CHECK FOR PIPELINE: {pipeline_id}")
        print(f"Timestamp: {datetime.now()}")
        print(f"{'='*80}\n")
        
        # 1. Check pipeline_results table
        print("1. PIPELINE RESULTS:")
        pipeline_results = await conn.fetch(
            "SELECT * FROM pipeline_results WHERE pipeline_id = $1",
            pipeline_id
        )
        print(f"   Found {len(pipeline_results)} pipeline result records")
        for r in pipeline_results:
            print(f"   - Status: {r['status']}, Mode: {r['mode']}, Started: {r['started_at']}")
        
        # 2. Check keyword_metrics table
        print("\n2. KEYWORD METRICS:")
        keyword_metrics = await conn.fetch(
            """
            SELECT km.*, k.keyword 
            FROM keyword_metrics km
            JOIN keywords k ON km.keyword_id = k.id
            WHERE km.updated_at >= NOW() - INTERVAL '10 minutes'
            ORDER BY km.updated_at DESC
            LIMIT 10
            """
        )
        print(f"   Found {len(keyword_metrics)} recent keyword metric updates")
        for km in keyword_metrics:
            print(f"   - Keyword: {km['keyword']}, Volume: {km['search_volume']}, Region: {km['region']}")
        
        # 3. Check serp_results table
        print("\n3. SERP RESULTS:")
        serp_results = await conn.fetch(
            """
            SELECT COUNT(*) as count, search_type, region 
            FROM serp_results 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            GROUP BY search_type, region
            """
        )
        print(f"   Recent SERP results by type and region:")
        for sr in serp_results:
            print(f"   - Type: {sr['search_type']}, Region: {sr['region']}, Count: {sr['count']}")
        
        # 4. Check companies table (from enrichment)
        print("\n4. COMPANY ENRICHMENTS:")
        companies = await conn.fetch(
            """
            SELECT COUNT(*) as count, source_type 
            FROM companies 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            GROUP BY source_type
            """
        )
        print(f"   Recent company enrichments by source type:")
        for c in companies:
            print(f"   - Source Type: {c['source_type']}, Count: {c['count']}")
        
        # 5. Check video_snapshots table
        print("\n5. VIDEO SNAPSHOTS:")
        video_snapshots = await conn.fetch(
            """
            SELECT COUNT(*) as count, serp_engine 
            FROM video_snapshots 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            GROUP BY serp_engine
            """
        )
        print(f"   Recent video snapshots:")
        for vs in video_snapshots:
            print(f"   - Engine: {vs['serp_engine']}, Count: {vs['count']}")
        
        # 6. Check youtube_channel_companies table
        print("\n6. YOUTUBE CHANNEL COMPANIES:")
        yt_companies = await conn.fetch(
            """
            SELECT * 
            FROM youtube_channel_companies 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            LIMIT 5
            """
        )
        print(f"   Found {len(yt_companies)} YouTube channel company extractions")
        for yc in yt_companies:
            print(f"   - Channel: {yc['channel_id']}, Domain: {yc['company_domain']}, Type: {yc['source_type']}")
        
        # 7. Check content_scraped table
        print("\n7. CONTENT SCRAPED:")
        content_scraped = await conn.fetch(
            """
            SELECT COUNT(*) as count, status 
            FROM content_scraped 
            WHERE scraped_at >= NOW() - INTERVAL '10 minutes'
            GROUP BY status
            """
        )
        print(f"   Recent content scraping by status:")
        for cs in content_scraped:
            print(f"   - Status: {cs['status']}, Count: {cs['count']}")
        
        # 8. Check content_analysis table
        print("\n8. CONTENT ANALYSIS:")
        content_analysis = await conn.fetch(
            """
            SELECT COUNT(*) as count 
            FROM content_analysis 
            WHERE analyzed_at >= NOW() - INTERVAL '10 minutes'
            """
        )
        if content_analysis:
            print(f"   Found {content_analysis[0]['count']} recent content analyses")
        
        # 9. Check dsi_results table
        print("\n9. DSI RESULTS:")
        dsi_results = await conn.fetch(
            """
            SELECT * 
            FROM dsi_results 
            WHERE created_at >= NOW() - INTERVAL '10 minutes'
            LIMIT 5
            """
        )
        print(f"   Found {len(dsi_results)} recent DSI calculations")
        for dsi in dsi_results:
            print(f"   - Type: {dsi['dsi_type']}, Score: {dsi['total_score']}")
        
        # 10. Check pipeline_state table
        print("\n10. PIPELINE STATE TRACKING:")
        pipeline_state = await conn.fetch(
            """
            SELECT phase, status, COUNT(*) as count 
            FROM pipeline_state 
            WHERE pipeline_execution_id = $1
            GROUP BY phase, status
            ORDER BY phase
            """,
            pipeline_id
        )
        print(f"   Pipeline state by phase:")
        for ps in pipeline_state:
            print(f"   - Phase: {ps['phase']}, Status: {ps['status']}, Count: {ps['count']}")
        
    except Exception as e:
        logger.error(f"Error checking database: {e}")
    finally:
        await conn.close()

async def monitor_pipeline(pipeline_id: str, interval_seconds: int = 30):
    """Monitor pipeline database writes at regular intervals"""
    print(f"Starting database monitoring for pipeline {pipeline_id}")
    print(f"Checking every {interval_seconds} seconds...")
    
    check_count = 0
    while check_count < 20:  # Monitor for up to 10 minutes
        check_count += 1
        await check_database_writes(pipeline_id)
        await asyncio.sleep(interval_seconds)

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        pipeline_id = sys.argv[1]
    else:
        pipeline_id = "c803396f-340f-43e2-adee-6000840a33f0"  # Default to the pipeline we just started
    
    asyncio.run(monitor_pipeline(pipeline_id))
