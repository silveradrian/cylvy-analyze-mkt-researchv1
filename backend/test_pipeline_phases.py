"""
Test Pipeline Phases Individually
Run each phase one by one to ensure they work correctly
"""

import asyncio
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4

# Add parent directory to path
sys.path.append('/app')

from loguru import logger
from app.core.config import get_settings
from app.core.database import get_db, db_pool
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig


class PhaseTestRunner:
    """Test runner for individual pipeline phases"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = None
        self.pipeline_service = None
        self.pipeline_id = uuid4()
        self.results = {}
        self.project_keywords = []
        self.project_config = None
        self.test_keyword_count = 5  # Default number of keywords to test with
        
    async def initialize(self):
        """Initialize services and load project data"""
        self.db = await get_db()
        self.pipeline_service = PipelineService(self.settings, self.db)
        
        # Load active project keywords
        await self._load_project_data()
        
        logger.info("✅ Initialized test runner")
        logger.info(f"📋 Project has {len(self.project_keywords)} keywords")
        
    async def _load_project_data(self):
        """Load project keywords and configuration"""
        async with db_pool.acquire() as conn:
            # Get all keywords from the project
            keywords_data = await conn.fetch("""
                SELECT id, keyword, category 
                FROM keywords 
                ORDER BY keyword
            """)
            
            self.project_keywords = [row['keyword'] for row in keywords_data]
            
            # Get project configuration
            config_data = await conn.fetchrow("""
                SELECT * FROM analysis_config LIMIT 1
            """)
            
            if config_data:
                self.project_config = dict(config_data)
                logger.info(f"📋 Loaded project config: regions={config_data.get('supported_regions', ['US', 'UK'])}")
            else:
                logger.warning("⚠️ No project configuration found, using defaults")
                self.project_config = {
                    'supported_regions': ['US', 'UK'],
                    'content_types': ['organic', 'news', 'video']
                }
            
            # Log some sample keywords
            if self.project_keywords:
                logger.info(f"📋 Sample keywords: {self.project_keywords[:5]}...")
    
    async def _create_test_pipeline_execution(self):
        """Create a test pipeline execution record"""
        async with db_pool.acquire() as conn:
            # Create pipeline execution record
            await conn.execute("""
                INSERT INTO pipeline_executions (
                    id, status, mode, started_at
                ) VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO NOTHING
            """, 
            self.pipeline_id,
            "running",
            "BATCH_OPTIMIZED",
            datetime.now()
            )
    
    async def test_phase_1_keyword_metrics(self) -> Dict[str, Any]:
        """Test Phase 1: Keyword Metrics Enrichment"""
        logger.info("\n" + "="*60)
        logger.info("📊 PHASE 1: KEYWORD METRICS ENRICHMENT")
        logger.info("="*60)
        
        # Use project keywords (or a subset for testing)
        test_keywords = self.project_keywords[:self.test_keyword_count] if self.project_keywords else []
        if not test_keywords:
            logger.error("❌ No keywords found in project")
            return {"success": False, "error": "No keywords in project"}
        
        logger.info(f"Testing with {len(test_keywords)} keywords: {test_keywords}")
        
        config = PipelineConfig(
            client_id="test",
            keywords=test_keywords,  # Use actual project keywords
            regions=self.project_config.get('supported_regions', ['US', 'UK']),
            content_types=["organic"],  # Focus on keyword metrics
            enable_keyword_metrics=True,
            enable_company_enrichment=False,
            enable_video_enrichment=False,
            enable_content_analysis=False,
            enable_historical_tracking=False,
            enable_landscape_dsi=False
        )
        
        try:
            # Test keyword metrics phase
            result = await self.pipeline_service._execute_keyword_metrics_enrichment_phase(
                config, 
                self.pipeline_id
            )
            
            self.results['keyword_metrics'] = result
            
            # Validate results
            if result.get('keywords_with_metrics', 0) > 0:
                logger.info(f"✅ Phase 1 SUCCESS: {result['keywords_with_metrics']} keywords enriched")
                logger.info(f"   Countries: {list(result.get('country_results', {}).keys())}")
                
                # Show sample metrics
                for country, data in result.get('country_results', {}).items():
                    logger.info(f"   {country}: {data['keywords_processed']} keywords, "
                              f"avg searches: {data.get('avg_monthly_searches', 0)}")
            else:
                logger.error("❌ Phase 1 FAILED: No keywords enriched")
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 1 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_2_serp_collection(self) -> Dict[str, Any]:
        """Test Phase 2: SERP Collection"""
        logger.info("\n" + "="*60)
        logger.info("🔍 PHASE 2: SERP COLLECTION")
        logger.info("="*60)
        
        # Use more project keywords (5 keywords for better testing)
        serp_test_count = min(self.test_keyword_count, 5)  # Use up to 5 keywords
        test_keywords = self.project_keywords[:serp_test_count] if self.project_keywords else []
        if not test_keywords:
            logger.error("❌ No keywords found in project")
            return {"success": False, "error": "No keywords in project"}
        
        logger.info(f"Testing SERP collection with {len(test_keywords)} keywords: {test_keywords}")
        
        # Create pipeline execution record first
        await self._create_test_pipeline_execution()
        
        config = PipelineConfig(
            client_id="test",
            keywords=test_keywords,  # Use actual project keywords
            regions=self.project_config.get('supported_regions', ['US', 'UK']),  # Test with both regions
            content_types=["organic", "news", "video"],
            enable_keyword_metrics=False,
            enable_company_enrichment=False,
            enable_video_enrichment=False,
            enable_content_analysis=False,
            enable_historical_tracking=False,
            enable_landscape_dsi=False,
            force_refresh=True
        )
        
        try:
            # Test SERP collection phase
            result = await self.pipeline_service._execute_serp_collection_phase(
                config,
                self.pipeline_id
            )
            
            self.results['serp_collection'] = result
            
            # Validate results
            if result.get('discrete_batches'):
                logger.info(f"✅ Phase 2: Created discrete batches")
                
                content_results = result.get('content_type_results', {})
                for content_type, data in content_results.items():
                    status = "✅" if data.get('success') else "❌"
                    logger.info(f"   {status} {content_type}: {data}")
                    
                logger.info(f"   Total results: {result.get('total_results', 0)}")
            else:
                logger.error("❌ Phase 2 FAILED: Did not use discrete batches")
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 2 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_3_company_enrichment_serp(self) -> Dict[str, Any]:
        """Test Phase 3: Company Enrichment (SERP Domains)"""
        logger.info("\n" + "="*60)
        logger.info("🏢 PHASE 3: COMPANY ENRICHMENT (SERP DOMAINS)")
        logger.info("="*60)
        
        try:
            # Get unique domains from SERP results
            domains = await self.pipeline_service._get_unique_serp_domains()
            logger.info(f"Found {len(domains)} unique domains from SERP")
            
            if domains:
                logger.info(f"Sample domains: {domains[:5]}")
                
                # Test company enrichment
                result = await self.pipeline_service._execute_company_enrichment_phase(
                    domains[:10],  # Test with first 10 domains
                    phase_name="serp_domains"
                )
                
                self.results['company_enrichment_serp'] = result
                
                if result.get('companies_enriched', 0) > 0:
                    logger.info(f"✅ Phase 3 SUCCESS: {result['companies_enriched']} companies enriched")
                else:
                    logger.warning(f"⚠️ Phase 3: No companies enriched from {len(domains[:10])} domains")
            else:
                logger.warning("⚠️ Phase 3 SKIPPED: No domains found in SERP results")
                result = {"success": True, "skipped": True, "reason": "No domains found"}
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 3 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_4_youtube_enrichment(self) -> Dict[str, Any]:
        """Test Phase 4: YouTube Enrichment"""
        logger.info("\n" + "="*60)
        logger.info("📹 PHASE 4: YOUTUBE ENRICHMENT")
        logger.info("="*60)
        
        try:
            # Get video URLs from SERP
            video_urls = await self.pipeline_service._get_video_urls_from_serp()
            logger.info(f"Found {len(video_urls)} video URLs from SERP")
            
            if video_urls:
                logger.info(f"Sample URLs: {video_urls[:3]}")
                
                # Test video enrichment
                result = await self.pipeline_service._execute_video_enrichment_phase(
                    video_urls[:5]  # Test with first 5 videos
                )
                
                self.results['youtube_enrichment'] = result
                
                if result.get('videos_enriched', 0) > 0:
                    logger.info(f"✅ Phase 4 SUCCESS: {result['videos_enriched']} videos enriched")
                else:
                    logger.warning(f"⚠️ Phase 4: No videos enriched from {len(video_urls[:5])} URLs")
            else:
                logger.warning("⚠️ Phase 4 SKIPPED: No video URLs found")
                result = {"success": True, "skipped": True, "reason": "No video URLs found"}
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 4 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_5_content_scraping(self) -> Dict[str, Any]:
        """Test Phase 5: Content Scraping"""
        logger.info("\n" + "="*60)
        logger.info("🌐 PHASE 5: CONTENT SCRAPING")
        logger.info("="*60)
        
        try:
            # Get content URLs from SERP results
            content_urls = await self.pipeline_service._get_content_urls_from_serp()
            logger.info(f"Found {len(content_urls)} content URLs from SERP")
            
            if content_urls:
                logger.info(f"Sample URLs: {list(content_urls)[:5]}")
                
                # Test content scraping
                result = await self.pipeline_service._execute_content_scraping_phase(
                    list(content_urls)[:10]  # Test with first 10 URLs
                )
                
                self.results['content_scraping'] = result
                
                if result.get('urls_scraped', 0) > 0:
                    logger.info(f"✅ Phase 5 SUCCESS: {result['urls_scraped']} URLs scraped")
                else:
                    logger.warning(f"⚠️ Phase 5: No content scraped from {len(content_urls[:10])} URLs")
            else:
                logger.warning("⚠️ Phase 5 SKIPPED: No content URLs found in SERP results")
                result = {"success": True, "skipped": True, "reason": "No content URLs found"}
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 5 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_6_company_enrichment_youtube(self) -> Dict[str, Any]:
        """Test Phase 6: Company Enrichment (YouTube Channels)"""
        logger.info("\n" + "="*60)
        logger.info("🏢 PHASE 6: COMPANY ENRICHMENT (YOUTUBE CHANNELS)")
        logger.info("="*60)
        
        try:
            # Get domains from YouTube channels
            domains = await self.pipeline_service._get_youtube_channel_domains()
            logger.info(f"Found {len(domains)} domains from YouTube channels")
            
            if domains:
                logger.info(f"Sample domains: {domains[:5]}")
                
                # Test company enrichment
                result = await self.pipeline_service._execute_company_enrichment_phase(
                    domains,
                    phase_name="youtube_domains"
                )
                
                self.results['company_enrichment_youtube'] = result
                
                if result.get('companies_enriched', 0) > 0:
                    logger.info(f"✅ Phase 6 SUCCESS: {result['companies_enriched']} companies enriched")
                else:
                    logger.warning(f"⚠️ Phase 6: No companies enriched from {len(domains)} domains")
            else:
                logger.info("⚠️ Phase 6 SKIPPED: No new domains from YouTube channels")
                result = {"success": True, "skipped": True, "reason": "No new YouTube domains found"}
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 6 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_7_content_analysis(self) -> Dict[str, Any]:
        """Test Phase 7: Content Analysis"""
        logger.info("\n" + "="*60)
        logger.info("🤖 PHASE 7: CONTENT ANALYSIS")
        logger.info("="*60)
        
        try:
            # Test content analysis
            result = await self.pipeline_service._execute_content_analysis_phase()
            
            self.results['content_analysis'] = result
            
            if result.get('content_analyzed', 0) > 0:
                logger.info(f"✅ Phase 7 SUCCESS: {result['content_analyzed']} content pieces analyzed")
            else:
                logger.warning("⚠️ Phase 7: No content analyzed")
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 7 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def test_phase_8_dsi_calculation(self) -> Dict[str, Any]:
        """Test Phase 8: DSI Calculation"""
        logger.info("\n" + "="*60)
        logger.info("📈 PHASE 8: DSI CALCULATION")
        logger.info("="*60)
        
        try:
            # Test DSI calculation
            result = await self.pipeline_service._execute_dsi_calculation_phase()
            
            self.results['dsi_calculation'] = result
            
            if result.get('dsi_calculated'):
                logger.info(f"✅ Phase 8 SUCCESS: DSI calculated")
                logger.info(f"   Companies ranked: {result.get('companies_ranked', 0)}")
                logger.info(f"   Pages ranked: {result.get('pages_ranked', 0)}")
            else:
                logger.error("❌ Phase 8 FAILED: DSI not calculated")
                if result.get('error'):
                    logger.error(f"   Error: {result['error']}")
                
            return result
            
        except Exception as e:
            logger.error(f"❌ Phase 8 ERROR: {e}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": str(e)}
    
    async def run_all_phases(self):
        """Run all phases in sequence"""
        await self.initialize()
        
        phases = [
            ("Phase 1: Keyword Metrics", self.test_phase_1_keyword_metrics),
            ("Phase 2: SERP Collection", self.test_phase_2_serp_collection),
            ("Phase 3: Company Enrichment (SERP)", self.test_phase_3_company_enrichment_serp),
            ("Phase 4: YouTube Enrichment", self.test_phase_4_youtube_enrichment),
            ("Phase 5: Content Scraping", self.test_phase_5_content_scraping),
            ("Phase 6: Company Enrichment (YouTube)", self.test_phase_6_company_enrichment_youtube),
            ("Phase 7: Content Analysis", self.test_phase_7_content_analysis),
            ("Phase 8: DSI Calculation", self.test_phase_8_dsi_calculation)
        ]
        
        logger.info("\n" + "="*60)
        logger.info("🚀 TESTING ALL PIPELINE PHASES")
        logger.info("="*60)
        
        for phase_name, phase_func in phases:
            try:
                result = await phase_func()
                await asyncio.sleep(2)  # Brief pause between phases
            except Exception as e:
                logger.error(f"Failed to test {phase_name}: {e}")
        
        # Summary
        logger.info("\n" + "="*60)
        logger.info("📊 PHASE TEST SUMMARY")
        logger.info("="*60)
        
        for phase, result in self.results.items():
            if result.get('success', False) or result.get('skipped'):
                status = "✅ SUCCESS" if not result.get('skipped') else "⏩ SKIPPED"
            else:
                status = "❌ FAILED"
            
            logger.info(f"{phase}: {status}")
            if result.get('error'):
                logger.info(f"   Error: {result['error']}")
        
        logger.info("\n✅ Phase testing complete!")


async def main():
    """Main test function"""
    runner = PhaseTestRunner()
    
    # Parse command line arguments
    phase_num = None
    keyword_count = 5  # Default to testing with 5 keywords
    
    if len(sys.argv) > 1:
        phase_num = sys.argv[1]
        
    if len(sys.argv) > 2:
        try:
            keyword_count = int(sys.argv[2])
        except ValueError:
            logger.error(f"Invalid keyword count: {sys.argv[2]}")
            return
    
    # Initialize runner
    await runner.initialize()
    
    # Set the number of keywords to test with
    if keyword_count > 0 and runner.project_keywords:
        runner.test_keyword_count = min(keyword_count, len(runner.project_keywords))
        logger.info(f"🔧 Testing with {runner.test_keyword_count} keywords")
    
    if phase_num:
        phase_map = {
            "1": runner.test_phase_1_keyword_metrics,
            "2": runner.test_phase_2_serp_collection,
            "3": runner.test_phase_3_company_enrichment_serp,
            "4": runner.test_phase_4_youtube_enrichment,
            "5": runner.test_phase_5_content_scraping,
            "6": runner.test_phase_6_company_enrichment_youtube,
            "7": runner.test_phase_7_content_analysis,
            "8": runner.test_phase_8_dsi_calculation
        }
        
        if phase_num in phase_map:
            await phase_map[phase_num]()
        else:
            logger.error(f"Invalid phase number: {phase_num}")
            logger.info("Usage: python test_pipeline_phases.py [phase_number] [keyword_count]")
            logger.info("  phase_number: 1-8 (specific phase) or omit for all phases")
            logger.info("  keyword_count: number of keywords to test with (default: 5)")
    else:
        # Run all phases
        await runner.run_all_phases()


if __name__ == "__main__":
    asyncio.run(main())
