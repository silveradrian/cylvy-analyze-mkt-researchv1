import asyncio
import asyncpg
from app.core.config import settings

async def check_dsi_data():
    conn = await asyncpg.connect(settings.DATABASE_URL)
    
    # Check SERP results
    serp_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT url) 
        FROM serp_results 
        WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    # Check domains
    domain_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT domain) 
        FROM serp_results 
        WHERE pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
        AND domain IS NOT NULL
    """)
    
    # Check content analysis
    analysis_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT oca.url)
        FROM optimized_content_analysis oca
        INNER JOIN serp_results sr ON sr.url = oca.url
        WHERE sr.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    # Check company profiles (even if enrichment failed)
    company_count = await conn.fetchval("""
        SELECT COUNT(DISTINCT cp.domain)
        FROM company_profiles cp
        INNER JOIN serp_results sr ON sr.domain = cp.domain
        WHERE sr.pipeline_execution_id = '1a1bac89-8056-41ff-8f20-8e82ec67999f'
    """)
    
    print(f"Pipeline 1a1bac89 data availability:")
    print(f"  SERP results: {serp_count}")
    print(f"  Unique domains: {domain_count}")
    print(f"  Content analyzed: {analysis_count}")
    print(f"  Company profiles available: {company_count}")
    print(f"\nDSI calculation requirements:")
    print(f"  - SERP results with domains: {'✓' if domain_count > 0 else '✗'}")
    print(f"  - Content analysis (optional but helpful): {'✓' if analysis_count > 0 else '✗'}")
    print(f"  - Company profiles (optional, will use domain fallback): {'✓' if company_count > 0 else '✗'}")
    print(f"\nCAN CALCULATE DSI: {'YES' if domain_count > 0 else 'NO'}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_dsi_data())
