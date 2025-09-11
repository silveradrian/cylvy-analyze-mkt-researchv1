#!/usr/bin/env python3
"""
Purge Pipeline Data Script

This script removes all pipeline execution data while preserving:
- Company configuration
- Personas and JTBD phases
- Custom dimensions
- Keywords
- API keys and system configuration

Perfect for testing and optimization without reconfiguring.
"""

import asyncio
import sys
from datetime import datetime

# Add app to path
sys.path.append('/app')

from app.core.database import db_pool
from app.core.config import settings


async def purge_pipeline_data():
    """Purge all pipeline execution data."""
    print("\n=== Purging Pipeline Execution Data ===")
    
    async with db_pool.acquire() as conn:
        # Start transaction
        async with conn.transaction():
            # 1. Delete analysis results
            print("\n📊 Clearing analysis data...")
            count = await conn.fetchval("SELECT COUNT(*) FROM optimized_content_analysis")
            if count:
                await conn.execute("DELETE FROM analysis_primary_dimensions")
                await conn.execute("DELETE FROM optimized_dimension_analysis")
                await conn.execute("DELETE FROM optimized_content_analysis")
                print(f"  ✓ Deleted {count} content analyses")
            
            # 2. Delete scraped content
            print("\n📄 Clearing scraped content...")
            count = await conn.fetchval("SELECT COUNT(*) FROM scraped_content")
            if count:
                await conn.execute("DELETE FROM scraped_content_summaries")
                await conn.execute("DELETE FROM scraped_content")
                print(f"  ✓ Deleted {count} scraped pages")
            
            # 3. Delete YouTube data
            print("\n📺 Clearing YouTube data...")
            video_count = await conn.fetchval("SELECT COUNT(*) FROM youtube_videos")
            channel_count = await conn.fetchval("SELECT COUNT(*) FROM youtube_channels")
            if video_count or channel_count:
                await conn.execute("DELETE FROM video_snapshots")
                await conn.execute("DELETE FROM youtube_videos")
                await conn.execute("DELETE FROM youtube_channels")
                print(f"  ✓ Deleted {channel_count} channels and {video_count} videos")
            
            # 4. Delete SERP results
            print("\n🔍 Clearing SERP data...")
            serp_count = await conn.fetchval("SELECT COUNT(*) FROM serp_results")
            if serp_count:
                # Check if news and video results tables exist before deleting
                tables_exist = await conn.fetch("""
                    SELECT tablename FROM pg_tables 
                    WHERE schemaname = 'public' 
                    AND tablename IN ('serp_news_results', 'serp_video_results', 'serp_batch_results', 'serp_batches')
                """)
                existing_tables = [row['tablename'] for row in tables_exist]
                
                if 'serp_news_results' in existing_tables:
                    await conn.execute("DELETE FROM serp_news_results")
                if 'serp_video_results' in existing_tables:
                    await conn.execute("DELETE FROM serp_video_results")
                await conn.execute("DELETE FROM serp_results")
                if 'serp_batch_results' in existing_tables:
                    await conn.execute("DELETE FROM serp_batch_results")
                if 'serp_batches' in existing_tables:
                    await conn.execute("DELETE FROM serp_batches")
                print(f"  ✓ Deleted {serp_count} SERP results")
            
            # 5. Delete company enrichment data (but keep client_config)
            print("\n🏢 Clearing company enrichment data...")
            count = await conn.fetchval("SELECT COUNT(*) FROM enriched_companies")
            if count:
                await conn.execute("DELETE FROM company_domains")
                await conn.execute("DELETE FROM enriched_companies")
                print(f"  ✓ Deleted {count} enriched companies")
            
            # 6. Delete DSI scores
            print("\n📈 Clearing DSI scores...")
            count = await conn.fetchval("SELECT COUNT(*) FROM dsi_scores")
            if count:
                await conn.execute("DELETE FROM dsi_scores")
                print(f"  ✓ Deleted {count} DSI scores")
            
            # 7. Delete pipeline runs
            print("\n⚙️ Clearing pipeline execution history...")
            run_count = await conn.fetchval("SELECT COUNT(*) FROM pipeline_runs")
            if run_count:
                await conn.execute("DELETE FROM pipeline_phase_runs")
                await conn.execute("DELETE FROM pipeline_runs")
                print(f"  ✓ Deleted {run_count} pipeline runs")
            
            # 8. Delete historical keyword metrics (optional - keeping for now)
            # print("\n📊 Clearing historical keyword metrics...")
            # count = await conn.fetchval("SELECT COUNT(*) FROM historical_keyword_metrics")
            # if count:
            #     await conn.execute("DELETE FROM historical_keyword_metrics")
            #     print(f"  ✓ Deleted {count} historical metrics")
            
            print("\n✅ Pipeline data purged successfully!")


async def show_retained_data():
    """Show what configuration data was retained."""
    print("\n=== Retained Configuration Data ===")
    
    async with db_pool.acquire() as conn:
        # Company config
        company = await conn.fetchrow("SELECT company_name, legal_name FROM client_config LIMIT 1")
        if company:
            print(f"\n🏢 Company: {company['company_name']} ({company['legal_name']})")
            
            # Count domains
            domains = await conn.fetchval("""
                SELECT array_length(additional_domains, 1) + 1 
                FROM client_config 
                LIMIT 1
            """)
            print(f"  - Domains: {domains or 1}")
            
            # Count competitors
            competitors = await conn.fetchval("""
                SELECT array_length(competitors, 1) 
                FROM client_config 
                LIMIT 1
            """)
            print(f"  - Competitors: {competitors or 0}")
        
        # Personas
        analysis = await conn.fetchrow("SELECT personas FROM analysis_config LIMIT 1")
        if analysis and analysis['personas']:
            personas = analysis['personas']
            if isinstance(personas, str):
                import json
                personas = json.loads(personas)
            print(f"\n👥 Personas: {len(personas)}")
            for p in personas[:3]:  # Show first 3
                print(f"  - {p['name']}")
        
        # JTBD Phases
        if analysis:
            jtbd_phases = await conn.fetchval("""
                SELECT jtbd_phases FROM analysis_config LIMIT 1
            """)
            if jtbd_phases:
                if isinstance(jtbd_phases, str):
                    import json
                    jtbd_phases = json.loads(jtbd_phases)
                print(f"\n🎯 JTBD Phases: {len(jtbd_phases)}")
                for phase in jtbd_phases[:3]:  # Show first 3
                    print(f"  - {phase.get('phase', phase.get('name', 'Unknown'))}")
        
        # Custom dimensions
        dimension_count = await conn.fetchval("SELECT COUNT(*) FROM generic_custom_dimensions")
        print(f"\n📐 Custom Dimensions: {dimension_count}")
        
        dimensions = await conn.fetch("""
            SELECT name, ai_context->>'scope' as scope 
            FROM generic_custom_dimensions 
            ORDER BY name 
            LIMIT 6
        """)
        for dim in dimensions:
            print(f"  - {dim['name']} ({dim['scope']})")
        
        # Keywords
        keyword_count = await conn.fetchval("SELECT COUNT(*) FROM keywords")
        print(f"\n🔑 Keywords: {keyword_count}")
        
        # Show top keywords
        top_keywords = await conn.fetch("""
            SELECT keyword, composite_score 
            FROM keywords 
            ORDER BY composite_score DESC 
            LIMIT 3
        """)
        for kw in top_keywords:
            print(f"  - {kw['keyword']} (score: {kw['composite_score']})")


async def main():
    """Main function."""
    print("=== Pipeline Data Purge Utility ===")
    print(f"Started at: {datetime.utcnow().isoformat()}")
    print("\n⚠️  This will DELETE all pipeline execution data!")
    print("Configuration (company, personas, dimensions, keywords) will be preserved.")
    
    # Confirm
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n❌ Cancelled")
        return
    
    try:
        await db_pool.initialize()
        await purge_pipeline_data()
        await show_retained_data()
        
        print("\n✅ Purge completed successfully!")
        print("\nYou can now run a fresh pipeline test with:")
        print("  docker exec -it cylvy-analyze-mkt-analysis-backend-1 python start_pipeline.py")
        
    except Exception as e:
        print(f"\n❌ Purge failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
