"""
Payment handlers for different payment methods
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import User, Order, Transaction, PaymentMethod
from services.paystack_service import PaystackService
from config import PAYMENT_METHODS, PAYSTACK_CONFIG
import logging

logger = logging.getLogger(__name__)


async def show_payment_methods(update: Update, context: ContextTypes.DEFAULT_TYPE, bot_id, amount, bot_name):
    """Show available payment methods"""
    try:
        query = update.callback_query
        await query.answer()
        
        text = f"""💳 Select Payment Method

🚀 Software: {bot_name}
💰 Amount: {amount}

Available payment methods:"""
        
        keyboard = []
        
        # Paystack option (supports card, bank, USSD, mobile money)
        if PAYMENT_METHODS.get('paystack', {}).get('is_active', True):
            keyboard.append([
                InlineKeyboardButton(
                    "💳 Paystack (Card/Bank/USSD/Mobile Money)",
                    callback_data=f"paystack_pay_{bot_id}"
                )
            ])
        
        # Bank transfer option
        if PAYMENT_METHODS.get('bank_transfer', {}).get('is_active', True):
            keyboard.append([
                InlineKeyboardButton(
                    "🏦 Direct Bank Transfer",
                    callback_data=f"bank_transfer_{bot_id}"
                )
            ])
        
        # Mobile money option
        keyboard.append([
            InlineKeyboardButton(
                "📱 Mobile Money (Ghana)",
                callback_data=f"mobile_money_{bot_id}"
            )
        ])
        
        keyboard.append([
            InlineKeyboardButton("⬅️ Back", callback_data=f"view_bot_{bot_id}"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in show_payment_methods: {e}", exc_info=True)


async def handle_mobile_money_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mobile money payment"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('mobile_money_', ''))
        
        from database.models import Bot
        db = create_session()
        
        try:
            # Get bot details
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            # Get user
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user:
                await query.edit_message_text("❌ User not found. Please use /start first.")
                return
            
            text = f"""📱 Mobile Money Payment

🚀 Software: {bot.name}
💰 Amount: ₦{bot.price:,.2f}

Select your mobile money provider:"""
            
            keyboard = [
                [
                    InlineKeyboardButton("📱 MTN", callback_data=f"mm_mtn_{bot_id}"),
                    InlineKeyboardButton("📱 AirtelTigo", callback_data=f"mm_airtel_{bot_id}")
                ],
                [
                    InlineKeyboardButton("📱 Vodafone", callback_data=f"mm_vodafone_{bot_id}"),
                    InlineKeyboardButton("📱 Other", callback_data=f"mm_other_{bot_id}")
                ],
                [
                    InlineKeyboardButton("⬅️ Back", callback_data=f"buy_options_{bot_id}"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in handle_mobile_money_payment: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading payment options.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_mobile_money_payment: {e}", exc_info=True)


async def handle_mobile_money_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle mobile money provider selection"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Parse callback data: mm_mtn_1 -> provider=mtn, bot_id=1
        data_parts = query.data.split('_')
        if len(data_parts) < 3:
            await query.edit_message_text("❌ Invalid request.")
            return
        
        provider = data_parts[1]  # mtn, airtel, vodafone, other
        bot_id = int(data_parts[2])
        
        # Ask for mobile money number
        context.user_data['awaiting_mobile_money'] = {
            'provider': provider,
            'bot_id': bot_id
        }
        
        provider_names = {
            'mtn': 'MTN',
            'airtel': 'AirtelTigo',
            'vodafone': 'Vodafone',
            'other': 'Mobile Money'
        }
        
        provider_name = provider_names.get(provider, 'Mobile Money')
        
        await query.edit_message_text(
            f"📱 {provider_name} Mobile Money\n\n"
            f"Please enter your {provider_name} mobile money number:\n\n"
            f"Format: 0241234567 or 0541234567\n"
            f"Example: 0241234567"
        )
        
    except Exception as e:
        logger.error(f"Error in handle_mobile_money_provider: {e}", exc_info=True)


async def process_mobile_money_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process mobile money number and initiate payment"""
    try:
        if not update.message:
            return
        
        mobile_number = update.message.text.strip()
        
        # Basic validation
        if not mobile_number.isdigit() or len(mobile_number) != 10:
            await update.message.reply_text(
                "❌ Invalid mobile number. Please enter a valid 10-digit Ghanaian mobile number.\n"
                "Example: 0241234567"
            )
            return
        
        mobile_data = context.user_data.get('awaiting_mobile_money')
        if not mobile_data:
            await update.message.reply_text("❌ No pending mobile money payment. Please start over.")
            return
        
        provider = mobile_data['provider']
        bot_id = mobile_data['bot_id']
        
        # Clear context
        context.user_data.pop('awaiting_mobile_money', None)
        
        from database.db import create_session
        from database.models import Bot, User, Order, Transaction
        from utils.helpers import generate_order_id
        from config import DEFAULT_CURRENCY
        
        db = create_session()
        
        try:
            # Get bot and user
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            
            if not bot or not user:
                await update.message.reply_text("❌ Error processing payment. Please try again.")
                return
            
            # Create order
            order_id = generate_order_id()
            
            # Map provider to Paystack bank codes
            provider_codes = {
                'mtn': 'MTN',
                'vodafone': 'VOD',
                'airtel': 'ATL',
                'other': 'MTN'  # Default to MTN
            }
            
            bank_code = provider_codes.get(provider, 'MTN')
            
            # Initialize Paystack payment with mobile money
            paystack = PaystackService()
            
            # For mobile money, we need to create a transfer recipient first
            recipient_name = f"{user.first_name} {user.last_name or ''}".strip()
            
            success, recipient_result = paystack.create_transfer_recipient(
                name=recipient_name,
                account_number=mobile_number,
                bank_code=bank_code,
                currency="GHS" if provider in ['mtn', 'vodafone', 'airtel'] else "NGN"
            )
            
            if not success:
                await update.message.reply_text(
                    f"❌ Error setting up mobile money payment: {recipient_result.get('message', 'Unknown error')}"
                )
                return
            
            recipient_code = recipient_result.get('data', {}).get('recipient_code')
            
            # Now initialize the payment
            success, result = paystack.initialize_transaction(
                email=user.email or f"{mobile_number}@mobile.money",
                amount=bot.price,
                reference=order_id,
                currency="GHS" if provider in ['mtn', 'vodafone', 'airtel'] else "NGN",
                callback_url=None
            )
            
            if not success:
                await update.message.reply_text(
                    f"❌ Payment initialization failed: {result.get('message', 'Unknown error')}"
                )
                return
            
            # Get authorization URL
            payment_data = result.get('data', {})
            authorization_url = payment_data.get('authorization_url')
            
            # Create order
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot.id,
                amount=bot.price,
                payment_method=PaymentMethod.PAYSTACK,
                payment_metadata={
                    'authorization_url': authorization_url,
                    'provider': provider,
                    'mobile_number': mobile_number,
                    'recipient_code': recipient_code,
                    'paystack_response': result
                }
            )
            
            db.add(order)
            db.commit()
            
            # Create transaction
            transaction = Transaction(
                transaction_id=order_id,
                order_id=order.id,
                user_id=user.id,
                amount=bot.price,
                currency=DEFAULT_CURRENCY,
                payment_method='paystack',
                status='pending',
                reference=order_id,
                transaction_data=result
            )
            
            db.add(transaction)
            db.commit()
            
            # Send payment link
            provider_names = {
                'mtn': 'MTN Mobile Money',
                'airtel': 'AirtelTigo Money',
                'vodafone': 'Vodafone Cash',
                'other': 'Mobile Money'
            }
            
            provider_name = provider_names.get(provider, 'Mobile Money')
            
            text = f"""📱 {provider_name} Payment

🚀 Software: {bot.name}
💰 Amount: ₦{bot.price:,.2f}
📱 Mobile Number: {mobile_number}
🔄 Provider: {provider_name}

Click the button below to complete your {provider_name} payment.

After payment, use: /verify {order_id}"""
            
            keyboard = [
                [InlineKeyboardButton("📱 Complete Payment Now", url=authorization_url)],
                [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"verify_payment_{order_id}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error processing mobile money: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error processing payment. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in process_mobile_money_number: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing your request.")