"""
Database initialization and migration management
"""
import asyncio
import os
from pathlib import Path
from typing import List, Tuple
from datetime import datetime

import asyncpg
from loguru import logger

from app.core.config import settings


class DatabaseInitializer:
    """Handles database initialization and migrations"""
    
    def __init__(self):
        self.migrations_path = Path(__file__).parent.parent.parent / "migrations"
        
    async def initialize_database(self):
        """Initialize database with schema and data"""
        logger.info("Starting database initialization...")
        
        try:
            # Create connection
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            # Check if database is already initialized
            if await self._is_initialized(conn):
                logger.info("Database already initialized")
                await conn.close()
                return
            
            # Run migrations
            await self._run_migrations(conn)
            
            # Mark as initialized
            await self._mark_initialized(conn)
            
            await conn.close()
            logger.info("Database initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            raise
    
    async def _is_initialized(self, conn: asyncpg.Connection) -> bool:
        """Check if database is already initialized"""
        try:
            # Check if our tables exist
            result = await conn.fetchval(
                """
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name IN ('users', 'client_config', 'keywords')
                """
            )
            return result >= 3
        except Exception:
            return False
    
    async def _run_migrations(self, conn: asyncpg.Connection):
        """Run all migration files in order"""
        migration_files = self._get_migration_files()
        
        # Create migrations tracking table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version VARCHAR(255) PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        
        # Get already applied migrations
        applied = await conn.fetch("SELECT version FROM schema_migrations")
        applied_versions = {row['version'] for row in applied}
        
        # Apply new migrations
        for version, file_path in migration_files:
            if version in applied_versions:
                logger.info(f"Migration {version} already applied, skipping")
                continue
            
            logger.info(f"Applying migration {version} from {file_path}")
            
            # Read and execute migration
            with open(file_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            # Split by statements and execute (handling potential errors)
            statements = self._split_sql_statements(sql_content)
            
            async with conn.transaction():
                for statement in statements:
                    if statement.strip():
                        try:
                            await conn.execute(statement)
                        except Exception as e:
                            logger.error(f"Error executing statement in {version}: {e}")
                            logger.error(f"Statement: {statement[:200]}...")
                            raise
                
                # Record migration as applied
                await conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES ($1)",
                    version
                )
            
            logger.info(f"Migration {version} applied successfully")
    
    def _get_migration_files(self) -> List[Tuple[str, Path]]:
        """Get list of migration files sorted by version"""
        migration_files = []
        
        if not self.migrations_path.exists():
            logger.warning(f"Migrations directory not found: {self.migrations_path}")
            return []
        
        for file_path in self.migrations_path.glob("*.sql"):
            # Extract version from filename (e.g., "001_initial_schema.sql" -> "001")
            version = file_path.stem.split('_')[0]
            migration_files.append((version, file_path))
        
        # Sort by version
        migration_files.sort(key=lambda x: x[0])
        return migration_files
    
    def _split_sql_statements(self, sql_content: str) -> List[str]:
        """Split SQL content into individual statements"""
        # Simple approach - split by semicolon at end of line
        # This might need refinement for complex SQL
        statements = []
        current_statement = []
        
        for line in sql_content.split('\n'):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith('--'):
                continue
            
            current_statement.append(line)
            
            # If line ends with semicolon, it's end of statement
            if line.endswith(';'):
                statement = ' '.join(current_statement)
                statements.append(statement)
                current_statement = []
        
        # Add remaining statement if any
        if current_statement:
            statement = ' '.join(current_statement)
            if statement.strip():
                statements.append(statement)
        
        return statements
    
    async def _mark_initialized(self, conn: asyncpg.Connection):
        """Mark database as initialized"""
        await conn.execute(
            "INSERT INTO schema_migrations (version) VALUES ('INIT') ON CONFLICT DO NOTHING"
        )
    
    async def create_admin_user(self, email: str = "admin@cylvy.com", password: str = "admin123"):
        """Create initial admin user"""
        from app.core.auth import AuthService
        
        try:
            conn = await asyncpg.connect(settings.DATABASE_URL)
            
            # Check if admin user already exists
            existing = await conn.fetchval(
                "SELECT COUNT(*) FROM users WHERE email = $1",
                email
            )
            
            if existing > 0:
                logger.info("Admin user already exists")
                await conn.close()
                return
            
            # Create admin user
            hashed_password = AuthService.get_password_hash(password)
            
            await conn.execute(
                """
                INSERT INTO users (email, hashed_password, full_name, role, is_active)
                VALUES ($1, $2, $3, $4, $5)
                """,
                email,
                hashed_password,
                "Default Admin",
                "superadmin",
                True
            )
            
            await conn.close()
            logger.info(f"Admin user created: {email}")
            
        except Exception as e:
            logger.error(f"Failed to create admin user: {e}")
            raise


async def init_database():
    """Main database initialization function"""
    initializer = DatabaseInitializer()
    await initializer.initialize_database()
    await initializer.create_admin_user()


async def reset_database():
    """Reset database (dangerous - for development only)"""
    if settings.ENVIRONMENT == "production":
        raise ValueError("Cannot reset production database")
    
    logger.warning("Resetting database - this will delete ALL data!")
    
    try:
        conn = await asyncpg.connect(settings.DATABASE_URL)
        
        # Drop all tables
        await conn.execute("""
            DROP SCHEMA public CASCADE;
            CREATE SCHEMA public;
            GRANT ALL ON SCHEMA public TO public;
        """)
        
        await conn.close()
        logger.info("Database reset completed")
        
        # Re-initialize
        await init_database()
        
    except Exception as e:
        logger.error(f"Database reset failed: {e}")
        raise


if __name__ == "__main__":
    # Command line usage
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == "init":
            asyncio.run(init_database())
        elif command == "reset":
            asyncio.run(reset_database())
        else:
            print("Usage: python -m app.core.db_init [init|reset]")
    else:
        asyncio.run(init_database())
