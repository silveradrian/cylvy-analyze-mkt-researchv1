"""
Dashboard service for aggregating and presenting analysis results
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from app.core.database import db_pool


class DashboardService:
    """Service for dashboard data aggregation"""
    
    def __init__(self, settings, db):
        self.settings = settings
        self.db = db
    
    async def get_summary(self) -> Dict[str, Any]:
        """Get dashboard summary statistics"""
        async with db_pool.acquire() as conn:
            # Get basic counts
            summary = await conn.fetchrow("""
                SELECT 
                    (SELECT COUNT(*) FROM keywords) as total_keywords,
                    (SELECT COUNT(DISTINCT domain) FROM scraped_content) as total_companies,
                    (SELECT COUNT(*) FROM scraped_content WHERE status = 'completed') as total_pages,
                    (SELECT COUNT(*) FROM content_analysis) as analyzed_content,
                    (SELECT COUNT(DISTINCT url) FROM serp_results) as serp_results,
                    (SELECT MAX(created_at) FROM content_analysis) as last_analysis
            """)
            
            return dict(summary) if summary else {}
    
    async def get_dsi_rankings(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get DSI company rankings"""
        async with db_pool.acquire() as conn:
            # Get latest DSI calculation
            latest_calc = await conn.fetchrow(
                "SELECT * FROM dsi_calculations ORDER BY calculation_date DESC LIMIT 1"
            )
            
            if not latest_calc or not latest_calc['company_rankings']:
                return []
            
            import json
            rankings = json.loads(latest_calc['company_rankings'])
            
            # Return top companies
            return rankings[:limit]
    
    async def get_content_analysis(
        self,
        limit: int = 100,
        domain: Optional[str] = None,
        persona: Optional[str] = None,
        jtbd_phase: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get content analysis results with filtering"""
        async with db_pool.acquire() as conn:
            query = """
                SELECT 
                    ca.*,
                    sc.title,
                    sc.domain,
                    cp.company_name
                FROM content_analysis ca
                JOIN scraped_content sc ON ca.url = sc.url
                LEFT JOIN company_profiles cp ON sc.domain = cp.domain
                WHERE 1=1
            """
            params = []
            
            if domain:
                params.append(domain)
                query += f" AND sc.domain = ${len(params)}"
            
            if persona:
                params.append(persona)
                query += f" AND ca.primary_persona = ${len(params)}"
            
            if jtbd_phase:
                params.append(jtbd_phase)
                query += f" AND ca.jtbd_phase = ${len(params)}"
            
            query += f" ORDER BY ca.created_at DESC LIMIT {limit}"
            
            rows = await conn.fetch(query, *params)
            return [dict(row) for row in rows]
    
    async def get_company_details(self, domain: str) -> Dict[str, Any]:
        """Get detailed company information"""
        async with db_pool.acquire() as conn:
            # Company profile
            company = await conn.fetchrow(
                "SELECT * FROM company_profiles WHERE domain = $1",
                domain
            )
            
            if not company:
                return {"error": "Company not found"}
            
            # Content analysis for this company
            content = await conn.fetch(
                """
                SELECT ca.*, sc.title, sc.url
                FROM content_analysis ca
                JOIN scraped_content sc ON ca.url = sc.url
                WHERE sc.domain = $1
                ORDER BY ca.created_at DESC
                LIMIT 20
                """,
                domain
            )
            
            # DSI ranking
            dsi_data = await self._get_company_dsi(domain)
            
            return {
                "company": dict(company),
                "content_analysis": [dict(row) for row in content],
                "dsi_metrics": dsi_data
            }
    
    async def get_trending_content(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get trending content"""
        # This would use the historical data service
        # For now, return recent high-performing content
        async with db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    ca.url,
                    sc.title,
                    sc.domain,
                    cp.company_name,
                    ca.content_classification,
                    ca.primary_persona,
                    ca.jtbd_phase,
                    ca.created_at
                FROM content_analysis ca
                JOIN scraped_content sc ON ca.url = sc.url
                LEFT JOIN company_profiles cp ON sc.domain = cp.domain
                WHERE ca.created_at >= $1
                ORDER BY ca.created_at DESC
                LIMIT 50
                """,
                datetime.now() - timedelta(days=days)
            )
            
            return [dict(row) for row in rows]
    
    async def _get_company_dsi(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get DSI metrics for a specific company"""
        async with db_pool.acquire() as conn:
            latest_calc = await conn.fetchrow(
                "SELECT * FROM dsi_calculations ORDER BY calculation_date DESC LIMIT 1"
            )
            
            if not latest_calc or not latest_calc['company_rankings']:
                return None
            
            import json
            rankings = json.loads(latest_calc['company_rankings'])
            
            # Find company in rankings
            for company in rankings:
                if company.get('domain') == domain:
                    return company
            
            return None
