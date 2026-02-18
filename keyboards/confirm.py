from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def get_confirm_keyboard(confirm_data, cancel_data):
    """Create confirmation keyboard"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Confirm", callback_data=confirm_data),
            InlineKeyboardButton("❌ Cancel", callback_data=cancel_data)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_order_actions_keyboard(order_id):
    """Create order action buttons for admin"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Approve Payment", callback_data=f"approve_{order_id}"),
            InlineKeyboardButton("❌ Reject Payment", callback_data=f"reject_{order_id}")
        ],
        [
            InlineKeyboardButton("⚙️ Mark In Progress", callback_data=f"progress_{order_id}"),
            InlineKeyboardButton("✅ Mark Completed", callback_data=f"complete_{order_id}")
        ],
        [
            InlineKeyboardButton("💬 Message Customer", callback_data=f"message_{order_id}"),
            InlineKeyboardButton("📋 View Details", callback_data=f"details_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_request_actions_keyboard(request_id):
    """Create request action buttons for admin"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Accept", callback_data=f"accept_request_{request_id}"),
            InlineKeyboardButton("❌ Reject", callback_data=f"reject_request_{request_id}")
        ],
        [
            InlineKeyboardButton("💰 Set Quote", callback_data=f"quote_{request_id}"),
            InlineKeyboardButton("💬 Message User", callback_data=f"message_req_{request_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)