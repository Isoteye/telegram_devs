#!/usr/bin/env python3
"""
Database migration script to add missing columns.
Run this script to update your database schema.
"""
import sqlite3
import os
from config import DATABASE_URL

def migrate_database():
    """Add missing columns to existing database"""
    # Extract database path from DATABASE_URL
    # DATABASE_URL format: sqlite:///./bot_marketplace.db
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    print(f"📊 Migrating database: {db_path}")
    
    if not os.path.exists(db_path):
        print(f"❌ Database file not found: {db_path}")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if is_developer column exists
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_developer' not in columns:
            print("🔄 Adding 'is_developer' column to users table...")
            cursor.execute("ALTER TABLE users ADD COLUMN is_developer BOOLEAN DEFAULT 0")
            print("✅ Column added successfully!")
        else:
            print("✅ 'is_developer' column already exists")
        
        # Check if developers table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='developers'")
        if not cursor.fetchone():
            print("⚠️ Developers table doesn't exist. Run the bot to create tables.")
        else:
            print("✅ Developers table exists")
        
        conn.commit()
        print("🎉 Database migration completed!")
        return True
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == '__main__':
    migrate_database()