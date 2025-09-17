#!/usr/bin/env python3
"""
Custom Dimensions Re-Analysis Script

This script re-analyzes all existing content for ALL custom dimensions (Strategic Imperatives,
Business Units, and any other custom dimensions) that were missing due to the analyzer not 
loading from generic_custom_dimensions table.

Usage:
    python strategic_imperatives_reanalysis.py

The script will:
1. Load ALL custom dimensions from generic_custom_dimensions (Strategic Imperatives, BUs, etc.)
2. Find all existing analyzed content
3. Re-analyze each page for all custom dimensions
4. Store results in optimized_dimension_analysis table
"""

import asyncio
import sys
import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID
import traceback

# Add the app directory to the path so we can import modules
sys.path.insert(0, '/app')

from app.core.database import db_pool
from app.core.config import get_settings
from app.services.analysis.optimized_unified_analyzer import OptimizedUnifiedAnalyzer
from loguru import logger


class CustomDimensionsReAnalyzer:
    """Re-analyze existing content for ALL custom dimensions (Strategic Imperatives, BUs, etc.)"""
    
    def __init__(self):
        self.settings = get_settings()
        self.db = db_pool
        self.analyzer = OptimizedUnifiedAnalyzer(self.settings, self.db)
        self.processed_count = 0
        self.error_count = 0
        self.start_time = None
        
        # Advanced concurrency control (matching ConcurrentContentAnalyzer)
        self._concurrent_limit = getattr(self.settings, 'DEFAULT_ANALYZER_CONCURRENT_LIMIT', 50)
        self._batch_size = 20  # Match main analyzer batch size
        self._global_semaphore = asyncio.Semaphore(self._concurrent_limit)
        self._max_concurrent_batches = max(1, self._concurrent_limit // self._batch_size)  # e.g., 50/20 = 2
        
        logger.info(f"🔧 Configured re-analyzer: {self._concurrent_limit} concurrent limit, "
                   f"batch size {self._batch_size}, {self._max_concurrent_batches} concurrent batches")
        
    async def run(self):
        """Main execution method"""
        logger.info("🚀 Starting Custom Dimensions Re-Analysis (Strategic Imperatives, BUs, etc.)")
        self.start_time = datetime.now()
        
        try:
            # Initialize database
            await self.db.initialize()
            
            # Load ALL custom dimensions
            custom_dimensions = await self._load_all_custom_dimensions()
            if not custom_dimensions:
                logger.error("❌ No custom dimensions found to analyze")
                return
            
            # Filter to only Strategic Imperatives (personas/JTBD already complete)
            strategic_imperatives = [d for d in custom_dimensions if d.get('dimension_type') == 'strategic_imperative']
            
            if not strategic_imperatives:
                logger.error("❌ No Strategic Imperatives found to analyze")
                return
            
            logger.info(f"✅ Found {len(strategic_imperatives)} Strategic Imperatives to add:")
            for si in strategic_imperatives:
                logger.info(f"   📋 {si['name']} ({si['dimension_id']})")
            
            logger.info(f"ℹ️  Personas and JTBD analysis already complete - only adding Strategic Imperatives")
            
            # Get content that has persona/JTBD but missing Strategic Imperatives
            content_to_reanalyze = await self._get_existing_analyzed_content()
            logger.info(f"📊 Found {len(content_to_reanalyze)} pages needing Strategic Imperative analysis")
            
            if not content_to_reanalyze:
                logger.info("ℹ️  No content found to re-analyze")
                return
            
            # Advanced concurrent batch processing (matching ConcurrentContentAnalyzer)
            logger.info(f"🚀 Starting concurrent batch processing: {self._max_concurrent_batches} batches × {self._batch_size} items = {self._max_concurrent_batches * self._batch_size} concurrent analyses")
            
            # Process all content using concurrent batches (Strategic Imperatives only)
            await self._process_all_content_concurrent(content_to_reanalyze, strategic_imperatives)
            
            # Final summary
            elapsed = (datetime.now() - self.start_time).total_seconds()
            logger.info(f"🎉 Re-analysis complete!")
            logger.info(f"   ✅ Processed: {self.processed_count} pages")
            logger.info(f"   ❌ Errors: {self.error_count} pages")
            logger.info(f"   ⏱️  Total time: {elapsed/60:.1f} minutes")
            logger.info(f"   📊 Average rate: {self.processed_count/(elapsed/60):.1f} pages/min")
            
        except Exception as e:
            logger.error(f"💥 Fatal error in re-analysis: {e}")
            traceback.print_exc()
        
    async def _load_all_custom_dimensions(self) -> List[Dict[str, Any]]:
        """Load ALL custom dimensions from generic_custom_dimensions table"""
        try:
            async with self.db.acquire() as conn:
                custom_dimensions = await conn.fetch("""
                    SELECT dimension_id, name, description, ai_context, criteria, 
                           scoring_framework, metadata
                    FROM generic_custom_dimensions
                    WHERE client_id = 'default' AND is_active = true
                    ORDER BY created_at
                """)
                
                result = []
                for dim in custom_dimensions:
                    if dim['ai_context'] and dim['criteria'] and dim['scoring_framework']:
                        # Determine dimension type based on ID and name patterns
                        dimension_type = 'custom_dimension'  # Default
                        
                        # Categorize based on dimension_id or name patterns
                        if any(keyword in dim['name'].lower() for keyword in ['obsession', 'secure', 'trusted', 'innovation', 'imperative']):
                            dimension_type = 'strategic_imperative'
                        elif any(keyword in dim['name'].lower() for keyword in ['payments', 'lending', 'banking', 'treasury', 'universal']):
                            dimension_type = 'business_unit'
                        elif 'bu_' in dim['dimension_id'] or 'business' in dim['dimension_id'].lower():
                            dimension_type = 'business_unit'
                        elif 'si_' in dim['dimension_id'] or 'strategic' in dim['dimension_id'].lower():
                            dimension_type = 'strategic_imperative'
                        
                        result.append({
                            'dimension_id': dim['dimension_id'],
                            'name': dim['name'], 
                            'description': dim['description'],
                            'ai_context': dim['ai_context'],
                            'criteria': dim['criteria'],
                            'scoring_framework': dim['scoring_framework'],
                            'metadata': dim['metadata'] or {},
                            'dimension_type': dimension_type
                        })
                
                return result
                
        except Exception as e:
            logger.error(f"Failed to load custom dimensions: {e}")
            return []
    
    async def _get_existing_analyzed_content(self) -> List[Dict[str, Any]]:
        """Get content that HAS persona/JTBD analysis but is MISSING Strategic Imperatives only"""
        try:
            async with self.db.acquire() as conn:
                # Get content that:
                # 1. HAS been analyzed (has persona/JTBD analysis) ✅
                # 2. Is MISSING Strategic Imperative analysis only ❌
                content = await conn.fetch("""
                    SELECT DISTINCT
                        oca.url,
                        oca.id as analysis_id,
                        sc.title,
                        sc.content,
                        sc.meta_description,
                        sc.domain,
                        oca.analyzed_at
                    FROM optimized_content_analysis oca
                    INNER JOIN scraped_content sc ON oca.url = sc.url
                    WHERE sc.content IS NOT NULL 
                      AND LENGTH(sc.content) > 100
                      AND EXISTS (
                          -- Must have existing persona/JTBD analysis ✅
                          SELECT 1 FROM optimized_dimension_analysis oda 
                          WHERE oda.analysis_id = oca.id 
                          AND oda.dimension_type IN ('persona', 'jtbd_phase')
                      )
                      AND NOT EXISTS (
                          -- But missing Strategic Imperative analysis ❌
                          SELECT 1 FROM optimized_dimension_analysis oda 
                          WHERE oda.analysis_id = oca.id 
                          AND oda.dimension_type = 'strategic_imperative'
                      )
                    ORDER BY oca.analyzed_at DESC
                """)
                
                return [dict(row) for row in content]
                
        except Exception as e:
            logger.error(f"Failed to get existing analyzed content: {e}")
            return []
    
    async def _process_all_content_concurrent(self, content_list: List[Dict[str, Any]], strategic_imperatives: List[Dict[str, Any]]):
        """Process all content using advanced concurrent batch processing"""
        
        # Track active batch tasks (matching ConcurrentContentAnalyzer pattern)
        active_batches = set()
        content_queue = content_list.copy()
        
        logger.info(f"📊 Processing {len(content_queue)} pages with {len(strategic_imperatives)} Strategic Imperatives")
        
        while content_queue or active_batches:
            # Clean up completed batches
            if active_batches:
                done_batches = {task for task in active_batches if task.done()}
                for task in done_batches:
                    try:
                        await task  # Retrieve any exceptions
                    except Exception as e:
                        logger.error(f"Batch processing error: {e}")
                active_batches -= done_batches
            
            # Launch new batches if under limit and content available
            while len(active_batches) < self._max_concurrent_batches and content_queue:
                # Get next batch
                batch = content_queue[:self._batch_size]
                content_queue = content_queue[self._batch_size:]
                
                if batch:
                    sample_urls = [c.get('url', '')[:50] + '...' for c in batch[:3]]
                    logger.info(f"🚀 Starting batch {len(active_batches)+1}/{self._max_concurrent_batches} "
                               f"with {len(batch)} items; sample={sample_urls}")
                    
                    # Launch batch processing as background task with semaphore control
                    batch_task = asyncio.create_task(self._process_batch_with_semaphore(batch, strategic_imperatives))
                    active_batches.add(batch_task)
            
            # Progress update
            if active_batches:
                elapsed = (datetime.now() - self.start_time).total_seconds()
                rate = self.processed_count / elapsed if elapsed > 0 else 0
                remaining = len(content_queue)
                in_flight = len(active_batches) * self._batch_size
                
                logger.info(f"📈 Concurrent status: {len(active_batches)} active batches | "
                           f"~{in_flight} items in flight | Rate: {rate:.1f} items/min | "
                           f"{remaining} remaining")
                
                # Wait a bit before next iteration
                await asyncio.sleep(2)
            else:
                # No active batches and no content queue - we're done
                break
    
    async def _process_batch_with_semaphore(self, content_batch: List[Dict[str, Any]], strategic_imperatives: List[Dict[str, Any]]):
        """Process a batch of content with semaphore control for OpenAI calls"""
        
        async def analyze_with_semaphore(content_data: Dict[str, Any]):
            async with self._global_semaphore:  # Control total concurrent OpenAI calls
                # Debug: Check what we're passing to _reanalyze_content
                if not isinstance(content_data, dict):
                    logger.error(f"🚨 analyze_with_semaphore got NON-DICT: {type(content_data)} - {str(content_data)[:200]}")
                    return False
                return await self._reanalyze_content(content_data, strategic_imperatives)
        
        # Process all items in batch concurrently (with semaphore limiting actual API calls)
        tasks = [analyze_with_semaphore(content) for content in content_batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes
        successful = sum(1 for result in results if result is True)
        
        logger.info(f"✅ Batch complete: {successful}/{len(content_batch)} successful | Total processed: {self.processed_count}")
        
        return successful
    
    async def _reanalyze_content(self, content: Dict[str, Any], strategic_imperatives: List[Dict[str, Any]]) -> bool:
        """Re-analyze a single piece of content for Strategic Imperatives only"""
        try:
            # Debug: Check content type and structure
            if not isinstance(content, dict):
                logger.error(f"🚨 CONTENT IS NOT DICT! Type: {type(content)}, Value: {str(content)[:200]}")
                return False
            
            # Safely extract required fields
            url = content.get('url', 'unknown_url')
            analysis_id = content.get('analysis_id')
            content_text = content.get('content', '')
            title = content.get('title', '')
            meta_description = content.get('meta_description', '')
            
            if not analysis_id:
                logger.error(f"🚨 Missing analysis_id for URL: {url}")
                return False
            
            if not content_text:
                logger.warning(f"⚠️ Empty content for URL: {url}")
                return False
            
            logger.info(f"🔍 Processing URL: {url[:50]}...")
            
            # Run analysis specifically for Strategic Imperatives only
            si_results = await self._analyze_strategic_imperatives(
                url=url,
                content=content_text,
                title=title,
                meta_description=meta_description,
                strategic_imperatives=strategic_imperatives
            )
            
            if si_results:
                # Store the Strategic Imperative analysis results
                await self._store_custom_dimension_results(analysis_id, si_results)
                logger.debug(f"✅ Added SI analysis: {url} ({len(si_results)} Strategic Imperative scores)")
            else:
                logger.warning(f"⚠️  No Strategic Imperative results for: {url}")
            
            self.processed_count += 1
            return True
            
        except Exception as e:
            # Handle case where content might be malformed
            try:
                url_for_error = content.get('url', 'unknown') if isinstance(content, dict) else str(content)[:100]
            except:
                url_for_error = 'unknown'
            logger.error(f"❌ Error analyzing Strategic Imperatives for {url_for_error}: {e}")
            logger.error(f"Content type: {type(content)}, Content preview: {str(content)[:200] if content else 'None'}")
            self.error_count += 1
            return False
    
    async def _analyze_strategic_imperatives(
        self,
        url: str,
        content: str, 
        title: str, 
        meta_description: str,
        strategic_imperatives: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Analyze content for Strategic Imperatives only using OptimizedUnifiedAnalyzer"""
        try:
            logger.info(f"🔍 About to analyze SI for {url[:50]}...")
            
            # Use the full analyzer.analyze_content method which handles all the parsing correctly
            analysis_result = await self.analyzer.analyze_content(
                url=url,
                content=content,
                title=title,
                project_id=None  # Use None instead of 'default' to avoid UUID validation error
            )
            
            logger.info(f"📄 Analyzer returned: {type(analysis_result)}")
            
            if not analysis_result or not isinstance(analysis_result, dict):
                logger.warning(f"No valid analysis result for {url[:50]}...")
                return []
            
            # Look for dimensions in the result
            dimensions_data = analysis_result.get('dimensions', {})
            logger.info(f"🔑 Found dimensions: {list(dimensions_data.keys()) if dimensions_data else 'None'}")
            
            # Extract only Strategic Imperative results
            si_results = []
            for dim_id, dim_result in dimensions_data.items():
                # Check if this dimension is a Strategic Imperative
                matching_si = next((si for si in strategic_imperatives if si['dimension_id'] == dim_id), None)
                if matching_si:
                    logger.info(f"✅ Found SI result for {matching_si['name']}: score {dim_result.get('score', 0)}")
                    si_results.append({
                        'dimension_id': dim_id,
                        'dimension_name': matching_si['name'],
                        'dimension_type': 'strategic_imperative',
                        'score': dim_result.get('score', 0),
                        'confidence': dim_result.get('confidence', 0),
                        'key_evidence': dim_result.get('key_evidence', ''),
                        'primary_signals': dim_result.get('primary_signals', []),
                        'score_factors': dim_result.get('score_factors', {})
                    })
            
            logger.info(f"📊 Returning {len(si_results)} SI results for {url[:50]}...")
            return si_results
            
        except Exception as e:
            logger.error(f"Failed to analyze Strategic Imperatives for {url}: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _store_custom_dimension_results(self, analysis_id: UUID, custom_results: List[Dict[str, Any]]):
        """Store custom dimension analysis results in optimized_dimension_analysis"""
        try:
            async with self.db.acquire() as conn:
                for custom_result in custom_results:
                    await conn.execute("""
                        INSERT INTO optimized_dimension_analysis (
                            analysis_id,
                            dimension_id,
                            dimension_name,
                            dimension_type,
                            score,
                            confidence,
                            key_evidence,
                            primary_signals,
                            score_factors,
                            created_at
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
                    """,
                        analysis_id,
                        custom_result['dimension_id'],
                        custom_result['dimension_name'],
                        custom_result['dimension_type'],
                        custom_result['score'],
                        custom_result['confidence'],
                        custom_result['key_evidence'],
                        json.dumps(custom_result['primary_signals']),
                        json.dumps(custom_result['score_factors'])
                    )
                    
        except Exception as e:
            logger.error(f"Failed to store custom dimension results: {e}")
            raise


async def main():
    """Main entry point"""
    reanalyzer = CustomDimensionsReAnalyzer()
    await reanalyzer.run()


if __name__ == "__main__":
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | {message}",
        level="INFO"
    )
    
    # Run the re-analysis
    asyncio.run(main())
