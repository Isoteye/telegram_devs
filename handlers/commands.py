from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from config import SUPER_ADMIN_ID, DEFAULT_CURRENCY, DEFAULT_COUNTRY, CURRENCY_SYMBOLS, TELEGRAM_TOKEN, DATABASE_URL
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - WITH CURRENCY SELECTION - FIXED VERSION"""
    try:
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        
        logger.info(f"📱 /start command from {telegram_id} (@{username})")
        
        # Use simple direct SQL to avoid ORM issues
        import sqlite3
        from config import SUPER_ADMIN_ID, DEFAULT_CURRENCY, DEFAULT_COUNTRY, CURRENCY_SYMBOLS
        
        try:
            # Connect to database directly
            conn = sqlite3.connect('software_marketplace.db')
            cursor = conn.cursor()
            
            # Check if users table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='users'
            """)
            if not cursor.fetchone():
                # Create users table if it doesn't exist (MATCHING models.py)
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
                conn.commit()
                logger.info("✅ Created users table")
            
            # Check if user exists
            cursor.execute(
                "SELECT id, is_admin, is_developer, balance, total_orders, currency, country FROM users WHERE telegram_id = ?", 
                (str(telegram_id),)
            )
            user = cursor.fetchone()
            
            if not user:
                # Check if user is super admin
                is_super_admin = str(telegram_id) == str(SUPER_ADMIN_ID)
                
                # Ask for country/currency
                keyboard = [
                    [InlineKeyboardButton("🇬🇭 Ghana (GHS)", callback_data="country_GH_GHS")],
                    [InlineKeyboardButton("🇳🇬 Nigeria (NGN)", callback_data="country_NG_NGN")],
                    [InlineKeyboardButton("🇰🇪 Kenya (KES)", callback_data="country_KE_KES")],
                    [InlineKeyboardButton("🇿🇦 South Africa (ZAR)", callback_data="country_ZA_ZAR")],
                    [InlineKeyboardButton("🇺🇸 United States (USD)", callback_data="country_US_USD")],
                    [InlineKeyboardButton("🇬🇧 United Kingdom (GBP)", callback_data="country_GB_GBP")],
                    [InlineKeyboardButton("🇪🇺 Europe (EUR)", callback_data="country_FR_EUR")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"👋 Welcome to Software Marketplace, {first_name}!\n\n"
                    f"🌍 **Please select your country/currency:**\n\n"
                    f"This will show prices in your local currency and allow you to pay in your preferred currency.",
                    reply_markup=reply_markup
                )
                
                # Store user info temporarily
                context.user_data['new_user'] = {
                    'telegram_id': str(telegram_id),
                    'username': username,
                    'first_name': first_name,
                    'last_name': last_name,
                    'is_super_admin': is_super_admin
                }
                
                return
            else:
                # Update user info if changed
                cursor.execute("""
                    UPDATE users 
                    SET username = ?, first_name = ?, last_name = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE telegram_id = ?
                """, (username, first_name, last_name, str(telegram_id)))
                
                # Ensure super admin remains admin
                if str(telegram_id) == str(SUPER_ADMIN_ID):
                    cursor.execute("UPDATE users SET is_admin = 1 WHERE telegram_id = ?", (str(telegram_id),))
                
                conn.commit()
                
                # Get order count (handle missing table)
                order_count = 0
                try:
                    cursor.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user[0],))
                    result = cursor.fetchone()
                    if result:
                        order_count = result[0]
                except sqlite3.OperationalError as e:
                    if "no such table" in str(e):
                        # Create orders table if it doesn't exist
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
                        conn.commit()
                        order_count = 0
                    else:
                        order_count = 0
                        print(f"⚠️ Error counting orders: {e}")
                
                # Update user's total orders
                cursor.execute("UPDATE users SET total_orders = ? WHERE id = ?", (order_count, user[0]))
                conn.commit()
                
                logger.info(f"✅ Returning user: {user[0]} ({first_name}) - Currency: {user[5]}")
                
                # Show welcome with user's currency
                currency_symbol = user[6] if len(user) > 6 and user[6] else "$"  # Get currency_symbol from DB
                if not currency_symbol:
                    currency_symbol = CURRENCY_SYMBOLS.get(user[5], "$")  # Fallback to config
                
                welcome_text = f"""👋 Welcome back, {first_name}!

🚀 Software Marketplace

What would you like to do today?
✅ Check new software arrivals
✅ Request custom development
✅ View your orders
✅ Get developer support

Your Settings:
🌍 Country: {user[6] if len(user) > 6 and user[6] else 'Not set'}
💰 Currency: {user[5]} ({currency_symbol})
📦 Orders: {order_count}
💵 Balance: {currency_symbol}{user[3]:.2f}
👑 Admin: {'✅ Yes' if user[1] else '❌ No'}
👨‍💻 Developer: {'✅ Yes' if user[2] else '❌ No'}

Use /menu to access all features!"""
            
            conn.close()
            
            # Create main menu keyboard
            keyboard = [
                [InlineKeyboardButton("📱 Main Menu", callback_data="menu_main")],
                [InlineKeyboardButton("🛒 Buy Software", callback_data="buy_bot")],
                [InlineKeyboardButton("⚙️ Request Custom Software", callback_data="start_custom_request")],
                [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                [InlineKeyboardButton("💬 Support", callback_data="support")]
            ]
            
            # Check if user is admin
            if user and user[1]:  # is_admin
                keyboard.insert(0, [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
            
            # Check if user is developer
            if user and user[2]:  # is_developer
                keyboard.append([InlineKeyboardButton("👨‍💻 Developer Dashboard", callback_data="dev_dashboard")])
            
            # Add currency change button
            keyboard.append([InlineKeyboardButton("🌍 Change Currency", callback_data="change_currency")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup
            )
            
            logger.info(f"✅ Start command completed for user {telegram_id}")
            
        except Exception as e:
            logger.error(f"❌ Database error in start_command: {e}", exc_info=True)
            
            # Fallback welcome message - don't use welcome_text variable here
            await update.message.reply_text(
                f"👋 Welcome to Software Marketplace, {first_name}!\n\n"
                f"🚀 Your Software Marketplace\n\n"
                f"Use /menu to access the main menu.\n"
                f"Use /help for assistance."
            )
            
    except Exception as e:
        logger.error(f"❌ Error in start_command: {e}", exc_info=True)
        
        try:
            await update.message.reply_text(
                "👋 Welcome to Software Marketplace!\n\n"
                "We're experiencing technical issues. Please use /menu to continue."
            )
        except:
            pass

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    try:
        help_text = """🚀 Software Marketplace Help

Available Commands:
/start - Start the bot and create account
/menu - Show main menu with all options
/help - Show this help message
/debug - Show bot status (admins)

For Users:
1. Use /menu → Buy Software to purchase pre-built solutions
2. Use /menu → Request Custom Software for custom development
3. Use /menu → My Orders to track purchases
4. Use /menu → Support for help

For Developers:
/developer - Access developer dashboard
/claim ORDER_ID - Claim an available order

For Admins:
/admin - Access admin panel

Need Help?
- Use /menu → Support
- Contact: @Isope23
- Email: devtools520@gmail.com"""
        
        await update.message.reply_text(help_text)
        
    except Exception as e:
        logger.error(f"Error in help_command: {e}")
        await update.message.reply_text("Use /menu to access the main menu.")


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug command"""
    try:
        from config import DATABASE_URL, TELEGRAM_TOKEN, SUPER_ADMIN_ID
        
        telegram_id = update.effective_user.id
        
        # Check database connection
        from database.db import create_session
        db = create_session()
        
        # Try to get user count safely
        try:
            user_count = db.execute("SELECT COUNT(*) FROM users").scalar()
        except:
            user_count = 0
            
        db.close()
        
        message = f"""🔧 Debug Information

User:
Telegram ID: {telegram_id}
Super Admin ID: {SUPER_ADMIN_ID}
Is Super Admin: {'✅ Yes' if str(telegram_id) == str(SUPER_ADMIN_ID) else '❌ No'}

Bot Status:
Token: {TELEGRAM_TOKEN[:15]}...{' (SET)' if TELEGRAM_TOKEN != 'YOUR_BOT_TOKEN_HERE' else ' (NOT SET)'}
Database: {DATABASE_URL}
Users in DB: {user_count}
Status: ✅ Running

Available Commands:
✅ /start - Working
✅ /menu - Working  
✅ /help - Working
✅ /debug - Working
✅ /admin - Working
✅ /developer - Working
✅ /verify - Working"""
        
        await update.message.reply_text(message)
        
    except Exception as e:
        logger.error(f"Debug error: {e}")
        await update.message.reply_text(f"❌ Debug Error: {str(e)[:200]}")

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /menu command - FIXED VERSION with updated callback_data"""
    try:
        telegram_id = update.effective_user.id
        
        text = """🚀 SOFTWARE MARKETPLACE - MAIN MENU

Select an option:"""
        
        keyboard = [
            [InlineKeyboardButton("🛒 Buy Software", callback_data="buy_bot")],
            [InlineKeyboardButton("⚙️ Request Custom Software", callback_data="start_custom_request")],
            [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
            [InlineKeyboardButton("🔍 Browse Jobs", callback_data="job_board")],
            [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📋 My Jobs", callback_data="my_jobs")],
            [InlineKeyboardButton("⭐ Featured Software", callback_data="featured_bots")],
            [InlineKeyboardButton("💼 Become Developer", callback_data="start_developer_application")],
            [InlineKeyboardButton("📞 Support", callback_data="support")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ]
        
        # Try to get user info, but don't fail if there's an error
        try:
            from database.db import create_session
            from database.models import User
            
            db = create_session()
            try:
                user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
                
                if user:
                    # Add admin button if user is admin
                    if user.is_admin:
                        keyboard.insert(0, [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
                    
                    # Add developer button if user is developer
                    if user.is_developer:
                        keyboard.append([InlineKeyboardButton("👨‍💻 Developer Dashboard", callback_data="dev_dashboard")])
            except Exception as e:
                logger.warning(f"Could not check user permissions for menu: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Database error in menu command: {e}")
            # Continue without admin/developer buttons
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in menu_command: {e}")
        await update.message.reply_text("❌ Error loading menu. Please try again.")