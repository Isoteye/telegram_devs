"""
Developer Handlers for Software Marketplace
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, CommandHandler
from database.db import create_session
from database.models import User, Developer, DeveloperStatus, Order, OrderStatus, CustomRequest, RequestStatus, Bot
from config import DEVELOPER_APPLICATION
import logging
from datetime import datetime, timedelta
import re

logger = logging.getLogger(__name__)

# Developer application states
DEV_APP_SKILLS = 1
DEV_APP_PORTFOLIO = 2
DEV_APP_GITHUB = 3
DEV_APP_HOURLY_RATE = 4

async def developer_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer dashboard - Professional version"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message_method = query.edit_message_text
        else:
            message_method = update.message.reply_text
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get user and developer profile
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                if update.callback_query:
                    await query.edit_message_text(
                        "❌ You are not registered as a developer.\n\n"
                        "Use /menu → Become Developer to apply."
                    )
                else:
                    await update.message.reply_text(
                        "❌ You are not registered as a developer.\n\n"
                        "Use /menu → Become Developer to apply."
                    )
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                if update.callback_query:
                    await query.edit_message_text("❌ Developer profile not found. Please contact support.")
                else:
                    await update.message.reply_text("❌ Developer profile not found. Please contact support.")
                return
            
            # Get developer statistics
            assigned_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).count()
            
            completed_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status == OrderStatus.COMPLETED
            ).count()
            
            pending_custom_requests = db.query(CustomRequest).filter(
                CustomRequest.assigned_to == developer.id,
                CustomRequest.status == RequestStatus.APPROVED
            ).count()
            
            # Get available orders (orders that are approved but not assigned)
            available_orders = db.query(Order).filter(
                Order.status == OrderStatus.APPROVED,
                Order.assigned_developer_id == None
            ).count()
            
            # Get recent assigned orders
            recent_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id
            ).order_by(Order.created_at.desc()).limit(5).all()
            
            status_emoji = "🟢" if developer.status == DeveloperStatus.ACTIVE else \
                         "🟡" if developer.status == DeveloperStatus.BUSY else "🔴"
            
            availability = "✅ Available" if developer.is_available else "⏳ Busy"
            
            text = f"""
👨‍💻 **DEVELOPER DASHBOARD** 👨‍💻

**Developer ID:** `{developer.developer_id}`
**Status:** {status_emoji} {developer.status.value.title()}
**Availability:** {availability}

📊 **STATISTICS:**
━━━━━━━━━━━━━━━━━━━━
✅ Completed Orders: **{completed_orders}**
📦 Assigned Orders: **{assigned_orders}**
📝 Custom Projects: **{pending_custom_requests}**
🎯 Available Orders: **{available_orders}**
💰 Total Earnings: **${developer.earnings:.2f}**
⭐ Average Rating: **{developer.rating:.1f}/5.0**
⏱️ Hourly Rate: **${developer.hourly_rate:.2f}**

🚀 **QUICK ACTIONS:**
━━━━━━━━━━━━━━━━━━━━
"""
            
            keyboard = [
                [InlineKeyboardButton("🎯 View Available Orders", callback_data="dev_available_orders")],
                [InlineKeyboardButton("📦 My Assigned Orders", callback_data="dev_assigned_orders")],
                [InlineKeyboardButton("✅ My Completed Orders", callback_data="dev_completed_orders")],
                [InlineKeyboardButton("⚙️ Custom Projects", callback_data="dev_custom_projects")],
                [InlineKeyboardButton("💰 Earnings & Payout", callback_data="dev_earnings")],
                [InlineKeyboardButton("⚙️ Profile Settings", callback_data="dev_profile_settings")]
            ]
            
            # Add toggle availability button
            if developer.is_available:
                keyboard.append([InlineKeyboardButton("⏳ Set as Busy", callback_data="dev_set_busy")])
            else:
                keyboard.append([InlineKeyboardButton("✅ Set as Available", callback_data="dev_set_available")])
            
            keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error in developer_dashboard: {e}", exc_info=True)
            error_text = "❌ Error loading developer dashboard. Please try again."
            if update.callback_query:
                await query.edit_message_text(error_text)
            else:
                await update.message.reply_text(error_text)
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Outer error in developer_dashboard: {e}", exc_info=True)

async def dev_available_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available orders for developers"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Check if user is developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            # Get available orders (approved but not assigned)
            available_orders = db.query(Order).filter(
                Order.status == OrderStatus.APPROVED,
                Order.assigned_developer_id == None
            ).order_by(Order.created_at.desc()).limit(20).all()
            
            if not available_orders:
                text = """
🎯 **AVAILABLE ORDERS**

No available orders at the moment.

Check back later or update your availability to get notified when new orders come in.
"""
                
                keyboard = [
                    [InlineKeyboardButton("🔄 Refresh", callback_data="dev_available_orders")],
                    [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard")]
                ]
                
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
                return
            
            text = f"""
🎯 **AVAILABLE ORDERS**

Found **{len(available_orders)}** available orders:

━━━━━━━━━━━━━━━━━━━━
"""
            
            for order in available_orders:
                # Get bot details
                bot_name = "Custom Software"
                if order.bot:
                    bot_name = order.bot.name
                
                # Format amount
                amount = order.amount if order.amount else 0.0
                
                # Truncate if too long
                display_name = bot_name[:30] + "..." if len(bot_name) > 30 else bot_name
                
                text += f"""
📦 **{order.order_id[:12]}...**
   🚀 {display_name}
   💰 ${amount:.2f}
   📅 {order.created_at.strftime('%Y-%m-%d')}
   🔗 /claim_{order.order_id}

"""
            
            text += """
━━━━━━━━━━━━━━━━━━━━

**To claim an order:**
Use `/claim ORDER_ID` command
Example: `/claim ORD20240116123456`
"""
            
            # Create keyboard with available orders
            keyboard = []
            for order in available_orders[:10]:
                bot_name = order.bot.name if order.bot else "Custom Software"
                button_text = f"📦 {order.order_id[:8]}... - ${order.amount:.2f}"
                if len(button_text) > 40:
                    button_text = button_text[:37] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"dev_view_order_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh", callback_data="dev_available_orders"),
                InlineKeyboardButton("⬅️ Dashboard", callback_data="dev_dashboard")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_available_orders: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading available orders.")

async def dev_assigned_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show developer's assigned orders"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            # Get assigned orders
            assigned_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).order_by(Order.created_at.desc()).all()
            
            text = f"""
📦 **MY ASSIGNED ORDERS**

Total assigned orders: **{len(assigned_orders)}**

━━━━━━━━━━━━━━━━━━━━
"""
            
            if not assigned_orders:
                text += "\nNo assigned orders at the moment.\n\nCheck available orders to claim new projects."
            else:
                for order in assigned_orders:
                    bot_name = order.bot.name if order.bot else "Custom Software"
                    status_emoji = "👷" if order.status == OrderStatus.ASSIGNED else "⚙️"
                    status_text = "Assigned" if order.status == OrderStatus.ASSIGNED else "In Progress"
                    
                    # Calculate days since assignment
                    days_ago = (datetime.now() - order.created_at).days
                    
                    text += f"""
{status_emoji} **{order.order_id[:12]}...**
   🚀 {bot_name[:25]}...
   💰 ${order.amount:.2f}
   📊 {status_text}
   📅 {days_ago} day{'s' if days_ago != 1 else ''} ago
   🔗 /order_{order.order_id}

"""
            
            keyboard = []
            for order in assigned_orders[:5]:
                status_emoji = "👷" if order.status == OrderStatus.ASSIGNED else "⚙️"
                button_text = f"{status_emoji} {order.order_id[:8]}... - ${order.amount:.2f}"
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"dev_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🎯 Available Orders", callback_data="dev_available_orders"),
                InlineKeyboardButton("✅ Mark as Completed", callback_data="dev_mark_completed_menu")
            ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh", callback_data="dev_assigned_orders"),
                InlineKeyboardButton("⬅️ Dashboard", callback_data="dev_dashboard")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_assigned_orders: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading assigned orders.")

async def dev_completed_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show developer's completed orders"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            # Get completed orders
            completed_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status == OrderStatus.COMPLETED
            ).order_by(Order.delivered_at.desc()).all()
            
            text = f"""
✅ **MY COMPLETED ORDERS**

Total completed orders: **{len(completed_orders)}**
Total earnings: **${developer.earnings:.2f}**

━━━━━━━━━━━━━━━━━━━━
"""
            
            if not completed_orders:
                text += "\nNo completed orders yet.\n\nComplete your first order to see it here!"
            else:
                for order in completed_orders[:10]:
                    bot_name = order.bot.name if order.bot else "Custom Software"
                    
                    # Format delivery date
                    delivered_date = order.delivered_at.strftime('%Y-%m-%d') if order.delivered_at else "N/A"
                    
                    # Developer earnings (70% of order amount)
                    dev_earning = order.amount * 0.7
                    
                    text += f"""
✅ **{order.order_id[:12]}...**
   🚀 {bot_name[:25]}...
   💰 ${order.amount:.2f} (You earned: ${dev_earning:.2f})
   📅 Delivered: {delivered_date}
   🔗 /order_{order.order_id}

"""
            
            keyboard = []
            for order in completed_orders[:5]:
                button_text = f"✅ {order.order_id[:8]}... - ${order.amount:.2f}"
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"dev_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("📦 Assigned Orders", callback_data="dev_assigned_orders"),
                InlineKeyboardButton("💰 Request Payout", callback_data="dev_request_payout")
            ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh", callback_data="dev_completed_orders"),
                InlineKeyboardButton("⬅️ Dashboard", callback_data="dev_dashboard")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_completed_orders: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading completed orders.")

async def dev_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show developer earnings"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            # Get recent earnings (last 30 days)
            thirty_days_ago = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=30)
            
            recent_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status == OrderStatus.COMPLETED,
                Order.delivered_at >= thirty_days_ago
            ).all()
            
            recent_earnings = sum(order.amount * 0.7 for order in recent_orders)
            
            # Calculate payout eligibility
            from config import DEVELOPER_PAYOUT_THRESHOLD
            eligible_for_payout = developer.earnings >= DEVELOPER_PAYOUT_THRESHOLD
            
            text = f"""
💰 **EARNINGS & PAYOUTS**

**Total Earnings:** ${developer.earnings:.2f}
**Recent Earnings (30 days):** ${recent_earnings:.2f}
**Completed Orders:** {developer.completed_orders}
**Hourly Rate:** ${developer.hourly_rate:.2f}

**Payout Information:**
━━━━━━━━━━━━━━━━━━━━
"""
            
            if eligible_for_payout:
                text += f"""
✅ **You are eligible for payout!**
💰 Available for payout: ${developer.earnings:.2f}
📋 Minimum payout: ${DEVELOPER_PAYOUT_THRESHOLD:.2f}

**To request a payout:**
1. Ensure you have at least ${DEVELOPER_PAYOUT_THRESHOLD:.2f}
2. Click "Request Payout" below
3. Provide your payment details
4. Payout processed within 3-5 business days
"""
            else:
                needed = DEVELOPER_PAYOUT_THRESHOLD - developer.earnings
                text += f"""
⏳ **Working towards payout...**
💰 Current balance: ${developer.earnings:.2f}
🎯 Minimum required: ${DEVELOPER_PAYOUT_THRESHOLD:.2f}
📈 Need ${needed:.2f} more to qualify

**Complete more orders to reach the payout threshold!**
"""
            
            keyboard = []
            
            if eligible_for_payout:
                keyboard.append([
                    InlineKeyboardButton("💰 Request Payout", callback_data="dev_request_payout")
                ])
            
            keyboard.append([
                InlineKeyboardButton("📦 Completed Orders", callback_data="dev_completed_orders"),
                InlineKeyboardButton("📊 View Transaction History", callback_data="dev_transaction_history")
            ])
            
            keyboard.append([
                InlineKeyboardButton("🔄 Refresh", callback_data="dev_earnings"),
                InlineKeyboardButton("⬅️ Dashboard", callback_data="dev_dashboard")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_earnings: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading earnings information.")

async def dev_profile_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer profile settings"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            status_emoji = "🟢" if developer.status == DeveloperStatus.ACTIVE else \
                         "🟡" if developer.status == DeveloperStatus.BUSY else "🔴"
            
            availability = "✅ Available" if developer.is_available else "⏳ Busy"
            
            text = f"""
⚙️ **DEVELOPER PROFILE SETTINGS**

**Basic Information:**
👤 Name: {user.first_name} {user.last_name or ''}
📱 Username: @{user.username or 'N/A'}
🆔 Developer ID: `{developer.developer_id}`

**Profile Settings:**
{status_emoji} Status: {developer.status.value.title()}
{availability}
⏱️ Hourly Rate: ${developer.hourly_rate:.2f}
⭐ Rating: {developer.rating:.1f}/5.0

**Profile Details:**
📝 Skills: {developer.skills_experience[:100] if developer.skills_experience else 'Not set'}
🔗 Portfolio: {developer.portfolio_url or 'Not set'}
💻 GitHub: {developer.github_url or 'Not set'}

**Update your profile to attract more clients!**
"""
            
            keyboard = [
                [InlineKeyboardButton("📝 Update Skills", callback_data="dev_update_skills")],
                [InlineKeyboardButton("🔗 Update Portfolio", callback_data="dev_update_portfolio")],
                [InlineKeyboardButton("💻 Update GitHub", callback_data="dev_update_github")],
                [InlineKeyboardButton("⏱️ Update Hourly Rate", callback_data="dev_update_rate")],
                [
                    InlineKeyboardButton("✅ Set Available", callback_data="dev_set_available"),
                    InlineKeyboardButton("⏳ Set Busy", callback_data="dev_set_busy")
                ],
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="dev_profile_settings"),
                    InlineKeyboardButton("⬅️ Dashboard", callback_data="dev_dashboard")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_profile_settings: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading profile settings.")

async def dev_set_available(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set developer as available"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            # Update status
            developer.status = DeveloperStatus.ACTIVE
            developer.is_available = True
            db.commit()
            
            await query.edit_message_text(
                "✅ **You are now available!**\n\n"
                "You will be notified when new orders are available.\n"
                "Make sure to check the available orders section regularly.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎯 Check Available Orders", callback_data="dev_available_orders")],
                    [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error setting available: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error updating availability.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_set_available: {e}", exc_info=True)

async def dev_set_busy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set developer as busy"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            # Update status
            developer.status = DeveloperStatus.BUSY
            developer.is_available = False
            db.commit()
            
            await query.edit_message_text(
                "⏳ **You are now marked as busy!**\n\n"
                "You won't be notified about new orders until you set yourself as available again.\n"
                "Focus on your current projects and update when ready.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 My Assigned Orders", callback_data="dev_assigned_orders")],
                    [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error setting busy: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error updating status.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_set_busy: {e}", exc_info=True)

async def dev_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order details for developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_order_detail_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get order
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            # Check if developer owns this order
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
                
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer or order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ You don't have permission to view this order.")
                return
            
            # Get customer info
            customer = db.query(User).filter(User.id == order.user_id).first()
            bot = db.query(Bot).filter(Bot.id == order.bot_id).first() if order.bot_id else None
            
            status_emoji = "⏳" if order.status == OrderStatus.PENDING_REVIEW else \
                         "✅" if order.status == OrderStatus.COMPLETED else \
                         "👷" if order.status == OrderStatus.ASSIGNED else \
                         "⚙️" if order.status == OrderStatus.IN_PROGRESS else \
                         "👍" if order.status == OrderStatus.APPROVED else "📦"
            
            text = f"""
📋 **ORDER DETAILS**

**Order ID:** `{order.order_id}`
**Status:** {status_emoji} {order.status.value.replace('_', ' ').title()}
**Amount:** ${order.amount:.2f}
**Your Earnings:** ${order.amount * 0.7:.2f}
**Created:** {order.created_at.strftime('%Y-%m-%d %H:%M')}

**Customer Information:**
👤 Name: {customer.first_name}
📱 Username: @{customer.username or 'N/A'}
🆔 Telegram ID: {customer.telegram_id}
"""
            
            if bot:
                text += f"""
**Software Details:**
🚀 Name: {bot.name}
💰 Price: ${bot.price:.2f}
📦 Delivery: {bot.delivery_time}
"""
            
            if order.developer_notes:
                text += f"\n**Developer Notes:**\n{order.developer_notes}"
            
            if order.admin_notes:
                text += f"\n**Admin Notes:**\n{order.admin_notes}"
            
            # Action buttons based on status
            keyboard = []
            
            if order.status == OrderStatus.ASSIGNED:
                keyboard.append([
                    InlineKeyboardButton("⚙️ Start Development", callback_data=f"dev_start_development_{order.id}")
                ])
            
            if order.status == OrderStatus.IN_PROGRESS:
                keyboard.append([
                    InlineKeyboardButton("✅ Mark as Completed", callback_data=f"dev_complete_order_{order.id}"),
                    InlineKeyboardButton("📝 Add Notes", callback_data=f"dev_add_notes_{order.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("📞 Contact Customer", callback_data=f"dev_contact_customer_{order.user_id}"),
                InlineKeyboardButton("🔄 Update Progress", callback_data=f"dev_update_progress_{order.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Orders", callback_data="dev_assigned_orders"),
                InlineKeyboardButton("🏠 Dashboard", callback_data="dev_dashboard")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_order_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading order details.")

async def dev_start_development(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark order as in progress"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_start_development_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get order
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            # Check if developer owns this order
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            
            if not developer or order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ You don't have permission to update this order.")
                return
            
            if order.status != OrderStatus.ASSIGNED:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, not 'assigned'.")
                return
            
            # Update order status
            order.status = OrderStatus.IN_PROGRESS
            order.developer_notes = f"Development started by developer on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            db.commit()
            
            # Notify customer
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                customer = db.query(User).filter(User.id == order.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=customer.telegram_id,
                        text=f"""
⚙️ **Development Started!**

Your order is now in progress:

📦 Order ID: `{order.order_id}`
👨‍💻 Developer: {user.first_name}
📊 Status: ⚙️ In Progress

The developer has started working on your order.
You'll receive updates on the progress.

Thank you for your patience! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer: {e}")
            
            await query.edit_message_text(
                "⚙️ **Development Started!**\n\n"
                "Order status updated to 'In Progress'.\n"
                "The customer has been notified.\n\n"
                "Remember to:\n"
                "1. Update progress regularly\n"
                "2. Communicate with the customer\n"
                "3. Mark as completed when done",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Order", callback_data=f"dev_order_detail_{order.id}")],
                    [InlineKeyboardButton("📦 My Orders", callback_data="dev_assigned_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error starting development: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error updating order status.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_start_development: {e}", exc_info=True)

async def dev_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark order as completed"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_complete_order_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get order
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            # Check if developer owns this order
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            
            if not developer or order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ You don't have permission to complete this order.")
                return
            
            if order.status != OrderStatus.IN_PROGRESS:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, not 'in_progress'.")
                return
            
            # Ask for confirmation
            context.user_data['completing_order'] = order_id
            
            await query.edit_message_text(
                "✅ **Complete Order**\n\n"
                "Are you sure you want to mark this order as completed?\n\n"
                "**Before completing, ensure:**\n"
                "1. All features are implemented\n"
                "2. Software is tested and working\n"
                "3. Customer has reviewed the work\n"
                "4. All files are delivered\n\n"
                "This action will notify the customer and admin.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Yes, Complete", callback_data=f"dev_confirm_complete_{order.id}"),
                        InlineKeyboardButton("❌ Cancel", callback_data=f"dev_order_detail_{order.id}")
                    ]
                ])
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_complete_order: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing completion.")

async def dev_confirm_complete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm order completion"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_confirm_complete_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            # Get order
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            # Check if developer owns this order
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            
            if not developer or order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ You don't have permission to complete this order.")
                return
            
            # Update order status
            order.status = OrderStatus.COMPLETED
            order.delivered_at = datetime.now()
            
            # Update developer stats
            developer.completed_orders += 1
            developer.earnings += order.amount * 0.7  # Developer gets 70%
            developer.status = DeveloperStatus.ACTIVE
            developer.is_available = True
            
            db.commit()
            
            # Clear context
            context.user_data.pop('completing_order', None)
            
            # Notify customer
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                customer = db.query(User).filter(User.id == order.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=customer.telegram_id,
                        text=f"""
🎉 **Order Completed!**

Your order has been marked as completed by the developer:

📦 Order ID: `{order.order_id}`
👨‍💻 Developer: {user.first_name}
✅ Status: ✅ Completed
📅 Delivered: {datetime.now().strftime('%Y-%m-%d %H:%M')}

**Please review the delivered work and provide feedback.**

Thank you for choosing Software Marketplace! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer: {e}")
            
            # Notify admin
            from config import SUPER_ADMIN_ID
            if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
                try:
                    await bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"""
✅ Order Completed by Developer

📦 Order ID: {order.order_id}
👨‍💻 Developer: {user.first_name} (@{user.username or 'N/A'})
👤 Customer: {customer.first_name} (@{customer.username or 'N/A'})
💰 Amount: ${order.amount:.2f}
💸 Developer Earnings: ${order.amount * 0.7:.2f}

Order completed successfully.
                        """
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")
            
            await query.edit_message_text(
                "🎉 **Order Completed Successfully!**\n\n"
                f"**Order ID:** `{order.order_id}`\n"
                f"**Amount:** ${order.amount:.2f}\n"
                f"**Your Earnings:** ${order.amount * 0.7:.2f}\n\n"
                "✅ Customer notified\n"
                "✅ Admin notified\n"
                "✅ Developer stats updated\n\n"
                "Thank you for your great work! 👨‍💻",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 View Earnings", callback_data="dev_earnings")],
                    [InlineKeyboardButton("📦 Completed Orders", callback_data="dev_completed_orders")],
                    [InlineKeyboardButton("🏠 Dashboard", callback_data="dev_dashboard")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error completing order: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error completing order.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_confirm_complete: {e}", exc_info=True)

# ========== DEVELOPER APPLICATION HANDLERS ==========

async def start_developer_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start developer application process"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
            if not user:
                await query.edit_message_text("❌ Please use /start first to create your account.")
                return
            
            # Check if already a developer
            if user.is_developer:
                await query.edit_message_text(
                    "🎉 You're already a developer!\n\n"
                    "Use /developer to access your dashboard."
                )
                return
            
            # Check for pending request
            from database.models import DeveloperRequest, RequestStatus
            pending_request = db.query(DeveloperRequest).filter(
                DeveloperRequest.user_id == user.id,
                DeveloperRequest.status == RequestStatus.NEW
            ).first()
            
            if pending_request:
                await query.edit_message_text(
                    "📝 Your developer application is pending review.\n\n"
                    "Our admin team will review your application soon.\n"
                    "You'll be notified once a decision is made.\n\n"
                    "Average review time: 24-48 hours ⏰",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            # Start application process
            text = """
👨‍💻 **BECOME A DEVELOPER**

Let's start your developer application!

**Step 1/4: Skills & Experience**

Please describe your skills and experience in software development:

**Include:**
• Programming languages you know (Python, JavaScript, etc.)
• Frameworks and technologies
• Previous projects or portfolio
• Years of experience
• Areas of specialization

**Minimum 50 characters required.**
"""
            
            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="menu_main")]
                ]),
                parse_mode='Markdown'
            )
            
            return DEV_APP_SKILLS
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in start_developer_application: {e}", exc_info=True)
        return ConversationHandler.END

async def receive_developer_skills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive developer skills"""
    try:
        if not update.message:
            return DEV_APP_SKILLS
        
        skills = update.message.text.strip()
        
        # Validate minimum length
        from config import DEVELOPER_APPLICATION
        if len(skills) < DEVELOPER_APPLICATION['min_skills_length']:
            await update.message.reply_text(
                f"❌ Please provide more details.\n\n"
                f"Your response is {len(skills)} characters, "
                f"minimum {DEVELOPER_APPLICATION['min_skills_length']} characters required.\n\n"
                f"Please describe your skills and experience in more detail:"
            )
            return DEV_APP_SKILLS
        
        context.user_data['dev_application'] = {
            'skills_experience': skills
        }
        
        await update.message.reply_text(
            "✅ **Skills saved!**\n\n"
            "**Step 2/4: Portfolio URL**\n\n"
            "Please provide a link to your portfolio or previous work (optional):\n\n"
            "Examples:\n"
            "• Personal website\n"
            "• Behance/Dribbble profile\n"
            "• Previous project links\n"
            "• LinkedIn profile\n\n"
            "If you don't have a portfolio, type 'skip'",
            parse_mode='Markdown'
        )
        
        return DEV_APP_PORTFOLIO
        
    except Exception as e:
        logger.error(f"Error in receive_developer_skills: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing your skills. Please try again.")
        return ConversationHandler.END

async def receive_portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive portfolio URL"""
    try:
        if not update.message:
            return DEV_APP_PORTFOLIO
        
        portfolio = update.message.text.strip()
        
        # Validate URL if provided
        if portfolio.lower() != 'skip' and portfolio:
            # Simple URL validation
            if not (portfolio.startswith('http://') or portfolio.startswith('https://')):
                portfolio = 'https://' + portfolio
        
        context.user_data['dev_application']['portfolio_url'] = portfolio if portfolio.lower() != 'skip' else None
        
        await update.message.reply_text(
            "✅ **Portfolio saved!**\n\n"
            "**Step 3/4: GitHub Profile**\n\n"
            "Please provide your GitHub profile URL (optional):\n\n"
            "Examples:\n"
            "• https://github.com/yourusername\n"
            "• GitLab/Bitbucket profile\n\n"
            "If you don't have a GitHub profile, type 'skip'",
            parse_mode='Markdown'
        )
        
        return DEV_APP_GITHUB
        
    except Exception as e:
        logger.error(f"Error in receive_portfolio: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing portfolio. Please try again.")
        return ConversationHandler.END

async def receive_github(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive GitHub URL"""
    try:
        if not update.message:
            return DEV_APP_GITHUB
        
        github = update.message.text.strip()
        
        # Validate URL if provided
        if github.lower() != 'skip' and github:
            # Simple URL validation
            if not (github.startswith('http://') or github.startswith('https://')):
                github = 'https://' + github
        
        context.user_data['dev_application']['github_url'] = github if github.lower() != 'skip' else None
        
        await update.message.reply_text(
            "✅ **GitHub saved!**\n\n"
            "**Step 4/4: Hourly Rate**\n\n"
            "What is your expected hourly rate? (in USD)\n\n"
            "Examples:\n"
            "• 25 (for $25/hour)\n"
            "• 50.50 (for $50.50/hour)\n\n"
            f"Default rate: ${DEVELOPER_APPLICATION['default_hourly_rate']:.2f}/hour\n"
            "Type a number or 'default' to use default rate:",
            parse_mode='Markdown'
        )
        
        return DEV_APP_HOURLY_RATE
        
    except Exception as e:
        logger.error(f"Error in receive_github: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing GitHub URL. Please try again.")
        return ConversationHandler.END

async def receive_hourly_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Receive hourly rate and submit application"""
    try:
        if not update.message:
            return DEV_APP_HOURLY_RATE
        
        rate_input = update.message.text.strip()
        
        # Parse hourly rate
        try:
            if rate_input.lower() == 'default':
                hourly_rate = DEVELOPER_APPLICATION['default_hourly_rate']
            else:
                hourly_rate = float(rate_input)
                if hourly_rate < 5:
                    await update.message.reply_text("❌ Hourly rate must be at least $5. Please enter a valid rate:")
                    return DEV_APP_HOURLY_RATE
                if hourly_rate > 500:
                    await update.message.reply_text("❌ Hourly rate cannot exceed $500. Please enter a valid rate:")
                    return DEV_APP_HOURLY_RATE
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number for hourly rate (e.g., 25 or 25.50):")
            return DEV_APP_HOURLY_RATE
        
        context.user_data['dev_application']['hourly_rate'] = hourly_rate
        
        # Save application to database
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
            if not user:
                await update.message.reply_text("❌ User not found. Please use /start first.")
                return ConversationHandler.END
            
            from database.models import DeveloperRequest, RequestStatus
            
            # Create developer request
            dev_request = DeveloperRequest(
                user_id=user.id,
                skills_experience=context.user_data['dev_application']['skills_experience'],
                portfolio_url=context.user_data['dev_application'].get('portfolio_url'),
                github_url=context.user_data['dev_application'].get('github_url'),
                hourly_rate=hourly_rate,
                status=RequestStatus.NEW
            )
            
            db.add(dev_request)
            db.commit()
            
            # Clear context
            context.user_data.pop('dev_application', None)
            
            # Notify admin
            from telegram import Bot
            from config import TELEGRAM_TOKEN, SUPER_ADMIN_ID
            
            if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
                bot = Bot(token=TELEGRAM_TOKEN)
                
                try:
                    await bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"""
📝 **New Developer Application**

👤 Applicant: {user.first_name} (@{user.username or 'N/A'})
🆔 Telegram ID: {user.telegram_id}
⏱️ Hourly Rate: ${hourly_rate:.2f}

**Skills Summary:**
{context.user_data['dev_application']['skills_experience'][:200]}...

**To review:**
Go to Admin Panel → Developer Applications
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")
            
            await update.message.reply_text(
                f"""
🎉 **Developer Application Submitted!**

✅ Your application has been received successfully.

**Application Details:**
👤 Name: {user.first_name}
⏱️ Hourly Rate: ${hourly_rate:.2f}
📊 Status: ⏳ Pending Review

**What happens next?**
1. Our admin team will review your application
2. You'll be notified within 24-48 hours
3. If approved, you'll receive your Developer ID
4. Start accepting orders and earning money

**Check your application status anytime in Main Menu → My Developer Application**

Thank you for applying! 👨‍💻
                """,
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
                    [InlineKeyboardButton("📋 My Application Status", callback_data="dev_application_status")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error saving developer application: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error submitting application. Please try again.")
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in receive_hourly_rate: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing application. Please try again.")
        return ConversationHandler.END

async def dev_application_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check developer application status"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message_method = query.edit_message_text
        else:
            message_method = update.message.reply_text
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                if update.callback_query:
                    await query.edit_message_text("❌ Please use /start first to create your account.")
                else:
                    await update.message.reply_text("❌ Please use /start first to create your account.")
                return
            
            from database.models import DeveloperRequest, RequestStatus, Developer
            
            # Check if already a developer
            if user.is_developer:
                developer = db.query(Developer).filter(Developer.user_id == user.id).first()
                if developer:
                    text = f"""
🎉 **You're Already a Developer!**

✅ **Developer ID:** `{developer.developer_id}`
📊 **Status:** {developer.status.value.title()}
💰 **Earnings:** ${developer.earnings:.2f}
✅ **Completed Orders:** {developer.completed_orders}

**Access your developer dashboard to start earning!**
"""
                    
                    keyboard = [
                        [InlineKeyboardButton("👨‍💻 Developer Dashboard", callback_data="dev_dashboard")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ]
                    
                    if update.callback_query:
                        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                    else:
                        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                    return
            
            # Check for application
            dev_request = db.query(DeveloperRequest).filter(
                DeveloperRequest.user_id == user.id
            ).order_by(DeveloperRequest.created_at.desc()).first()
            
            if not dev_request:
                text = """
📝 **No Developer Application Found**

You haven't submitted a developer application yet.

**To become a developer:**
1. Click "Apply Now" below
2. Fill out the application form
3. Wait for admin approval (24-48 hours)
4. Start earning money!
"""
                
                keyboard = [
                    [InlineKeyboardButton("📝 Apply Now", callback_data="start_developer_application")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ]
                
                if update.callback_query:
                    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                else:
                    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
                return
            
            # Show application status
            status_emoji = "⏳" if dev_request.status == RequestStatus.NEW else \
                         "✅" if dev_request.status == RequestStatus.APPROVED else \
                         "❌" if dev_request.status == RequestStatus.REJECTED else \
                         "📝" if dev_request.status == RequestStatus.IN_REVIEW else "❓"
            
            status_text = dev_request.status.value.replace('_', ' ').title()
            
            # Calculate days since application
            days_since = (datetime.now() - dev_request.created_at).days
            
            text = f"""
📋 **DEVELOPER APPLICATION STATUS**

{status_emoji} **Status:** {status_text}
📅 **Applied:** {dev_request.created_at.strftime('%Y-%m-%d')}
⏰ **Days since application:** {days_since} day{'s' if days_since != 1 else ''}
⏱️ **Requested Hourly Rate:** ${dev_request.hourly_rate:.2f}
"""
            
            if dev_request.status == RequestStatus.NEW:
                text += "\n⏳ **Your application is pending review.**\nAverage review time: 24-48 hours"
            
            elif dev_request.status == RequestStatus.IN_REVIEW:
                text += "\n📝 **Your application is currently under review.**\nYou'll be notified soon!"
            
            elif dev_request.status == RequestStatus.APPROVED:
                text += "\n✅ **Congratulations! Your application has been approved!**\nCheck your messages for your Developer ID."
            
            elif dev_request.status == RequestStatus.REJECTED:
                text += "\n❌ **Your application was rejected.**\n"
                if dev_request.admin_notes:
                    text += f"\n**Admin Notes:**\n{dev_request.admin_notes}\n"
                text += "\nYou can apply again after 30 days."
            
            if dev_request.reviewed_at:
                text += f"\n\n**Reviewed on:** {dev_request.reviewed_at.strftime('%Y-%m-%d %H:%M')}"
            
            keyboard = []
            
            if dev_request.status == RequestStatus.NEW:
                keyboard.append([InlineKeyboardButton("🔄 Refresh Status", callback_data="dev_application_status")])
            
            if dev_request.status == RequestStatus.REJECTED:
                keyboard.append([InlineKeyboardButton("📝 Reapply", callback_data="start_developer_application")])
            
            keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
            
            if update.callback_query:
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            else:
                await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_application_status: {e}", exc_info=True)
        if update.callback_query:
            await query.edit_message_text("❌ Error loading application status.")
        else:
            await update.message.reply_text("❌ Error loading application status.")

# In developer_handlers.py, add this function
async def developer_view_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show available custom requests for developers"""
    try:
        query = update.callback_query
        await query.answer()
        
        from database.db import create_session
        from database.models import CustomRequest, User, RequestStatus
        
        db = create_session()
        try:
            # Get approved custom requests with deposit paid
            custom_requests = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.APPROVED,
                CustomRequest.is_deposit_paid == True,
                CustomRequest.assigned_to == None  # Not assigned yet
            ).order_by(CustomRequest.created_at.desc()).all()
            
            if not custom_requests:
                text = """📋 Available Custom Requests

No custom requests available at the moment.

Check back later for new projects!"""
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Developer Dashboard", callback_data="dev_dashboard")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            text = "📋 Available Custom Requests\n\n"
            
            for req in custom_requests[:10]:
                # Get customer info
                customer = db.query(User).filter(User.id == req.user_id).first()
                customer_name = customer.first_name if customer else "Unknown"
                
                text += f"📋 {req.request_id}\n"
                text += f"  📝 {req.title[:30]}{'...' if len(req.title) > 30 else ''}\n"
                text += f"  👤 Customer: {customer_name}\n"
                text += f"  💰 Price: ${req.estimated_price:.2f}\n"
                text += f"  📊 Deposit Paid: ${req.deposit_paid:.2f} ✅\n"
                text += f"  ⏱️ Delivery: {req.delivery_time}\n\n"
            
            # Create buttons for each request
            keyboard = []
            for req in custom_requests[:5]:
                button_text = f"📋 {req.request_id[:8]}... - ${req.estimated_price:.2f}"
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"view_custom_request_{req.request_id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Developer Dashboard", callback_data="dev_dashboard"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in developer_view_requests: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading requests.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in developer_view_requests: {e}", exc_info=True)

async def developer_view_custom_request_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show custom request details for developers"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = query.data.replace('view_custom_request_', '')
        
        from database.db import create_session
        from database.models import CustomRequest, User
        
        db = create_session()
        try:
            custom_request = db.query(CustomRequest).filter(
                CustomRequest.request_id == request_id
            ).first()
            
            if not custom_request:
                await query.edit_message_text("❌ Request not found.")
                return
            
            customer = db.query(User).filter(User.id == custom_request.user_id).first()
            
            text = f"""📋 Custom Request Details

Request ID: {request_id}
Customer: {customer.first_name if customer else 'Unknown'}
Title: {custom_request.title}
Total Price: ${custom_request.estimated_price:.2f}
Deposit Paid: ${custom_request.deposit_paid:.2f} ✅
Delivery Time: {custom_request.delivery_time}
Timeline: {custom_request.timeline}

Description:
{custom_request.description[:1000]}...

Features:
{custom_request.features[:1000]}...

Budget Tier: {custom_request.budget_tier.title()}

⚠️ Note: Customer has paid 20% deposit. You'll receive payment upon completion."""
            
            keyboard = [
                [InlineKeyboardButton("✅ Claim This Request", callback_data=f"claim_request_{request_id}")],
                [
                    InlineKeyboardButton("⬅️ Available Requests", callback_data="dev_view_requests"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in developer_view_custom_request_details: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading request details.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in developer_view_custom_request_details: {e}", exc_info=True)

async def developer_claim_custom_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer claims a custom request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = query.data.replace('claim_request_', '')
        
        from database.db import create_session
        from database.models import CustomRequest, User, Developer, Order, OrderStatus
        
        db = create_session()
        try:
            # Get developer
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            # Get custom request
            custom_request = db.query(CustomRequest).filter(
                CustomRequest.request_id == request_id
            ).first()
            
            if not custom_request:
                await query.edit_message_text("❌ Request not found.")
                return
            
            # Check if already assigned
            if custom_request.assigned_to:
                await query.edit_message_text("❌ Request already assigned to another developer.")
                return
            
            # Assign to developer
            custom_request.assigned_to = developer.id
            
            # Create an order for the remaining balance
            from utils.helpers import generate_order_id
            remaining_amount = custom_request.estimated_price - custom_request.deposit_paid
            
            order = Order(
                order_id=generate_order_id(),
                user_id=custom_request.user_id,
                amount=remaining_amount,
                status=OrderStatus.ASSIGNED,
                admin_notes=f"Custom request: {request_id}. Deposit already paid: ${custom_request.deposit_paid:.2f}"
            )
            
            db.add(order)
            db.commit()
            
            # Notify customer
            customer = db.query(User).filter(User.id == custom_request.user_id).first()
            if customer:
                from telegram import Bot
                from config import TELEGRAM_TOKEN
                
                if TELEGRAM_TOKEN:
                    bot = Bot(token=TELEGRAM_TOKEN)
                    
                    message = f"""👨‍💻 Developer Assigned!

📋 Request ID: {request_id}
📝 Title: {custom_request.title}
👨‍💻 Developer: {user.first_name}
💼 Status: Development Started
💰 Remaining Balance: ${remaining_amount:.2f}

Great news! A developer has been assigned to your project.

What's next:
1. Developer will contact you shortly
2. Development will begin
3. You'll receive regular updates
4. Remaining balance due upon completion

Thank you for your patience! 🚀"""
                    
                    try:
                        await bot.send_message(
                            chat_id=customer.telegram_id,
                            text=message
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify customer: {e}")
            
            await query.edit_message_text(
                f"✅ Successfully claimed request {request_id}!\n\n"
                f"Customer has been notified. Please contact them to begin development.\n\n"
                f"💰 Remaining balance to collect: ${remaining_amount:.2f}"
            )
            
        except Exception as e:
            logger.error(f"Error in developer_claim_custom_request: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error claiming request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in developer_claim_custom_request: {e}", exc_info=True)

        
async def cancel_developer_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel developer application"""
    try:
        # Clear context
        context.user_data.pop('dev_application', None)
        
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "❌ Developer application cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        elif update.message:
            await update.message.reply_text(
                "❌ Developer application cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in cancel_developer_application: {e}", exc_info=True)
        return ConversationHandler.END

# ========== REGISTER DEVELOPER HANDLERS ==========

def register_developer_handlers(application):
    """Register all developer handlers"""
    
    # Developer dashboard callbacks
    application.add_handler(CallbackQueryHandler(developer_dashboard, pattern="^dev_dashboard$"))
    application.add_handler(CallbackQueryHandler(dev_available_orders, pattern="^dev_available_orders$"))
    application.add_handler(CallbackQueryHandler(dev_assigned_orders, pattern="^dev_assigned_orders$"))
    application.add_handler(CallbackQueryHandler(dev_completed_orders, pattern="^dev_completed_orders$"))
    application.add_handler(CallbackQueryHandler(dev_earnings, pattern="^dev_earnings$"))
    application.add_handler(CallbackQueryHandler(dev_profile_settings, pattern="^dev_profile_settings$"))
    application.add_handler(CallbackQueryHandler(dev_set_available, pattern="^dev_set_available$"))
    application.add_handler(CallbackQueryHandler(dev_set_busy, pattern="^dev_set_busy$"))
    application.add_handler(CallbackQueryHandler(dev_order_detail, pattern="^dev_order_detail_"))
    application.add_handler(CallbackQueryHandler(dev_start_development, pattern="^dev_start_development_"))
    application.add_handler(CallbackQueryHandler(dev_complete_order, pattern="^dev_complete_order_"))
    application.add_handler(CallbackQueryHandler(dev_confirm_complete, pattern="^dev_confirm_complete_"))
    
    # Developer application status
    application.add_handler(CallbackQueryHandler(dev_application_status, pattern="^dev_application_status$"))
    
    # Developer application conversation handler
    dev_application_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_developer_application, pattern="^start_developer_application$")],
        states={
            DEV_APP_SKILLS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_developer_skills)
            ],
            DEV_APP_PORTFOLIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_portfolio)
            ],
            DEV_APP_GITHUB: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_github)
            ],
            DEV_APP_HOURLY_RATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_hourly_rate)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_developer_application, pattern="^menu_main$"),
            CommandHandler("cancel", cancel_developer_application)
        ],
        allow_reentry=True
    )
    
    application.add_handler(dev_application_conv_handler)