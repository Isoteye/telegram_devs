"""
Configuration file for Software Marketplace
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ========== TELEGRAM BOT CONFIG ==========
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN_HERE")
SUPER_ADMIN_ID = os.getenv("SUPER_ADMIN_ID", "YOUR_TELEGRAM_ID_HERE")

# ========== DATABASE CONFIG ==========
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///software_marketplace.db")

# ========== PAYMENT CONFIG ==========
DEFAULT_CURRENCY = "USD"
DEFAULT_CURRENCY_SYMBOL = "$"

# Developer payout threshold
DEVELOPER_PAYOUT_THRESHOLD = 50.0

# Payment Methods Configuration
PAYMENT_METHODS = {
    "paystack": {
        "name": "Paystack",
        "is_active": True,
        "public_key": os.getenv("PAYSTACK_PUBLIC_KEY", ""),
        "secret_key": os.getenv("PAYSTACK_SECRET_KEY", ""),
        "instructions": "Pay securely with Paystack using card, bank transfer, or USSD."
    },
    "bank_transfer": {
        "name": "Bank Transfer",
        "is_active": True,
        "account": os.getenv("BANK_ACCOUNT", "Contact Support for Account Details"),
        "name": os.getenv("BANK_NAME", "Software Marketplace"),
        "instructions": "Transfer the exact amount to the account below and upload proof of payment."
    }
}

# ========== CUSTOM SOFTWARE PRICES ==========
CUSTOM_BOT_PRICES = {
    'basic': 299.0,
    'standard': 799.0,
    'premium': 1499.0,
    'enterprise': 2999.0
}

CUSTOM_BOT_DELIVERY = {
    'basic': '2-3 weeks',
    'standard': '3-4 weeks',
    'premium': '4-6 weeks',
    'enterprise': '8-12 weeks'
}

# ========== DEVELOPER APPLICATION SETTINGS ==========
DEVELOPER_APPLICATION = {
    'min_skills_length': 50,
    'default_hourly_rate': 25.0,
    'review_days': 2,
    'auto_approve': False,
    'required_fields': ['skills_experience']
}

# ========== CATEGORIES FOR SOFTWARE ==========
SOFTWARE_CATEGORIES = [
    "Web Application",
    "Mobile App",
    "Telegram Bot",
    "Desktop Software",
    "E-commerce",
    "Business Management",
    "Automation Tool",
    "Custom Solution"
]

# ========== LOGGING CONFIG ==========
LOG_LEVEL = "INFO"
LOG_FILE = "software_marketplace.log"

# ========== SECURITY CONFIG ==========
MAX_LOGIN_ATTEMPTS = 5
SESSION_TIMEOUT = 3600

# ========== API CONFIG ==========
API_TIMEOUT = 30
API_RETRY_ATTEMPTS = 3

# ========== NOTIFICATION CONFIG ==========
SEND_EMAIL_NOTIFICATIONS = True
SEND_TELEGRAM_NOTIFICATIONS = True

# ========== TEST MODE ==========
TEST_MODE = os.getenv("TEST_MODE", "False").lower() == "true"

# ========== CUSTOM BUDGET RECOMMENDATIONS ==========
CUSTOM_BUDGET_RECOMMENDATIONS = {
    'basic': {
        'min': 100,
        'max': 499,
        'description': 'Simple software with basic features',
        'examples': ['Simple website', 'Basic automation script', 'Small utility bot']
    },
    'standard': {
        'min': 500,
        'max': 1499,
        'description': 'Advanced software with more features',
        'examples': ['E-commerce website', 'Mobile app with API', 'Advanced Telegram bot']
    },
    'premium': {
        'min': 1500,
        'max': 2999,
        'description': 'Complex software with custom integrations',
        'examples': ['Multi-vendor marketplace', 'Custom CRM system', 'Enterprise automation']
    },
    'enterprise': {
        'min': 3000,
        'max': 10000,
        'description': 'Large-scale business solutions',
        'examples': ['Custom ERP system', 'Large-scale platform', 'Complex SaaS application']
    }
}

# ========== PAYMENT CONFIG ==========
# Paystack Configuration - Multi-currency support
PAYSTACK_SUPPORTED_CURRENCIES = [
    "USD", "GHS", "NGN", "KES", "ZAR", "XOF", "XAF", "EUR", "GBP"
]

DEFAULT_CURRENCY = "USD"
DEFAULT_COUNTRY = "GH"

# Country to currency mapping
COUNTRY_CURRENCY_MAP = {
    "GH": "GHS",
    "NG": "NGN",
    "KE": "KES",
    "ZA": "ZAR",
    "CI": "XOF",
    "CM": "XAF",
    "FR": "EUR",
    "GB": "GBP",
    "US": "USD",
    "CA": "USD",
    "AU": "USD",
}

# Currency symbols
CURRENCY_SYMBOLS = {
    "USD": "$",
    "GHS": "GH₵",
    "NGN": "₦",
    "KES": "KSh",
    "ZAR": "R",
    "XOF": "CFA",
    "XAF": "FCFA",
    "EUR": "€",
    "GBP": "£"
}

# Fixed exchange rates (update these regularly)
EXCHANGE_RATES = {
    "USD": 1.0,
    "GHS": 10.5,
    "NGN": 1450.0,
    "KES": 160.0,
    "ZAR": 18.0,
    "XOF": 600.0,
    "XAF": 600.0,
    "EUR": 0.92,
    "GBP": 0.79
}

# ========== JOB MARKETPLACE CATEGORIES ==========
JOB_CATEGORIES = [
    "Web Development",
    "Mobile App Development",
    "Telegram Bot Development",
    "Graphic Design",
    "Content Writing",
    "Digital Marketing",
    "Data Entry",
    "Virtual Assistance",
    "Customer Support",
    "Other"
]
