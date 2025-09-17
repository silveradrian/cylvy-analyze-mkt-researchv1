import asyncio
import asyncpg
from app.core.config import settings

async def debug_url_filtering():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    pipeline_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    
    print("Debugging URL filtering issue...\n")
    
    # Get a sample URL that should be in both pipelines
    sample_url = await conn.fetchrow("""
        WITH overlap_urls AS (
            SELECT sr1.url, sr1.domain
            FROM serp_results sr1
            JOIN serp_results sr2 ON sr1.url = sr2.url
            WHERE sr1.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
            AND sr2.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        SELECT url, domain FROM overlap_urls LIMIT 1
    """)
    
    if sample_url:
        test_url = sample_url['url']
        print(f"Testing with URL: {test_url}")
        print(f"Domain: {sample_url['domain']}\n")
        
        # Check if it exists in scraped_content
        scraped_records = await conn.fetch("""
            SELECT url, pipeline_execution_id, status, created_at
            FROM scraped_content
            WHERE url = $1
            ORDER BY created_at DESC
        """, test_url)
        
        print(f"Scraped content records for this URL: {len(scraped_records)}")
        for record in scraped_records:
            print(f"  - Pipeline: {record['pipeline_execution_id']}")
            print(f"    Status: {record['status']}")
            print(f"    Created: {record['created_at']}")
        
        # Check URL normalization
        print(f"\n\nChecking URL variations...")
        
        # Look for similar URLs
        similar = await conn.fetch("""
            SELECT DISTINCT url, COUNT(*) as count
            FROM scraped_content
            WHERE url LIKE $1
            GROUP BY url
            ORDER BY count DESC
            LIMIT 5
        """, f"%{sample_url['domain']}%")[:5]
        
        print(f"Similar URLs in scraped_content:")
        for s in similar:
            print(f"  - {s['url'][:100]}... (scraped {s['count']} times)")
    
    # Check how many URLs should be filtered
    print(f"\n\nExpected filtering analysis:")
    
    should_be_filtered = await conn.fetchval("""
        WITH current_urls AS (
            SELECT DISTINCT url
            FROM serp_results
            WHERE pipeline_execution_id = $1
        ),
        already_scraped AS (
            SELECT DISTINCT url
            FROM scraped_content
            WHERE status = 'completed'
        )
        SELECT COUNT(*)
        FROM current_urls c
        JOIN already_scraped s ON c.url = s.url
    """, pipeline_id)
    
    print(f"URLs that SHOULD be filtered (already scraped): {should_be_filtered}")
    
    # Check the actual scraped_content linking
    print(f"\n\nActual pipeline linking:")
    
    linked_to_current = await conn.fetchval("""
        SELECT COUNT(DISTINCT url)
        FROM scraped_content
        WHERE pipeline_execution_id = $1
    """, pipeline_id)
    
    print(f"URLs linked to current pipeline in scraped_content: {linked_to_current}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(debug_url_filtering())
