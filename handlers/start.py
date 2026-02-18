from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import User, DeveloperRequest, RequestStatus
import logging

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    try:
        telegram_id = update.effective_user.id
        username = update.effective_user.username
        first_name = update.effective_user.first_name
        last_name = update.effective_user.last_name
        
        logger.info(f"📱 /start command from {telegram_id} (@{username})")
        
        db = create_session()
        try:
            # Check if user exists
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                # Create new user
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name,
                    is_admin=False,
                    is_developer=False,
                    balance=0.0
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                
                logger.info(f"✅ New user created: {user.id} ({first_name})")
                
                welcome_text = f"""
👋 Welcome to Bot Marketplace, {first_name}!

🤖 Your one-stop shop for Telegram bots

With our marketplace, you can:
✅ Buy pre-built bots instantly
✅ Request custom bot development  
✅ Hire professional developers
✅ Get 24/7 support

Getting Started:
1. Browse available bots with /menu → Buy a Bot
2. Request custom bot with /menu → Request Custom Bot
3. Check your orders with /menu → My Orders
4. Get help with /menu → Support

Start by exploring our bot collection!
                """
            else:
                # Update user info if changed
                user.username = username
                user.first_name = first_name
                user.last_name = last_name
                db.commit()
                
                logger.info(f"✅ Returning user: {user.id} ({first_name})")
                
                welcome_text = f"""
👋 Welcome back, {first_name}!

🤖 Bot Marketplace

What would you like to do today?
✅ Check new bot arrivals
✅ Request custom bot development
✅ View your orders
✅ Get developer support

Quick Stats:
📦 Orders: {user.total_orders}
💰 Balance: ${user.balance:.2f}
👑 Admin: {'✅ Yes' if user.is_admin else '❌ No'}
👨‍💻 Developer: {'✅ Yes' if user.is_developer else '❌ No'}

Use /menu to access all features!
                """
            
            # Create main menu keyboard
            keyboard = [
                [InlineKeyboardButton("📱 Main Menu", callback_data="menu_main")],
                [InlineKeyboardButton("🛒 Buy a Bot", callback_data="buy_bot")],
                [InlineKeyboardButton("⚙️ Request Custom Bot", callback_data="request_custom_bot")],
                [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
                [InlineKeyboardButton("🔍 Browse Jobs", callback_data="job_board")],
                [InlineKeyboardButton("💬 Support", callback_data="support")],
               

            ]
            
            # Add admin button if user is admin
            if user.is_admin:
                keyboard.insert(0, [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
            
            # Add developer button if user is developer
            if user.is_developer:
                keyboard.append([InlineKeyboardButton("👨‍💻 Developer Dashboard", callback_data="dev_dashboard")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=reply_markup
            )
            
            logger.info(f"✅ Start command completed for user {telegram_id}")
            
        except Exception as e:
            logger.error(f"❌ Database error in start_command: {e}", exc_info=True)
            
            # Fallback welcome message
            await update.message.reply_text(
                f"👋 Welcome to Bot Marketplace, {first_name}!\n\n"
                f"🤖 Your Telegram Bot Marketplace\n\n"
                f"Use /menu to access the main menu.\n"
                f"Use /help for assistance."
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"❌ Error in start_command: {e}", exc_info=True)
        
        try:
            await update.message.reply_text(
                "👋 Welcome to Bot Marketplace!\n\n"
                "We're experiencing technical issues. Please use /menu to continue."
            )
        except:
            pass

async def become_developer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle become developer callback"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                await query.edit_message_text("❌ Please use /start first to create your account.")
                return
            
            # Check if already a developer
            if user.is_developer:
                await query.edit_message_text(
                    "🎉 You're already a developer!\n\n"
                    "Use /developer to access your dashboard."
                )
                return
            
            # Check for pending request
            pending_request = db.query(DeveloperRequest).filter(
                DeveloperRequest.user_id == user.id,
                DeveloperRequest.status == RequestStatus.NEW
            ).first()
            
            if pending_request:
                await query.edit_message_text(
                    "📝 Your developer application is pending review.\n\n"
                    "Our admin team will review your application soon.\n"
                    "You'll be notified once a decision is made.\n\n"
                    "Average review time: 24-48 hours ⏰"
                )
                return
            
            # Simple developer application
            text = """
👨‍💻 Become a Developer

Join our developer community and start earning!

Requirements:
✅ Experience with Python
✅ Knowledge of Telegram Bot API
✅ Portfolio of previous work

Benefits:
💰 Earn from bot development
📈 Build your reputation
🤝 Work with global clients

To apply, please contact @botmarketplace_support
            """
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Contact Support", callback_data="support")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in become_developer_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing request. Please try again.")