"""
Helper functions for Software Marketplace
"""
import random
import string
from datetime import datetime
import uuid
from datetime import datetime

def generate_order_id():
    """Generate unique order ID"""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_chars = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"ORD{timestamp}{random_chars}"

def generate_request_id():
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_part = uuid.uuid4().hex[:6].upper()
    return f"CR{timestamp}{random_part}"    # ✅ new prefix (CR)


def format_price(price):
    """Format price with 2 decimal places"""
    try:
        return f"${float(price):.2f}"
    except:
        return "$0.00"

def validate_email(email):
    """Simple email validation"""
    if '@' not in email or '.' not in email:
        return False
    return True

def safe_text(text: str) -> str:
    """Remove Markdown formatting that might cause parsing errors"""
    replacements = {
        '_': '\\_',
        '*': '\\*',
        '[': '\\[',
        ']': '\\]',
        '(': '\\(',
        ')': '\\)',
        '~': '\\~',
        '`': '\\`',
        '>': '\\>',
        '#': '\\#',
        '+': '\\+',
        '-': '\\-',
        '=': '\\=',
        '|': '\\|',
        '{': '\\{',
        '}': '\\}',
        '.': '\\.',
        '!': '\\!'
    }
    
    for old, new in replacements.items():
        text = text.replace(old, new)
    
    return text


# Add this helper function at the top of main.py after imports
def get_request_status_enum():
    """Helper function to get RequestStatus enum with fallback"""
    from database.models import RequestStatus
    
    # Try to get common enum values with fallbacks
    enum_values = {}
    
    # NEW status
    try:
        enum_values['NEW'] = RequestStatus.NEW
    except AttributeError:
        try:
            enum_values['NEW'] = RequestStatus.NEW_REQUEST
        except AttributeError:
            enum_values['NEW'] = None
    
    # PENDING status
    try:
        enum_values['PENDING'] = RequestStatus.PENDING
    except AttributeError:
        try:
            enum_values['PENDING'] = RequestStatus.PENDING_REVIEW
        except AttributeError:
            try:
                enum_values['PENDING'] = RequestStatus.REVIEW_PENDING
            except AttributeError:
                enum_values['PENDING'] = None
    
    # APPROVED status
    try:
        enum_values['APPROVED'] = RequestStatus.APPROVED
    except AttributeError:
        try:
            enum_values['APPROVED'] = RequestStatus.APPROVED_REQUEST
        except AttributeError:
            enum_values['APPROVED'] = None
    
    # REJECTED status
    try:
        enum_values['REJECTED'] = RequestStatus.REJECTED
    except AttributeError:
        enum_values['REJECTED'] = None
    
    # IN_PROGRESS status
    try:
        enum_values['IN_PROGRESS'] = RequestStatus.IN_PROGRESS
    except AttributeError:
        try:
            enum_values['IN_PROGRESS'] = RequestStatus.INPROGRESS
        except AttributeError:
            enum_values['IN_PROGRESS'] = None
    
    # COMPLETED status
    try:
        enum_values['COMPLETED'] = RequestStatus.COMPLETED
    except AttributeError:
        enum_values['COMPLETED'] = None
    
    # REFUNDED status
    try:
        enum_values['REFUNDED'] = RequestStatus.REFUNDED
    except AttributeError:
        enum_values['REFUNDED'] = None
    
    return enum_values

def check_email_context(context):
    """Check if we're expecting email input (not broadcast)"""
    return 'awaiting_email_for_paystack' in context.user_data or 'awaiting_email_for_custom_deposit' in context.user_data

# ========== DATABASE INITIALIZATION ==========


    
def generate_paystack_reference(prefix="BOT"):
    """Generate truly unique reference for Paystack"""
    # Get microsecond timestamp
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    
    # Add random UUID
    random_part = uuid.uuid4().hex[:8].upper()
    
    # Add user-specific part if available
    user_part = ""
    
    return f"{prefix}_{timestamp}_{random_part}"
