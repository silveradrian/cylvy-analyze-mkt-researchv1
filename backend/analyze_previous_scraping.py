import asyncio
import asyncpg
from app.core.config import settings

async def analyze_previous_scraping():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    print("Analyzing what the previous pipeline actually scraped...\n")
    
    # What domains did the previous pipeline scrape?
    prev_scraped_domains = await conn.fetch("""
        SELECT domain, COUNT(*) as count
        FROM scraped_content
        WHERE pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        AND status = 'completed'
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 10
    """)
    
    print("Top domains scraped by previous pipeline:")
    for d in prev_scraped_domains:
        print(f"  - {d['domain']}: {d['count']} URLs")
    
    # Compare with current pipeline's top domains
    print("\n\nTop domains in current pipeline SERP results:")
    
    current_domains = await conn.fetch("""
        SELECT domain, COUNT(*) as count
        FROM serp_results
        WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        GROUP BY domain
        ORDER BY count DESC
        LIMIT 10
    """)
    
    for d in current_domains:
        print(f"  - {d['domain']}: {d['count']} URLs")
    
    # Check if previous pipeline had different search parameters
    print("\n\nChecking search parameters...")
    
    # Get keyword/region combinations
    prev_params = await conn.fetch("""
        SELECT DISTINCT k.keyword, sr.location, sr.serp_type, COUNT(*) as results
        FROM serp_results sr
        JOIN keywords k ON sr.keyword_id = k.id
        WHERE sr.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
        GROUP BY k.keyword, sr.location, sr.serp_type
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """)
    
    print("\nPrevious pipeline search parameters (top 5):")
    for p in prev_params:
        print(f"  - {p['keyword']} | {p['location']} | {p['serp_type']} | {p['results']} results")
    
    current_params = await conn.fetch("""
        SELECT DISTINCT k.keyword, sr.location, sr.serp_type, COUNT(*) as results
        FROM serp_results sr
        JOIN keywords k ON sr.keyword_id = k.id
        WHERE sr.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        GROUP BY k.keyword, sr.location, sr.serp_type
        ORDER BY COUNT(*) DESC
        LIMIT 5
    """)
    
    print("\nCurrent pipeline search parameters (top 5):")
    for p in current_params:
        print(f"  - {p['keyword']} | {p['location']} | {p['serp_type']} | {p['results']} results")
    
    # Check if scraped URLs match SERP results
    print("\n\nAnalyzing scraping pattern...")
    
    prev_scraping_match = await conn.fetchrow("""
        SELECT 
            COUNT(DISTINCT sc.url) as scraped_urls,
            COUNT(DISTINCT sr.url) as serp_urls,
            COUNT(DISTINCT CASE WHEN sc.url = sr.url THEN sc.url END) as matching_urls
        FROM serp_results sr
        LEFT JOIN scraped_content sc ON sc.url = sr.url AND sc.pipeline_execution_id = sr.pipeline_execution_id
        WHERE sr.pipeline_execution_id = '9d27a991-150e-4110-8432-ee4afce5fb10'
    """)
    
    print(f"\nPrevious pipeline scraping analysis:")
    print(f"  SERP URLs: {prev_scraping_match['serp_urls']}")
    print(f"  Scraped URLs: {prev_scraping_match['scraped_urls']}")
    print(f"  Matching (scraped from SERP): {prev_scraping_match['matching_urls']}")
    print(f"  Non-SERP scraped URLs: {prev_scraping_match['scraped_urls'] - prev_scraping_match['matching_urls']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_previous_scraping())
