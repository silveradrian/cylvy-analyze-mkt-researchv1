import asyncio
import asyncpg
from app.core.config import settings

async def analyze_overlap():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    # Compare URLs between pipelines
    print("Comparing URL overlap between pipelines...\n")
    
    # Get domain overlap between current and previous pipeline
    overlap = await conn.fetchval("""
        WITH current_domains AS (
            SELECT DISTINCT domain
            FROM serp_results
            WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        ),
        previous_domains AS (
            SELECT DISTINCT domain
            FROM serp_results
            WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        )
        SELECT COUNT(*)
        FROM current_domains c
        JOIN previous_domains p ON c.domain = p.domain
    """)
    
    current_total = await conn.fetchval("""
        SELECT COUNT(DISTINCT domain)
        FROM serp_results
        WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    previous_total = await conn.fetchval("""
        SELECT COUNT(DISTINCT domain)
        FROM serp_results  
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"Domain Analysis:")
    print(f"  Current pipeline domains: {current_total}")
    print(f"  Previous pipeline domains: {previous_total}")
    print(f"  Overlapping domains: {overlap}")
    print(f"  New domains in current: {current_total - overlap}")
    print(f"  Overlap percentage: {overlap/current_total*100:.1f}%")
    
    # Check scraped content dates
    print(f"\n\nScraping Timeline:")
    
    dates = await conn.fetch("""
        SELECT 
            DATE(created_at) as scrape_date,
            COUNT(*) as urls_scraped,
            COUNT(DISTINCT pipeline_execution_id) as pipelines
        FROM scraped_content
        WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY DATE(created_at)
        ORDER BY scrape_date DESC
        LIMIT 10
    """)
    
    for d in dates:
        print(f"  {d['scrape_date']}: {d['urls_scraped']} URLs from {d['pipelines']} pipeline(s)")
    
    # Check if scraping was actually done for previous URLs
    print(f"\n\nChecking if previous pipeline URLs were scraped...")
    
    previous_scraped = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        JOIN serp_results sr ON sc.url = sr.url
        WHERE sr.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND sc.status = 'completed'
    """)
    
    previous_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT url)
        FROM serp_results
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"  Previous pipeline had {previous_urls} URLs")
    print(f"  Previous pipeline scraped {previous_scraped} URLs ({previous_scraped/previous_urls*100:.1f}%)")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_overlap())
