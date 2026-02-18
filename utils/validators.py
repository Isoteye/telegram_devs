import re

def is_valid_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def is_valid_phone(phone):
    """Validate phone number format"""
    pattern = r'^\+?1?\d{9,15}$'
    return re.match(pattern, phone) is not None

def is_valid_amount(amount):
    """Validate amount is positive number"""
    try:
        amount_float = float(amount)
        return amount_float > 0
    except ValueError:
        return False