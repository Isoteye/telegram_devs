from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from utils.constants import CATEGORIES, PAYMENT_METHODS

def get_category_keyboard():
    """Create category selection keyboard"""
    keyboard = []
    for key, value in CATEGORIES.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"category_{key}")])
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)

def get_bots_keyboard(bots, page=0, bots_per_page=5):
    """Create keyboard for bots list with pagination"""
    keyboard = []
    start_idx = page * bots_per_page
    end_idx = start_idx + bots_per_page
    
    for bot in bots[start_idx:end_idx]:
        keyboard.append([
            InlineKeyboardButton(f"🤖 {bot.name} - ${bot.price}", 
                               callback_data=f"bot_{bot.id}")
        ])
    
    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Previous", callback_data=f"page_{page-1}"))
    if end_idx < len(bots):
        nav_buttons.append(InlineKeyboardButton("Next ▶️", callback_data=f"page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([
        InlineKeyboardButton("⬅️ Back to Categories", callback_data="back_to_categories")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def get_bot_details_keyboard(bot_id):
    """Create keyboard for bot details"""
    keyboard = [
        [InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_bot_{bot_id}")],
        [InlineKeyboardButton("⬅️ Back to List", callback_data="back_to_bots")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_payment_methods_keyboard():
    """Create payment methods keyboard"""
    keyboard = []
    for key, value in PAYMENT_METHODS.items():
        keyboard.append([InlineKeyboardButton(value, callback_data=f"payment_{key}")])
    keyboard.append([InlineKeyboardButton("❌ Cancel Order", callback_data="cancel_order")])
    return InlineKeyboardMarkup(keyboard)