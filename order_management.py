"""
Order management with verification, admin notification, and refund policy
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import Order, OrderStatus, PaymentStatus, User, Bot as SoftwareBot, CustomRequest, RequestStatus, Transaction
from services.paystack_service import PaystackService
from config import TELEGRAM_TOKEN, SUPER_ADMIN_ID, DEFAULT_CURRENCY_SYMBOL
import logging
from datetime import datetime, timedelta
import json
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Global instance for background tasks
refund_checker_thread = None

async def send_admin_notification(message: str):
    """Send notification to admin"""
    try:
        if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
            bot = Bot(token=TELEGRAM_TOKEN)
            await bot.send_message(
                chat_id=SUPER_ADMIN_ID,
                text=message
            )
            logger.info(f"Admin notification sent: {message[:100]}...")
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


async def verify_order_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_reference: str, is_callback: bool = False):
    """Verify order payment and notify admin - UPDATED for unique payment references"""
    db = create_session()
    try:
        # Get order by payment_reference (NOT order_id)
        order = db.query(Order).filter(Order.payment_reference == payment_reference).first()
        if not order:
            # Try searching by order_id as fallback (for backward compatibility)
            order = db.query(Order).filter(Order.order_id == payment_reference).first()
            if not order:
                error_msg = f"❌ Payment reference {payment_reference} not found.\n\nTry using the exact payment reference shown during payment."
                if is_callback:
                    await update.callback_query.edit_message_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
                return
        
        # Get user
        user = db.query(User).filter(User.id == order.user_id).first()
        if not user:
            error_msg = "❌ User not found."
            if is_callback:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        # Check if payment is already verified
        if order.payment_status == PaymentStatus.VERIFIED:
            text = f"""✅ Payment Already Verified!

📦 Order ID: {order.order_id}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
📅 Verified: {order.paid_at.strftime('%Y-%m-%d %H:%M') if order.paid_at else 'N/A'}
📊 Status: {order.status.value.replace('_', ' ').title()}

Your payment has already been verified and is being processed."""
            
            keyboard = [
                [InlineKeyboardButton("📦 View Order", callback_data=f"order_{order.order_id}")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            if is_callback:
                await update.callback_query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            return
        
        # Verify with Paystack using payment_reference
        paystack = PaystackService()
        
        # Use the order's payment_reference for verification
        reference_to_verify = order.payment_reference or order.order_id
        
        logger.info(f"Verifying payment with reference: {reference_to_verify}")
        success, result = paystack.verify_transaction(reference_to_verify)
        
        if success:
            payment_data = result.get('data', {})
            
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
            
            # Send admin notification
            admin_message = f"""💰 NEW ORDER PAYMENT VERIFIED

📦 Order ID: {order.order_id}
🔖 Payment Ref: {reference_to_verify}
👤 Customer: {user.first_name} (@{user.username or 'N/A'})
📧 Email: {user.email or 'Not provided'}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
💳 Method: Paystack
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ Status: Verified

⚠️ **Action Required:** Admin needs to review and assign developer

Order will be automatically refunded if not assigned within 48 hours."""
            
            await send_admin_notification(admin_message)
            
            # Send success message to user
            success_text = f"""✅ Payment Verified Successfully!

📦 Order ID: {order.order_id}
🔖 Payment Ref: {reference_to_verify}
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
                await update.callback_query.edit_message_text(success_text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(success_text, reply_markup=reply_markup)
                
        else:
            # Payment verification failed
            error_text = f"""❌ Payment Verification Failed

📦 Order ID: {order.order_id}
🔖 Payment Ref: {reference_to_verify}
❌ Status: Payment not found or failed

**Error:** {result.get('message', 'Unknown error')}

**Possible reasons:**
1. Payment not completed
2. Payment is still processing
3. Transaction failed
4. Wrong payment reference used

**What to do:**
1. Check if you completed the payment
2. Wait 5-10 minutes for payment to process
3. Try again with: /verify {reference_to_verify}
4. Contact support if issue persists

**Need help?** Use /menu → Support"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Try Again", callback_data=f"verify_payment_{reference_to_verify}")],
                [InlineKeyboardButton("📞 Support", callback_data="support")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            if is_callback:
                await update.callback_query.edit_message_text(
                    error_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    error_text,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
    except Exception as e:
        logger.error(f"Error in verify_order_payment: {e}", exc_info=True)
        db.rollback()
        error_msg = f"""❌ Error verifying payment.

**Technical Details:** {str(e)[:100]}

Please try again or contact support."""
        
        if is_callback:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
    finally:
        db.close()

        
async def verify_custom_request_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_reference: str, is_callback: bool = False):
    """Verify custom request deposit and notify admin"""
    db = create_session()
    try:
        # Get custom request
        custom_request = db.query(CustomRequest).filter(
            CustomRequest.payment_reference == payment_reference
        ).first()
        
        if not custom_request:
            error_msg = f"❌ Payment reference {payment_reference} not found."
            if is_callback:
                await update.callback_query.edit_message_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
            return
        
        if custom_request.is_deposit_paid:
            text = f"✅ Deposit Already Paid\n\n📋 Request ID: {custom_request.request_id}"
            if is_callback:
                await update.callback_query.edit_message_text(text)
            else:
                await update.message.reply_text(text)
            return
        
        # Verify with Paystack
        paystack = PaystackService()
        success, result = paystack.verify_transaction(payment_reference)
        
        if success:
            payment_data = result.get('data', {})
            
            # Update custom request - Try to find the correct enum value
            custom_request.is_deposit_paid = True
            
            # Try different enum values for pending status
            try:
                # First try PENDING
                custom_request.status = RequestStatus.PENDING
            except AttributeError:
                try:
                    # Try PENDING_REVIEW
                    custom_request.status = RequestStatus.PENDING_REVIEW
                except AttributeError:
                    # Try REVIEW_PENDING
                    custom_request.status = RequestStatus.REVIEW_PENDING
            
            custom_request.payment_metadata = payment_data
            custom_request.deposit_paid_at = datetime.now()
            
            # Update transaction
            transaction = db.query(Transaction).filter(
                Transaction.reference == payment_reference
            ).first()
            
            if transaction:
                transaction.status = 'successful'
                transaction.gateway_response = json.dumps(result)
                transaction.transaction_data = payment_data
                transaction.verified_at = datetime.now()
            
            db.commit()
            
            # Get user
            user = db.query(User).filter(User.id == custom_request.user_id).first()
            
            # Send admin notification
            admin_message = f"""💰 CUSTOM REQUEST DEPOSIT PAID

📋 Request ID: {custom_request.request_id}
👤 Customer: {user.first_name} (@{user.username or 'N/A'})
📧 Email: {user.email or 'Not provided'}
📝 Title: {custom_request.title}
💰 Total Price: {DEFAULT_CURRENCY_SYMBOL}{custom_request.estimated_price:.2f}
💳 Deposit (20%): {DEFAULT_CURRENCY_SYMBOL}{custom_request.estimated_price * 0.2:.2f}
📅 Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}

⚠️ **Action Required:** Admin needs to review custom request

Request will be automatically refunded if not approved within 48 hours."""
            
            await send_admin_notification(admin_message)
            
            # Send success message to user
            success_text = f"""✅ Deposit Payment Verified!

📋 Request ID: {custom_request.request_id}
📊 Deposit Paid (20%): {DEFAULT_CURRENCY_SYMBOL}{custom_request.estimated_price * 0.2:.2f}
📅 Status: ⏳ Pending Admin Review

**What happens next:**
1. Admin will review your custom request
2. Once approved, available to all developers
3. Developer will be assigned when claimed

⚠️ **Refund Policy:** If your request is not approved within 48 hours, you will receive a full deposit refund.

Thank you for submitting your request! 🎉"""
            
            if is_callback:
                await update.callback_query.edit_message_text(success_text)
            else:
                await update.message.reply_text(success_text)
        else:
            # Verification failed
            error_text = f"""❌ Deposit Payment Verification Failed

📋 Request ID: {custom_request.request_id}
❌ Status: Payment not found or failed

**Possible reasons:**
1. Payment not completed
2. Payment is still processing
3. Transaction failed

Please complete the payment and try again.

If you've already paid, wait 5 minutes and try again."""
            
            if is_callback:
                await update.callback_query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
                
    except Exception as e:
        logger.error(f"Error in verify_custom_request_deposit: {e}", exc_info=True)
        db.rollback()
        error_msg = "❌ Error verifying payment. Please try again."
        if is_callback:
            await update.callback_query.edit_message_text(error_msg)
        else:
            await update.message.reply_text(error_msg)
    finally:
        db.close()


def process_automatic_refunds():
    """Process automatic refunds for unclaimed orders (runs every hour)"""
    while True:
        try:
            db = create_session()
            
            # Get current time and 48 hours ago
            now = datetime.now()
            forty_eight_hours_ago = now - timedelta(hours=48)
            
            logger.info(f"Running automatic refund check at {now}")
            
            # ========== 1. Check for unassigned orders (after admin approval) ==========
            # These are orders that have been approved by admin but no developer claimed within 48 hours
            unassigned_orders = db.query(Order).filter(
                Order.status == OrderStatus.APPROVED,
                Order.approved_at != None,
                Order.approved_at <= forty_eight_hours_ago,
                Order.assigned_developer_id == None,
                Order.refunded_at == None,
                Order.payment_status == PaymentStatus.VERIFIED
            ).all()
            
            for order in unassigned_orders:
                try:
                    logger.info(f"Processing refund for unclaimed order: {order.order_id}")
                    
                    # Process refund via Paystack
                    paystack = PaystackService()
                    success, result = paystack.refund_transaction(
                        reference=order.payment_reference or order.order_id,
                        amount=order.amount
                    )
                    
                    if success:
                        # Update order status
                        order.status = OrderStatus.REFUNDED
                        order.refunded_at = now
                        order.refund_reason = "Automatic refund: No developer claimed within 48 hours"
                        order.refund_metadata = result
                        
                        # Update transaction
                        transaction = db.query(Transaction).filter(
                            Transaction.reference == (order.payment_reference or order.order_id)
                        ).first()
                        
                        if transaction:
                            transaction.status = 'refunded'
                            transaction.refund_data = result
                        
                        # Notify admin
                        admin_msg = f"""⚠️ AUTOMATIC REFUND PROCESSED

📦 Order ID: {order.order_id}
💰 Amount Refunded: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
🔄 Reason: No developer claimed within 48 hours
📅 Refund Time: {now.strftime('%Y-%m-%d %H:%M')}
✅ Status: Refund successful

The customer has been automatically refunded."""
                        
                        try:
                            bot = Bot(token=TELEGRAM_TOKEN)
                            bot.send_message(chat_id=SUPER_ADMIN_ID, text=admin_msg)
                        except:
                            pass
                        
                        # Notify user
                        try:
                            user = db.query(User).filter(User.id == order.user_id).first()
                            if user and user.telegram_id:
                                user_msg = f"""💸 Automatic Refund Processed

📦 Order ID: {order.order_id}
💰 Amount Refunded: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}
🔄 Reason: No developer claimed your order within 48 hours
📅 Refund Time: {now.strftime('%Y-%m-%d %H:%M')}
✅ Status: Refund successful

Your payment has been automatically refunded to your original payment method.

Refunds usually take 3-5 business days to appear in your account.

We apologize for the inconvenience. You can place a new order at any time."""
                                
                                bot.send_message(chat_id=user.telegram_id, text=user_msg)
                        except:
                            pass
                        
                        logger.info(f"Successfully refunded order {order.order_id}")
                    else:
                        logger.error(f"Failed to refund order {order.order_id}: {result}")
                        
                except Exception as e:
                    logger.error(f"Error processing refund for order {order.order_id}: {e}")
            
            # ========== 2. Check for unapproved custom requests ==========
            # Custom requests that haven't been approved by admin within 48 hours of deposit
            # Try to find the correct enum value for pending status
            try:
                # First try to get the enum value
                pending_status = RequestStatus.PENDING
            except AttributeError:
                try:
                    pending_status = RequestStatus.PENDING_REVIEW
                except AttributeError:
                    try:
                        pending_status = RequestStatus.REVIEW_PENDING
                    except AttributeError:
                        # If we can't find it, skip this check
                        logger.warning("Could not find pending status enum value, skipping custom request refund check")
                        pending_status = None
            
            if pending_status:
                unapproved_requests = db.query(CustomRequest).filter(
                    CustomRequest.status == pending_status,
                    CustomRequest.deposit_paid_at != None,
                    CustomRequest.deposit_paid_at <= forty_eight_hours_ago,
                    CustomRequest.is_deposit_paid == True,
                    CustomRequest.refunded_at == None
                ).all()
                
                for request in unapproved_requests:
                    try:
                        logger.info(f"Processing refund for unapproved custom request: {request.request_id}")
                        
                        # Process refund for deposit
                        deposit_amount = request.estimated_price * 0.2
                        paystack = PaystackService()
                        success, result = paystack.refund_transaction(
                            reference=request.payment_reference,
                            amount=deposit_amount
                        )
                        
                        if success:
                            # Update custom request
                            request.status = RequestStatus.REFUNDED
                            request.refunded_at = now
                            request.refund_reason = "Automatic refund: Request not approved within 48 hours"
                            request.refund_metadata = result
                            
                            # Update transaction
                            transaction = db.query(Transaction).filter(
                                Transaction.reference == request.payment_reference
                            ).first()
                            
                            if transaction:
                                transaction.status = 'refunded'
                                transaction.refund_data = result
                            
                            # Notify admin
                            admin_msg = f"""⚠️ CUSTOM REQUEST DEPOSIT REFUNDED

📋 Request ID: {request.request_id}
📝 Title: {request.title}
💰 Deposit Refunded: {DEFAULT_CURRENCY_SYMBOL}{deposit_amount:.2f}
🔄 Reason: Request not approved within 48 hours
📅 Refund Time: {now.strftime('%Y-%m-%d %H:%M')}
✅ Status: Refund successful

Customer deposit has been automatically refunded."""
                            
                            try:
                                bot = Bot(token=TELEGRAM_TOKEN)
                                bot.send_message(chat_id=SUPER_ADMIN_ID, text=admin_msg)
                            except:
                                pass
                            
                            # Notify user
                            try:
                                user = db.query(User).filter(User.id == request.user_id).first()
                                if user and user.telegram_id:
                                    user_msg = f"""💸 Custom Request Deposit Refunded

📋 Request ID: {request.request_id}
📝 Title: {request.title}
💰 Deposit Refunded: {DEFAULT_CURRENCY_SYMBOL}{deposit_amount:.2f}
🔄 Reason: Your request was not approved within 48 hours
📅 Refund Time: {now.strftime('%Y-%m-%d %H:%M')}
✅ Status: Refund successful

Your deposit has been automatically refunded to your original payment method.

Refunds usually take 3-5 business days to appear in your account.

You can submit a new request at any time."""
                                    
                                    bot.send_message(chat_id=user.telegram_id, text=user_msg)
                            except:
                                pass
                            
                            logger.info(f"Successfully refunded custom request {request.request_id}")
                        else:
                            logger.error(f"Failed to refund custom request {request.request_id}: {result}")
                            
                    except Exception as e:
                        logger.error(f"Error processing refund for custom request {request.request_id}: {e}")
            
            # ========== 3. Check for abandoned orders (payment but no verification) ==========
            # Orders that have payment reference but haven't been verified within 24 hours
            twenty_four_hours_ago = now - timedelta(hours=24)
            abandoned_orders = db.query(Order).filter(
                Order.status == OrderStatus.PENDING_PAYMENT,
                Order.payment_reference != None,
                Order.created_at <= twenty_four_hours_ago,
                Order.payment_status == PaymentStatus.PENDING
            ).all()
            
            for order in abandoned_orders:
                # Send reminder to user
                try:
                    user = db.query(User).filter(User.id == order.user_id).first()
                    if user and user.telegram_id:
                        reminder_msg = f"""⏰ Payment Reminder

📦 Order ID: {order.order_id}
💰 Amount: {DEFAULT_CURRENCY_SYMBOL}{order.amount:.2f}

Your payment is still pending. Please complete your payment or your order will be cancelled in 24 hours.

Use /verify {order.order_id} to check payment status."""
                        
                        bot = Bot(token=TELEGRAM_TOKEN)
                        bot.send_message(chat_id=user.telegram_id, text=reminder_msg)
                except:
                    pass
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error in automatic refund checker: {e}", exc_info=True)
            try:
                db.rollback()
            except:
                pass
        finally:
            try:
                db.close()
            except:
                pass
        
        # Wait for 1 hour before next check
        time.sleep(3600)


def start_refund_checker():
    """Start the automatic refund checker thread"""
    global refund_checker_thread
    
    if refund_checker_thread and refund_checker_thread.is_alive():
        logger.info("Refund checker already running")
        return
    
    logger.info("Starting automatic refund checker...")
    refund_checker_thread = threading.Thread(
        target=process_automatic_refunds,
        daemon=True,
        name="RefundChecker"
    )
    refund_checker_thread.start()
    logger.info("Automatic refund checker started successfully")


async def manual_refund_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manual refund command for admins"""
    try:
        # Check if user is admin
        telegram_id = update.effective_user.id
        from config import SUPER_ADMIN_ID
        
        if str(telegram_id) != str(SUPER_ADMIN_ID):
            await update.message.reply_text("❌ This command is for administrators only.")
            return
        
        if not context.args:
            await update.message.reply_text(
                "Usage: /refund ORDER_ID [REASON]\n\n"
                "Example: /refund BOT2024011612345678 'Customer requested refund'\n\n"
                "Or for custom request: /refund CR2024011612345678 'Request cancelled'"
            )
            return
        
        reference = context.args[0]
        reason = " ".join(context.args[1:]) if len(context.args) > 1 else "Manual refund by admin"
        
        db = create_session()
        try:
            # Check if it's an order
            order = db.query(Order).filter(Order.order_id == reference).first()
            if order:
                amount = order.amount
                order_type = "order"
                user_id = order.user_id
                
            # Check if it's a custom request
            else:
                custom_request = db.query(CustomRequest).filter(
                    CustomRequest.request_id == reference
                ).first()
                if custom_request:
                    amount = custom_request.estimated_price * 0.2 if custom_request.is_deposit_paid else custom_request.estimated_price
                    order_type = "custom request"
                    user_id = custom_request.user_id
                else:
                    await update.message.reply_text(f"❌ No order or custom request found with ID: {reference}")
                    return
            
            # Get user
            user = db.query(User).filter(User.id == user_id).first()
            
            # Confirm refund
            await update.message.reply_text(
                f"⚠️ **REFUND CONFIRMATION**\n\n"
                f"Type: {order_type.title()}\n"
                f"Reference: {reference}\n"
                f"Amount: {DEFAULT_CURRENCY_SYMBOL}{amount:.2f}\n"
                f"Customer: {user.first_name} (@{user.username or 'N/A'})\n"
                f"Reason: {reason}\n\n"
                f"**Are you sure you want to process this refund?**\n"
                f"Reply with 'YES' to confirm or 'NO' to cancel.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ YES", callback_data=f"confirm_refund_{reference}")],
                    [InlineKeyboardButton("❌ NO", callback_data="cancel_refund")]
                ])
            )
            
            # Store refund context
            context.user_data['pending_refund'] = {
                'reference': reference,
                'amount': amount,
                'type': order_type,
                'reason': reason,
                'user_id': user_id
            }
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in manual_refund_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing refund command.")


async def confirm_refund_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle refund confirmation"""
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel_refund":
            await query.edit_message_text("❌ Refund cancelled.")
            return
        
        # Extract reference from callback data: confirm_refund_ORDER123
        if not query.data.startswith('confirm_refund_'):
            await query.edit_message_text("❌ Invalid refund request.")
            return
        
        reference = query.data.replace('confirm_refund_', '')
        refund_data = context.user_data.get('pending_refund')
        
        if not refund_data or refund_data['reference'] != reference:
            await query.edit_message_text("❌ Refund data not found. Please start over.")
            return
        
        amount = refund_data['amount']
        order_type = refund_data['type']
        reason = refund_data['reason']
        user_id = refund_data['user_id']
        
        # Process refund
        db = create_session()
        try:
            paystack = PaystackService()
            
            # Determine payment reference based on order type
            if order_type == "order":
                order = db.query(Order).filter(Order.order_id == reference).first()
                payment_reference = order.payment_reference or order.order_id
            else:
                custom_request = db.query(CustomRequest).filter(
                    CustomRequest.request_id == reference
                ).first()
                payment_reference = custom_request.payment_reference
            
            # Process refund via Paystack
            success, result = paystack.refund_transaction(
                reference=payment_reference,
                amount=amount
            )
            
            if success:
                # Update records
                if order_type == "order":
                    order.status = OrderStatus.REFUNDED
                    order.refunded_at = datetime.now()
                    order.refund_reason = reason
                    order.refund_metadata = result
                    
                    transaction = db.query(Transaction).filter(
                        Transaction.reference == payment_reference
                    ).first()
                else:
                    custom_request.status = RequestStatus.REFUNDED
                    custom_request.refunded_at = datetime.now()
                    custom_request.refund_reason = reason
                    custom_request.refund_metadata = result
                    
                    transaction = db.query(Transaction).filter(
                        Transaction.reference == payment_reference
                    ).first()
                
                if transaction:
                    transaction.status = 'refunded'
                    transaction.refund_data = result
                
                db.commit()
                
                # Get user for notification
                user = db.query(User).filter(User.id == user_id).first()
                
                # Notify admin
                admin_msg = f"""✅ MANUAL REFUND PROCESSED

📋 Reference: {reference}
💰 Amount Refunded: {DEFAULT_CURRENCY_SYMBOL}{amount:.2f}
👤 Customer: {user.first_name} (@{user.username or 'N/A'})
🔄 Reason: {reason}
📅 Refund Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ Status: Refund successful"""
                
                await send_admin_notification(admin_msg)
                
                # Notify user
                if user and user.telegram_id:
                    try:
                        bot = Bot(token=TELEGRAM_TOKEN)
                        user_msg = f"""💸 Refund Processed

📋 Reference: {reference}
💰 Amount Refunded: {DEFAULT_CURRENCY_SYMBOL}{amount:.2f}
🔄 Reason: {reason}
📅 Refund Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}
✅ Status: Refund successful

Your refund has been processed and will be credited to your original payment method within 3-5 business days.

Thank you for your understanding."""
                        
                        await bot.send_message(chat_id=user.telegram_id, text=user_msg)
                    except:
                        pass
                
                await query.edit_message_text(
                    f"✅ Refund processed successfully!\n\n"
                    f"Reference: {reference}\n"
                    f"Amount: {DEFAULT_CURRENCY_SYMBOL}{amount:.2f}\n"
                    f"Customer has been notified."
                )
            else:
                error_msg = result.get('message', 'Unknown error')
                await query.edit_message_text(
                    f"❌ Refund failed: {error_msg}\n\n"
                    f"Please check Paystack dashboard or try again later."
                )
                
        except Exception as e:
            logger.error(f"Error processing manual refund: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error processing refund. Please try again.")
        finally:
            db.close()
            context.user_data.pop('pending_refund', None)
            
    except Exception as e:
        logger.error(f"Error in confirm_refund_callback: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing refund confirmation.")