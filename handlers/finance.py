# handlers/finance.py - COMPLETE FINANCE SYSTEM (FIXED)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import User, Order, PaymentStatus, Bot, OrderStatus
from config import PAYMENT_METHODS
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

async def finance_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finance panel for admins"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is admin
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            text = """
💰 *Finance Panel*

Manage payments, transactions, and payment methods.
"""
            
            keyboard = [
                [InlineKeyboardButton("📊 Payment Statistics", callback_data="finance_stats")],
                [InlineKeyboardButton("⏳ Pending Payments", callback_data="finance_pending")],
                [InlineKeyboardButton("✅ Verified Payments", callback_data="finance_verified")],
                [InlineKeyboardButton("❌ Rejected Payments", callback_data="finance_rejected")],
                [InlineKeyboardButton("💳 Payment Methods", callback_data="finance_methods")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_panel: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading finance panel.")

async def finance_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show financial statistics"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is admin
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Calculate stats
            today = datetime.now().date()
            week_ago = today - timedelta(days=7)
            month_ago = today - timedelta(days=30)
            
            # Total revenue from completed orders
            completed_orders = db.query(Order).filter(Order.status == OrderStatus.COMPLETED).all()
            total_revenue = sum(order.amount for order in completed_orders if order.amount)
            
            # Today's revenue
            today_orders = db.query(Order).filter(
                Order.created_at >= today,
                Order.status == OrderStatus.COMPLETED
            ).all()
            today_revenue = sum(order.amount for order in today_orders if order.amount)
            
            # Weekly revenue
            week_orders = db.query(Order).filter(
                Order.created_at >= week_ago,
                Order.status == OrderStatus.COMPLETED
            ).all()
            week_revenue = sum(order.amount for order in week_orders if order.amount)
            
            # Monthly revenue
            month_orders = db.query(Order).filter(
                Order.created_at >= month_ago,
                Order.status == OrderStatus.COMPLETED
            ).all()
            month_revenue = sum(order.amount for order in month_orders if order.amount)
            
            # Pending payments
            pending_payments = db.query(Order).filter(Order.payment_status == PaymentStatus.PENDING).count()
            
            # Verified payments
            verified_payments = db.query(Order).filter(Order.payment_status == PaymentStatus.VERIFIED).count()
            
            # Payment method breakdown
            payment_methods = {}
            for order in completed_orders:
                if order.payment_method:
                    method = order.payment_method.value
                    payment_methods[method] = payment_methods.get(method, 0) + (order.amount or 0)
            
            text = f"""
📊 *Financial Statistics*

*Revenue Overview:*
💰 Total Revenue: ${total_revenue:.2f}
📈 Today's Revenue: ${today_revenue:.2f}
📅 Weekly Revenue: ${week_revenue:.2f}
📆 Monthly Revenue: ${month_revenue:.2f}

*Payment Status:*
⏳ Pending Payments: {pending_payments}
✅ Verified Payments: {verified_payments}

*Payment Method Breakdown:*
"""
            
            for method, amount in payment_methods.items():
                text += f"  • {method.replace('_', ' ').title()}: ${amount:.2f}\n"
            
            # Add developer earnings
            from database.models import Developer
            developers = db.query(User).filter(User.is_developer == True).all()
            total_developer_earnings = 0
            for dev_user in developers:
                if dev_user.developer:
                    total_developer_earnings += dev_user.developer.earnings or 0
            
            text += f"\n*Developer Earnings:*\n"
            text += f"  💰 Total Paid to Developers: ${total_developer_earnings:.2f}\n"
            text += f"  👨‍💻 Active Developers: {len(developers)}\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="finance_stats")],
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="finance_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_stats: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading statistics.")

async def finance_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending payments for review"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is admin
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Get pending payments
            pending_orders = db.query(Order).filter(
                Order.payment_status == PaymentStatus.PENDING,
                Order.payment_proof_url != None
            ).order_by(Order.created_at.desc()).all()
            
            if not pending_orders:
                text = "⏳ *Pending Payments*\n\nNo pending payments to review."
            else:
                text = f"⏳ *Pending Payments*\n\n*Total:* {len(pending_orders)}\n\n"
                
                for order in pending_orders[:10]:  # Show first 10
                    order_user = db.query(User).filter(User.id == order.user_id).first()
                    text += f"📦 *{order.order_id}*\n"
                    text += f"   👤 {order_user.first_name if order_user else 'Unknown'}\n"
                    text += f"   💰 ${order.amount:.2f if order.amount else 0:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
            
            keyboard = []
            for order in pending_orders[:10]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 {order.order_id[:8]} - ${order.amount:.2f if order.amount else 0:.2f}",
                        callback_data=f"finance_review_payment_{order.order_id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Finance", callback_data="finance_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_pending_payments: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading pending payments.")

async def finance_review_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Review a specific payment with proof image"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = query.data.replace('finance_review_payment_', '')
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is admin
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Get order
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            order_user = db.query(User).filter(User.id == order.user_id).first()
            
            text = f"""
💰 *Payment Review*

*Order ID:* `{order.order_id}`
*Customer:* {order_user.first_name} (@{order_user.username or 'N/A'})
*Amount:* ${order.amount:.2f if order.amount else 0:.2f}
*Payment Method:* {order.payment_method.value if order.payment_method else 'Not specified'}
*Status:* ⏳ Pending Review
*Date:* {order.created_at.strftime('%Y-%m-%d %H:%M')}

*Payment Details:*
"""
            
            if order.payment_details:
                for key, value in order.payment_details.items():
                    text += f"  • {key}: {value}\n"
            
            text += "\n*Actions:*\n- View the payment proof below\n- Verify if payment is correct\n- Approve or reject\n"
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Verify Payment", callback_data=f"finance_verify_{order.order_id}"),
                    InlineKeyboardButton("❌ Reject Payment", callback_data=f"finance_reject_{order.order_id}")
                ],
                [InlineKeyboardButton("💬 Ask for Clarification", callback_data=f"finance_clarify_{order.order_id}")],
                [InlineKeyboardButton("⬅️ Pending Payments", callback_data="finance_pending")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
            # Send the payment proof image if available
            if order.payment_proof_url and order.payment_proof_url.startswith('telegram_file:'):
                file_id = order.payment_proof_url.replace('telegram_file:', '')
                
                from config import TELEGRAM_TOKEN
                
                if TELEGRAM_TOKEN:
                    from telegram import Bot as TelegramBot
                    bot = TelegramBot(token=TELEGRAM_TOKEN)
                    
                    try:
                        await bot.send_photo(
                            chat_id=telegram_id,
                            photo=file_id,
                            caption=f"📸 *Payment Proof for Order {order.order_id}*\n\n"
                                   f"Please review this payment proof and take action above.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to send payment proof: {e}")
                        await query.message.reply_text(
                            f"⚠️ Could not load payment proof. Error: {str(e)[:100]}"
                        )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_review_payment: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading payment details.")

async def finance_handle_payment_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment verification actions"""
    try:
        query = update.callback_query
        await query.answer()
        
        data = query.data
        if data.startswith('finance_verify_'):
            order_id = data.replace('finance_verify_', '')
            action = "verify"
        elif data.startswith('finance_reject_'):
            order_id = data.replace('finance_reject_', '')
            action = "reject"
        elif data.startswith('finance_clarify_'):
            order_id = data.replace('finance_clarify_', '')
            action = "clarify"
        else:
            return
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is admin
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Get order
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if action == "verify":
                # Verify payment
                order.payment_status = PaymentStatus.VERIFIED
                order.status = OrderStatus.APPROVED
                
                db.commit()
                
                # Notify user
                order_user = db.query(User).filter(User.id == order.user_id).first()
                
                from config import TELEGRAM_TOKEN
                from telegram import Bot as TelegramBot
                
                if TELEGRAM_TOKEN:
                    bot = TelegramBot(token=TELEGRAM_TOKEN)
                    
                    try:
                        await bot.send_message(
                            chat_id=order_user.telegram_id,
                            text=f"✅ *Payment Verified!*\n\n"
                                 f"Your payment for order `{order.order_id}` has been verified.\n\n"
                                 f"*Amount:* ${order.amount:.2f}\n"
                                 f"*Status:* ✅ Approved\n\n"
                                 f"The order is now available for developers to work on.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
                
                await query.edit_message_text(
                    f"✅ *Payment Verified!*\n\n"
                    f"Order `{order.order_id}` has been approved and is now available for developers.",
                    parse_mode='Markdown'
                )
                
            elif action == "reject":
                # Store for rejection reason
                context.user_data['rejecting_payment_order_id'] = order_id
                context.user_data['rejecting_payment_user_id'] = order.user_id
                
                await query.edit_message_text(
                    f"📝 *Reject Payment*\n\n"
                    f"Please provide a reason for rejecting the payment for order `{order.order_id}`:\n\n"
                    f"Send your reason now (will be sent to the user).",
                    parse_mode='Markdown'
                )
                
            elif action == "clarify":
                # Ask for clarification
                context.user_data['clarifying_payment_order_id'] = order_id
                context.user_data['clarifying_payment_user_id'] = order.user_id
                
                await query.edit_message_text(
                    f"💬 *Request Clarification*\n\n"
                    f"What clarification do you need about the payment for order `{order.order_id}`?\n\n"
                    f"Send your question now (will be forwarded to the user).",
                    parse_mode='Markdown'
                )
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_handle_payment_action: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error processing payment action.")

async def finance_verified_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show verified payments"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Get verified payments
            verified_orders = db.query(Order).filter(
                Order.payment_status == PaymentStatus.VERIFIED
            ).order_by(Order.created_at.desc()).all()
            
            text = "✅ *Verified Payments*\n\n"
            
            if not verified_orders:
                text += "No verified payments found."
            else:
                text += f"Total: {len(verified_orders)}\n\n"
                for order in verified_orders[:10]:
                    order_user = db.query(User).filter(User.id == order.user_id).first()
                    text += f"📦 {order.order_id}\n"
                    text += f"   👤 {order_user.first_name if order_user else 'Unknown'}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="finance_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_verified_payments: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading verified payments.")

async def finance_rejected_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show rejected payments"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Get rejected payments
            rejected_orders = db.query(Order).filter(
                Order.payment_status == PaymentStatus.REJECTED
            ).order_by(Order.created_at.desc()).all()
            
            text = "❌ *Rejected Payments*\n\n"
            
            if not rejected_orders:
                text += "No rejected payments found."
            else:
                text += f"Total: {len(rejected_orders)}\n\n"
                for order in rejected_orders[:10]:
                    order_user = db.query(User).filter(User.id == order.user_id).first()
                    text += f"📦 {order.order_id}\n"
                    text += f"   👤 {order_user.first_name if order_user else 'Unknown'}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="finance_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_rejected_payments: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading rejected payments.")

async def finance_methods(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage payment methods"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await query.edit_message_text("❌ Access denied.")
                return
            
            text = "💳 *Payment Methods*\n\n"
            
            for method_key, method_info in PAYMENT_METHODS.items():
                text += f"*{method_info.get('name', method_key.title())}*\n"
                text += f"Account: {method_info.get('account', 'Not set')}\n"
                text += f"Status: ✅ Active\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="finance_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in finance_methods: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading payment methods.")