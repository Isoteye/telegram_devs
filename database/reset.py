#!/usr/bin/env python3
"""
Simple database reset script for database folder
"""
import os
import sys

# Add parent directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

try:
    from config import DATABASE_URL
except ImportError:
    print("⚠️ Could not import config")
    DATABASE_URL = "sqlite:///./bot_marketplace.db"

def simple_reset():
    """Simple database reset"""
    db_path = DATABASE_URL.replace('sqlite:///', '')
    
    # Handle SQLite paths
    if db_path.startswith('///'):
        db_path = db_path[3:]
    elif db_path.startswith('//'):
        db_path = db_path[2:]
    elif db_path.startswith('/'):
        db_path = db_path[1:]
    
    print(f"Database path: {db_path}")
    
    if os.path.exists(db_path):
        print(f"⚠️ Database exists: {db_path}")
        print("To reset the database:")
        print(f"1. Delete the file: rm {db_path}")
        print(f"2. Or run the bot, it will create a fresh database")
    else:
        print(f"✅ Database doesn't exist, bot will create it on startup")
    
    input("\nPress Enter to continue...")

if __name__ == '__main__':
    simple_reset()