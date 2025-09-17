import asyncio
import asyncpg
from app.core.config import settings

async def check_scraping_overlap():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    pipeline_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    
    print("Analyzing URL scraping overlap...\n")
    
    # 1. Get all URLs from this pipeline's SERP results
    pipeline_urls = await conn.fetch("""
        SELECT DISTINCT url
        FROM serp_results 
        WHERE pipeline_execution_id = $1
    """, pipeline_id)
    
    total_urls = len(pipeline_urls)
    print(f"Total URLs in pipeline SERP results: {total_urls}")
    
    # 2. Check how many were already scraped (from ANY source/pipeline)
    already_scraped = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        WHERE sc.url IN (
            SELECT DISTINCT url FROM serp_results 
            WHERE pipeline_execution_id = $1
        )
        AND sc.status = 'completed'
    """, pipeline_id)
    
    # 3. Check how many were scraped SPECIFICALLY by this pipeline
    scraped_by_pipeline = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        WHERE sc.pipeline_execution_id = $1
        AND sc.status = 'completed'
    """, pipeline_id)
    
    # 4. Check overlap with previous pipelines
    overlap_with_previous = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        WHERE sc.url IN (
            SELECT DISTINCT url FROM serp_results 
            WHERE pipeline_execution_id = $1
        )
        AND sc.pipeline_execution_id != $1
        AND sc.status = 'completed'
    """, pipeline_id)
    
    # 5. Get truly new URLs (never scraped before)
    new_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT sr.url)
        FROM serp_results sr
        LEFT JOIN scraped_content sc ON sr.url = sc.url AND sc.status = 'completed'
        WHERE sr.pipeline_execution_id = $1
        AND sc.url IS NULL
    """, pipeline_id)
    
    print(f"\nScraping Analysis:")
    print(f"  - Already scraped (from any source): {already_scraped} ({already_scraped/total_urls*100:.1f}%)")
    print(f"  - Scraped by THIS pipeline: {scraped_by_pipeline}")
    print(f"  - Scraped by PREVIOUS pipelines: {overlap_with_previous} ({overlap_with_previous/total_urls*100:.1f}%)")
    print(f"  - Truly NEW URLs to scrape: {new_urls} ({new_urls/total_urls*100:.1f}%)")
    
    # 6. Show sample of new URLs
    if new_urls > 0:
        print(f"\nSample of new URLs that need scraping:")
        sample_new = await conn.fetch("""
            SELECT DISTINCT sr.url, sr.title, sr.domain
            FROM serp_results sr
            LEFT JOIN scraped_content sc ON sr.url = sc.url AND sc.status = 'completed'
            WHERE sr.pipeline_execution_id = $1
            AND sc.url IS NULL
            ORDER BY sr.position
            LIMIT 10
        """, pipeline_id)
        for url in sample_new:
            print(f"  - {url['domain']}: {url['title'][:60]}...")
    
    # 7. Check content analysis overlap
    analyzed_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT oca.url)
        FROM optimized_content_analysis oca
        WHERE oca.url IN (
            SELECT DISTINCT url FROM serp_results 
            WHERE pipeline_execution_id = $1
        )
    """, pipeline_id)
    
    print(f"\nContent Analysis:")
    print(f"  - Total analyzed (from scraped): {analyzed_urls} ({analyzed_urls/already_scraped*100 if already_scraped > 0 else 0:.1f}%)")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_scraping_overlap())
