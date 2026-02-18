# handlers/admin_requests.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import User, AdminRequest, AdminRequestStatus
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

async def request_admin_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin access requests from users"""
    try:
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                await update.message.reply_text(
                    "❌ Please use /start first to create your account.",
                    parse_mode='Markdown'
                )
                return
            
            # Check if user is already admin
            if user.is_admin:
                await update.message.reply_text(
                    "✅ You are already an admin!",
                    parse_mode='Markdown'
                )
                return
            
            # Check if user already has a pending request
            existing_request = db.query(AdminRequest).filter(
                AdminRequest.user_id == user.id,
                AdminRequest.status == AdminRequestStatus.PENDING
            ).first()
            
            if existing_request:
                await update.message.reply_text(
                    "⏳ You already have a pending admin request. Please wait for review.",
                    parse_mode='Markdown'
                )
                return
            
            # Get reason from command arguments
            reason = " ".join(context.args) if context.args else "No reason provided"
            
            # Create admin request
            admin_request = AdminRequest(
                user_id=user.id,
                reason=reason[:500],  # Limit reason length
                status=AdminRequestStatus.PENDING
            )
            db.add(admin_request)
            db.commit()
            
            # Notify super admin
            from config import SUPER_ADMIN_ID, TELEGRAM_TOKEN
            from telegram import Bot as TelegramBot
            
            if TELEGRAM_TOKEN:
                bot = TelegramBot(token=TELEGRAM_TOKEN)
                
                notification_text = f"""
🔔 *New Admin Request*

*User:* {user.first_name} (@{user.username or 'N/A'})
*Telegram ID:* {user.telegram_id}
*Reason:* {reason[:200]}

*Actions:*
- Use /review_admin_requests to view all pending requests
- Or click below to review directly
"""
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        f"👑 Review {user.first_name}'s Request",
                        callback_data=f"admin_review_request_{admin_request.id}"
                    )]
                ])
                
                try:
                    await bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=notification_text,
                        parse_mode='Markdown',
                        reply_markup=keyboard
                    )
                except Exception as e:
                    logger.error(f"Failed to notify super admin: {e}", exc_info=True)
            
            await update.message.reply_text(
                f"✅ *Admin request submitted!*\n\n"
                f"Your request has been sent for review.\n"
                f"*Reason:* {reason[:200]}\n\n"
                f"You'll be notified once it's reviewed.",
                parse_mode='Markdown'
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in request_admin_access: {e}", exc_info=True)
        await update.message.reply_text(
            "❌ Error submitting admin request. Please try again later.",
            parse_mode='Markdown'
        )

async def review_admin_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending admin requests to admins"""
    try:
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is admin
            user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not user:
                await update.message.reply_text("❌ Access denied.")
                return
            
            # Get pending requests
            pending_requests = db.query(AdminRequest).filter(
                AdminRequest.status == AdminRequestStatus.PENDING
            ).order_by(AdminRequest.created_at.desc()).all()
            
            if not pending_requests:
                text = "📋 *Pending Admin Requests*\n\nNo pending requests."
            else:
                text = f"📋 *Pending Admin Requests*\n\n*Total:* {len(pending_requests)}\n\n"
                
                for req in pending_requests[:5]:  # Show first 5
                    request_user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"👤 *{request_user.first_name}* (@{request_user.username or 'N/A'})\n"
                    text += f"📅 Requested: {req.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                    text += f"📝 Reason: {req.reason[:100]}...\n\n"
            
            keyboard = []
            for req in pending_requests[:5]:
                request_user = db.query(User).filter(User.id == req.user_id).first()
                keyboard.append([
                    InlineKeyboardButton(
                        f"👤 {request_user.first_name} - Review",
                        callback_data=f"admin_review_request_{req.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.message:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            elif update.callback_query:
                query = update.callback_query
                await query.answer()
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in review_admin_requests: {e}", exc_info=True)
        if update.message:
            await update.message.reply_text("❌ Error loading admin requests.")
        elif update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading admin requests.")

async def handle_admin_request_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin request review actions"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract request ID from callback data
        if query.data.startswith('admin_review_request_'):
            request_id = int(query.data.replace('admin_review_request_', ''))
            
            db = create_session()
            try:
                # Check if user is admin
                telegram_id = update.effective_user.id
                admin = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
                if not admin:
                    await query.edit_message_text("❌ Access denied.")
                    return
                
                # Get the request
                admin_request = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
                if not admin_request:
                    await query.edit_message_text("❌ Request not found.")
                    return
                
                request_user = db.query(User).filter(User.id == admin_request.user_id).first()
                
                text = f"""
👑 *Review Admin Request*

*User:* {request_user.first_name} {request_user.last_name or ''}
*Username:* @{request_user.username or 'N/A'}
*Telegram ID:* {request_user.telegram_id}
*Email:* {request_user.email or 'Not provided'}
*Phone:* {request_user.phone or 'Not provided'}

*Request Details:*
📅 Requested: {admin_request.created_at.strftime('%Y-%m-%d %H:%M')}
📝 Reason: {admin_request.reason or 'No reason provided'}

*User Stats:*
📦 Orders: {db.query(User).get(request_user.id).orders.count() if hasattr(request_user, 'orders') else 0}
💬 Requests: {db.query(User).get(request_user.id).requests.count() if hasattr(request_user, 'requests') else 0}
💰 Balance: ${request_user.balance:.2f if hasattr(request_user, 'balance') else 0}

Choose an action:
"""
                
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_request_{request_id}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_request_{request_id}")
                    ],
                    [InlineKeyboardButton("💬 Ask for More Info", callback_data=f"admin_more_info_request_{request_id}")],
                    [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_review_requests")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                
            finally:
                db.close()
                
    except Exception as e:
        logger.error(f"Error in handle_admin_request_review: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading request details.")

async def handle_request_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle approve/reject decisions for admin requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Parse callback data
        data = query.data
        if data.startswith('admin_approve_request_'):
            request_id = int(data.replace('admin_approve_request_', ''))
            action = "approve"
        elif data.startswith('admin_reject_request_'):
            request_id = int(data.replace('admin_reject_request_', ''))
            action = "reject"
        elif data.startswith('admin_more_info_request_'):
            request_id = int(data.replace('admin_more_info_request_', ''))
            action = "more_info"
        else:
            return
        
        db = create_session()
        try:
            # Check if user is admin
            telegram_id = update.effective_user.id
            admin = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not admin:
                await query.edit_message_text("❌ Access denied.")
                return
            
            # Get the request
            admin_request = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
            if not admin_request:
                await query.edit_message_text("❌ Request not found.")
                return
            
            request_user = db.query(User).filter(User.id == admin_request.user_id).first()
            
            if action == "approve":
                # Approve the request
                request_user.is_admin = True
                admin_request.status = AdminRequestStatus.APPROVED
                admin_request.reviewed_by = admin.id
                admin_request.reviewed_at = func.now()
                admin_request.notes = "Approved by admin"
                
                db.commit()
                
                # Notify user
                from config import TELEGRAM_TOKEN
                from telegram import Bot as TelegramBot
                
                if TELEGRAM_TOKEN:
                    bot = TelegramBot(token=TELEGRAM_TOKEN)
                    
                    try:
                        await bot.send_message(
                            chat_id=request_user.telegram_id,
                            text=f"🎉 *Congratulations!*\n\n"
                                 f"Your admin request has been *approved*!\n\n"
                                 f"You now have access to the admin panel. "
                                 f"Use /menu to access admin features.",
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}", exc_info=True)
                
                await query.edit_message_text(
                    f"✅ *Request Approved!*\n\n"
                    f"User {request_user.first_name} is now an admin.",
                    parse_mode='Markdown'
                )
                
            elif action == "reject":
                # Ask for rejection reason
                context.user_data['rejecting_request_id'] = request_id
                context.user_data['rejecting_user_id'] = request_user.id
                
                await query.edit_message_text(
                    f"📝 *Reject Admin Request*\n\n"
                    f"Please provide a reason for rejecting {request_user.first_name}'s request:\n\n"
                    f"Send your reason now (max 500 characters).",
                    parse_mode='Markdown'
                )
                
            elif action == "more_info":
                # Ask for more information
                context.user_data['requesting_info_request_id'] = request_id
                context.user_data['requesting_info_user_id'] = request_user.id
                
                await query.edit_message_text(
                    f"💬 *Request More Information*\n\n"
                    f"What additional information do you need from {request_user.first_name}?\n\n"
                    f"Send your question now (will be forwarded to the user).",
                    parse_mode='Markdown'
                )
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_request_decision: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error processing request.")

async def handle_rejection_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle rejection reason input"""
    try:
        if not update.message or not update.message.text:
            return
        
        request_id = context.user_data.get('rejecting_request_id')
        user_id = context.user_data.get('rejecting_user_id')
        
        if not request_id or not user_id:
            return
        
        reason = update.message.text[:500]
        
        db = create_session()
        try:
            telegram_id = update.effective_user.id
            admin = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not admin:
                return
            
            # Update request
            admin_request = db.query(AdminRequest).filter(AdminRequest.id == request_id).first()
            if not admin_request:
                return
            
            request_user = db.query(User).filter(User.id == user_id).first()
            
            admin_request.status = AdminRequestStatus.REJECTED
            admin_request.reviewed_by = admin.id
            admin_request.reviewed_at = func.now()
            admin_request.notes = f"Rejected: {reason}"
            
            db.commit()
            
            # Notify user
            from config import TELEGRAM_TOKEN
            from telegram import Bot as TelegramBot
            
            if TELEGRAM_TOKEN:
                bot = TelegramBot(token=TELEGRAM_TOKEN)
                
                try:
                    await bot.send_message(
                        chat_id=request_user.telegram_id,
                        text=f"📝 *Admin Request Update*\n\n"
                             f"Your admin request has been *rejected*.\n\n"
                             f"*Reason:* {reason}\n\n"
                             f"You can submit a new request with better justification.",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}", exc_info=True)
            
            await update.message.reply_text(
                f"❌ *Request Rejected!*\n\n"
                f"User {request_user.first_name} has been notified.",
                parse_mode='Markdown'
            )
            
            # Clear context
            context.user_data.pop('rejecting_request_id', None)
            context.user_data.pop('rejecting_user_id', None)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_rejection_reason: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing rejection.")

async def handle_more_info_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle request for more information"""
    try:
        if not update.message or not update.message.text:
            return
        
        request_id = context.user_data.get('requesting_info_request_id')
        user_id = context.user_data.get('requesting_info_user_id')
        
        if not request_id or not user_id:
            return
        
        question = update.message.text[:500]
        
        db = create_session()
        try:
            telegram_id = update.effective_user.id
            admin = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
            if not admin:
                return
            
            request_user = db.query(User).filter(User.id == user_id).first()
            
            # Send question to user
            from config import TELEGRAM_TOKEN
            from telegram import Bot as TelegramBot
            
            if TELEGRAM_TOKEN:
                bot = TelegramBot(token=TELEGRAM_TOKEN)
                
                try:
                    await bot.send_message(
                        chat_id=request_user.telegram_id,
                        text=f"❓ *Additional Information Requested*\n\n"
                             f"An admin needs more information about your admin request:\n\n"
                             f"*Question:* {question}\n\n"
                             f"Please reply to this message with your answer.",
                        parse_mode='Markdown'
                    )
                    
                    # Store question in context for user's response
                    context.user_data[f'awaiting_answer_{user_id}'] = {
                        'admin_id': admin.id,
                        'question': question,
                        'request_id': request_id
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to send question to user: {e}", exc_info=True)
            
            await update.message.reply_text(
                f"✅ *Question Sent!*\n\n"
                f"Your question has been sent to {request_user.first_name}.",
                parse_mode='Markdown'
            )
            
            # Clear context
            context.user_data.pop('requesting_info_request_id', None)
            context.user_data.pop('requesting_info_user_id', None)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_more_info_request: {e}", exc_info=True)
        await update.message.reply_text("❌ Error sending question.")