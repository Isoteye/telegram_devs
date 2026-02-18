# utils/constants.py
# Conversation states
STATE = {
    'SELECT_CATEGORY': 1,
    'SELECT_BOT': 2,
    'CONFIRM_ORDER': 3,
    'PAYMENT_METHOD': 4,
    'UPLOAD_PROOF': 5,
    'REQUEST_DESCRIPTION': 10,
    'REQUEST_PLATFORM': 11,
    'REQUEST_BUDGET': 12,
    'REQUEST_DEADLINE': 13,
    'REQUEST_NOTES': 14,
}

# Categories
CATEGORIES = {
    'business': '🏢 Business',
    'automation': '⚡ Automation',
    'crypto': '💰 Crypto',
    'betting': '🎰 Betting',
    'community': '👥 Community',
    'e-commerce': '🛒 E-commerce',
    'customer-service': '📞 Customer Service',
    'content': '📚 Content',
    'social-media': '📱 Social Media'
}

# Payment methods
PAYMENT_METHODS = {
    'mobile_money': '📱 Mobile Money',
    'crypto': '₿ Cryptocurrency',
    'bank_transfer': '🏦 Bank Transfer',
    'paystack': '💳 Paystack'
}

# Budget ranges
BUDGET_RANGES = {
    '20_50': '$20–$50',
    '50_100': '$50–$100',
    '100_plus': '$100+',
    'custom': 'Custom Budget'
}

# Platforms
PLATFORMS = {
    'telegram': 'Telegram Bot',
    'web': 'Web Application',
    'discord': 'Discord Bot',
    'other': 'Other Platform'
}

# Order status display
ORDER_STATUS_DISPLAY = {
    'pending_payment': '⏳ Pending Payment',
    'pending_review': '👁 Pending Review',
    'in_progress': '⚙️ In Progress',
    'completed': '✅ Completed',
    'cancelled': '❌ Cancelled',
    'approved': '✅ Approved',
    'assigned': '👷 Assigned'
}

# Request status display
REQUEST_STATUS_DISPLAY = {
    'new': '🆕 New',
    'reviewed': '👁 Reviewed',
    'quoted': '💰 Quoted',
    'accepted': '✅ Accepted',
    'rejected': '❌ Rejected'
}

# Developer status display
DEVELOPER_STATUS_DISPLAY = {
    'active': '🟢 Active',
    'busy': '🟡 Busy',
    'inactive': '🔴 Inactive'
}