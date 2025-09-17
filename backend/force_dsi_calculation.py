import asyncio
from uuid import UUID
from app.core.config import settings
from app.core.database import db_pool
from app.services.metrics.simplified_dsi_calculator import SimplifiedDSICalculator
from datetime import datetime
from loguru import logger

async def force_dsi_calculation():
    pipeline_id = "1a1bac89-8056-41ff-8f20-8e82ec67999f"
    
    print(f"Force running DSI calculation for pipeline {pipeline_id}...")
    
    # Initialize services
    dsi_calculator = SimplifiedDSICalculator(settings, db_pool)
    
    try:
        # 1. Calculate DSI
        print("\n1. Calculating DSI rankings...")
        dsi_result = await dsi_calculator.calculate_dsi_rankings(pipeline_id)
        print(f"   ✓ DSI calculated: {dsi_result['companies_ranked']} companies, {dsi_result['pages_ranked']} pages")
        
        # Show top companies by DSI type
        print("\n   Top 5 Organic DSI companies:")
        for i, company in enumerate(dsi_result['organic_dsi'][:5], 1):
            print(f"   {i}. {company['company_name']} - DSI: {company['dsi_score']:.2f}")
        
        print("\n   Top 5 News DSI publishers:")
        for i, company in enumerate(dsi_result['news_dsi'][:5], 1):
            print(f"   {i}. {company['company_name']} - DSI: {company['dsi_score']:.2f}")
        
        print("\n   Top 5 YouTube DSI channels:")
        for i, company in enumerate(dsi_result['youtube_dsi'][:5], 1):
            print(f"   {i}. {company['company_name']} - DSI: {company['dsi_score']:.2f}")
        
        # 2. Update pipeline status
        async with db_pool.acquire() as conn:
            # Update phase results
            await conn.execute("""
                UPDATE pipeline_executions
                SET phase_results = phase_results || jsonb_build_object(
                    'dsi_calculation', jsonb_build_object(
                        'success', true,
                        'dsi_calculated', true,
                        'companies_ranked', $2,
                        'pages_ranked', $3,
                        'forced_calculation', true,
                        'calculated_at', NOW()
                    )
                )
                WHERE id = $1
            """, pipeline_id, dsi_result['companies_ranked'], 
                dsi_result['pages_ranked'])
            
            # Update phase status
            await conn.execute("""
                UPDATE pipeline_phase_status
                SET status = 'completed',
                    completed_at = NOW(),
                    result_data = jsonb_build_object(
                        'success', true,
                        'forced_calculation', true,
                        'companies_ranked', $2,
                        'pages_ranked', $3
                    )
                WHERE pipeline_execution_id = $1
                AND phase_name = 'dsi_calculation'
            """, pipeline_id, dsi_result['companies_ranked'], dsi_result['pages_ranked'])
            
        print(f"\n✅ DSI calculation completed successfully!")
        print(f"   Companies ranked: {dsi_result['companies_ranked']}")
        print(f"   Pages ranked: {dsi_result['pages_ranked']}")
        
    except Exception as e:
        logger.error(f"Failed to calculate DSI: {e}", exc_info=True)
        print(f"\n❌ DSI calculation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(force_dsi_calculation())
