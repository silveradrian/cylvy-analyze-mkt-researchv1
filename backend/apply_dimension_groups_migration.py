#!/usr/bin/env python3
"""
Apply Dimension Groups Migration

This script applies the dimension groups migration to enable grouping functionality
for custom dimensions in the analysis framework.
"""

import asyncio
import sys
from pathlib import Path

# Add app to path
sys.path.append('/app')

from app.core.database import db_pool
from app.core.config import settings


async def apply_migration():
    """Apply the dimension groups migration."""
    print("=== Applying Dimension Groups Migration ===")
    
    async with db_pool.acquire() as conn:
        # Read the migration file
        migration_path = Path('/app/migrations/add_dimension_groups_simplified.sql')
        if not migration_path.exists():
            print(f"❌ Migration file not found: {migration_path}")
            return False
        
        print(f"📄 Reading migration from: {migration_path}")
        migration_sql = migration_path.read_text()
        
        # Check if dimension_groups table already exists
        exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename = 'dimension_groups'
            )
        """)
        
        if exists:
            print("⚠️  Dimension groups table already exists. Skipping migration.")
            return True
        
        try:
            # Execute the migration
            print("🔄 Applying migration...")
            await conn.execute(migration_sql)
            print("✅ Migration applied successfully!")
            
            # Verify tables were created
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables 
                WHERE schemaname = 'public' 
                AND tablename IN ('dimension_groups', 'dimension_group_members', 'analysis_primary_dimensions')
                ORDER BY tablename
            """)
            
            print("\n📊 Created tables:")
            for table in tables:
                print(f"  ✓ {table['tablename']}")
            
            return True
            
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            return False


async def main():
    """Main function."""
    try:
        await db_pool.initialize()
        success = await apply_migration()
        
        if success:
            print("\n✅ Dimension groups migration completed!")
            print("\nYou can now run the setup script again to create dimension groups:")
            print("  docker exec -it cylvy-analyze-mkt-analysis-backend-1 python setup_project_data.py")
        else:
            print("\n❌ Migration failed!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await db_pool.close()


if __name__ == "__main__":
    asyncio.run(main())
