import asyncio
import asyncpg
from app.core.config import settings

async def check_url_sharing():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    print("Checking URL sharing between pipelines...\n")
    
    # 1. How many URLs are shared between pipelines in serp_results?
    shared_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT sr1.url)
        FROM serp_results sr1
        JOIN serp_results sr2 ON sr1.url = sr2.url
        WHERE sr1.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        AND sr2.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"URLs appearing in both pipelines' SERP results: {shared_urls}")
    
    # 2. Of those shared URLs, how many were scraped by the previous pipeline?
    prev_scraped_shared = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        JOIN serp_results sr1 ON sc.url = sr1.url
        JOIN serp_results sr2 ON sr1.url = sr2.url
        WHERE sr1.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        AND sr2.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND sc.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND sc.status = 'completed'
    """)
    
    print(f"Shared URLs that were scraped by previous pipeline: {prev_scraped_shared}")
    
    # 3. Are these being filtered by the current pipeline?
    current_scraped_shared = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        WHERE sc.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        AND sc.url IN (
            SELECT DISTINCT sc2.url
            FROM scraped_content sc2
            WHERE sc2.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
            AND sc2.status = 'completed'
        )
    """)
    
    print(f"Shared URLs that were re-scraped by current pipeline: {current_scraped_shared}")
    
    # 4. Check the _filter_unscraped_urls logic
    print(f"\n\nTesting _filter_unscraped_urls logic...")
    
    # Get a sample of URLs that should have been filtered
    sample_urls = await conn.fetch("""
        SELECT DISTINCT sc.url
        FROM scraped_content sc
        JOIN serp_results sr ON sc.url = sr.url
        WHERE sc.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND sr.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        AND sc.status = 'completed'
        LIMIT 5
    """)
    
    if sample_urls:
        test_url = sample_urls[0]['url']
        print(f"\nTesting with URL that SHOULD have been filtered: {test_url[:80]}...")
        
        # Check scraped_content entries
        entries = await conn.fetch("""
            SELECT pipeline_execution_id, status, created_at
            FROM scraped_content
            WHERE url = $1
            ORDER BY created_at
        """, test_url)
        
        print(f"Found {len(entries)} entries in scraped_content:")
        for e in entries:
            print(f"  - Pipeline {e['pipeline_execution_id'][:8]}... status={e['status']} created={e['created_at']}")
    
    # 5. Check if it's a timing issue
    print(f"\n\nChecking scraping timeline...")
    
    timeline = await conn.fetch("""
        SELECT 
            pipeline_execution_id,
            MIN(created_at) as first_scrape,
            MAX(created_at) as last_scrape,
            COUNT(*) as urls_scraped
        FROM scraped_content
        WHERE pipeline_execution_id IN (
            '1a1bac89-8056-41ff-8f20-8e82ec67999f',
            '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        GROUP BY pipeline_execution_id
        ORDER BY MIN(created_at)
    """)
    
    for t in timeline:
        print(f"\nPipeline {t['pipeline_execution_id'][:8]}...")
        print(f"  First scrape: {t['first_scrape']}")
        print(f"  Last scrape: {t['last_scrape']}")
        print(f"  Total URLs: {t['urls_scraped']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_url_sharing())
