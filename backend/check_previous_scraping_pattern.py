import asyncio
import asyncpg
from app.core.config import settings

async def check_scraping_pattern():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    print("Analyzing previous pipeline's scraping pattern...\n")
    
    # 1. What did previous pipeline scrape?
    prev_scraped = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        WHERE sc.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    # 2. How many of those were actually from its SERP results?
    prev_scraped_from_serp = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        JOIN serp_results sr ON sc.url = sr.url AND sc.pipeline_execution_id = sr.pipeline_execution_id
        WHERE sc.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"Previous pipeline scraped: {prev_scraped:,} URLs")
    print(f"Of those, from its own SERP results: {prev_scraped_from_serp:,}")
    print(f"Scraped from other sources: {prev_scraped - prev_scraped_from_serp:,}")
    
    # 3. What types of URLs did it scrape?
    print("\n\nTop scraped domains by previous pipeline:")
    domains = await conn.fetch("""
        SELECT domain, COUNT(*) as count
        FROM scraped_content
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 10
    """)
    
    for d in domains:
        print(f"  {d['domain']}: {d['count']:,}")
    
    # 4. What types were in SERP?
    print("\n\nTop SERP types for previous pipeline:")
    serp_types = await conn.fetch("""
        SELECT serp_type, COUNT(*) as count
        FROM serp_results
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        GROUP BY serp_type
        ORDER BY count DESC
    """)
    
    for st in serp_types:
        print(f"  {st['serp_type']}: {st['count']:,}")
    
    # 5. Did it scrape the video URLs?
    video_urls = await conn.fetchval("""
        SELECT COUNT(*)
        FROM serp_results
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND serp_type = 'video'
    """)
    
    video_scraped = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        JOIN serp_results sr ON sc.url = sr.url
        WHERE sr.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND sr.serp_type = 'video'
        AND sc.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"\n\nVideo URL analysis:")
    print(f"  Video URLs in SERP: {video_urls:,}")
    print(f"  Video URLs scraped: {video_scraped:,}")
    
    # 6. Current pipeline scraping pattern
    print("\n\nCurrent pipeline scraping pattern:")
    current_by_type = await conn.fetch("""
        SELECT sr.serp_type, 
               COUNT(DISTINCT sr.url) as serp_count,
               COUNT(DISTINCT sc.url) as scraped_count
        FROM serp_results sr
        LEFT JOIN scraped_content sc ON sr.url = sc.url AND sr.pipeline_execution_id = sc.pipeline_execution_id
        WHERE sr.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        GROUP BY sr.serp_type
    """)
    
    for ct in current_by_type:
        pct = (ct['scraped_count'] / ct['serp_count'] * 100) if ct['serp_count'] > 0 else 0
        print(f"  {ct['serp_type']}: {ct['scraped_count']:,}/{ct['serp_count']:,} ({pct:.1f}%)")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_scraping_pattern())
