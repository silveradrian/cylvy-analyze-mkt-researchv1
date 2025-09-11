"""Test content scraping phase with document support"""
import asyncio
import uuid
from datetime import datetime
from app.core.config import settings
from app.core.database import DatabasePool
from app.services.pipeline.pipeline_service import PipelineService, PipelineConfig, PipelineMode
import json


async def test_content_scraping():
    """Test content scraping phase with various URLs including documents"""
    
    # Initialize database
    db_pool = DatabasePool()
    await db_pool.initialize()
    
    # Create pipeline service
    pipeline_service = PipelineService(settings, db_pool)
    
    # Test URLs including documents
    test_urls = [
        # Regular web pages
        "https://example.com",
        "https://www.python.org",
        
        # PDF documents
        "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "https://www.adobe.com/support/products/enterprise/knowledgecenter/media/c4611_sample_explain.pdf",
        
        # Add more URLs as needed
    ]
    
    print("🔍 Testing Content Scraping Phase with Document Support\n")
    print(f"Testing {len(test_urls)} URLs (including PDFs)...\n")
    
    # Test individual scraping first
    for url in test_urls:
        print(f"\n📄 Scraping: {url}")
        try:
            result = await pipeline_service.web_scraper.scrape(url)
            
            # Print results
            print(f"  ✅ Success!")
            print(f"  Engine: {result.get('engine', 'unknown')}")
            print(f"  Content Type: {result.get('content_type', 'unknown')}")
            print(f"  Word Count: {result.get('word_count', 0)}")
            print(f"  Status Code: {result.get('status_code', 'N/A')}")
            
            # Show metadata for documents
            if result.get('metadata'):
                if result.get('metadata', {}).get('document_type'):
                    print(f"  Document Type: {result['metadata']['document_type']}")
                    print(f"  Page Count: {result['metadata'].get('page_count', 'N/A')}")
                    print(f"  Table Count: {result['metadata'].get('table_count', 'N/A')}")
            
            # Show content preview
            content = result.get('content', '')
            if content:
                preview = content[:150].replace('\n', ' ')
                print(f"  Content Preview: {preview}...")
            
            if result.get('error'):
                print(f"  ⚠️  Error: {result['error']}")
                
        except Exception as e:
            print(f"  ❌ Error: {str(e)}")
    
    # Now test the content scraping phase
    print("\n\n🚀 Testing Content Scraping Phase Execution\n")
    
    try:
        # Execute the content scraping phase
        result = await pipeline_service._execute_content_scraping_phase(test_urls)
        
        print(f"Phase Result:")
        print(f"  URLs Total: {result.get('urls_total', 0)}")
        print(f"  URLs Scraped: {result.get('urls_scraped', 0)}")
        print(f"  Success Rate: {result.get('urls_scraped', 0) / result.get('urls_total', 1) * 100:.1f}%")
        
        if result.get('errors'):
            print(f"\n  Errors ({len(result['errors'])}):")
            for error in result['errors'][:5]:  # Show first 5 errors
                print(f"    - {error}")
                
    except Exception as e:
        print(f"❌ Phase execution error: {str(e)}")
    
    # Close database
    await db_pool.close()
    
    print("\n✅ Content scraping test completed!")


if __name__ == "__main__":
    asyncio.run(test_content_scraping())
