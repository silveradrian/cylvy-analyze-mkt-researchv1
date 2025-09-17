import asyncio
import asyncpg
from app.core.config import settings
from datetime import datetime

async def investigate_url_tracking():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    print("Investigating URL tracking issue...\n")
    
    # 1. Check timeline - when did pipelines run?
    pipelines = await conn.fetch("""
        SELECT id, started_at, completed_at, 
               keywords_processed, serp_results_collected
        FROM pipeline_executions
        WHERE id IN (
            '1a1bac89-8056-41ff-8f20-8e82ec67999f',
            '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        ORDER BY started_at DESC
    """)
    
    print("Pipeline Timeline:")
    for p in pipelines:
        print(f"  {str(p['id'])[:8]}... Started: {p['started_at']}, SERP results: {p['serp_results_collected']}")
    
    # 2. Take a specific keyword that should be in both
    print("\n\nChecking a specific keyword's URLs across pipelines...")
    
    keyword_urls = await conn.fetch("""
        WITH keyword_in_both AS (
            SELECT k.id, k.keyword
            FROM keywords k
            WHERE k.keyword IN (
                SELECT DISTINCT k2.keyword
                FROM serp_results sr1
                JOIN keywords k2 ON sr1.keyword_id = k2.id
                WHERE sr1.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
                INTERSECT
                SELECT DISTINCT k3.keyword
                FROM serp_results sr2
                JOIN keywords k3 ON sr2.keyword_id = k3.id
                WHERE sr2.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
            )
            LIMIT 1
        )
        SELECT 
            kib.keyword,
            sr.pipeline_execution_id,
            COUNT(DISTINCT sr.url) as url_count,
            ARRAY_AGG(DISTINCT sr.url ORDER BY sr.position LIMIT 5) as sample_urls
        FROM keyword_in_both kib
        JOIN serp_results sr ON sr.keyword_id = kib.id
        WHERE sr.pipeline_execution_id IN (
            '1a1bac89-8056-41ff-8f20-8e82ec67999f',
            '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        GROUP BY kib.keyword, sr.pipeline_execution_id
    """)
    
    if keyword_urls:
        print(f"Keyword: {keyword_urls[0]['keyword']}")
        for ku in keyword_urls:
            print(f"\n  Pipeline {str(ku['pipeline_execution_id'])[:8]}...")
            print(f"  Total URLs: {ku['url_count']}")
            print(f"  Sample URLs:")
            for url in ku['sample_urls'][:3]:
                print(f"    - {url[:80]}...")
    
    # 3. Check if there's a pipeline_execution_id issue in scraped_content
    print("\n\nChecking scraped_content pipeline linking...")
    
    sc_stats = await conn.fetch("""
        SELECT 
            pipeline_execution_id,
            COUNT(*) as total_scraped,
            COUNT(DISTINCT url) as unique_urls,
            MIN(created_at) as first_scrape,
            MAX(created_at) as last_scrape
        FROM scraped_content
        WHERE pipeline_execution_id IN (
            '1a1bac89-8056-41ff-8f20-8e82ec67999f',
            '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        OR pipeline_execution_id IS NULL
        GROUP BY pipeline_execution_id
    """)
    
    for s in sc_stats:
        print(f"\nPipeline: {s['pipeline_execution_id'] or 'NULL'}")
        print(f"  Total scraped: {s['total_scraped']}")
        print(f"  Unique URLs: {s['unique_urls']}")
        print(f"  First: {s['first_scrape']}, Last: {s['last_scrape']}")
    
    # 4. Check for orphaned scraped content
    orphaned = await conn.fetchval("""
        SELECT COUNT(*)
        FROM scraped_content
        WHERE pipeline_execution_id IS NULL
        AND created_at >= '2025-09-15'
    """)
    
    print(f"\n\nOrphaned scraped content (no pipeline_id): {orphaned}")
    
    # 5. Direct check - are URLs being stored without pipeline_execution_id?
    sample_check = await conn.fetch("""
        SELECT url, pipeline_execution_id, created_at
        FROM scraped_content
        WHERE url IN (
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
            LIMIT 10
        )
        ORDER BY created_at DESC
    """)
    
    print(f"\n\nSample URL check (should show previous scrapes):")
    for sc in sample_check[:5]:
        print(f"  URL: {sc['url'][:60]}...")
        print(f"    Pipeline: {sc['pipeline_execution_id'] or 'NULL'}")
        print(f"    Created: {sc['created_at']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(investigate_url_tracking())
