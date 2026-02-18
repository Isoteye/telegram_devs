# handlers/paystack_handler.py - COMPLETELY FIXED VERSION
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, MessageHandler, filters
from database.db import create_session
from database.models import User, Order, OrderStatus, PaymentMethod, PaymentStatus, Transaction, Bot
from services.paystack_service import PaystackService
from utils.helpers import generate_order_id
from config import DEFAULT_CURRENCY, DEFAULT_CURRENCY_SYMBOL
import logging
from datetime import datetime
import json
import uuid
import traceback

logger = logging.getLogger(__name__)

def generate_unique_paystack_reference(user_id: int, prefix: str = "BOT") -> str:
    """
    Generate truly unique reference for Paystack to avoid duplicate reference errors
    
    Format: PREFIX_USERID_TIMESTAMP_RANDOM
    Example: BOT_123_20250128123045987654_ABCDEF12
    """
    try:
        # Get microsecond timestamp for maximum uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # Last 3 digits of microseconds
        
        # Generate random part
        random_part = uuid.uuid4().hex[:8].upper()  # 8 character hex string
        
        # Create reference
        reference = f"{prefix}_{user_id}_{timestamp}_{random_part}"
        
        logger.info(f"Generated unique Paystack reference: {reference}")
        return reference
    except Exception as e:
        logger.error(f"Error generating Paystack reference: {e}")
        # Fallback to simpler reference
        return f"{prefix}_{user_id}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:6].upper()}"

async def handle_paystack_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Paystack payment initialization - FIXED VERSION"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract bot ID from callback data: paystack_bot_1 -> 1
        data_parts = query.data.split('_')
        if len(data_parts) < 3:
            await query.edit_message_text("❌ Invalid payment request.")
            return
        
        bot_id = int(data_parts[2])
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
            if not user:
                await query.edit_message_text("❌ User not found. Please use /start first.")
                return
            
            # Get bot
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Bot not found.")
                return
            
            # Generate UNIQUE reference for Paystack
            paystack_ref = generate_unique_paystack_reference(user.id, f"BOT{bot_id}")
            logger.info(f"Generated Paystack ref: {paystack_ref} for user {user.id}, bot {bot_id}")
            
            # Check if user has email
            if not user.email:
                # Ask for email
                context.user_data['awaiting_email_for_paystack'] = {
                    'bot_id': bot_id,
                    'bot_name': bot.name,
                    'amount': bot.price,
                    'paystack_ref': paystack_ref,
                    'user_id': user.id
                }
                
                await query.edit_message_text(
                    f"📧 *Paystack Payment*\n\n"
                    f"To proceed with Paystack payment, please provide your email address.\n\n"
                    f"🤖 Bot: {bot.name}\n"
                    f"💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{bot.price:.2f}\n\n"
                    f"Please send your email now:",
                    parse_mode='Markdown'
                )
                return
            
            # Create order
            order_id = generate_order_id()
            logger.info(f"Creating order {order_id} with Paystack ref: {paystack_ref}")
            
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot.id,
                amount=bot.price,
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=PaymentMethod.PAYSTACK,
                payment_status=PaymentStatus.PENDING,
                payment_reference=paystack_ref  # Store the unique Paystack reference
            )
            
            db.add(order)
            db.commit()
            
            # Initialize Paystack transaction
            paystack = PaystackService()
            logger.info(f"Initializing Paystack transaction: email={user.email}, amount={bot.price}, ref={paystack_ref}")
            
            success, result = paystack.initialize_transaction(
                email=user.email,
                amount=bot.price,
                reference=paystack_ref,  # Use the unique reference
                currency=DEFAULT_CURRENCY,
                callback_url=None
            )
            
            if not success:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Paystack initialization failed: {error_msg}")
                
                await query.edit_message_text(
                    f"❌ *Payment Failed*\n\n"
                    f"Error: {error_msg}\n\n"
                    f"Please try another payment method or contact support.",
                    parse_mode='Markdown'
                )
                return
            
            # Get payment URL
            payment_data = result.get('data', {})
            authorization_url = payment_data.get('authorization_url')
            access_code = payment_data.get('access_code')
            
            # Update order with Paystack response
            order.payment_metadata = {
                'access_code': access_code,
                'authorization_url': authorization_url,
                'paystack_response': result,
                'order_id': order_id,
                'bot_name': bot.name
            }
            db.commit()
            
            # Create transaction record with unique reference
            transaction = Transaction(
                transaction_id=paystack_ref,  # Use the Paystack reference as transaction ID
                order_id=order.id,
                user_id=user.id,
                amount=bot.price,
                currency=DEFAULT_CURRENCY,
                payment_method=PaymentMethod.PAYSTACK,
                status='pending',
                reference=paystack_ref,  # Use the Paystack reference
                transaction_data=result
            )
            db.add(transaction)
            db.commit()
            
            logger.info(f"Order {order_id} created successfully. Paystack ref: {paystack_ref}")
            
            # Send payment link to user
            text = f"""
💳 *Paystack Payment*

📦 Order ID: `{order_id}`
🤖 Bot: {bot.name}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{bot.price:.2f}
🔖 Payment Reference: `{paystack_ref}`

Click the button below to pay securely via Paystack.

*Instructions:*
1. Click "Pay Now" button
2. Complete payment on Paystack
3. Return to this chat
4. Use `/verify {paystack_ref}` to verify payment

⚠️ *Important:* Save this payment reference: `{paystack_ref}`
            """
            
            keyboard = [
                [InlineKeyboardButton("💳 Pay Now", url=authorization_url)],
                [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"verify_payment_{paystack_ref}")],
                [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in handle_paystack_payment: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error processing payment. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_paystack_payment: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ Error processing payment request.")
        except:
            pass

async def handle_email_for_paystack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle email provided for Paystack payment - FIXED VERSION"""
    try:
        if not update.message:
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
        paystack_ref = paystack_data['paystack_ref']  # Get the pre-generated unique reference
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
            if not user:
                await update.message.reply_text("❌ User not found. Please use /start first.")
                return
            
            # Update user email
            user.email = email
            db.commit()
            
            # Clear context
            context.user_data.pop('awaiting_email_for_paystack', None)
            
            # Create order
            order_id = generate_order_id()
            
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            
            # Create order with the UNIQUE Paystack reference
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot_id,
                amount=amount,
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=PaymentMethod.PAYSTACK,
                payment_status=PaymentStatus.PENDING,
                payment_reference=paystack_ref  # Store the unique reference
            )
            
            db.add(order)
            db.commit()
            
            # Initialize Paystack transaction with UNIQUE reference
            paystack = PaystackService()
            logger.info(f"Initializing Paystack transaction for email: {email}, amount: {amount}, ref: {paystack_ref}")
            
            success, result = paystack.initialize_transaction(
                email=email,
                amount=amount,
                reference=paystack_ref,  # Use the unique reference
                currency=DEFAULT_CURRENCY
            )
            
            if not success:
                error_msg = result.get('message', 'Unknown error')
                logger.error(f"Paystack initialization failed: {error_msg}")
                await update.message.reply_text(
                    f"❌ Payment initialization failed: {error_msg}"
                )
                return
            
            # Get payment URL
            payment_data = result.get('data', {})
            authorization_url = payment_data.get('authorization_url')
            
            # Update order
            order.payment_metadata = result
            db.commit()
            
            # Create transaction with UNIQUE reference
            transaction = Transaction(
                transaction_id=paystack_ref,
                order_id=order.id,
                user_id=user.id,
                amount=amount,
                currency=DEFAULT_CURRENCY,
                payment_method=PaymentMethod.PAYSTACK,
                status='pending',
                reference=paystack_ref,
                transaction_data=result
            )
            db.add(transaction)
            db.commit()
            
            logger.info(f"Order {order_id} created. Paystack ref: {paystack_ref}")
            
            # Send payment link
            text = f"""
💳 *Paystack Payment*

📦 Order ID: `{order_id}`
🤖 Bot: {bot_name}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{amount:.2f}
📧 Email: {email}
🔖 Payment Reference: `{paystack_ref}`

Click the button below to pay securely via Paystack.

*After payment, use:* `/verify {paystack_ref}`
            """
            
            keyboard = [
                [InlineKeyboardButton("💳 Pay Now", url=authorization_url)],
                [InlineKeyboardButton("🔄 Verify Payment", callback_data=f"verify_payment_{paystack_ref}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in handle_email_for_paystack: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error processing payment. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_email_for_paystack: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing your request.")

async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Verify Paystack payment - FIXED VERSION"""
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
                await update.message.reply_text("Usage: /verify PAYMENT_REFERENCE\n\nExample: /verify BOT_123_20250128123045987654_ABCDEF12")
            return
        
        logger.info(f"Verifying payment with reference: {payment_reference}")
        
        db = create_session()
        try:
            # Get order by payment_reference (the unique Paystack reference)
            order = db.query(Order).filter(Order.payment_reference == payment_reference).first()
            if not order:
                # Try searching by order_id as fallback (for backward compatibility)
                order = db.query(Order).filter(Order.order_id == payment_reference).first()
                if not order:
                    error_msg = f"""❌ Payment reference not found.

Reference: `{payment_reference}`

*Possible reasons:*
1. Payment reference is incorrect
2. Order was not created properly
3. You're using the wrong reference

*What to do:*
1. Check your payment confirmation email
2. Use the exact payment reference shown during payment
3. Contact support if issue persists"""
                    
                    if is_callback:
                        await query.edit_message_text(error_msg, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(error_msg, parse_mode='Markdown')
                    return
            
            # Get user
            user = db.query(User).filter(User.id == order.user_id).first()
            if not user:
                error_msg = "❌ User not found."
                if is_callback:
                    await query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
                return
            
            # Check if payment is already verified
            if order.payment_status == PaymentStatus.VERIFIED:
                text = f"""✅ Payment Already Verified!

📦 Order ID: `{order.order_id}`
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
📅 Verified: {order.paid_at.strftime('%Y-%m-%d %H:%M') if order.paid_at else 'N/A'}
📊 Status: {order.status.value.replace('_', ' ').title()}

Your payment has already been verified and is being processed."""
                
                keyboard = [
                    [InlineKeyboardButton("📦 View Order", callback_data=f"order_{order.order_id}")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ]
                
                if is_callback:
                    await query.edit_message_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                return
            
            # Verify with Paystack using payment_reference
            paystack = PaystackService()
            
            # Use the order's payment_reference for verification
            reference_to_verify = order.payment_reference
            
            logger.info(f"Verifying Paystack transaction: {reference_to_verify}")
            success, result = paystack.verify_transaction(reference_to_verify)
            
            if success:
                payment_data = result.get('data', {})
                transaction_status = payment_data.get('status', '').lower()
                
                # Check if transaction was successful
                if transaction_status == 'success':
                    # Update order
                    order.status = OrderStatus.PENDING_REVIEW
                    order.payment_status = PaymentStatus.VERIFIED
                    order.paid_at = datetime.now()
                    order.payment_metadata = {
                        **(order.payment_metadata or {}),
                        'verification_response': payment_data,
                        'verified_at': datetime.now().isoformat()
                    }
                    
                    # Update transaction
                    transaction = db.query(Transaction).filter(
                        Transaction.reference == reference_to_verify
                    ).first()
                    
                    if not transaction:
                        # Try to find by order_id
                        transaction = db.query(Transaction).filter(
                            Transaction.order_id == order.id
                        ).first()
                    
                    if transaction:
                        transaction.status = 'successful'
                        transaction.gateway_response = json.dumps(result)
                        transaction.transaction_data = payment_data
                        transaction.verified_at = datetime.now()
                    
                    db.commit()
                    
                    # Get bot info for notification
                    bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                    bot_name = bot.name if bot else "Unknown Bot"
                    
                    # Send admin notification
                    admin_message = f"""💰 NEW ORDER PAYMENT VERIFIED

📦 Order ID: `{order.order_id}`
🔖 Payment Ref: `{reference_to_verify}`
👤 Customer: {user.first_name} (@{user.username or 'N/A'})
📧 Email: {user.email or 'Not provided'}
🤖 Bot: {bot_name}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
💳 Method: Paystack
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ Status: Verified

⚠️ **Action Required:** Admin needs to review and assign developer

Order will be automatically refunded if not assigned within 48 hours."""
                    
                    await notify_admin_payment(order, user, bot_name)
                    
                    # Send success message to user
                    success_text = f"""✅ Payment Verified Successfully!

📦 Order ID: `{order.order_id}`
🔖 Payment Ref: `{reference_to_verify}`
🤖 Bot: {bot_name}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
📅 Paid: {datetime.now().strftime('%Y-%m-%d %H:%M')}
📊 Status: ⏳ Pending Admin Review

**What happens next:**
1. Admin will review your order
2. Order will be assigned to a developer
3. You'll receive updates on progress

⚠️ **Refund Policy:** If no developer claims your order within 48 hours, you will receive a full automatic refund.

Thank you for your purchase! 🎉"""
                    
                    keyboard = [
                        [InlineKeyboardButton("📦 View Order", callback_data=f"order_{order.order_id}")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    if is_callback:
                        await query.edit_message_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
                    else:
                        await update.message.reply_text(success_text, reply_markup=reply_markup, parse_mode='Markdown')
                        
                else:
                    # Payment verification failed (transaction exists but not successful)
                    error_text = f"""❌ Payment Not Successful

📦 Order ID: `{order.order_id}`
🔖 Payment Ref: `{reference_to_verify}`
❌ Status: {transaction_status.title()}

**Transaction found but payment was not successful.**

**Possible reasons:**
1. Payment was cancelled
2. Payment failed
3. Transaction is still pending

**What to do:**
1. Check your payment status on Paystack
2. Complete the payment process
3. Try verifying again in 5 minutes
4. Contact support if issue persists"""
                    
                    keyboard = [
                        [InlineKeyboardButton("🔄 Try Again", callback_data=f"verify_payment_{reference_to_verify}")],
                        [InlineKeyboardButton("📞 Support", callback_data="support")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ]
                    
                    if is_callback:
                        await query.edit_message_text(
                            error_text,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
                    else:
                        await update.message.reply_text(
                            error_text,
                            reply_markup=InlineKeyboardMarkup(keyboard),
                            parse_mode='Markdown'
                        )
            else:
                # Payment verification failed (transaction not found)
                error_text = f"""❌ Payment Verification Failed

📦 Order ID: `{order.order_id}`
🔖 Payment Ref: `{reference_to_verify}`
❌ Status: Payment not found

**Error:** {result.get('message', 'Unknown error')}

**Possible reasons:**
1. Payment not completed
2. Payment is still processing
3. Transaction failed
4. Wrong payment reference used

**What to do:**
1. Check if you completed the payment
2. Wait 5-10 minutes for payment to process
3. Try again with: `/verify {reference_to_verify}`
4. Contact support if issue persists

**Need help?** Use /menu → Support"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Try Again", callback_data=f"verify_payment_{reference_to_verify}")],
                    [InlineKeyboardButton("📞 Support", callback_data="support")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ]
                
                if is_callback:
                    await query.edit_message_text(
                        error_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(
                        error_text,
                        reply_markup=InlineKeyboardMarkup(keyboard),
                        parse_mode='Markdown'
                    )
                    
        except Exception as e:
            logger.error(f"Error in verify_payment: {e}", exc_info=True)
            db.rollback()
            error_msg = f"""❌ Error verifying payment.

**Technical Details:** {str(e)[:100]}

Please try again or contact support."""
            
            if is_callback:
                await query.edit_message_text(error_msg, parse_mode='Markdown')
            else:
                await update.message.reply_text(error_msg, parse_mode='Markdown')
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in verify_payment: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error verifying payment.")
        elif update.message:
            await update.message.reply_text("❌ Error verifying payment.")

async def notify_admin_payment(order, user, bot_name):
    """Notify admin about successful payment"""
    try:
        from telegram import Bot
        from config import TELEGRAM_TOKEN, SUPER_ADMIN_ID
        
        if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
            bot = Bot(token=TELEGRAM_TOKEN)
            
            message = f"""
💰 *New Payment Verified*

📦 Order ID: `{order.order_id}`
👤 Customer: {user.first_name} (@{user.username or 'N/A'})
🤖 Bot: {bot_name}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
💳 Method: Paystack
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
🔖 Payment Ref: `{order.payment_reference}`

*To review:* Go to Admin Panel → Orders
            """
            
            await bot.send_message(
                chat_id=SUPER_ADMIN_ID,
                text=message,
                parse_mode='Markdown'
            )
            
            logger.info(f"Notified admin about payment for order {order.order_id}")
    except Exception as e:
        logger.error(f"Failed to notify admin: {e}", exc_info=True)

# Command handler for /verify
async def verify_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /verify command"""
    await verify_payment(update, context)

# Handler for verify payment callback
async def verify_payment_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle verify payment callback queries"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract payment reference from callback data
        if query.data.startswith('verify_payment_'):
            payment_reference = query.data.replace('verify_payment_', '')
            await verify_payment(update, context)
    except Exception as e:
        logger.error(f"Error in verify_payment_callback: {e}")
        try:
            await query.edit_message_text("❌ Error verifying payment.")
        except:
            pass