import asyncio
import asyncpg
from app.core.config import settings
import json

async def check_pipeline_config():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    pipeline_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    
    # Get pipeline configuration
    pipeline = await conn.fetchrow("""
        SELECT mode, config, phase_results, errors, started_at, completed_at
        FROM pipeline_executions
        WHERE id = $1
    """, pipeline_id)
    
    print(f"Pipeline Configuration Analysis:\n")
    print(f"Mode: {pipeline['mode']}")
    print(f"Started: {pipeline['started_at']}")
    
    config = json.loads(pipeline['config']) if pipeline['config'] else {}
    print(f"\nConfiguration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    
    # Check scraping status in detail
    print(f"\n\nDetailed Scraping Status:")
    
    # URLs scraped successfully
    successful = await conn.fetchval("""
        SELECT COUNT(DISTINCT url)
        FROM scraped_content
        WHERE pipeline_execution_id = $1
        AND status = 'completed'
    """, pipeline_id)
    
    # URLs that failed
    failed = await conn.fetchval("""
        SELECT COUNT(DISTINCT url)
        FROM scraped_content
        WHERE pipeline_execution_id = $1
        AND status = 'failed'
    """, pipeline_id)
    
    # Get sample of failed URLs
    failed_samples = await conn.fetch("""
        SELECT url, error_message
        FROM scraped_content
        WHERE pipeline_execution_id = $1
        AND status = 'failed'
        LIMIT 5
    """, pipeline_id)
    
    print(f"  Successful scrapes: {successful}")
    print(f"  Failed scrapes: {failed}")
    
    if failed_samples:
        print(f"\n  Sample failed URLs:")
        for f in failed_samples:
            print(f"    - {f['url'][:80]}...")
            if f['error_message']:
                print(f"      Error: {f['error_message'][:100]}...")
    
    # Check for URL normalization issues
    print(f"\n\nChecking URL variations...")
    
    # Find URLs that might be duplicates with different formats
    duplicates = await conn.fetch("""
        WITH url_variants AS (
            SELECT 
                url,
                REPLACE(REPLACE(url, 'https://', ''), 'http://', '') as normalized,
                COUNT(*) OVER (PARTITION BY REPLACE(REPLACE(url, 'https://', ''), 'http://', '')) as variant_count
            FROM scraped_content
            WHERE pipeline_execution_id = $1
        )
        SELECT url, normalized, variant_count
        FROM url_variants
        WHERE variant_count > 1
        ORDER BY variant_count DESC
        LIMIT 5
    """, pipeline_id)
    
    if duplicates:
        print(f"  Found URL variants that might be duplicates:")
        for d in duplicates:
            print(f"    - {d['normalized']} ({d['variant_count']} variants)")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_pipeline_config())
