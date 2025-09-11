#!/usr/bin/env python3
"""Start a pipeline run via the API"""
import httpx
import asyncio
import json
import sys
from datetime import datetime

async def start_pipeline():
    """Start a pipeline run through the API"""
    # Use test token for auth bypass
    headers = {
        'Authorization': 'Bearer test-token-for-development',
        'Content-Type': 'application/json'
    }
    
    # Start pipeline with all phases enabled
    data = {
        'regions': ['US', 'UK'],
        'content_types': ['organic', 'news', 'video'],
        'mode': 'BATCH_OPTIMIZED',
        'enable_all_phases': True,
        'force_refresh': True  # Force fresh data collection
    }
    
    print(f"🚀 Starting pipeline at {datetime.now()}")
    print(f"📋 Configuration: {json.dumps(data, indent=2)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                'http://localhost:8001/api/v1/pipeline/start',
                headers=headers,
                json=data
            )
            
            print(f'\n📊 Status: {response.status_code}')
            
            if response.status_code == 200:
                result = response.json()
                pipeline_id = result.get('pipeline_id')
                print(f"✅ Pipeline started successfully!")
                print(f"🆔 Pipeline ID: {pipeline_id}")
                print(f"📄 Message: {result.get('message')}")
                print(f"⏳ Status: {result.get('status')}")
                
                # Monitor the pipeline
                print(f"\n👀 Monitoring pipeline progress...")
                print(f"Check logs: docker-compose logs -f backend")
                print(f"Or monitor at: http://localhost:3000/pipeline")
                
                return pipeline_id
            else:
                print(f"❌ Failed to start pipeline")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Error starting pipeline: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(start_pipeline())

