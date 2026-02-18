from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes
from config import CURRENCY_SYMBOLS, COUNTRY_CURRENCY_MAP
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
logger = logging.getLogger(__name__)


async def handle_country_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle country/currency selection for new users"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract country and currency from callback data: country_GH_GHS
        data = query.data.replace('country_', '')
        country_code, currency_code = data.split('_')
        
        # Get user data from context
        user_data = context.user_data.get('new_user')
        if not user_data:
            await query.edit_message_text("❌ User data not found. Please use /start again.")
            return
        
        from config import CURRENCY_SYMBOLS
        
        # Get currency symbol
        currency_symbol = CURRENCY_SYMBOLS.get(currency_code, "$")
        
        # Save user to database with selected currency
        import sqlite3
        conn = sqlite3.connect('software_marketplace.db')
        cursor = conn.cursor()
        
        # Create user with selected currency (MATCHING models.py)
        cursor.execute("""
            INSERT INTO users (telegram_id, username, first_name, last_name, country, currency, currency_symbol, is_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_data['telegram_id'],
            user_data['username'],
            user_data['first_name'],
            user_data['last_name'],
            country_code,
            currency_code,
            currency_symbol,
            user_data['is_super_admin']
        ))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        # Clear context
        context.user_data.pop('new_user', None)
        
        # Show welcome message with selected currency
        text = f"""✅ **Welcome to Software Marketplace!**

🌍 **Your settings:**
Country: {country_code}
Currency: {currency_code} ({currency_symbol})

💰 **All prices will be shown in {currency_code}**
💳 **You can pay in {currency_code}**
🌐 **Browse software in your local currency**

Click **"Main Menu"** to get started!"""
        
        keyboard = [
            [InlineKeyboardButton("📱 Main Menu", callback_data="menu_main")],
            [InlineKeyboardButton("🌍 Change Currency", callback_data="change_currency")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in handle_country_selection: {e}", exc_info=True)
        await query.edit_message_text("❌ Error setting your currency. Please try /start again.")

async def handle_change_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow users to change their currency"""
    try:
        query = update.callback_query
        await query.answer()
        
        keyboard = [
            [InlineKeyboardButton("🇬🇭 Ghana (GHS)", callback_data="set_currency_GHS")],
            [InlineKeyboardButton("🇳🇬 Nigeria (NGN)", callback_data="set_currency_NGN")],
            [InlineKeyboardButton("🇰🇪 Kenya (KES)", callback_data="set_currency_KES")],
            [InlineKeyboardButton("🇿🇦 South Africa (ZAR)", callback_data="set_currency_ZAR")],
            [InlineKeyboardButton("🇺🇸 United States (USD)", callback_data="set_currency_USD")],
            [InlineKeyboardButton("🇬🇧 United Kingdom (GBP)", callback_data="set_currency_GBP")],
            [InlineKeyboardButton("🇪🇺 Europe (EUR)", callback_data="set_currency_EUR")],
            [InlineKeyboardButton("⬅️ Back", callback_data="menu_main")]
        ]
        
        text = """🌍 **Change Your Currency**

Select your preferred currency:

• All prices will be shown in your selected currency
• You can pay in your local currency
• Your past orders will remain in original currency

Select a currency:"""
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in handle_change_currency: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading currency options.")


        await query.edit_message_text("❌ Error loading currency options.")

async def handle_set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's currency preference"""
    try:
        query = update.callback_query
        await query.answer()
        
        currency_code = query.data.replace('set_currency_', '')
        
        from config import CURRENCY_SYMBOLS, COUNTRY_CURRENCY_MAP
        
        # Find country for this currency
        country_code = None
        for country, currency in COUNTRY_CURRENCY_MAP.items():
            if currency == currency_code:
                country_code = country
                break
        
        if not country_code:
            # Default to GH for GHS, US for USD, etc.
            if currency_code == "GHS":
                country_code = "GH"
            elif currency_code == "USD":
                country_code = "US"
            else:
                country_code = "US"  # Default
        
        # Get currency symbol
        currency_symbol = CURRENCY_SYMBOLS.get(currency_code, "$")
        
        # Update user in database (MATCHING models.py)
        import sqlite3
        conn = sqlite3.connect('software_marketplace.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE users 
            SET currency = ?, country = ?, currency_symbol = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE telegram_id = ?
        """, (currency_code, country_code, currency_symbol, str(query.from_user.id)))
        
        conn.commit()
        conn.close()
        
        text = f"""✅ **Currency Updated!**

Your currency has been set to:
**{currency_code} ({currency_symbol})**

• All prices will now show in {currency_code}
• You can pay in {currency_code}
• Browse software in your local currency"""
        
        keyboard = [
            [InlineKeyboardButton("📱 Main Menu", callback_data="menu_main")],
            [InlineKeyboardButton("🛒 Browse Software", callback_data="buy_bot")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in handle_set_currency: {e}", exc_info=True)
        await query.edit_message_text("❌ Error updating currency. Please try again.")


