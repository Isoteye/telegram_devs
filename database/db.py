"""
Database initialization and connection management
"""
import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from config import DATABASE_URL

logger = logging.getLogger(__name__)

# Create engine
engine = create_engine(DATABASE_URL, echo=False, pool_pre_ping=True)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Session = scoped_session(SessionLocal)

# Create base class for models
Base = declarative_base()

def create_session():
    """Create a new database session"""
    return Session()

def close_session():
    """Close the current database session"""
    Session.remove()

def init_db():
    """Initialize database tables"""
    print("🔧 Importing database models...")
    try:
        # Import all models to ensure they're registered
        from database import models
        print("✅ Models imported successfully")
        
        # Check if database file exists
        if DATABASE_URL.startswith('sqlite:///'):
            db_file = DATABASE_URL.replace('sqlite:///', '')
            if os.path.exists(db_file):
                print(f"📁 Database file exists: {db_file}")
                # Backup existing database
                backup_file = f"{db_file}.backup"
                if os.path.exists(db_file):
                    import shutil
                    try:
                        shutil.copy2(db_file, backup_file)
                        print(f"📦 Backed up to: {backup_file}")
                    except Exception as e:
                        print(f"⚠️ Could not backup: {e}")
        
        print("🔄 Creating fresh database...")
        # Drop all tables and create fresh ones
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        
        print("✅ Database tables created successfully")
        
        # Verify tables were created
        db = create_session()
        try:
            tables = db.execute(text("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)).fetchall()
            
            print(f"📊 Created tables: {len(tables)}")
            for table in tables:
                print(f"   - {table.name}")
            
            # Add initial data
            add_initial_data()
            
            return True
        except Exception as e:
            logger.error(f"❌ Error listing tables: {e}", exc_info=True)
            return False
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error creating database tables: {e}", exc_info=True)
        return False

def add_initial_data():
    """Add initial data to database"""
    db = create_session()
    try:
        from database.models import User, Bot
        from config import SUPER_ADMIN_ID
        
        # Check if super admin exists
        super_admin = db.query(User).filter(User.telegram_id == str(SUPER_ADMIN_ID)).first()
        if not super_admin:
            # Create super admin user
            super_admin = User(
                telegram_id=str(SUPER_ADMIN_ID),
                username="admin",
                first_name="Super",
                last_name="Admin",
                is_admin=True,
                is_developer=False,
                currency="USD",
                country="US",
                currency_symbol="$"
            )
            db.add(super_admin)
            print("✅ Created super admin user")
        
        # Add some sample bots if none exist
        bots_count = db.query(Bot).count()
        if bots_count == 0:
            sample_bots = [
                Bot(
                    name="Telegram Marketing Bot",
                    description="Automated marketing and lead generation bot for Telegram",
                    price=299.99,
                    category="Telegram Bots",
                    features="User segmentation, Automated messaging, Analytics dashboard",
                    delivery_time="3-5 days"
                ),
                Bot(
                    name="E-commerce Website",
                    description="Complete e-commerce solution with payment integration",
                    price=799.99,
                    category="Websites",
                    features="Product catalog, Shopping cart, Payment gateway, Admin panel",
                    delivery_time="7-10 days"
                ),
                Bot(
                    name="Inventory Management System",
                    description="Desktop application for inventory tracking",
                    price=499.99,
                    category="Desktop Software",
                    features="Stock tracking, Barcode scanning, Reporting, Multi-user access",
                    delivery_time="5-7 days"
                )
            ]
            
            for bot in sample_bots:
                db.add(bot)
            
            print("✅ Added sample software listings")
        
        db.commit()
        
    except Exception as e:
        logger.error(f"❌ Error adding initial data: {e}", exc_info=True)
        db.rollback()
    finally:
        db.close()

def test_connection():
    """Test database connection"""
    try:
        db = create_session()
        try:
            # Simple query to test connection
            result = db.execute(text("SELECT 1 as test")).fetchone()
            return result.test == 1
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {e}")
            return False
        finally:
            db.close()
    except Exception as e:
        logger.error(f"❌ Could not create session: {e}")
        return False
