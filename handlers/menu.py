from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging

logger = logging.getLogger(__name__)

async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show support information"""
    try:
        query = update.callback_query
        await query.answer()
        
        text = """
📞 *Support*

Need help with the Bot Marketplace?

*Contact Options:*
👨‍💻 Support Bot: @botmarketplace_support
📧 Email: support@botmarketplace.com
⏰ Hours: 24/7

*Common Issues:*
1. Payment verification issues
2. Order status questions
3. Developer application status
4. Technical problems

*Before Contacting:*
✅ Check your order status in My Orders
✅ Make sure payment is completed
✅ Have your order ID ready

We're here to help! 🚀
        """
        
        keyboard = [
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_support: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading support information.")

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show about information"""
    try:
        query = update.callback_query
        await query.answer()
        
        text = """
🤖 *About Bot Marketplace*

Welcome to the premier Telegram Bot Marketplace!

*Our Mission:*
To connect businesses with talented developers and provide high-quality bot solutions.

*Features:*
✅ Buy pre-built bots instantly
✅ Request custom bot development
✅ Hire professional developers
✅ Secure payment processing
✅ 24/7 customer support

*Security:*
🔒 All payments are secure
🔒 Personal data is protected
🔒 Quality guaranteed

*Contact:*
📧 contact@botmarketplace.com

*Version:* 2.0.0
*Last Updated:* January 2024
        """
        
        keyboard = [
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            [InlineKeyboardButton("📞 Support", callback_data="support")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in show_about: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading about information.")

async def handle_menu_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu_main callback"""
    try:
        query = update.callback_query
        await query.answer()
        
        text = """
🤖 BOT MARKETPLACE - MAIN MENU

Select an option:
"""
        
        keyboard = [
            [InlineKeyboardButton("🛒 Buy a Bot", callback_data="buy_bot")],
            [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("⭐ Featured Bots", callback_data="featured_bots")],
            [InlineKeyboardButton("💼 Become Developer", callback_data="become_developer")],
            [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
            [InlineKeyboardButton("🔍 Browse Jobs", callback_data="job_board")], 
            [InlineKeyboardButton("📞 Support", callback_data="support")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error in handle_menu_main: {e}")
        try:
            await query.edit_message_text("❌ Error loading menu. Please try /menu command.")
        except:
            pass