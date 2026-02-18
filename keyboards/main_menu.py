from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from database.db import create_session
from database.models import User
from utils.constants import CATEGORIES, PAYMENT_METHODS

def get_main_menu_keyboard(telegram_id: int = None) -> InlineKeyboardMarkup:
    """Create main menu keyboard with admin detection"""
    if telegram_id:
        try:
            db = create_session()
            try:
                user = db.query(User).filter(User.telegram_id == telegram_id).first()
                if user and user.is_admin:
                    keyboard = [
                        [InlineKeyboardButton("🛒 Buy a Bot", callback_data="buy_bot")],
                        [InlineKeyboardButton("🧠 Request Custom Bot", callback_data="request_bot")],
                        [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                        [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")],
                        [InlineKeyboardButton("💬 Support", callback_data="support")]
                    ]
                    return InlineKeyboardMarkup(keyboard)
            finally:
                db.close()
        except Exception:
            pass
    
    # Default user menu
    keyboard = [
        [InlineKeyboardButton("🛒 Buy a Bot", callback_data="buy_bot")],
        [InlineKeyboardButton("🧠 Request Custom Bot", callback_data="request_bot")],
        [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
        [InlineKeyboardButton("💬 Support", callback_data="support")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_category_keyboard() -> InlineKeyboardMarkup:
    """Create category selection keyboard"""
    keyboard = []
    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"category_{key}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

def get_payment_methods_keyboard() -> InlineKeyboardMarkup:
    """Create payment methods keyboard"""
    keyboard = []
    for key, value in PAYMENT_METHODS.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"payment_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")])
    return InlineKeyboardMarkup(keyboard)

def get_back_keyboard(back_to: str = "menu_main") -> InlineKeyboardMarkup:
    """Create simple back keyboard"""
    keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data=back_to)]]
    return InlineKeyboardMarkup(keyboard)