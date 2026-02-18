# database/schema_fix.py
from database.db import engine
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)

def fix_database_schema():
    """Add missing columns to database tables"""
    try:
        with engine.connect() as conn:
            # Check if users table exists
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'"))
            if not result.fetchone():
                logger.info("Users table doesn't exist yet")
                return True
            
            # Check for missing columns in users table
            result = conn.execute(text("PRAGMA table_info(users)"))
            existing_columns = {row[1] for row in result}
            
            # Columns to add
            columns_to_add = [
                ('email', 'TEXT'),
                ('phone', 'TEXT'),
                ('is_premium', 'BOOLEAN DEFAULT 0'),
                ('balance', 'REAL DEFAULT 0.0')
            ]
            
            for column_name, column_type in columns_to_add:
                if column_name not in existing_columns:
                    logger.info(f"Adding column {column_name} to users table")
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))
                    conn.commit()
            
            # Also check for is_developer column
            if 'is_developer' not in existing_columns:
                logger.info("Adding is_developer column to users table")
                conn.execute(text("ALTER TABLE users ADD COLUMN is_developer BOOLEAN DEFAULT 0"))
                conn.commit()
            
            logger.info("✅ Database schema updated successfully")
            return True
            
    except Exception as e:
        logger.error(f"❌ Error fixing database schema: {e}")
        return False