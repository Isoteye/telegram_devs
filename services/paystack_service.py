"""
Paystack payment service - REAL IMPLEMENTATION
"""
import requests
import json
import logging
from datetime import datetime
from config import PAYMENT_METHODS
import uuid
from services.currency_service import currency_service


logger = logging.getLogger(__name__)

class PaystackService:
    def __init__(self):
        # Get Paystack credentials from config
        paystack_config = PAYMENT_METHODS.get('paystack', {})
        self.public_key = paystack_config.get('public_key', '')
        self.secret_key = paystack_config.get('secret_key', '')
        self.base_url = "https://api.paystack.co"
        
        # Validate keys
        if not self.secret_key or self.secret_key == "":
            logger.warning("Paystack secret key not configured. Using dummy mode.")
            self.dummy_mode = True
        else:
            self.dummy_mode = False
        
        # Headers for API requests
        self.headers = {
            'Authorization': f'Bearer {self.secret_key}',
            'Content-Type': 'application/json'
        }
    
    def initialize_transaction(self, email, amount, reference, currency="USD", callback_url=None):
        """Initialize real Paystack transaction"""
        
        # If in dummy mode or no secret key, use dummy implementation
        if self.dummy_mode or not self.secret_key:
            return self._dummy_initialize_transaction(email, amount, reference, currency, callback_url)
        
        try:
            # Convert amount to kobo (for NGN) or cents (for USD)
            # Paystack expects amount in the smallest currency unit
            amount_in_kobo = int(amount * 100)
            
            # Prepare request data
            data = {
                "email": email,
                "amount": amount_in_kobo,
                "reference": reference,
                "currency": currency,
                "callback_url": callback_url or f"https://t.me/your_bot_username?start=verify_{reference}"
            }
            
            # Make API request
            response = requests.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=data
            )
            
            # Parse response
            result = response.json()
            
            if response.status_code == 200 and result.get('status'):
                logger.info(f"Paystack transaction initialized: {reference}")
                return True, result
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Paystack initialization failed: {error_msg}")
                return False, result
                
        except Exception as e:
            logger.error(f"Error initializing Paystack transaction: {e}")
            return False, {"status": False, "message": str(e)}
    
    def verify_transaction(self, reference):
        """Verify real Paystack transaction"""
        
        # If in dummy mode or no secret key, use dummy implementation
        if self.dummy_mode or not self.secret_key:
            return self._dummy_verify_transaction(reference)
        
        try:
            # Make API request to verify transaction
            response = requests.get(
                f"{self.base_url}/transaction/verify/{reference}",
                headers=self.headers
            )
            
            # Parse response
            result = response.json()
            
            if response.status_code == 200 and result.get('status'):
                transaction_data = result.get('data', {})
                
                # Check if transaction was successful
                if transaction_data.get('status') == 'success':
                    logger.info(f"Paystack transaction verified successfully: {reference}")
                    return True, result
                else:
                    logger.warning(f"Paystack transaction not successful: {reference}")
                    return False, result
            else:
                error_msg = result.get('message', 'Transaction not found')
                logger.error(f"Paystack verification failed: {error_msg}")
                return False, result
                
        except Exception as e:
            logger.error(f"Error verifying Paystack transaction: {e}")
            return False, {"status": False, "message": str(e)}
    
    def create_transfer_recipient(self, name, account_number, bank_code, currency="NGN"):
        """Create a transfer recipient for mobile money or bank transfers"""
        try:
            data = {
                "type": "nuban",  # Nigerian Uniform Bank Account Number
                "name": name,
                "account_number": account_number,
                "bank_code": bank_code,
                "currency": currency
            }
            
            response = requests.post(
                f"{self.base_url}/transferrecipient",
                headers=self.headers,
                json=data
            )
            
            result = response.json()
            if response.status_code == 201 and result.get('status'):
                return True, result
            else:
                return False, result
                
        except Exception as e:
            logger.error(f"Error creating transfer recipient: {e}")
            return False, {"status": False, "message": str(e)}
    

    def initiate_transfer(self, amount, recipient_code, reason="Payment"):
        """Initiate a transfer to a recipient (for mobile money or bank transfer)"""
        try:
            # Convert amount to kobo
            amount_in_kobo = int(amount * 100)
            
            data = {
                "source": "balance",
                "amount": amount_in_kobo,
                "recipient": recipient_code,
                "reason": reason
            }
            
            response = requests.post(
                f"{self.base_url}/transfer",
                headers=self.headers,
                json=data
            )
            
            result = response.json()
            if response.status_code == 200 and result.get('status'):
                return True, result
            else:
                return False, result
                
        except Exception as e:
            logger.error(f"Error initiating transfer: {e}")
            return False, {"status": False, "message": str(e)}
    
    def list_banks(self, country="nigeria", currency="NGN"):
        """List available banks for transfer"""
        try:
            response = requests.get(
                f"{self.base_url}/bank",
                headers=self.headers,
                params={"country": country, "currency": currency}
            )
            
            result = response.json()
            if response.status_code == 200 and result.get('status'):
                return True, result
            else:
                return False, result
                
        except Exception as e:
            logger.error(f"Error listing banks: {e}")
            return False, {"status": False, "message": str(e)}
    
    def create_charge_for_card(self, email, amount, card_details, reference):
        """Create a charge for card payments"""
        try:
            amount_in_kobo = int(amount * 100)
            
            data = {
                "email": email,
                "amount": amount_in_kobo,
                "reference": reference,
                "card": card_details
            }
            
            response = requests.post(
                f"{self.base_url}/charge",
                headers=self.headers,
                json=data
            )
            
            result = response.json()
            return response.status_code == 200, result
            
        except Exception as e:
            logger.error(f"Error creating charge: {e}")
            return False, {"status": False, "message": str(e)}
    
    def validate_webhook(self, payload, signature):
        """Validate Paystack webhook signature"""
        try:
            # Import hashlib here to avoid dependency issues
            import hashlib
            import hmac
            
            # Compute HMAC SHA512
            computed_signature = hmac.new(
                self.secret_key.encode('utf-8'),
                payload,
                hashlib.sha512
            ).hexdigest()
            
            # Compare signatures
            return hmac.compare_digest(computed_signature, signature)
            
        except Exception as e:
            logger.error(f"Error validating webhook: {e}")
            return False
    

    def generate_unique_reference(prefix=""):
        """Generate unique transaction reference for Paystack"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = uuid.uuid4().hex[:8].upper()
        return f"{prefix}{timestamp}{unique_id}"
    
    def initialize_transaction(self, email, amount, reference, currency="USD", callback_url=None):
        """Initialize real Paystack transaction with multi-currency support"""
        
        # If in dummy mode or no secret key, use dummy implementation
        if self.dummy_mode or not self.secret_key:
            return self._dummy_initialize_transaction(email, amount, reference, currency, callback_url)
        
        try:
            # Paystack requires amount in kobo (for NGN) or cents (for other currencies)
            # Conversion based on currency
            if currency == "NGN":
                # For NGN, multiply by 100 (kobo)
                amount_in_smallest_unit = int(amount * 100)
            elif currency == "GHS":
                # For GHS, multiply by 100 (pesewas)
                amount_in_smallest_unit = int(amount * 100)
            elif currency in ["USD", "EUR", "GBP"]:
                # For major currencies, multiply by 100 (cents/pence)
                amount_in_smallest_unit = int(amount * 100)
            elif currency == "KES":
                # For KES, multiply by 100 (cents)
                amount_in_smallest_unit = int(amount * 100)
            elif currency == "ZAR":
                # For ZAR, multiply by 100 (cents)
                amount_in_smallest_unit = int(amount * 100)
            else:
                # Default to cents
                amount_in_smallest_unit = int(amount * 100)
            
            # Check if currency is supported by Paystack
            supported_currencies = ["NGN", "USD", "GHS", "ZAR", "KES"]
            if currency not in supported_currencies:
                logger.warning(f"Currency {currency} might not be supported by Paystack. Using USD instead.")
                currency = "USD"
                amount_in_smallest_unit = int(amount * 100)
            
            # Prepare request data
            data = {
                "email": email,
                "amount": amount_in_smallest_unit,
                "reference": reference,
                "currency": currency,
                "callback_url": callback_url or f"https://t.me/your_bot_username?start=verify_{reference}"
            }
            
            logger.info(f"Paystack transaction data: {data}")
            
            # Make API request
            response = requests.post(
                f"{self.base_url}/transaction/initialize",
                headers=self.headers,
                json=data,
                timeout=30
            )
            
            # Parse response
            result = response.json()
            
            if response.status_code == 200 and result.get('status'):
                logger.info(f"Paystack transaction initialized: {reference} in {currency}")
                return True, result
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Paystack initialization failed: {error_msg}")
                return False, result
                
        except Exception as e:
            logger.error(f"Error initializing Paystack transaction: {e}")
            return False, {"status": False, "message": str(e)}

    # Dummy implementations for testing
    def _dummy_initialize_transaction(self, email, amount, reference, currency, callback_url):
        """Dummy implementation for testing"""
        try:
            logger.info(f"Dummy: Initializing transaction for {email}, amount: {amount}, reference: {reference}")
            
            response = {
                "status": True,
                "message": "Authorization URL created",
                "data": {
                    "authorization_url": "https://checkout.paystack.com/test_payment",
                    "access_code": f"access_{reference}",
                    "reference": reference,
                    "amount": amount * 100,
                    "currency": currency
                }
            }
            return True, response
        except Exception as e:
            return False, {"status": False, "message": str(e)}
    
    def _dummy_verify_transaction(self, reference):
        """Dummy implementation for testing"""
        try:
            logger.info(f"Dummy: Verifying transaction {reference}")
            
            # Simulate successful payment 80% of the time
            import random
            if random.random() > 0.2:
                response = {
                    "status": True,
                    "message": "Verification successful",
                    "data": {
                        "id": random.randint(100000, 999999),
                        "domain": "test",
                        "status": "success",
                        "reference": reference,
                        "amount": 100000,  # In kobo (1000 = 10 NGN)
                        "currency": "NGN",
                        "gateway_response": "Successful",
                        "paid_at": datetime.now().isoformat(),
                        "created_at": datetime.now().isoformat(),
                        "metadata": {
                            "custom_fields": []
                        }
                    }
                }
                return True, response
            else:
                return False, {"status": False, "message": "Transaction not found"}
        except Exception as e:
            return False, {"status": False, "message": str(e)}
# Add this to your existing PaystackService class

    def refund_transaction(self, reference: str, amount: float = None):
        """Process a refund for a transaction"""
        
        # If in dummy mode, use dummy implementation
        if self.dummy_mode or not self.secret_key:
            return self._dummy_refund_transaction(reference, amount)
        
        try:
            # Prepare request data
            data = {
                "transaction": reference
            }
            
            # If amount specified, include it (in kobo)
            if amount is not None:
                amount_in_kobo = int(amount * 100)
                data['amount'] = amount_in_kobo
            
            # Make API request
            response = requests.post(
                f"{self.base_url}/refund",
                headers=self.headers,
                json=data
            )
            
            # Parse response
            result = response.json()
            
            if response.status_code == 200 and result.get('status'):
                logger.info(f"Refund successful for transaction {reference}")
                return True, result
            else:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Refund failed for {reference}: {error_msg}")
                return False, result
                
        except Exception as e:
            logger.error(f"Error refunding transaction {reference}: {e}")
            return False, {"status": False, "message": str(e)}


    def _dummy_refund_transaction(self, reference: str, amount: float = None):
        """Dummy implementation for testing refunds"""
        try:
            logger.info(f"Dummy: Processing refund for {reference}, amount: {amount}")
            
            # Simulate successful refund 90% of the time
            import random
            if random.random() > 0.1:
                response = {
                    "status": True,
                    "message": "Refund successful",
                    "data": {
                        "transaction": {"id": random.randint(100000, 999999)},
                        "integration": random.randint(1000, 9999),
                        "domain": "test",
                        "amount": int(amount * 100) if amount else 100000,
                        "currency": "NGN",
                        "reference": f"RF_{reference}",
                        "source": "balance",
                        "reason": "Refund for unclaimed order",
                        "status": "success",
                        "createdAt": datetime.now().isoformat()
                    }
                }
                return True, response
            else:
                return False, {"status": False, "message": "Refund failed in dummy mode"}
                
        except Exception as e:
            return False, {"status": False, "message": str(e)}

# Global instance
paystack = PaystackService()