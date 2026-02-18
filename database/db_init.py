# database/db_init.py - UPDATED TO WORK WITH YOUR STRUCTURE
import os
import traceback
import sqlite3
import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize database with proper error handling - UPDATED"""
    try:
        print("=" * 60)
        print("🔄 DATABASE INITIALIZATION")
        print("=" * 60)
        
        # First, try the proper SQLAlchemy method
        print("📦 Setting up database engine...")
        try:
            # Import after logging is set up
            from database.db import engine, Base, init_db, add_initial_data
            from database.models import User, Bot, Order, CustomRequest, Developer, DeveloperRequest, Transaction, PaymentMethodConfig
            
            print("✅ Database modules imported successfully")
            
            # Check if database file exists
            from config import DATABASE_URL
            if DATABASE_URL.startswith('sqlite:///'):
                db_file = DATABASE_URL.replace('sqlite:///', '')
                if os.path.exists(db_file):
                    print(f"📁 Database file exists: {db_file}")
                    print(f"📏 File size: {os.path.getsize(db_file)} bytes")
                else:
                    print("📁 Creating new database file...")
            
            # Initialize database (this creates tables)
            print("🔄 Creating database tables...")
            success = init_db()
            
            if success:
                print("✅ Database tables created successfully")
                
                # Add initial data
                print("🔄 Adding initial data...")
                add_initial_data()
                
                return True
            else:
                print("❌ Database initialization failed, trying fallback...")
                return create_fallback_database()
                
        except ImportError as e:
            print(f"❌ Import error: {e}")
            traceback.print_exc()
            return create_fallback_database()
        except Exception as e:
            print(f"❌ Error with SQLAlchemy approach: {e}")
            traceback.print_exc()
            return create_fallback_database()
            
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()
        return create_fallback_database()

def create_fallback_database():
    """Create database tables using direct SQL as fallback"""
    try:
        print("🔄 Creating fallback database...")
        
        # Connect to database
        conn = sqlite3.connect('software_marketplace.db')
        cursor = conn.cursor()
        
        # Create users table (matching models.py)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id TEXT UNIQUE NOT NULL,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                email TEXT,
                phone TEXT,
                country TEXT DEFAULT 'GH',
                currency TEXT DEFAULT 'USD',
                currency_symbol TEXT DEFAULT '$',
                is_admin BOOLEAN DEFAULT 0,
                is_developer BOOLEAN DEFAULT 0,
                balance REAL DEFAULT 0.0,
                total_orders INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create bots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT UNIQUE,
                description TEXT,
                features TEXT,
                price REAL NOT NULL,
                category TEXT,
                delivery_time TEXT,
                is_available BOOLEAN DEFAULT 1,
                is_featured BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                bot_id INTEGER,
                assigned_developer_id INTEGER,
                amount REAL NOT NULL,
                status TEXT DEFAULT 'pending_payment',
                payment_method TEXT,
                payment_status TEXT DEFAULT 'pending',
                payment_proof_url TEXT,
                payment_reference TEXT,
                payment_metadata TEXT,
                admin_notes TEXT,
                developer_notes TEXT,
                delivered_at TIMESTAMP,
                paid_at TIMESTAMP,
                refunded_at TIMESTAMP,
                refund_reason TEXT,
                refund_metadata TEXT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (bot_id) REFERENCES bots(id)
            )
        """)
        
        # Create custom_requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS custom_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE NOT NULL,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                features TEXT,
                budget_tier TEXT,
                estimated_price REAL DEFAULT 0.0,
                deposit_paid REAL DEFAULT 0.0,
                is_deposit_paid BOOLEAN DEFAULT 0,
                delivery_time TEXT,
                timeline TEXT,
                status TEXT DEFAULT 'new',
                assigned_to INTEGER,
                admin_notes TEXT,
                payment_reference TEXT,
                payment_metadata TEXT,
                deposit_paid_at TIMESTAMP,
                refunded_at TIMESTAMP,
                refund_reason TEXT,
                refund_metadata TEXT,
                approved_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Create developers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS developers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                developer_id TEXT UNIQUE,
                status TEXT DEFAULT 'active',
                is_available BOOLEAN DEFAULT 1,
                skills TEXT,
                experience TEXT,
                hourly_rate REAL DEFAULT 25.0,
                portfolio_url TEXT,
                github_url TEXT,
                completed_orders INTEGER DEFAULT 0,
                rating REAL DEFAULT 0.0,
                earnings REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Create developer_requests table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS developer_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                skills_experience TEXT NOT NULL,
                portfolio_url TEXT,
                github_url TEXT,
                hourly_rate REAL DEFAULT 25.0,
                status TEXT DEFAULT 'new',
                reviewed_by INTEGER,
                reviewed_at TIMESTAMP,
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (reviewed_by) REFERENCES users(id)
            )
        """)
        
        # Create transactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT UNIQUE,
                order_id INTEGER,
                user_id INTEGER,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                payment_method TEXT,
                status TEXT,
                reference TEXT,
                gateway_response TEXT,
                transaction_data TEXT,
                usd_amount REAL,
                refund_data TEXT,
                verified_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        
        # Create payment_method_configs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_method_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                method TEXT UNIQUE NOT NULL,
                is_active BOOLEAN DEFAULT 1,
                config_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
        
        print("✅ Fallback database created successfully")
        
        # Add sample data
        add_sample_data()
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating fallback database: {e}")
        traceback.print_exc()
        return False

def add_sample_data():
    """Add sample data to database"""
    try:
        import sqlite3
        
        conn = sqlite3.connect('software_marketplace.db')
        cursor = conn.cursor()
        
        # Add sample bots if none exist
        cursor.execute("SELECT COUNT(*) FROM bots")
        bot_count = cursor.fetchone()[0]
        
        if bot_count == 0:
            sample_bots = [
                ("Telegram Marketing Bot", "telegram-marketing-bot", 
                 "Automated marketing and lead generation bot for Telegram", 
                 299.99, "Telegram Bots", "User segmentation, Automated messaging, Analytics dashboard", "3-5 days"),
                ("E-commerce Website", "ecommerce-website",
                 "Complete e-commerce solution with payment integration", 
                 799.99, "Websites", "Product catalog, Shopping cart, Payment gateway, Admin panel", "7-10 days"),
                ("Inventory Management System", "inventory-management",
                 "Desktop application for inventory tracking", 
                 499.99, "Desktop Software", "Stock tracking, Barcode scanning, Reporting, Multi-user access", "5-7 days")
            ]
            
            for bot in sample_bots:
                cursor.execute("""
                    INSERT INTO bots (name, slug, description, price, category, features, delivery_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, bot)
            
            print("✅ Added sample software listings")
        
        conn.commit()
        conn.close()
        
    except Exception as e:
        print(f"⚠️ Could not add sample data: {e}")

def test_database_connection():
    """Test database connection before starting bot"""
    print("=" * 60)
    print("🔧 DATABASE CONNECTION TEST")
    print("=" * 60)
    
    try:
        # First try SQLAlchemy connection
        try:
            from database.db import create_session
            
            db = create_session()
            try:
                # Test basic connection
                result = db.execute(text("SELECT 1 as test")).fetchone()
                print(f"✅ Basic connection test: {result.test}")
                
                # Check if users table exists
                tables = db.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' 
                    ORDER BY name
                """)).fetchall()
                
                print(f"📊 Tables found: {len(tables)}")
                for table in tables:
                    print(f"   - {table.name}")
                
                # Check users table specifically
                if any(table.name == 'users' for table in tables):
                    print("✅ Users table exists")
                    
                    # Count users
                    try:
                        user_count = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
                        print(f"👥 Total users: {user_count}")
                    except:
                        print("⚠️ Could not count users")
                else:
                    print("⚠️ Users table doesn't exist")
                    
                return True
            except Exception as e:
                print(f"❌ SQLAlchemy test failed: {e}")
                traceback.print_exc()
                return False
            finally:
                db.close()
        except ImportError:
            # Fallback to direct SQLite test
            return test_database_fallback()
            
    except Exception as e:
        print(f"❌ Could not create database session: {e}")
        traceback.print_exc()
        return test_database_fallback()

def test_database_fallback():
    """Fallback database test using direct SQLite"""
    try:
        conn = sqlite3.connect('software_marketplace.db')
        cursor = conn.cursor()
        
        # Test basic connection
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        print(f"✅ Basic connection test: {result[0]}")
        
        # Check tables
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' 
            ORDER BY name
        """)
        tables = cursor.fetchall()
        
        print(f"📊 Tables found: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Check users table specifically
        if any('users' in table for table in tables):
            print("✅ Users table exists")
            
            # Count users
            try:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                print(f"👥 Total users: {user_count}")
            except:
                print("⚠️ Could not count users")
        else:
            print("⚠️ Users table doesn't exist")
            
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Database test failed: {e}")
        traceback.print_exc()
        return False