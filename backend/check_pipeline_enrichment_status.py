import asyncio
import asyncpg
from app.core.config import settings

async def check_enrichment_status():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    pipeline_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    
    # 1. Get unique domains from SERP results for this pipeline
    serp_domains = await conn.fetch("""
        SELECT DISTINCT domain, COUNT(*) as occurrences
        FROM serp_results 
        WHERE pipeline_execution_id = $1
        AND domain IS NOT NULL
        GROUP BY domain
        ORDER BY occurrences DESC
    """, pipeline_id)
    
    total_domains = len(serp_domains)
    print(f"Total unique domains in SERP results: {total_domains}")
    
    # 2. Check how many were enriched IN THIS PIPELINE RUN
    enriched_in_pipeline = await conn.fetchval("""
        SELECT COUNT(DISTINCT cp.domain)
        FROM company_profiles cp
        WHERE cp.created_at >= (
            SELECT started_at FROM pipeline_executions WHERE id = $1
        )
        AND cp.domain IN (
            SELECT DISTINCT domain FROM serp_results WHERE pipeline_execution_id = $1
        )
    """, pipeline_id)
    
    # 3. Check total company profiles available (from any source)
    total_profiles = await conn.fetchval("""
        SELECT COUNT(DISTINCT cp.domain)
        FROM company_profiles cp
        WHERE cp.domain IN (
            SELECT DISTINCT domain FROM serp_results WHERE pipeline_execution_id = $1
        )
    """, pipeline_id)
    
    # 4. Check content scraping status
    scraped_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT sc.url)
        FROM scraped_content sc
        INNER JOIN serp_results sr ON sr.url = sc.url
        WHERE sr.pipeline_execution_id = $1
        AND sc.status = 'completed'
    """, pipeline_id)
    
    total_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT url)
        FROM serp_results
        WHERE pipeline_execution_id = $1
    """, pipeline_id)
    
    # 5. Check content analysis status
    analyzed_urls = await conn.fetchval("""
        SELECT COUNT(DISTINCT oca.url)
        FROM optimized_content_analysis oca
        INNER JOIN serp_results sr ON sr.url = oca.url
        WHERE sr.pipeline_execution_id = $1
    """, pipeline_id)
    
    print(f"\nCompany Enrichment Status:")
    print(f"  - Total domains to enrich: {total_domains}")
    print(f"  - Enriched in this pipeline: {enriched_in_pipeline}")
    print(f"  - Total profiles available: {total_profiles}")
    print(f"  - Enrichment completion: {(total_profiles/total_domains*100):.1f}%")
    
    print(f"\nContent Scraping Status:")
    print(f"  - Total URLs: {total_urls}")
    print(f"  - Scraped URLs: {scraped_urls}")
    print(f"  - Scraping completion: {(scraped_urls/total_urls*100):.1f}%")
    
    print(f"\nContent Analysis Status:")
    print(f"  - Analyzed URLs: {analyzed_urls}")
    print(f"  - Analysis completion: {(analyzed_urls/scraped_urls*100 if scraped_urls > 0 else 0):.1f}%")
    
    # Check if DSI requirements are met
    enrichment_complete = (total_profiles/total_domains) >= 0.90  # 90% tolerance
    scraping_complete = (scraped_urls/total_urls) >= 0.90  # 90% tolerance
    analysis_complete = (analyzed_urls/scraped_urls) >= 0.90 if scraped_urls > 0 else False
    
    print(f"\nDSI Calculation Requirements:")
    print(f"  - Company enrichment ≥90%: {'✅' if enrichment_complete else '❌'} ({(total_profiles/total_domains*100):.1f}%)")
    print(f"  - Content scraping ≥90%: {'✅' if scraping_complete else '❌'} ({(scraped_urls/total_urls*100):.1f}%)")
    print(f"  - Content analysis ≥90%: {'✅' if analysis_complete else '❌'} ({(analyzed_urls/scraped_urls*100 if scraped_urls > 0 else 0):.1f}%)")
    print(f"\nCAN CALCULATE DSI: {'YES' if all([enrichment_complete, scraping_complete, analysis_complete]) else 'NO'}")
    
    # Show some missing domains
    if enrichment_complete < 1.0:
        print(f"\nSample domains needing enrichment:")
        missing_domains = await conn.fetch("""
            SELECT DISTINCT sr.domain, COUNT(*) as occurrences
            FROM serp_results sr
            LEFT JOIN company_profiles cp ON sr.domain = cp.domain
            WHERE sr.pipeline_execution_id = $1
            AND cp.domain IS NULL
            GROUP BY sr.domain
            ORDER BY occurrences DESC
            LIMIT 10
        """, pipeline_id)
        for d in missing_domains:
            print(f"  - {d['domain']} ({d['occurrences']} occurrences)")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_enrichment_status())
