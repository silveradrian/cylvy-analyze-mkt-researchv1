"""
Database health checks and connectivity validation
"""
import asyncio
from typing import Dict, Any, List

import asyncpg
from loguru import logger

from app.core.config import settings


class DatabaseHealthChecker:
    """Performs database health checks and validation"""
    
    async def check_connection(self) -> Dict[str, Any]:
        """Test database connectivity"""
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            # Test basic query
            version = await conn.fetchval("SELECT version()")
            
            await conn.close()
            
            return {
                "status": "healthy",
                "connection": True,
                "version": version,
                "message": "Database connection successful"
            }
            
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return {
                "status": "unhealthy",
                "connection": False,
                "error": str(e),
                "message": "Database connection failed"
            }
    
    async def check_tables(self) -> Dict[str, Any]:
        """Check if required tables exist"""
        required_tables = [
            'users', 'client_config', 'analysis_config', 'api_keys',
            'keywords', 'serp_results', 'scraped_content', 'company_profiles',
            'content_analysis', 'video_content', 'dsi_calculations',
            'pipeline_schedules', 'schedule_executions', 'pipeline_executions'
        ]
        
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            # Check which tables exist
            existing_tables = await conn.fetch("""
                SELECT table_name FROM information_schema.tables 
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
            
            existing_names = {row['table_name'] for row in existing_tables}
            missing_tables = [table for table in required_tables if table not in existing_names]
            
            await conn.close()
            
            return {
                "status": "healthy" if not missing_tables else "warning",
                "total_tables": len(existing_names),
                "required_tables": len(required_tables),
                "missing_tables": missing_tables,
                "existing_tables": sorted(existing_names)
            }
            
        except Exception as e:
            logger.error(f"Table check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def check_data_integrity(self) -> Dict[str, Any]:
        """Check basic data integrity"""
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            # Check for basic data
            checks = {
                "users_count": await conn.fetchval("SELECT COUNT(*) FROM users") or 0,
                "keywords_count": await conn.fetchval("SELECT COUNT(*) FROM keywords") or 0,
                "serp_results_count": await conn.fetchval("SELECT COUNT(*) FROM serp_results") or 0,
                "content_analysis_count": await conn.fetchval("SELECT COUNT(*) FROM content_analysis") or 0,
                "companies_count": await conn.fetchval("SELECT COUNT(*) FROM company_profiles") or 0
            }
            
            # Check for admin user
            admin_exists = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE role IN ('admin', 'superadmin')"
            ) or 0
            
            await conn.close()
            
            status = "healthy"
            warnings = []
            
            if admin_exists == 0:
                warnings.append("No admin users found")
                status = "warning"
            
            if checks["keywords_count"] == 0:
                warnings.append("No keywords configured")
            
            return {
                "status": status,
                "data_counts": checks,
                "admin_users": admin_exists,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"Data integrity check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def run_full_health_check(self) -> Dict[str, Any]:
        """Run comprehensive database health check"""
        logger.info("Running full database health check...")
        
        connection_check = await self.check_connection()
        tables_check = await self.check_tables()
        integrity_check = await self.check_data_integrity()
        
        overall_status = "healthy"
        if any(check["status"] == "unhealthy" for check in [connection_check, tables_check, integrity_check]):
            overall_status = "unhealthy"
        elif any(check["status"] == "warning" for check in [connection_check, tables_check, integrity_check]):
            overall_status = "warning"
        
        return {
            "overall_status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": {
                "connection": connection_check,
                "tables": tables_check,
                "data_integrity": integrity_check
            }
        }


async def main():
    """CLI entry point for database checks"""
    checker = DatabaseHealthChecker()
    result = await checker.run_full_health_check()
    
    print("=" * 60)
    print("DATABASE HEALTH CHECK REPORT")
    print("=" * 60)
    print(f"Overall Status: {result['overall_status'].upper()}")
    print(f"Timestamp: {result['timestamp']}")
    print()
    
    for check_name, check_result in result['checks'].items():
        print(f"{check_name.upper()}:")
        print(f"  Status: {check_result['status']}")
        if 'message' in check_result:
            print(f"  Message: {check_result['message']}")
        if 'error' in check_result:
            print(f"  Error: {check_result['error']}")
        if 'warnings' in check_result:
            for warning in check_result['warnings']:
                print(f"  Warning: {warning}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
