from config import PAYMENT_METHODS, MOBILE_MONEY_ACCOUNT, MOBILE_MONEY_NAME
import logging

logger = logging.getLogger(__name__)

class PaymentService:
    def initialize_transaction(self, email, amount, reference, currency=None, callback_url=None):
        """Initialize Paystack payment - FORCE GHS CURRENCY"""
        # Convert any currency to GHS first
        from services.currency_service import currency_service
        
        if currency and currency != "GHS":
            # Convert to GHS (base currency)
            amount_in_ghs = currency_service.convert_to_base(amount, currency)
            currency = "GHS"
            amount = amount_in_ghs * 100  # Paystack uses kobo/pesewas
        else:
            # Already in GHS or no currency specified
            currency = "GHS"
            amount = amount * 100  # Convert to pesewas
        

    def get_payment_instructions(self, method: str) -> dict:
        """Get payment instructions for a specific method"""
        try:
            if method in PAYMENT_METHODS:
                return PAYMENT_METHODS[method]
            
            # Fallback to mobile money if method not found
            logger.warning(f"Payment method {method} not found, using mobile money fallback")
            return {
                "account": MOBILE_MONEY_ACCOUNT,
                "name": MOBILE_MONEY_NAME,
                "instructions": "Send payment to the mobile money number provided with order ID as reference"
            }
        except Exception as e:
            logger.error(f"Error getting payment instructions: {e}")
            return {
                "account": MOBILE_MONEY_ACCOUNT,
                "name": MOBILE_MONEY_NAME,
                "instructions": "Please contact support for payment details."
            }
    
    def format_payment_message(self, order, method: str = None) -> str:
        """Format payment instructions message"""
        try:
            if not method:
                method = "mobile_money"
                
            instructions = self.get_payment_instructions(method)
            
            # Determine method name
            if method:
                method_name = method.replace('_', ' ').title()
            else:
                method_name = "Mobile Money"
            
            amount = order.amount if hasattr(order, 'amount') and order.amount else 0.0
            order_id = order.order_id if hasattr(order, 'order_id') else "UNKNOWN"
            
            return f"""
💳 *Payment Instructions*

Order: `{order_id}`
Amount: *${amount:.2f}*

*Payment Method:* {method_name}

📱 *Send to:*
Account: `{instructions.get('account', MOBILE_MONEY_ACCOUNT)}`
Name: {instructions.get('name', MOBILE_MONEY_NAME)}

*Instructions:*
{instructions.get('instructions', 'Please contact support for payment instructions.')}

⚠️ *Important:*
1. Send exact amount: ${amount:.2f}
2. Include order ID in payment note: `{order_id}`
3. Take screenshot of confirmation
4. Upload screenshot here

After payment, upload proof by sending it as a photo.
            """
        except Exception as e:
            logger.error(f"Error formatting payment message: {e}")
            return f"""
💳 *Payment Instructions - Error*

Order: `{order.order_id if hasattr(order, 'order_id') else 'UNKNOWN'}`
Amount: *${order.amount if hasattr(order, 'amount') else 0.0:.2f}*

📱 *Send to:*
Account: `{MOBILE_MONEY_ACCOUNT}`
Name: {MOBILE_MONEY_NAME}

*Instructions:*
1. Send ${order.amount if hasattr(order, 'amount') else 0.0:.2f} to the number above
2. Include order ID in payment note
3. Upload screenshot of payment proof
            """