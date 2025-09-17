import asyncio
import asyncpg
from app.core.config import settings

async def check_url_overlap():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    print("Checking URL overlap between pipelines...\n")
    
    # 1. Get URL counts
    current_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT url) 
        FROM serp_results 
        WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    previous_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT url) 
        FROM serp_results 
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"Current pipeline URLs: {current_urls:,}")
    print(f"Previous pipeline URLs: {previous_urls:,}")
    
    # 2. Check direct overlap
    overlap_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT url) FROM (
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
            INTERSECT
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        ) as overlap
    """)
    
    print(f"Overlapping URLs: {overlap_count:,} ({overlap_count/current_urls*100:.1f}% of current)")
    
    # 3. Check which overlapping URLs were scraped by previous pipeline
    scraped_overlap = await conn.fetchval("""
        WITH overlapping_urls AS (
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
            INTERSECT
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        JOIN overlapping_urls ou ON sc.url = ou.url
        WHERE sc.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND sc.status = 'completed'
    """)
    
    print(f"\nOverlapping URLs scraped by previous pipeline: {scraped_overlap:,}")
    
    # 4. Check if current pipeline is re-scraping these
    rescraped = await conn.fetchval("""
        WITH overlapping_urls AS (
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
            INTERSECT
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        JOIN overlapping_urls ou ON sc.url = ou.url
        WHERE sc.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    print(f"Overlapping URLs re-scraped by current pipeline: {rescraped:,}")
    
    # 5. Sample overlapping URL to see what happened
    sample = await conn.fetchrow("""
        WITH overlapping_urls AS (
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
            INTERSECT
            SELECT url FROM serp_results 
            WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        SELECT url FROM overlapping_urls LIMIT 1
    """)
    
    if sample:
        print(f"\n\nSample overlapping URL: {sample['url'][:80]}...")
        
        # Check its scraping history
        history = await conn.fetch("""
            SELECT pipeline_execution_id, status, created_at
            FROM scraped_content
            WHERE url = $1
            ORDER BY created_at
        """, sample['url'])
        
        print(f"Scraping history:")
        for h in history:
            print(f"  Pipeline {str(h['pipeline_execution_id'])[:8]}...: {h['status']} at {h['created_at']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_url_overlap())
