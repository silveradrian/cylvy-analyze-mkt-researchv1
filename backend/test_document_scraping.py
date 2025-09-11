"""Test document scraping functionality"""
import asyncio
from app.core.config import settings
from app.core.database import DatabasePool
from app.services.scraping.web_scraper import WebScraper
import json


async def test_document_scraping():
    """Test scraping PDF and Word documents"""
    
    # Initialize components
    db_pool = DatabasePool(settings.DATABASE_URL)
    await db_pool.initialize()
    
    scraper = WebScraper(settings, db_pool)
    
    # Test URLs - these are example URLs, replace with actual document URLs
    test_urls = [
        # PDF examples
        "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf",
        "https://www.adobe.com/support/products/enterprise/knowledgecenter/media/c4611_sample_explain.pdf",
        
        # Add Word document URLs if available
        # "https://example.com/sample.docx",
        
        # Regular webpage for comparison
        "https://example.com",
    ]
    
    print("Testing document scraping capabilities...\n")
    
    for url in test_urls:
        print(f"Scraping: {url}")
        try:
            result = await scraper.scrape(url)
            
            # Print summary
            print(f"  Engine: {result.get('engine', 'unknown')}")
            print(f"  Status: {result.get('status_code', 'N/A')}")
            print(f"  Content Type: {result.get('content_type', 'unknown')}")
            print(f"  Word Count: {result.get('word_count', 0)}")
            
            if result.get('metadata'):
                print(f"  Metadata: {json.dumps(result.get('metadata'), indent=2)}")
            
            if result.get('error'):
                print(f"  Error: {result.get('error')}")
            else:
                # Show first 200 characters of content
                content = result.get('content', '')
                if content:
                    print(f"  Content Preview: {content[:200]}...")
            
            print()
            
        except Exception as e:
            print(f"  ERROR: {str(e)}\n")
    
    await db_pool.close()


if __name__ == "__main__":
    asyncio.run(test_document_scraping())
