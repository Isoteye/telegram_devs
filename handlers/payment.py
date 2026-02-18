# payment.py - FIXED
import sys
import os
import traceback
import logging
from datetime import datetime
import uuid

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

async def handle_paystack_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Paystack payment initialization - USING USER'S CURRENCY"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('paystack_bot_', ''))
        
        from database.db import create_session
        from database.models import User, Order, OrderStatus, PaymentMethod, PaymentStatus, Transaction, Bot
        from utils.helpers import generate_order_id
        from services.currency_service import currency_service
        from config import PAYSTACK_SUPPORTED_CURRENCIES
        
        db = create_session()
        try:
            # Get user with currency info
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user:
                await query.edit_message_text("❌ User not found. Please use /start first.")
                return
            
            # Get user's currency
            user_currency = user.currency if user.currency else "USD"
            currency_symbol = currency_service.get_currency_symbol(user_currency)
            
            # Check if currency is supported by Paystack
            if user_currency not in PAYSTACK_SUPPORTED_CURRENCIES:
                # Fallback to USD
                user_currency = "USD"
                currency_symbol = "$"
                logger.warning(f"Currency {user_currency} not supported, falling back to USD")
            
            # Get software
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            # Convert price to user's currency
            usd_price = bot.price
            local_price = currency_service.convert_usd_to_currency(usd_price, user_currency)
            
            # Generate unique reference
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            random_part = uuid.uuid4().hex[:8].upper()
            unique_ref = f"BOT_{user.id}_{timestamp}_{random_part}"
            
            logger.info(f"Price: ${usd_price:.2f} USD → {currency_symbol}{local_price:.2f} {user_currency}")
            
            # Check if user has email
            if not user.email:
                # Ask for email
                context.user_data['awaiting_email_for_paystack'] = {
                    'bot_id': bot_id,
                    'bot_name': bot.name,
                    'usd_amount': usd_price,
                    'local_amount': local_price,
                    'local_currency': user_currency,
                    'local_symbol': currency_symbol,
                    'unique_ref': unique_ref,
                    'user_id': user.id
                }
                
                await query.edit_message_text(
                    f"📧 **Paystack Payment**\n\n"
                    f"To proceed with payment, please provide your email address.\n\n"
                    f"🚀 **Software:** {bot.name}\n"
                    f"💰 **Amount:** {currency_symbol}{local_price:.2f} {user_currency}\n"
                    f"💵 **USD Equivalent:** ${usd_price:.2f}\n\n"
                    f"📧 **Please send your email now:**"
                )
                return
            
            # Create order with currency info
            order_id = generate_order_id()
            
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot.id,
                amount=usd_price,  # Store USD amount
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=PaymentMethod.PAYSTACK,
                payment_status=PaymentStatus.PENDING,
                payment_reference=unique_ref
            )
            
            db.add(order)
            db.commit()
            
            # Initialize Paystack transaction in USER'S CURRENCY
            from services.paystack_service import PaystackService
            paystack = PaystackService()
            
            success, result = paystack.initialize_transaction(
                email=user.email,
                amount=local_price,  # Use local amount in user's currency
                reference=unique_ref,
                currency=user_currency,  # Use user's currency
                callback_url=None
            )
            
            if not success:
                error_msg = result.get('message', 'Unknown error')
                await query.edit_message_text(
                    f"❌ **Payment Failed**\n\n"
                    f"**Error:** {error_msg}\n\n"
                    f"Please try another payment method or contact support."
                )
                return
            
            payment_data = result.get('data', {})
            authorization_url = payment_data.get('authorization_url')
            
            # Update order
            order.payment_metadata = {
                'access_code': payment_data.get('access_code'),
                'authorization_url': authorization_url,
                'paystack_response': result,
                'currency': user_currency,
                'local_amount': local_price,
                'usd_amount': usd_price
            }
            db.commit()
            
            # Create transaction with currency info
            transaction = Transaction(
                transaction_id=unique_ref,
                order_id=order.id,
                user_id=user.id,
                amount=local_price,  # Local amount
                currency=user_currency,  # Local currency
                payment_method=PaymentMethod.PAYSTACK,
                status='pending',
                reference=unique_ref,
                transaction_data=result,
                usd_amount=usd_price  # USD amount
            )
            db.add(transaction)
            db.commit()
            
            # Send payment link in user's currency
            text = f"""💳 **Paystack Payment**

📦 **Order ID:** {order_id}
🚀 **Software:** {bot.name}
💰 **Amount:** {currency_symbol}{local_price:.2f} {user_currency}
💵 **USD Equivalent:** ${usd_price:.2f}
🔖 **Payment Reference:** {unique_ref}
🏦 **Currency:** {user_currency}

Click the button below to pay securely via Paystack."""
            
            keyboard = [
                [InlineKeyboardButton(f"💳 Pay Now ({currency_symbol}{local_price:.2f})", url=authorization_url)],
                [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"verify_payment_{unique_ref}")],
                [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in handle_paystack_payment: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error processing payment. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_paystack_payment: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing payment request.")

async def handle_bank_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bank transfer payment"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('bank_transfer_', ''))
        
        from database.db import create_session
        from database.models import Bot, User, Order, OrderStatus, PaymentMethod, PaymentStatus
        from utils.helpers import generate_order_id
        from config import PAYMENT_METHODS
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user:
                await query.edit_message_text("❌ User not found. Please use /start first.")
                return
            
            # Get software
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            # Create order
            order_id = generate_order_id()
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot.id,
                amount=bot.price,
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=PaymentMethod.BANK_TRANSFER,
                payment_status=PaymentStatus.PENDING
            )
            
            db.add(order)
            db.commit()
            
            # Update user's total orders
            user.total_orders = db.query(Order).filter(Order.user_id == user.id).count()
            db.commit()
            
            # Get bank details
            bank_details = PAYMENT_METHODS.get('bank_transfer', {})
            
            text = f"""🏦 Bank Transfer Payment

✅ Order Created: {order_id}
🚀 Software: {bot.name}
💰 Amount: ${bot.price:.2f}

Bank Details:
🏦 Account: {bank_details.get('account', 'Contact Support')}
👤 Name: {bank_details.get('name', 'Contact Support')}

Instructions:
{bank_details.get('instructions', 'Transfer the exact amount and upload proof.')}

Important:
1. Send exactly ${bot.price:.2f}
2. Include Order ID: {order_id} in payment reference
3. Upload payment proof after payment"""
            
            keyboard = [
                [InlineKeyboardButton("📸 Upload Payment Proof", callback_data=f"upload_proof_{order_id}")],
                [
                    InlineKeyboardButton("📦 My Orders", callback_data="my_orders"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in handle_bank_transfer: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error creating order. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_bank_transfer: {e}")
        await query.edit_message_text("❌ Error processing payment. Please try again.")

async def handle_email_for_paystack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email provided for Paystack payment - FIXED with unique references"""
    try:
        if not update.message:
            return
        
        # Check if this is for email (not broadcast)
        from utils.helpers import check_email_context
        if not check_email_context(context):
            # This might be a broadcast message, skip it
            return
        
        email = update.message.text.strip()
        
        # Basic email validation
        if '@' not in email or '.' not in email:
            await update.message.reply_text("❌ Please enter a valid email address.")
            return
        
        paystack_data = context.user_data.get('awaiting_email_for_paystack')
        if not paystack_data:
            await update.message.reply_text("❌ No pending payment. Please start over.")
            return
        
        bot_id = paystack_data['bot_id']
        bot_name = paystack_data['bot_name']
        amount = paystack_data['amount']
        unique_ref = paystack_data['unique_ref']  # Get the pre-generated unique reference
        
        from database.db import create_session
        from database.models import User, Order, OrderStatus, PaymentMethod, PaymentStatus, Transaction, Bot
        from utils.helpers import generate_order_id
        from config import DEFAULT_CURRENCY, DEFAULT_CURRENCY_SYMBOL
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user:
                await update.message.reply_text("❌ User not found. Please use /start first.")
                return
            
            # Update user email
            user.email = email
            db.commit()
            
            # Clear context
            context.user_data.pop('awaiting_email_for_paystack', None)
            
            # Create order with unique reference
            order_id = generate_order_id()
            
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            
            # Create order with the UNIQUE reference
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot_id,
                amount=amount,
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=PaymentMethod.PAYSTACK,
                payment_status=PaymentStatus.PENDING,
                payment_reference=unique_ref  # Store the unique reference
            )
            
            db.add(order)
            db.commit()
            
            # Initialize Paystack transaction with UNIQUE reference
            try:
                from services.paystack_service import PaystackService
                paystack = PaystackService()
                success, result = paystack.initialize_transaction(
                    email=email,
                    amount=amount,
                    reference=unique_ref,  # Use the pre-generated unique reference
                    currency=DEFAULT_CURRENCY
                )
            except ImportError:
                await update.message.reply_text("❌ Paystack service not configured. Please use another payment method.")
                return
            
            if not success:
                await update.message.reply_text(
                    f"❌ Payment initialization failed: {result.get('message', 'Unknown error')}"
                )
                return
            
            # Get payment URL
            payment_data = result.get('data', {})
            authorization_url = payment_data.get('authorization_url')
            
            # Update order with Paystack response
            order.payment_metadata = result
            db.commit()
            
            # Create transaction with UNIQUE reference
            transaction = Transaction(
                transaction_id=unique_ref,  # Use unique_ref as transaction_id
                order_id=order.id,
                user_id=user.id,
                amount=amount,
                currency=DEFAULT_CURRENCY,
                payment_method=PaymentMethod.PAYSTACK,
                status='pending',
                reference=unique_ref,  # Use unique_ref as reference
                transaction_data=result
            )
            db.add(transaction)
            db.commit()
            
            # Send payment link
            text = f"""💳 Paystack Payment

📦 Order ID: {order_id}
🚀 Software: {bot_name}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{amount:.2f}
📧 Email: {email}
🔖 Payment Reference: {unique_ref}

Click the button below to pay securely via Paystack.

After payment, use: /verify {unique_ref}"""
            
            keyboard = [
                [InlineKeyboardButton("💳 Pay Now", url=authorization_url)],
                [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"verify_payment_{unique_ref}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in handle_email_for_paystack: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error processing payment. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_email_for_paystack: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing your request.")

async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify command - Updated for unique references"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            
            # Extract payment reference from callback data
            payment_reference = query.data.replace('verify_payment_', '')
            is_callback = True
        elif update.message and context.args:
            # Extract from command: /verify PAYMENT_REFERENCE
            payment_reference = context.args[0]
            is_callback = False
        else:
            if update.message:
                await update.message.reply_text("Usage: /verify PAYMENT_REFERENCE")
            return
        
        # Now verify using the payment reference
        from order_management import verify_order_payment
        await verify_order_payment(update, context, payment_reference, is_callback)
            
    except Exception as e:
        logger.error(f"Error in verify_command: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error verifying payment.")
        elif update.message:
            await update.message.reply_text("❌ Error verifying payment.")