
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from database.db import create_session
from database.models import User, Order, OrderStatus, Developer, DeveloperStatus, Bot, CustomRequest, Transaction
from database.models import DeveloperRequest, RequestStatus, PaymentMethod, PaymentStatus
import logging
from datetime import datetime, timedelta
from database.models import CustomRequest, RequestStatus, Order, OrderStatus, User
from sqlalchemy import func, desc, and_
import json
import traceback
import re

logger = logging.getLogger(__name__)

# Admin conversation states
BROADCAST_MESSAGE = 1
ADD_BOT_NAME = 20
ADD_BOT_DESCRIPTION = 21
ADD_BOT_FEATURES = 22
ADD_BOT_PRICE = 23
ADD_BOT_CATEGORY = 6
ADD_BOT_DELIVERY = 25
ADD_DEVELOPER = 8

def check_admin_access(telegram_id):
    """Check if user has admin access"""
    from config import SUPER_ADMIN_ID
    
    # First check if user is super admin
    if str(telegram_id) == str(SUPER_ADMIN_ID):
        return True
    
    db = create_session()
    try:
        user = db.query(User).filter(User.telegram_id == telegram_id, User.is_admin == True).first()
        return user is not None
    except Exception as e:
        logger.error(f"Error checking admin access: {e}")
        return False
    finally:
        db.close()

async def admin_jobs_pending_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all jobs pending admin approval"""
    try:
        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return

        db = create_session()
        try:
            from database.models import Job, User

            pending_jobs = db.query(Job).filter(
                Job.status == 'pending_approval'
            ).order_by(Job.created_at.desc()).all()

            if not pending_jobs:
                await query.edit_message_text(
                    "✅ No jobs pending approval at the moment.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Back to Job Management", callback_data="admin_job_management")]
                    ])
                )
                return

            text = "⏳ **PENDING JOBS FOR APPROVAL**\n\n"
            keyboard = []

            for job in pending_jobs[:10]:  # limit to 10 per page
                user = db.query(User).filter(User.id == job.user_id).first()
                username = f"@{user.username}" if user and user.username else f"ID: {user.telegram_id if user else 'Unknown'}"
                created = job.created_at.strftime('%Y-%m-%d') if job.created_at else 'N/A'

                text += (
                    f"🔹 **{job.title}**\n"
                    f"   📅 {created}  |  💰 ${job.budget:.2f}\n"
                    f"   👤 {username}\n"
                    f"   🆔 `{job.job_id}`\n\n"
                )

                keyboard.append([
                    InlineKeyboardButton(
                        f"📋 Review {job.job_id}",
                        callback_data=f"admin_review_job_{job.job_id}"
                    )
                ])

            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Job Management", callback_data="admin_job_management"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])

            await query.edit_message_text(
                text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Error in admin_jobs_pending_list: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading pending jobs.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in admin_jobs_pending_list: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading pending jobs.")

async def admin_jobs_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show approved (public) jobs"""
    try:
        query = update.callback_query
        await query.answer()
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return

        db = create_session()
        try:
            from database.models import Job, User
            jobs = db.query(Job).filter(Job.is_public == True).order_by(Job.created_at.desc()).limit(20).all()
            if not jobs:
                text = "✅ No approved jobs found."
            else:
                text = "✅ **APPROVED JOBS**\n\n"
                for job in jobs:
                    user = db.query(User).filter(User.id == job.user_id).first()
                    text += f"🔹 `{job.job_id}` – {job.title} (${job.budget:.2f}) – by {user.first_name if user else 'Unknown'}\n"
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_job_management")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in admin_jobs_approved: {e}")

async def admin_jobs_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active jobs (open, assigned, in_progress)"""
    try:
        query = update.callback_query
        await query.answer()
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        db = create_session()
        try:
            from database.models import Job, User
            jobs = db.query(Job).filter(Job.status.in_(['open', 'assigned', 'in_progress'])).order_by(Job.created_at.desc()).limit(20).all()
            if not jobs:
                text = "👨‍💻 No active jobs."
            else:
                text = "👨‍💻 **ACTIVE JOBS**\n\n"
                for job in jobs:
                    user = db.query(User).filter(User.id == job.user_id).first()
                    text += f"🔹 `{job.job_id}` – {job.title} ({job.status}) – ${job.budget:.2f}\n"
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_job_management")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in admin_jobs_active: {e}")

async def admin_jobs_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Job statistics"""
    try:
        query = update.callback_query
        await query.answer()
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        db = create_session()
        try:
            from database.models import Job
            from sqlalchemy import func

            total = db.query(Job).count()
            pending = db.query(Job).filter(Job.status == 'pending_approval').count()
            approved = db.query(Job).filter(Job.is_public == True).count()
            rejected = db.query(Job).filter(Job.status == 'rejected').count()
            total_budget = db.query(func.sum(Job.budget)).filter(Job.is_public == True).scalar() or 0

            text = f"""
📊 **JOB STATISTICS**

📋 Total Jobs: **{total}**
⏳ Pending Approval: **{pending}**
✅ Approved & Public: **{approved}**
❌ Rejected: **{rejected}**

💰 Total Budget of Public Jobs: **${total_budget:.2f}**
            """
            keyboard = [[InlineKeyboardButton("⬅️ Back", callback_data="admin_job_management")]]
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in admin_jobs_stats: {e}")

async def admin_jobs_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search jobs (placeholder)"""
    try:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            "🔍 **Search Jobs** – Coming soon!\n\n"
            "Use /search_job <id> or /search_job <title> in the chat.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ Back", callback_data="admin_job_management")]
            ]),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Error in admin_jobs_search: {e}")

async def admin_jobs_active(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active jobs"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "👨‍💻 *ACTIVE JOBS*\n\n*Feature coming soon!*\n\nThis section will show all active jobs being worked on."
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Job Management", callback_data="admin_job_management")],
            [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_jobs_active: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading active jobs.")

async def admin_jobs_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Job statistics"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
📊 *JOB STATISTICS*

*Feature coming soon!*

This section will show detailed statistics about jobs.
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Job Management", callback_data="admin_job_management")],
            [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_jobs_stats: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job statistics.")

async def admin_jobs_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search jobs"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
🔍 *SEARCH JOBS*

*Feature coming soon!*

This section will allow you to search for jobs by:
- Job ID
- Customer name
- Budget range
- Status
- Date range
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to Job Management", callback_data="admin_job_management")],
            [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_jobs_search: {e}", exc_info=True)
        await query.edit_message_text("❌ Error in search interface.")

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main admin panel"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message_method = query.edit_message_text
        else:
            message_method = update.message.reply_text
        
        telegram_id = update.effective_user.id
        
        if not check_admin_access(telegram_id):
            if update.callback_query:
                await query.edit_message_text("❌ Access denied.")
            else:
                await update.message.reply_text("❌ Access denied.")
            return
        
        text = """
👑 ADMIN PANEL

Select an option:
"""
        
        keyboard = [
            [InlineKeyboardButton("📊 Statistics Dashboard", callback_data="admin_stats")],
            [InlineKeyboardButton("📦 Order Management", callback_data="admin_orders")],
            [InlineKeyboardButton("👨‍💻 Developer Management", callback_data="admin_developers")],
            [InlineKeyboardButton("📝 Developer Applications", callback_data="admin_developer_requests")],
            [InlineKeyboardButton("⚙️ Custom Requests", callback_data="admin_custom_requests")],
            [InlineKeyboardButton("💰 Finance Management", callback_data="admin_finance")],
            [InlineKeyboardButton("🚀 Software Management", callback_data="admin_bots")],
            [InlineKeyboardButton("👥 User Management", callback_data="admin_users")],
            [InlineKeyboardButton("🎯 Job Management", callback_data="admin_job_management")],
            [InlineKeyboardButton("📢 Broadcast Message", callback_data="admin_broadcast")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            # REMOVE parse_mode for callback queries to ensure buttons work
            await query.edit_message_text(text, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error in admin_panel: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text(f"❌ Error: {str(e)}")


# ========== STATISTICS DASHBOARD ==========

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin statistics dashboard"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Total counts
            total_users = db.query(User).count()
            total_orders = db.query(Order).count()
            total_developers = db.query(Developer).count()
            total_bots = db.query(Bot).count()
            total_requests = db.query(CustomRequest).count()
            
            # Order status breakdown
            order_statuses = db.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
            status_text = ""
            for status, count in order_statuses:
                if status:
                    status_text += f"  • {status.value.replace('_', ' ').title()}: {count}\n"
            
            # Revenue calculations
            total_revenue = db.query(func.sum(Order.amount)).filter(Order.status == OrderStatus.COMPLETED).scalar() or 0
            today = datetime.now().date()
            today_revenue = db.query(func.sum(Order.amount)).filter(
                func.date(Order.created_at) == today,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            
            # Today's activity
            today_orders = db.query(Order).filter(func.date(Order.created_at) == today).count()
            today_users = db.query(User).filter(func.date(User.created_at) == today).count()
            today_custom_requests = db.query(CustomRequest).filter(func.date(CustomRequest.created_at) == today).count()
            
            # Developer stats
            active_devs = db.query(Developer).filter(Developer.status == DeveloperStatus.ACTIVE).count()
            busy_devs = db.query(Developer).filter(Developer.status == DeveloperStatus.BUSY).count()
            
            # Pending developer requests
            pending_dev_requests = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.NEW
            ).count()
            
            # Pending custom requests
            pending_custom_requests = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.NEW
            ).count()
            
            # Pending orders for review
            pending_order_review = db.query(Order).filter(
                Order.status == OrderStatus.PENDING_REVIEW
            ).count()
            
            text = f"""
📊 *ADMIN STATISTICS DASHBOARD*

*Overview:*
👥 Total Users: *{total_users}*
📦 Total Orders: *{total_orders}*
👨‍💻 Total Developers: *{total_developers}*
🚀 Total Software: *{total_bots}*
📝 Total Custom Requests: *{total_requests}*

*Pending Actions:*
📋 Pending Dev Applications: *{pending_dev_requests}*
⚙️ Pending Custom Requests: *{pending_custom_requests}*
⏳ Orders Pending Review: *{pending_order_review}*

*Revenue:*
💰 Total Revenue: *${total_revenue:.2f}*
📈 Today's Revenue: *${today_revenue:.2f}*

*Today's Activity:*
📊 New Orders: *{today_orders}*
👤 New Users: *{today_users}*
📝 New Custom Requests: *{today_custom_requests}*

*Order Status Breakdown:*
{status_text}

*Developer Status:*
🟢 Active Developers: *{active_devs}*
🟡 Busy Developers: *{busy_devs}*
"""
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats"),
                 InlineKeyboardButton("📈 Detailed Stats", callback_data="admin_stats_detailed")],
                [InlineKeyboardButton("📋 Dev Applications", callback_data="admin_developer_requests")],
                [InlineKeyboardButton("⚙️ Custom Requests", callback_data="admin_custom_requests")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading statistics.")

async def admin_stats_detailed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed statistics dashboard"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Get data for last 7 days
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            # Daily orders for last 7 days
            daily_orders = []
            for i in range(7):
                date = start_date + timedelta(days=i)
                count = db.query(Order).filter(func.date(Order.created_at) == date).count()
                revenue = db.query(func.sum(Order.amount)).filter(
                    func.date(Order.created_at) == date,
                    Order.status == OrderStatus.COMPLETED
                ).scalar() or 0
                daily_orders.append((date, count, revenue))
            
            # Top selling software
            top_bots = db.query(
                Bot.name,
                func.count(Order.id),
                func.sum(Order.amount)
            ).join(Order, Bot.id == Order.bot_id).filter(
                Order.status == OrderStatus.COMPLETED
            ).group_by(Bot.id).order_by(desc(func.count(Order.id))).limit(5).all()
            
            # Top developers by earnings
            top_developers = db.query(
                User.first_name,
                Developer.developer_id,
                Developer.completed_orders,
                Developer.earnings,
                Developer.rating
            ).join(Developer, User.id == Developer.user_id).filter(
                Developer.earnings > 0
            ).order_by(desc(Developer.earnings)).limit(5).all()
            
            # Payment method breakdown
            payment_methods = db.query(
                Order.payment_method,
                func.count(Order.id),
                func.sum(Order.amount)
            ).filter(
                Order.status == OrderStatus.COMPLETED,
                Order.payment_method.isnot(None)
            ).group_by(Order.payment_method).all()
            
            text = "📈 *DETAILED STATISTICS*\n\n"
            
            text += "*Last 7 Days Activity:*\n"
            for date, count, revenue in daily_orders:
                text += f"  {date.strftime('%b %d')}: {count} orders (${revenue:.2f})\n"
            
            text += "\n*Top Selling Software:*\n"
            for bot_name, order_count, total_revenue in top_bots:
                text += f"  🚀 {bot_name[:20]}: {order_count} sales (${total_revenue:.2f})\n"
            
            text += "\n*Top Developers:*\n"
            for first_name, dev_id, completed, earnings, rating in top_developers:
                text += f"  👨‍💻 {first_name} ({dev_id}): ${earnings:.2f}, {completed} orders, {rating:.1f}⭐\n"
            
            text += "\n*Payment Methods:*\n"
            for method, count, amount in payment_methods:
                if method:
                    method_name = method.value.replace('_', ' ').title()
                    text += f"  💳 {method_name}: {count} payments (${amount:.2f})\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_stats_detailed")],
                [InlineKeyboardButton("📊 Basic Stats", callback_data="admin_stats")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_stats_detailed: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading detailed statistics.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /admin command"""
    try:
        telegram_id = update.effective_user.id
        
        from config import SUPER_ADMIN_ID
        from database.db import create_session
        from database.models import User
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            is_admin = user and (user.is_admin or str(telegram_id) == str(SUPER_ADMIN_ID))
            
            if not is_admin:
                await update.message.reply_text(
                    f"❌ Access denied. You are not an admin.\n\n"
                    f"Your Telegram ID: {telegram_id}\n"
                    f"Super Admin ID: {SUPER_ADMIN_ID}"
                )
                return
            
            # Try to use the full admin panel
            try:
                from handlers.admin import admin_panel as full_admin_panel
                await full_admin_panel(update, context)
            except ImportError:
                # Fallback to simple admin panel
                await full_admin_panel(update, context)
                
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error in admin_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Error accessing admin panel.")

async def simple_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Simple admin panel fallback"""
    try:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            message_method = query.edit_message_text
        else:
            message_method = update.message.reply_text
        
        telegram_id = update.effective_user.id
        
        from config import SUPER_ADMIN_ID
        from database.db import create_session
        from database.models import User
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            is_admin = user and (user.is_admin or str(telegram_id) == str(SUPER_ADMIN_ID))
            
            if not is_admin:
                if update.callback_query:
                    await query.edit_message_text("❌ Access denied. You are not an admin.")
                else:
                    await update.message.reply_text("❌ Access denied. You are not an admin.")
                return
            
            text = """👑 ADMIN PANEL - BASIC VERSION

Full admin system is temporarily unavailable.

Available Commands:
/debug - Check bot status
/verify ORDER_ID - Verify payments
/verify_deposit PAYMENT_REF - Verify custom request deposits
/refund ORDER_ID [REASON] - Process manual refunds

Coming soon:
✅ Full admin dashboard
✅ Order management
✅ User management

Contact support for admin tasks."""
            
            keyboard = [
                [InlineKeyboardButton("🔧 Debug Info", callback_data="admin_debug")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if update.callback_query:
                await query.edit_message_text(text, reply_markup=reply_markup)
            else:
                await update.message.reply_text(text, reply_markup=reply_markup)
                
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in simple_admin_panel: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error accessing admin panel.")
        elif update.message:
            await update.message.reply_text("❌ Error accessing admin panel.")

# ========== ORDER MANAGEMENT ==========

async def admin_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Order management panel"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
📦 *ORDER MANAGEMENT*

*Select an option:*
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 View All Orders", callback_data="admin_view_orders")],
            [InlineKeyboardButton("⏳ Pending Review", callback_data="admin_orders_pending")],
            [InlineKeyboardButton("✅ Completed Orders", callback_data="admin_orders_completed")],
            [InlineKeyboardButton("❌ Cancelled Orders", callback_data="admin_orders_cancelled")],
            [InlineKeyboardButton("👷 Assigned Orders", callback_data="admin_orders_assigned")],
            [InlineKeyboardButton("🔍 Search Order", callback_data="admin_search_order")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_orders: {e}", exc_info=True)

async def admin_view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all orders with filtering"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            orders = db.query(Order).order_by(desc(Order.created_at)).limit(20).all()
            
            text = "📋 *ALL ORDERS*\n\n"
            
            if not orders:
                text += "No orders found."
            else:
                for order in orders:
                    user = db.query(User).filter(User.id == order.user_id).first()
                    bot_name = "Custom Software"
                    if order.bot_id:
                        bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                        if bot:
                            bot_name = bot.name
                    
                    status_icon = "⏳" if order.status == OrderStatus.PENDING_REVIEW else \
                                 "✅" if order.status == OrderStatus.COMPLETED else \
                                 "👷" if order.status == OrderStatus.IN_PROGRESS else \
                                 "👍" if order.status == OrderStatus.APPROVED else \
                                 "📦" if order.status == OrderStatus.ASSIGNED else \
                                 "❌" if order.status == OrderStatus.CANCELLED else "📦"
                    
                    text += f"{status_icon} *{order.order_id}*\n"
                    text += f"   👤 {user.first_name if user else 'Unknown'}\n"
                    text += f"   🚀 {bot_name}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n"
                    text += f"   📊 {order.status.value if order.status else 'Unknown'}\n\n"
            
            keyboard = []
            for order in orders[:10]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 {order.order_id[:8]}... - ${order.amount:.2f}",
                        callback_data=f"admin_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back to Order Management", callback_data="admin_orders")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_view_orders: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading orders.")

async def admin_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View order details"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('admin_order_detail_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            user = db.query(User).filter(User.id == order.user_id).first()
            bot = db.query(Bot).filter(Bot.id == order.bot_id).first() if order.bot_id else None
            developer = db.query(Developer).filter(Developer.id == order.assigned_developer_id).first() if order.assigned_developer_id else None
            
            text = f"""
📋 *ORDER DETAILS*

*Order ID:* `{order.order_id}`
*Status:* {order.status.value if order.status else 'Unknown'}
*Amount:* ${order.amount:.2f}
*Created:* {order.created_at.strftime('%Y-%m-%d %H:%M')}
*Payment Method:* {order.payment_method.value if order.payment_method else 'N/A'}
*Payment Status:* {order.payment_status.value if order.payment_status else 'N/A'}

*Customer Info:*
👤 Name: {user.first_name} {user.last_name or ''}
📱 Username: @{user.username or 'N/A'}
🆔 Telegram ID: {user.telegram_id}
"""
            
            if bot:
                text += f"""
*Software Details:*
🚀 Name: {bot.name}
💰 Price: ${bot.price:.2f}
📦 Delivery: {bot.delivery_time}
"""
            
            if developer:
                dev_user = db.query(User).filter(User.id == developer.user_id).first()
                text += f"""
*Assigned Developer:*
👨‍💻 ID: {developer.developer_id}
👤 Name: {dev_user.first_name if dev_user else 'N/A'}
📞 Status: {developer.status.value}
"""
            
            if order.payment_proof_url:
                text += "\n*Payment Proof:* ✅ Uploaded"
            
            if order.admin_notes:
                text += f"\n*Admin Notes:* {order.admin_notes}"
            
            if order.developer_notes:
                text += f"\n*Developer Notes:* {order.developer_notes[:200]}..."
            
            if order.paid_at:
                text += f"\n*Paid At:* {order.paid_at.strftime('%Y-%m-%d %H:%M')}"
            
            if order.delivered_at:
                text += f"\n*Delivered At:* {order.delivered_at.strftime('%Y-%m-%d %H:%M')}"
            
            # Action buttons based on status
            keyboard = []
            
            if order.status == OrderStatus.PENDING_REVIEW:
                keyboard.append([
                    InlineKeyboardButton("✅ Approve Payment", callback_data=f"admin_approve_payment_{order.id}"),
                    InlineKeyboardButton("❌ Reject Payment", callback_data=f"admin_reject_payment_{order.id}")
                ])
            
            if order.status == OrderStatus.APPROVED:
                keyboard.append([
                    InlineKeyboardButton("👷 Assign to Developer", callback_data=f"admin_assign_developer_{order.id}")
                ])
            
            if order.status == OrderStatus.IN_PROGRESS:
                keyboard.append([
                    InlineKeyboardButton("✅ Mark as Completed", callback_data=f"admin_complete_order_{order.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("📝 Add Admin Note", callback_data=f"admin_add_note_{order.id}"),
                InlineKeyboardButton("🔄 Update Status", callback_data=f"admin_update_status_{order.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_view_orders"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_order_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading order details.")

async def admin_approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve order payment"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('admin_approve_payment_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.status != OrderStatus.PENDING_REVIEW:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, not pending review.")
                return
            
            # Update order status
            order.status = OrderStatus.APPROVED
            order.payment_status = PaymentStatus.VERIFIED
            order.admin_notes = f"Payment approved by admin on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                user = db.query(User).filter(User.id == order.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
✅ *Payment Approved!*

📦 Order ID: `{order.order_id}`
💰 Amount: ${order.amount:.2f}
📊 Status: ✅ Approved

Your payment has been verified and approved. Your order is now being processed.

*Next Steps:*
1. Order will be assigned to a developer
2. Development will begin soon
3. You'll receive updates on progress

Thank you for your purchase! 🎉
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Payment Approved!*\n\n"
                f"Order `{order.order_id}` has been approved.\n"
                f"User has been notified.\n\n"
                f"*Next:* Assign to a developer.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👷 Assign Developer", callback_data=f"admin_assign_developer_{order.id}")],
                    [InlineKeyboardButton("📋 View Order", callback_data=f"admin_order_detail_{order.id}")],
                    [InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_view_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error approving payment: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error approving payment.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_approve_payment: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing approval.")

async def admin_job_management(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main job management dashboard"""
    try:
        query = update.callback_query
        await query.answer()

        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return

        db = create_session()
        try:
            # Count jobs by status
            from database.models import Job

            pending_count = db.query(Job).filter(
                Job.status == 'pending_approval'
            ).count()

            approved_count = db.query(Job).filter(
                Job.is_public == True
            ).count()

            active_count = db.query(Job).filter(
                Job.status.in_(['open', 'assigned', 'in_progress'])
            ).count()

            total_count = db.query(Job).count()

            text = f"""
🎯 **JOB MANAGEMENT DASHBOARD**

📊 **Statistics:**
⏳ Pending Approval: **{pending_count}**
✅ Approved & Public: **{approved_count}**
👨‍💻 Active Jobs: **{active_count}**
📋 Total Jobs: **{total_count}**

Select an option below:
            """

            keyboard = [
                [InlineKeyboardButton(f"⏳ Pending Approval ({pending_count})", callback_data="admin_jobs_pending_list")],
                [InlineKeyboardButton("✅ Approved Jobs", callback_data="admin_jobs_approved")],
                [InlineKeyboardButton("👨‍💻 Active Jobs", callback_data="admin_jobs_active")],
                [InlineKeyboardButton("📊 Job Statistics", callback_data="admin_jobs_stats")],
                [InlineKeyboardButton("🔍 Search Jobs", callback_data="admin_jobs_search")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

        except ImportError:
            await query.edit_message_text(
                "❌ Job module not fully installed. Please ensure database models exist.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back", callback_data="admin_panel")]
                ])
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in admin_job_management: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job management.")

async def admin_review_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Review a specific job for approval"""
    try:
        query = update.callback_query
        await query.answer()

        job_id = query.data.replace("admin_review_job_", "")

        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return

        db = create_session()
        try:
            from database.models import Job, User

            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job:
                await query.edit_message_text("❌ Job not found.")
                return

            user = db.query(User).filter(User.id == job.user_id).first()
            username = f"@{user.username}" if user and user.username else "No username"
            email = user.email if user and user.email else "Not provided"

            text = f"""
📋 **JOB REVIEW**

**Job ID:** `{job.job_id}`
**Title:** {job.title}
**Category:** {job.category or 'Not specified'}
**Budget:** ${job.budget:.2f}
**Timeline:** {job.expected_timeline or 'Not specified'}

**Posted by:** {user.first_name if user else 'Unknown'} {username}
**Telegram ID:** `{user.telegram_id if user else 'N/A'}`
**Email:** {email}

**Description:**
{job.description}

**Expected Outcome:**
{job.expected_outcome or 'Not specified'}

**Created:** {job.created_at.strftime('%Y-%m-%d %H:%M') if job.created_at else 'N/A'}
**Status:** `{job.status}`

**Action Required:**
Approve to make this job public, or reject with reason.
            """

            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_approve_job_{job.job_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_reject_job_{job.job_id}")
                ],
                [
                    InlineKeyboardButton("📞 Contact User", callback_data=f"admin_contact_job_{job.job_id}"),
                    InlineKeyboardButton("📝 Add Notes", callback_data=f"admin_job_notes_{job.job_id}")
                ],
                [InlineKeyboardButton("⬅️ Back to Pending", callback_data="admin_jobs_pending_list")],
                [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
            ]

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')

        except Exception as e:
            logger.error(f"Error in admin_review_job: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading job details.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in admin_review_job: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading job details.")


async def admin_approve_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve job – set is_public = True, status = 'open'"""
    try:
        query = update.callback_query
        await query.answer()

        job_id = query.data.replace("admin_approve_job_", "")

        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return

        db = create_session()
        try:
            from database.models import Job, User
            from datetime import datetime

            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job:
                await query.edit_message_text("❌ Job not found.")
                return

            # Update job status
            job.status = 'open'
            job.is_public = True
            job.approved_at = datetime.now()
            db.commit()

            # Notify the job poster
            user = db.query(User).filter(User.id == job.user_id).first()
            if user:
                from telegram import Bot
                from config import TELEGRAM_TOKEN
                if TELEGRAM_TOKEN:
                    bot = Bot(token=TELEGRAM_TOKEN)
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"""
✅ **Your Job Has Been Approved!**

📋 **Job ID:** `{job.job_id}`
📝 **Title:** {job.title}
💰 **Budget:** ${job.budget:.2f}
⏰ **Timeline:** {job.expected_timeline}

Your job is now public and visible to developers.
Developers can view the details and contact you directly via Telegram.

🔍 **View your job:** /my_jobs

Thank you for using Software Marketplace!
                            """,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")

            await query.edit_message_text(
                f"✅ **Job Approved!**\n\n"
                f"Job `{job.job_id}` is now public.\n"
                f"The customer has been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Job", callback_data=f"view_job_{job.job_id}")],
                    [InlineKeyboardButton("⬅️ Back to Pending", callback_data="admin_jobs_pending_list")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )

        except Exception as e:
            logger.error(f"Error approving job: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error approving job.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in admin_approve_job: {e}", exc_info=True)
        await query.edit_message_text("❌ Error approving job.")


async def admin_reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject order payment"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('admin_reject_payment_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.status != OrderStatus.PENDING_REVIEW:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, not pending review.")
                return
            
            # Update order status
            order.status = OrderStatus.CANCELLED
            order.payment_status = PaymentStatus.FAILED
            order.admin_notes = f"Payment rejected by admin on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                user = db.query(User).filter(User.id == order.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
❌ *Payment Rejected*

📦 Order ID: `{order.order_id}`
💰 Amount: ${order.amount:.2f}
📊 Status: ❌ Rejected

Your payment has been rejected. Please check the payment details and try again.

*Possible reasons:*
1. Incorrect payment amount
2. Missing payment proof
3. Payment proof unclear

If you believe this is a mistake, please contact support.
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"❌ *Payment Rejected!*\n\n"
                f"Order `{order.order_id}` has been rejected.\n"
                f"User has been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Order", callback_data=f"admin_order_detail_{order.id}")],
                    [InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_view_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error rejecting payment: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error rejecting payment.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_reject_payment: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing rejection.")

async def admin_assign_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Assign order to developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('admin_assign_developer_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.status != OrderStatus.APPROVED:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, must be 'approved'.")
                return
            
            # Get available developers
            developers = db.query(Developer).filter(
                Developer.status == DeveloperStatus.ACTIVE,
                Developer.is_available == True
            ).all()
            
            if not developers:
                await query.edit_message_text(
                    "❌ No available developers.\n\n"
                    "All developers are busy or inactive.\n"
                    "Please wait or add more developers.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👨‍💻 Add Developer", callback_data="admin_add_developer")],
                        [InlineKeyboardButton("📋 View Order", callback_data=f"admin_order_detail_{order.id}")]
                    ])
                )
                return
            
            text = f"""
👷 *Assign Developer*

Select a developer for order:
📦 Order ID: `{order.order_id}`
🚀 Software: {order.bot.name if order.bot else 'Custom Software'}
💰 Amount: ${order.amount:.2f}

*Available Developers:*
"""
            
            keyboard = []
            for dev in developers[:10]:
                user = db.query(User).filter(User.id == dev.user_id).first()
                keyboard.append([
                    InlineKeyboardButton(
                        f"👨‍💻 {user.first_name} ({dev.developer_id}) - Rating: {dev.rating:.1f}⭐",
                        callback_data=f"admin_assign_dev_{order.id}_{dev.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("📋 View Order", callback_data=f"admin_order_detail_{order.id}"),
                InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_view_orders")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_assign_developer: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developers.")

async def admin_goto_add_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Redirect to add developer from order assignment"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Redirect to the developer management panel
        await admin_developers(update, context)
        
    except Exception as e:
        logger.error(f"Error in admin_goto_add_developer: {e}", exc_info=True)
        await query.edit_message_text("❌ Error redirecting to developer management.")

async def admin_assign_dev_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm developer assignment"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract order_id and developer_id from callback data
        data = query.data.replace('admin_assign_dev_', '').split('_')
        order_id = int(data[0])
        developer_id = int(data[1])
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            developer = db.query(Developer).filter(Developer.id == developer_id).first()
            
            if not order or not developer:
                await query.edit_message_text("❌ Order or developer not found.")
                return
            
            if order.status != OrderStatus.APPROVED:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, must be 'approved'.")
                return
            
            # Assign developer
            order.assigned_developer_id = developer.id
            order.status = OrderStatus.ASSIGNED
            developer.status = DeveloperStatus.BUSY
            developer.is_available = False
            
            db.commit()
            
            # Notify developer
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                dev_user = db.query(User).filter(User.id == developer.user_id).first()
                customer = db.query(User).filter(User.id == order.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=dev_user.telegram_id,
                        text=f"""
📦 *New Order Assigned!*

You have been assigned a new order:

📋 Order ID: `{order.order_id}`
👤 Customer: {customer.first_name} (@{customer.username or 'N/A'})
🚀 Software: {order.bot.name if order.bot else 'Custom Software'}
💰 Amount: ${order.amount:.2f}

*Instructions:*
1. Contact the customer to discuss requirements
2. Start development
3. Update order status regularly
4. Mark as completed when done

Use /developer to manage your orders.
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify developer: {e}")
            
            # Notify customer
            if TELEGRAM_TOKEN:
                try:
                    await bot.send_message(
                        chat_id=customer.telegram_id,
                        text=f"""
👷 *Developer Assigned!*

A developer has been assigned to your order:

📋 Order ID: `{order.order_id}`
👨‍💻 Developer: {dev_user.first_name}
📞 Status: Development Started

*What's next:*
1. Developer will contact you soon
2. Discuss your requirements
3. Development will begin
4. Regular updates will be provided

Thank you for your patience! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer: {e}")
            
            await query.edit_message_text(
                f"✅ *Developer Assigned!*\n\n"
                f"Order `{order.order_id}` has been assigned to:\n"
                f"👨‍💻 Developer: {dev_user.first_name}\n"
                f"📱 Telegram: @{dev_user.username or 'N/A'}\n\n"
                f"Both developer and customer have been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Order", callback_data=f"admin_order_detail_{order.id}")],
                    [InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_view_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error assigning developer: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error assigning developer.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_assign_dev_confirm: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing assignment.")

async def admin_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark order as completed"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('admin_complete_order_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.status != OrderStatus.IN_PROGRESS:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, must be 'in_progress'.")
                return
            
            # Update order status
            order.status = OrderStatus.COMPLETED
            order.delivered_at = datetime.now()
            
            # Update developer stats
            if order.assigned_developer_id:
                developer = db.query(Developer).filter(Developer.id == order.assigned_developer_id).first()
                if developer:
                    developer.completed_orders += 1
                    developer.earnings += order.amount * 0.7  # Developer gets 70%
                    developer.status = DeveloperStatus.ACTIVE
                    developer.is_available = True
            
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
🎉 *Order Completed!*

Your order has been completed:

📋 Order ID: `{order.order_id}`
🚀 Software: {order.bot.name if order.bot else 'Custom Software'}
✅ Status: ✅ Completed
📅 Delivered: {datetime.now().strftime('%Y-%m-%d %H:%M')}

*Next Steps:*
1. Review the delivered software
2. Test all features
3. Provide feedback to the developer
4. Contact support if any issues

Thank you for choosing Software Marketplace! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer: {e}")
            
            await query.edit_message_text(
                f"✅ *Order Completed!*\n\n"
                f"Order `{order.order_id}` has been marked as completed.\n"
                f"Customer has been notified.\n"
                f"Developer earnings updated.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Order", callback_data=f"admin_order_detail_{order.id}")],
                    [InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_view_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error completing order: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error completing order.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_complete_order: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing completion.")

async def admin_orders_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View pending orders for review"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            orders = db.query(Order).filter(
                Order.status == OrderStatus.PENDING_REVIEW
            ).order_by(Order.created_at.desc()).all()
            
            text = "⏳ *PENDING ORDERS FOR REVIEW*\n\n"
            
            if not orders:
                text += "No pending orders found."
            else:
                for order in orders:
                    user = db.query(User).filter(User.id == order.user_id).first()
                    bot_name = "Custom Software"
                    if order.bot_id:
                        bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                        if bot:
                            bot_name = bot.name
                    
                    text += f"📦 *{order.order_id}*\n"
                    text += f"   👤 {user.first_name if user else 'Unknown'}\n"
                    text += f"   🚀 {bot_name}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = []
            for order in orders[:10]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 {order.order_id[:8]}... - ${order.amount:.2f}",
                        callback_data=f"admin_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Orders", callback_data="admin_orders"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_orders_pending: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading pending orders.")

# ========== DEVELOPER MANAGEMENT ==========

async def admin_developers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer management panel"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
👨‍💻 *DEVELOPER MANAGEMENT*

*Select an option:*
"""
        
        keyboard = [
            [InlineKeyboardButton("➕ Add Developer", callback_data="admin_add_developer")],
            [InlineKeyboardButton("➖ Remove Developer", callback_data="admin_remove_developer")],
            [InlineKeyboardButton("📋 View All Developers", callback_data="admin_view_developers")],
            [InlineKeyboardButton("🟢 Active Developers", callback_data="admin_active_developers")],
            [InlineKeyboardButton("🔴 Inactive Developers", callback_data="admin_inactive_developers")],
            [InlineKeyboardButton("📊 Developer Stats", callback_data="admin_developer_stats")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_developers: {e}", exc_info=True)

async def admin_view_developers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all developers"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            developers = db.query(Developer).order_by(desc(Developer.created_at)).all()
            
            text = "👨‍💻 *ALL DEVELOPERS*\n\n"
            
            if not developers:
                text += "No developers found."
            else:
                for dev in developers:
                    user = db.query(User).filter(User.id == dev.user_id).first()
                    status_emoji = "🟢" if dev.status == DeveloperStatus.ACTIVE else "🟡" if dev.status == DeveloperStatus.BUSY else "🔴"
                    
                    text += f"{status_emoji} *{dev.developer_id}*\n"
                    text += f"   👤 {user.first_name if user else 'N/A'}\n"
                    text += f"   📱 @{user.username or 'N/A'}\n"
                    text += f"   📊 Status: {dev.status.value}\n"
                    text += f"   ✅ Completed Orders: {dev.completed_orders}\n"
                    text += f"   💰 Earnings: ${dev.earnings:.2f}\n"
                    text += f"   ⭐ Rating: {dev.rating:.1f}\n\n"
            
            keyboard = []
            for dev in developers[:10]:
                user = db.query(User).filter(User.id == dev.user_id).first()
                status_emoji = "🟢" if dev.status == DeveloperStatus.ACTIVE else "🟡" if dev.status == DeveloperStatus.BUSY else "🔴"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_emoji} {user.first_name[:10]} ({dev.developer_id})",
                        callback_data=f"admin_developer_detail_{dev.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back to Developer Management", callback_data="admin_developers")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_view_developers: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developers.")

async def admin_developer_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View developer details"""
    try:
        query = update.callback_query
        await query.answer()
        
        developer_id = int(query.data.replace('admin_developer_detail_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            developer = db.query(Developer).filter(Developer.id == developer_id).first()
            if not developer:
                await query.edit_message_text("❌ Developer not found.")
                return
            
            user = db.query(User).filter(User.id == developer.user_id).first()
            status_emoji = "🟢" if developer.status == DeveloperStatus.ACTIVE else "🟡" if developer.status == DeveloperStatus.BUSY else "🔴"
            
            # Get assigned orders
            assigned_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).all()
            
            # Get completed orders
            completed_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status == OrderStatus.COMPLETED
            ).all()
            
            text = f"""
👨‍💻 *DEVELOPER DETAILS*

*Developer ID:* {developer.developer_id}
*Status:* {status_emoji} {developer.status.value.title()}
*User:* {user.first_name} {user.last_name or ''}
*Username:* @{user.username or 'N/A'}
*Telegram ID:* {user.telegram_id}
*Joined:* {developer.created_at.strftime('%Y-%m-%d')}

*Statistics:*
✅ Completed Orders: {developer.completed_orders}
💰 Total Earnings: ${developer.earnings:.2f}
⭐ Average Rating: {developer.rating:.1f}/5.0
⏰ Hourly Rate: ${developer.hourly_rate:.2f}

*Skills & Experience:*
{developer.skills_experience or 'Not specified'}

*Current Assignments:*
📦 Assigned Orders: {len(assigned_orders)}
✅ Completed Orders: {len(completed_orders)}
"""
            
            if developer.portfolio_url:
                text += f"\n*Portfolio:* {developer.portfolio_url}"
            
            if developer.github_url:
                text += f"\n*GitHub:* {developer.github_url}"
            
            keyboard = []
            
            if developer.status == DeveloperStatus.ACTIVE:
                keyboard.append([
                    InlineKeyboardButton("🟡 Mark as Busy", callback_data=f"admin_dev_busy_{developer.id}"),
                    InlineKeyboardButton("🔴 Deactivate", callback_data=f"admin_dev_deactivate_{developer.id}")
                ])
            elif developer.status == DeveloperStatus.BUSY:
                keyboard.append([
                    InlineKeyboardButton("🟢 Mark as Active", callback_data=f"admin_dev_activate_{developer.id}"),
                    InlineKeyboardButton("🔴 Deactivate", callback_data=f"admin_dev_deactivate_{developer.id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("🟢 Activate", callback_data=f"admin_dev_activate_{developer.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("📝 Edit Developer", callback_data=f"admin_dev_edit_{developer.id}"),
                InlineKeyboardButton("💰 Update Earnings", callback_data=f"admin_dev_earnings_{developer.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Developers", callback_data="admin_view_developers"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_developer_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developer details.")

async def admin_add_developer_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process adding a new developer"""
    try:
        if not update.message or not context.user_data.get('adding_developer'):
            return
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        developer_telegram_id = update.message.text.strip()
        
        if not developer_telegram_id.isdigit():
            await update.message.reply_text("❌ Please send a valid Telegram ID (numbers only).")
            return
        
        developer_telegram_id = int(developer_telegram_id)
        
        db = create_session()
        try:
            # Check if user exists
            user = db.query(User).filter(User.telegram_id == developer_telegram_id).first()
            if not user:
                await update.message.reply_text("❌ User not found. Please ask them to use /start first.")
                return
            
            # Check if already a developer
            existing_dev = db.query(Developer).filter(Developer.user_id == user.id).first()
            if existing_dev:
                await update.message.reply_text(f"❌ User is already a developer (ID: {existing_dev.developer_id}).")
                return
            
            # Generate developer ID
            last_dev = db.query(Developer).order_by(desc(Developer.id)).first()
            dev_number = last_dev.id + 1 if last_dev else 1
            developer_id = f"DEV{dev_number:03d}"
            
            # Create developer
            developer = Developer(
            user_id=user.id,
            developer_id=developer_id,
            status=DeveloperStatus.ACTIVE,
            is_available=True,
            rating=0.0,
            completed_orders=0,
            earnings=0.0,
            hourly_rate=25.0
        )
            db.add(developer)
            user.is_developer = True
            db.commit()
            
            # Send notification to new developer
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=developer_telegram_id,
                        text=f"""
🎉 *Congratulations!*

You have been registered as a developer!

*Developer ID:* `{developer_id}`
*Status:* ✅ Active
*Earnings:* $0.00 (start earning now!)

*Next Steps:*
1. Use /developer to access your dashboard
2. Set your availability status
3. Start claiming orders
4. Build your reputation

Welcome to the developer team! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify new developer: {e}")
            
            await update.message.reply_text(
                f"✅ *Developer Added Successfully!*\n\n"
                f"*Developer ID:* `{developer_id}`\n"
                f"*Name:* {user.first_name}\n"
                f"*Telegram ID:* {user.telegram_id}\n"
                f"*Username:* @{user.username or 'N/A'}\n\n"
                f"The developer has been notified.",
                parse_mode='Markdown'
            )
            
            # Clear context
            context.user_data.pop('adding_developer', None)
            
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in admin_add_developer_process: {e}", exc_info=True)
        await update.message.reply_text("❌ Error adding developer.")
        return ConversationHandler.END

# ========== FINANCE MANAGEMENT ==========

async def admin_finance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Finance management panel"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
💰 *FINANCE MANAGEMENT*

*Select an option:*
"""
        
        keyboard = [
            [InlineKeyboardButton("📊 Financial Overview", callback_data="admin_finance_overview")],
            [InlineKeyboardButton("💵 Pending Payments", callback_data="admin_pending_payments")],
            [InlineKeyboardButton("✅ Verified Payments", callback_data="admin_verified_payments")],
            [InlineKeyboardButton("❌ Rejected Payments", callback_data="admin_rejected_payments")],
            [InlineKeyboardButton("👨‍💻 Developer Payouts", callback_data="admin_developer_payouts")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_finance: {e}", exc_info=True)

async def admin_finance_overview(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Financial overview"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Total revenue
            total_revenue = db.query(func.sum(Order.amount)).filter(Order.status == OrderStatus.COMPLETED).scalar() or 0
            
            # Today's revenue
            today = datetime.now().date()
            today_revenue = db.query(func.sum(Order.amount)).filter(
                func.date(Order.created_at) == today,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            
            # This week's revenue
            week_ago = today - timedelta(days=7)
            week_revenue = db.query(func.sum(Order.amount)).filter(
                Order.created_at >= week_ago,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            
            # This month's revenue
            month_ago = today - timedelta(days=30)
            month_revenue = db.query(func.sum(Order.amount)).filter(
                Order.created_at >= month_ago,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            
            # Pending payments
            pending_payments = db.query(Order).filter(
                Order.status == OrderStatus.PENDING_REVIEW
            ).count()
            
            pending_amount = db.query(func.sum(Order.amount)).filter(
                Order.status == OrderStatus.PENDING_REVIEW
            ).scalar() or 0
            
            # Developer earnings (platform keeps 30%, developers get 70%)
            total_developer_earnings = db.query(func.sum(Developer.earnings)).scalar() or 0
            platform_revenue = total_revenue - total_developer_earnings
            
            # Recent transactions
            recent_transactions = db.query(Transaction).order_by(desc(Transaction.created_at)).limit(5).all()
            
            text = f"""
💰 *FINANCIAL OVERVIEW*

*Revenue Summary:*
💰 Total Revenue: *${total_revenue:.2f}*
📈 This Month: *${month_revenue:.2f}*
📊 This Week: *${week_revenue:.2f}*
📅 Today: *${today_revenue:.2f}*

*Revenue Breakdown:*
🏢 Platform Revenue: *${platform_revenue:.2f}* (30%)
👨‍💻 Developer Earnings: *${total_developer_earnings:.2f}* (70%)

*Pending Payments:*
⏳ Pending Count: *{pending_payments}*
💵 Pending Amount: *${pending_amount:.2f}*

*Recent Transactions:*
"""
            
            for transaction in recent_transactions:
                user = db.query(User).filter(User.id == transaction.user_id).first()
                status_emoji = "✅" if transaction.status == 'successful' else "⏳" if transaction.status == 'pending' else "❌"
                text += f"{status_emoji} {transaction.transaction_id[:10]}... - ${transaction.amount:.2f} ({user.first_name if user else 'Unknown'})\n"
            
            keyboard = [
                [InlineKeyboardButton("🔄 Refresh", callback_data="admin_finance_overview")],
                [InlineKeyboardButton("👨‍💻 Developer Payouts", callback_data="admin_developer_payouts")],
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="admin_finance")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_finance_overview: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading financial overview.")

async def admin_pending_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending payments"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            pending_orders = db.query(Order).filter(
                Order.status == OrderStatus.PENDING_REVIEW
            ).order_by(Order.created_at.desc()).all()
            
            text = "💵 *PENDING PAYMENTS*\n\n"
            
            if not pending_orders:
                text += "No pending payments found."
            else:
                total_pending = sum(order.amount for order in pending_orders)
                text += f"Total Pending: *${total_pending:.2f}*\n"
                text += f"Number of Payments: *{len(pending_orders)}*\n\n"
                
                for order in pending_orders[:10]:
                    user = db.query(User).filter(User.id == order.user_id).first()
                    bot = db.query(Bot).filter(Bot.id == order.bot_id).first() if order.bot_id else None
                    
                    text += f"📦 *{order.order_id}*\n"
                    text += f"   👤 {user.first_name if user else 'Unknown'}\n"
                    text += f"   🚀 {bot.name if bot else 'Custom Software'}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
                    text += f"   💳 {order.payment_method.value if order.payment_method else 'N/A'}\n\n"
            
            keyboard = []
            for order in pending_orders[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 {order.order_id[:8]}... - ${order.amount:.2f}",
                        callback_data=f"admin_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Finance", callback_data="admin_finance"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_pending_payments: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading pending payments.")

async def admin_developer_payouts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage developer payouts"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Get developers with earnings
            developers = db.query(Developer).filter(
                Developer.earnings > 0
            ).order_by(desc(Developer.earnings)).all()
            
            total_payouts = sum(dev.earnings for dev in developers)
            
            text = f"""
👨‍💻 *DEVELOPER PAYOUTS*

*Total Payouts Due:* *${total_payouts:.2f}*
*Number of Developers:* *{len(developers)}*

*Developers with Earnings:*
"""
            
            if not developers:
                text += "\nNo developers with earnings yet."
            else:
                for dev in developers[:15]:
                    user = db.query(User).filter(User.id == dev.user_id).first()
                    text += f"\n👨‍💻 *{dev.developer_id}*\n"
                    text += f"   👤 {user.first_name}\n"
                    text += f"   📱 @{user.username or 'N/A'}\n"
                    text += f"   💰 Earnings: ${dev.earnings:.2f}\n"
                    text += f"   ✅ Orders: {dev.completed_orders}\n"
            
            keyboard = []
            for dev in developers[:5]:
                user = db.query(User).filter(User.id == dev.user_id).first()
                keyboard.append([
                    InlineKeyboardButton(
                        f"💰 {user.first_name[:10]} - ${dev.earnings:.2f}",
                        callback_data=f"admin_dev_payout_{dev.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Finance", callback_data="admin_finance"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_developer_payouts: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developer payouts.")

# ========== SOFTWARE MANAGEMENT ==========

async def admin_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Software management panel"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
🚀 *SOFTWARE MANAGEMENT*

*Select an option:*
"""
        
        keyboard = [
            [InlineKeyboardButton("➕ Add New Software", callback_data="admin_add_bot")],
            [InlineKeyboardButton("📋 View All Software", callback_data="admin_view_bots")],
            [InlineKeyboardButton("✏️ Edit Software", callback_data="admin_edit_bot")],
            [InlineKeyboardButton("🚫 Disable Software", callback_data="admin_disable_bot")],
            [InlineKeyboardButton("✅ Enable Software", callback_data="admin_enable_bot")],
            [InlineKeyboardButton("⭐ Featured Software", callback_data="admin_featured_bots")],
            [InlineKeyboardButton("📊 Software Analytics", callback_data="admin_bot_analytics")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_bots: {e}", exc_info=True)

async def admin_view_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all software"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bots = db.query(Bot).order_by(desc(Bot.created_at)).all()
            
            text = "🚀 *ALL SOFTWARE*\n\n"
            
            if not bots:
                text += "No software found."
            else:
                total_sales = 0
                total_revenue = 0
                
                for bot in bots:
                    # Get sales count for this software
                    sales = db.query(Order).filter(
                        Order.bot_id == bot.id,
                        Order.status == OrderStatus.COMPLETED
                    ).count()
                    
                    # Get revenue for this software
                    revenue = db.query(func.sum(Order.amount)).filter(
                        Order.bot_id == bot.id,
                        Order.status == OrderStatus.COMPLETED
                    ).scalar() or 0
                    
                    total_sales += sales
                    total_revenue += revenue
                    
                    status = "✅ Available" if bot.is_available else "🚫 Disabled"
                    featured = "⭐" if bot.is_featured else ""
                    
                    text += f"{featured} *{bot.name}*\n"
                    text += f"   💰 ${bot.price:.2f}\n"
                    text += f"   📦 {bot.delivery_time}\n"
                    text += f"   🏷️ {bot.category}\n"
                    text += f"   📊 {status}\n"
                    text += f"   🛒 Sales: {sales}\n"
                    text += f"   💰 Revenue: ${revenue:.2f}\n\n"
                
                text += f"\n*Totals:* {len(bots)} software, {total_sales} sales, ${total_revenue:.2f} revenue"
            
            keyboard = []
            for bot in bots[:10]:
                status_emoji = "✅" if bot.is_available else "🚫"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_emoji} {bot.name[:15]} - ${bot.price:.2f}",
                        callback_data=f"admin_bot_detail_{bot.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back to Software Management", callback_data="admin_bots")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_view_bots: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading software.")

async def admin_bot_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View software details"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('admin_bot_detail_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            # Get sales statistics
            sales = db.query(Order).filter(
                Order.bot_id == bot.id,
                Order.status == OrderStatus.COMPLETED
            ).count()
            
            revenue = db.query(func.sum(Order.amount)).filter(
                Order.bot_id == bot.id,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            
            # Get pending orders
            pending_orders = db.query(Order).filter(
                Order.bot_id == bot.id,
                Order.status.in_([OrderStatus.PENDING_REVIEW, OrderStatus.APPROVED, OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).count()
            
            status = "✅ Available" if bot.is_available else "🚫 Disabled"
            featured = "⭐ Featured" if bot.is_featured else "Normal"
            
            text = f"""
🚀 *SOFTWARE DETAILS*

*Name:* {bot.name}
*Price:* ${bot.price:.2f}
*Delivery Time:* {bot.delivery_time}
*Category:* {bot.category}
*Status:* {status}
*Featured:* {featured}
*Created:* {bot.created_at.strftime('%Y-%m-%d')}

*Sales Statistics:*
🛒 Total Sales: {sales}
💰 Total Revenue: ${revenue:.2f}
⏳ Pending Orders: {pending_orders}

*Description:*
{bot.description}

*Features:*
{bot.features}
"""
            
            keyboard = []
            
            if bot.is_available:
                keyboard.append([
                    InlineKeyboardButton("🚫 Disable Software", callback_data=f"admin_bot_disable_{bot.id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("✅ Enable Software", callback_data=f"admin_bot_enable_{bot.id}")
                ])
            
            if bot.is_featured:
                keyboard.append([
                    InlineKeyboardButton("📌 Remove Featured", callback_data=f"admin_bot_unfeature_{bot.id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("⭐ Make Featured", callback_data=f"admin_bot_feature_{bot.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("✏️ Edit Software", callback_data=f"admin_bot_edit_{bot.id}"),
                InlineKeyboardButton("📊 Analytics", callback_data=f"admin_bot_analytics_{bot.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_view_bots"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading software details.")

async def admin_add_bot_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding new software"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        context.user_data['adding_bot'] = True
        context.user_data['bot_data'] = {}
        
        text = """
➕ *ADD NEW SOFTWARE*

Let's add new software to the marketplace.

*Step 1/7: Software Name*

Please send the name of the software (e.g., "Customer Management System", "E-commerce Website"):
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data="admin_bots")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        return ADD_BOT_NAME
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_start: {e}", exc_info=True)
        return ConversationHandler.END

async def admin_add_bot_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get software name"""
    try:
        if not update.message:
            return ADD_BOT_NAME
        
        context.user_data['bot_data']['name'] = update.message.text
        
        await update.message.reply_text(
            "✅ *Software Name Saved!*\n\n"
            "*Step 2/7: Software Description*\n\n"
            "Please send a detailed description of the software:",
            parse_mode='Markdown'
        )
        
        return ADD_BOT_DESCRIPTION
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_name: {e}", exc_info=True)
        return ADD_BOT_NAME

async def admin_add_bot_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get software description"""
    try:
        if not update.message:
            return ADD_BOT_DESCRIPTION
        
        context.user_data['bot_data']['description'] = update.message.text
        
        await update.message.reply_text(
            "✅ *Description Saved!*\n\n"
            "*Step 3/7: Software Features*\n\n"
            "Please list the features (one per line, separate with commas or new lines):",
            parse_mode='Markdown'
        )
        
        return ADD_BOT_FEATURES
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_description: {e}", exc_info=True)
        return ADD_BOT_DESCRIPTION

async def admin_add_bot_features(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get software features"""
    try:
        if not update.message:
            return ADD_BOT_FEATURES
        
        context.user_data['bot_data']['features'] = update.message.text
        
        await update.message.reply_text(
            "✅ *Features Saved!*\n\n"
            "*Step 4/7: Software Price*\n\n"
            "Please send the price in USD (e.g., 299.99):",
            parse_mode='Markdown'
        )
        
        return ADD_BOT_PRICE
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_features: {e}", exc_info=True)
        return ADD_BOT_FEATURES

async def admin_add_bot_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get software price"""
    try:
        if not update.message:
            return ADD_BOT_PRICE
        
        try:
            price = float(update.message.text)
            context.user_data['bot_data']['price'] = price
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number (e.g., 299.99)")
            return ADD_BOT_PRICE
        
        await update.message.reply_text(
            "✅ *Price Saved!*\n\n"
            "*Step 5/7: Software Category*\n\n"
            "Please send the category (e.g., Web Application, Mobile App, Bot, Desktop Software):",
            parse_mode='Markdown'
        )
        
        return ADD_BOT_CATEGORY
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_price: {e}", exc_info=True)
        return ADD_BOT_PRICE

async def admin_add_bot_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get software category"""
    try:
        if not update.message:
            return ADD_BOT_CATEGORY
        
        context.user_data['bot_data']['category'] = update.message.text
        
        await update.message.reply_text(
            "✅ *Category Saved!*\n\n"
            "*Step 6/7: Delivery Time*\n\n"
            "Please send the delivery time (e.g., '3-5 days', '2 weeks', '1 month'):",
            parse_mode='Markdown'
        )
        
        return ADD_BOT_DELIVERY
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_category: {e}", exc_info=True)
        return ADD_BOT_CATEGORY

async def admin_add_bot_delivery(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Get software delivery time and create software"""
    try:
        if not update.message:
            return ADD_BOT_DELIVERY
        
        context.user_data['bot_data']['delivery_time'] = update.message.text
        
        # Create the software
        db = create_session()
        try:
            bot_data = context.user_data['bot_data']
            
            # Generate slug from name
            import re
            from datetime import datetime
            slug = re.sub(r'[^a-z0-9]+', '-', bot_data['name'].lower()).strip('-')
            
            # Check if slug already exists
            existing_bot = db.query(Bot).filter(Bot.slug == slug).first()
            if existing_bot:
                # Add timestamp to make unique
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                slug = f"{slug}-{timestamp}"
            
            bot = Bot(
                name=bot_data['name'],
                slug=slug,
                description=bot_data['description'],
                features=bot_data['features'],
                price=bot_data['price'],
                category=bot_data['category'],
                delivery_time=bot_data['delivery_time'],
                is_available=True,
                is_featured=False
            )
            
            db.add(bot)
            db.commit()
            
            # Clear context
            context.user_data.pop('adding_bot', None)
            context.user_data.pop('bot_data', None)
            
            await update.message.reply_text(
                f"🎉 *Software Added Successfully!*\n\n"
                f"*Name:* {bot.name}\n"
                f"*Price:* ${bot.price:.2f}\n"
                f"*Category:* {bot.category}\n"
                f"*Delivery:* {bot.delivery_time}\n"
                f"*Status:* ✅ Available\n\n"
                f"The software is now available in the marketplace.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Software", callback_data="admin_view_bots")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error creating software: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error creating software. Please try again.")
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in admin_add_bot_delivery: {e}", exc_info=True)
        return ConversationHandler.END

async def admin_bot_disable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable software"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('admin_bot_disable_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            bot.is_available = False
            db.commit()
            
            await query.edit_message_text(
                f"🚫 *Software Disabled!*\n\n"
                f"Software '{bot.name}' has been disabled.\n"
                f"It will no longer be available for purchase.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Software", callback_data=f"admin_bot_detail_{bot.id}")],
                    [InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_view_bots")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error disabling software: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error disabling software.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_disable: {e}", exc_info=True)

async def admin_bot_enable(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable software"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('admin_bot_enable_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            bot.is_available = True
            db.commit()
            
            await query.edit_message_text(
                f"✅ *Software Enabled!*\n\n"
                f"Software '{bot.name}' has been enabled.\n"
                f"It is now available for purchase.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Software", callback_data=f"admin_bot_detail_{bot.id}")],
                    [InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_view_bots")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error enabling software: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error enabling software.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_enable: {e}", exc_info=True)

async def admin_bot_feature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Feature software"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('admin_bot_feature_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            bot.is_featured = True
            db.commit()
            
            await query.edit_message_text(
                f"⭐ *Software Featured!*\n\n"
                f"Software '{bot.name}' is now featured.\n"
                f"It will appear in the featured software section.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Software", callback_data=f"admin_bot_detail_{bot.id}")],
                    [InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_view_bots")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error featuring software: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error featuring software.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_feature: {e}", exc_info=True)

async def admin_bot_unfeature(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove featured status from software"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('admin_bot_unfeature_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            bot.is_featured = False
            db.commit()
            
            await query.edit_message_text(
                f"📌 *Featured Status Removed!*\n\n"
                f"Software '{bot.name}' is no longer featured.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Software", callback_data=f"admin_bot_detail_{bot.id}")],
                    [InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_view_bots")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error removing featured status: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error removing featured status.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_unfeature: {e}", exc_info=True)

# ========== USER MANAGEMENT ==========

async def admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User management panel"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
👥 *USER MANAGEMENT*

*Select an option:*
"""
        
        keyboard = [
            [InlineKeyboardButton("📋 View All Users", callback_data="admin_view_users")],
            [InlineKeyboardButton("👑 Make Admin", callback_data="admin_make_admin")],
            [InlineKeyboardButton("👤 Remove Admin", callback_data="admin_remove_admin")],
            [InlineKeyboardButton("📊 User Activity", callback_data="admin_user_activity")],
            [InlineKeyboardButton("🔍 Search User", callback_data="admin_search_user")],
            [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_users: {e}", exc_info=True)

async def admin_view_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all users"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            users = db.query(User).order_by(desc(User.created_at)).limit(20).all()
            
            text = "👥 *ALL USERS*\n\n"
            
            if not users:
                text += "No users found."
            else:
                for user in users:
                    admin_emoji = "👑" if user.is_admin else ""
                    dev_emoji = "👨‍💻" if user.is_developer else ""
                    
                    text += f"{admin_emoji}{dev_emoji} *{user.first_name}*\n"
                    text += f"   📱 @{user.username or 'N/A'}\n"
                    text += f"   🆔 {user.telegram_id}\n"
                    text += f"   📅 Joined: {user.created_at.strftime('%Y-%m-%d')}\n"
                    text += f"   📦 Orders: {user.total_orders}\n"
                    text += f"   💰 Balance: ${user.balance:.2f}\n\n"
            
            keyboard = []
            for user in users[:10]:
                status = ""
                if user.is_admin:
                    status = "👑"
                elif user.is_developer:
                    status = "👨‍💻"
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status} {user.first_name[:10]}",
                        callback_data=f"admin_user_detail_{user.id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("⬅️ Back to User Management", callback_data="admin_users")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_view_users: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading users.")

async def admin_user_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View user details"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.replace('admin_user_detail_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
            
            # Get user orders
            orders = db.query(Order).filter(Order.user_id == user.id).order_by(desc(Order.created_at)).limit(5).all()
            
            # Get custom requests
            requests = db.query(CustomRequest).filter(CustomRequest.user_id == user.id).order_by(desc(CustomRequest.created_at)).limit(3).all()
            
            admin_status = "✅ Admin" if user.is_admin else "❌ Not Admin"
            dev_status = "✅ Developer" if user.is_developer else "❌ Not Developer"
            
            text = f"""
👤 *USER DETAILS*

*Name:* {user.first_name} {user.last_name or ''}
*Username:* @{user.username or 'N/A'}
*Telegram ID:* {user.telegram_id}
*Email:* {user.email or 'Not provided'}
*Phone:* {user.phone or 'Not provided'}
*Joined:* {user.created_at.strftime('%Y-%m-%d %H:%M')}
*Last Updated:* {user.updated_at.strftime('%Y-%m-%d %H:%M')}

*Status:*
{admin_status}
{dev_status}

*Balance:* ${user.balance:.2f}
*Total Orders:* {user.total_orders}

*Recent Orders:*
"""
            
            if not orders:
                text += "No orders yet.\n"
            else:
                for order in orders:
                    bot = db.query(Bot).filter(Bot.id == order.bot_id).first() if order.bot_id else None
                    bot_name = bot.name if bot else "Custom Software"
                    status_emoji = "✅" if order.status == OrderStatus.COMPLETED else "⏳" if order.status == OrderStatus.PENDING_REVIEW else "📦"
                    text += f"{status_emoji} {order.order_id} - {bot_name} - ${order.amount:.2f}\n"
            
            text += "\n*Recent Custom Requests:*\n"
            if not requests:
                text += "No custom requests.\n"
            else:
                for req in requests:
                    status_emoji = "⏳" if req.status == RequestStatus.NEW else "✅" if req.status == RequestStatus.APPROVED else "❌"
                    text += f"{status_emoji} {req.request_id} - ${req.estimated_price:.2f}\n"
            
            keyboard = []
            
            if not user.is_admin:
                keyboard.append([
                    InlineKeyboardButton("👑 Make Admin", callback_data=f"admin_user_make_admin_{user.id}")
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton("👤 Remove Admin", callback_data=f"admin_user_remove_admin_{user.id}")
                ])
            
            if not user.is_developer:
                keyboard.append([
                    InlineKeyboardButton("👨‍💻 Make Developer", callback_data=f"admin_user_make_dev_{user.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("💵 Add Balance", callback_data=f"admin_user_add_balance_{user.id}"),
                InlineKeyboardButton("📊 User Orders", callback_data=f"admin_user_orders_{user.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_view_users"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_user_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading user details.")

async def admin_user_make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Make user an admin"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.replace('admin_user_make_admin_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
            
            if user.is_admin:
                await query.edit_message_text("❌ User is already an admin.")
                return
            
            user.is_admin = True
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
🎉 *Admin Privileges Granted!*

You have been granted admin privileges in Software Marketplace.

*What you can do now:*
1. Access admin panel with /admin
2. Manage orders, users, and developers
3. Review payments and requests
4. Add/edit software

*Admin Panel:* /admin

Use your new powers responsibly! 👑
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Admin Privileges Granted!*\n\n"
                f"User {user.first_name} (@{user.username or 'N/A'}) is now an admin.\n"
                f"They have been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👤 View User", callback_data=f"admin_user_detail_{user.id}")],
                    [InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_view_users")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error making user admin: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error making user admin.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_user_make_admin: {e}", exc_info=True)

async def admin_user_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove admin privileges from user"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.replace('admin_user_remove_admin_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
            
            if not user.is_admin:
                await query.edit_message_text("❌ User is not an admin.")
                return
            
            user.is_admin = False
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
⚠️ *Admin Privileges Removed*

Your admin privileges in Software Marketplace have been removed.

*What this means:*
1. You can no longer access admin panel
2. You cannot manage orders, users, or developers
3. You cannot review payments or requests

If you believe this is a mistake, please contact support.
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Admin Privileges Removed!*\n\n"
                f"User {user.first_name} (@{user.username or 'N/A'}) is no longer an admin.\n"
                f"They have been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👤 View User", callback_data=f"admin_user_detail_{user.id}")],
                    [InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_view_users")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error removing admin privileges.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_user_remove_admin: {e}", exc_info=True)

# ========== DEVELOPER REQUESTS MANAGEMENT ==========

async def admin_developer_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage developer requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Count requests by status
            pending_count = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.NEW
            ).count()
            
            approved_count = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.APPROVED
            ).count()
            
            rejected_count = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.REJECTED
            ).count()
            
            total_count = pending_count + approved_count + rejected_count
            
            text = f"""
👨‍💻 *DEVELOPER APPLICATIONS MANAGEMENT*

*Statistics:*
⏳ Pending: {pending_count}
✅ Approved: {approved_count}
❌ Rejected: {rejected_count}
📊 Total: {total_count}

*Quick Actions:*
            """
            
            keyboard = [
                [InlineKeyboardButton(f"⏳ Pending ({pending_count})", callback_data="admin_dev_requests_pending")],
                [InlineKeyboardButton(f"✅ Approved ({approved_count})", callback_data="admin_dev_requests_approved")],
                [InlineKeyboardButton(f"❌ Rejected ({rejected_count})", callback_data="admin_dev_requests_rejected")],
                [InlineKeyboardButton("📊 Applications Stats", callback_data="admin_dev_requests_stats")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_developer_requests: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developer requests.")

async def admin_dev_requests_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending developer requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Get pending developer requests
            requests = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.NEW
            ).order_by(DeveloperRequest.created_at.desc()).all()
            
            if not requests:
                text = "📋 *Pending Developer Requests*\n\nNo pending applications."
            else:
                text = f"📋 *Pending Developer Requests*\n\n*Total:* {len(requests)}\n\n"
                
                for req in requests[:10]:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"📝 *Request #{req.id}*\n"
                    text += f"   👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    text += f"   📅 {req.created_at.strftime('%Y-%m-%d')}\n"
                    text += f"   📝 Skills: {req.skills_experience[:50]}...\n\n"
            
            keyboard = []
            for req in requests[:10]:
                user = db.query(User).filter(User.id == req.user_id).first()
                keyboard.append([
                    InlineKeyboardButton(
                        f"👤 {user.first_name[:10]} - Request #{req.id}",
                        callback_data=f"admin_dev_review_{req.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_developer_requests"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_requests_pending: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading pending requests.")

async def admin_dev_review_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Review a specific developer request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_dev_review_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            dev_request = db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            
            if not dev_request:
                await query.edit_message_text("❌ Developer request not found.")
                return
            
            user = db.query(User).filter(User.id == dev_request.user_id).first()
            
            # Calculate application age
            app_age = (datetime.now() - dev_request.created_at).days
            app_age_text = f"{app_age} day{'s' if app_age != 1 else ''}"
            
            text = f"""
📝 *Developer Request Review*

*Request ID:* {dev_request.id}
*Applicant:* {user.first_name} (@{user.username or 'N/A'})
*Telegram ID:* {user.telegram_id}
*Status:* {dev_request.status.value.replace('_', ' ').title()}
*Submitted:* {dev_request.created_at.strftime('%Y-%m-%d %H:%M')}
*Age:* {app_age_text}

*Skills & Experience:*
{dev_request.skills_experience}

*Portfolio/GitHub:*
{dev_request.portfolio_url or 'Not provided'}
{dev_request.github_url or 'Not provided'}

*Hourly Rate:* ${dev_request.hourly_rate:.2f}

*Actions:*
            """
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_dev_approve_{dev_request.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_dev_reject_{dev_request.id}")
                ],
                [
                    InlineKeyboardButton("💬 Add Notes", callback_data=f"admin_dev_notes_{dev_request.id}"),
                    InlineKeyboardButton("📞 Contact User", callback_data=f"admin_dev_contact_{dev_request.id}")
                ],
                [
                    InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_dev_requests_pending"),
                    InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_review_request: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading request details.")

async def admin_dev_approve_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve a developer request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_dev_approve_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            dev_request = db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            
            if not dev_request:
                await query.edit_message_text("❌ Developer request not found.")
                return
            
            user = db.query(User).filter(User.id == dev_request.user_id).first()
            
            # Check if already a developer
            if user.is_developer:
                await query.edit_message_text("❌ User is already a developer.")
                return
            
            # Generate developer ID
            last_dev = db.query(Developer).order_by(desc(Developer.id)).first()
            dev_number = last_dev.id + 1 if last_dev else 1
            developer_id = f"DEV{dev_number:03d}"
            
            # Create developer profile
            developer = Developer(
                user_id=user.id,
                developer_id=developer_id,
                status=DeveloperStatus.ACTIVE,
                is_available=True,
                skills_experience=dev_request.skills_experience,
                hourly_rate=dev_request.hourly_rate or 25.0,
                completed_orders=0,
                rating=0.0,
                earnings=0.0
            )
            
            # Update user and request
            user.is_developer = True
            dev_request.status = RequestStatus.APPROVED
            dev_request.reviewed_by = user.id
            dev_request.reviewed_at = datetime.now()
            
            db.add(developer)
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
🎉 *Congratulations! Your Developer Application Has Been Approved!*

👨‍💻 *Developer ID:* `{developer_id}`
📊 *Status:* ✅ Active
💰 *Earnings:* $0.00 (start earning now!)

*Next Steps:*
1. Use /developer to access your dashboard
2. Set your availability status
3. Start claiming orders
4. Build your reputation

Welcome to the developer team! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Developer Approved!*\n\n"
                f"*Developer ID:* `{developer_id}`\n"
                f"*Name:* {user.first_name}\n"
                f"*Telegram ID:* {user.telegram_id}\n\n"
                f"The user has been notified and can now access the developer dashboard.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 More Requests", callback_data="admin_dev_requests_pending")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error approving developer: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error approving developer request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_approve_request: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing approval.")

async def admin_dev_reject_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject a developer request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_dev_reject_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            dev_request = db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            
            if not dev_request:
                await query.edit_message_text("❌ Developer request not found.")
                return
            
            user = db.query(User).filter(User.id == dev_request.user_id).first()
            
            # Update request status
            dev_request.status = RequestStatus.REJECTED
            dev_request.reviewed_by = user.id
            dev_request.reviewed_at = datetime.now()
            
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
❌ *Developer Application Rejected*

Your developer application has been reviewed and rejected.

*Reason:* Did not meet requirements

*You can:*
1. Improve your skills and reapply in 30 days
2. Contact support for more information
3. Check our requirements at /menu → Become Developer

Thank you for your interest in Software Marketplace.
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"❌ *Developer Request Rejected!*\n\n"
                f"*Applicant:* {user.first_name}\n"
                f"*Telegram ID:* {user.telegram_id}\n\n"
                f"The user has been notified about the rejection.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 More Requests", callback_data="admin_dev_requests_pending")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error rejecting developer: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error rejecting developer request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_reject_request: {e}")

# ========== CUSTOM REQUESTS MANAGEMENT ==========

async def admin_custom_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage custom software requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Count requests by status
            pending_count = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.NEW
            ).count()
            
            in_review_count = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.IN_REVIEW
            ).count()
            
            approved_count = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.APPROVED
            ).count()
            
            rejected_count = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.REJECTED
            ).count()
            
            total_count = pending_count + in_review_count + approved_count + rejected_count
            
            text = f"""
⚙️ *CUSTOM SOFTWARE REQUESTS MANAGEMENT*

*Statistics:*
⏳ Pending: {pending_count}
📝 In Review: {in_review_count}
✅ Approved: {approved_count}
❌ Rejected: {rejected_count}
📊 Total: {total_count}

*Estimated Revenue:* ${sum([req.estimated_price for req in db.query(CustomRequest).all()]):.2f}

*Quick Actions:*
            """
            
            keyboard = [
                [InlineKeyboardButton(f"⏳ Pending ({pending_count})", callback_data="admin_custom_requests_pending")],
                [InlineKeyboardButton(f"📝 In Review ({in_review_count})", callback_data="admin_custom_requests_review")],
                [InlineKeyboardButton(f"✅ Approved ({approved_count})", callback_data="admin_custom_requests_approved")],
                [InlineKeyboardButton(f"❌ Rejected ({rejected_count})", callback_data="admin_custom_requests_rejected")],
                [InlineKeyboardButton("📊 Requests Stats", callback_data="admin_custom_requests_stats")],
                [InlineKeyboardButton("⬅️ Back to Admin", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_requests: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading custom requests.")

async def admin_custom_requests_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show pending custom requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Get pending custom requests
            requests = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.NEW
            ).order_by(CustomRequest.created_at.desc()).all()
            
            if not requests:
                text = "⏳ *Pending Custom Requests*\n\nNo pending custom requests."
            else:
                text = f"⏳ *Pending Custom Requests*\n\n*Total:* {len(requests)}\n\n"
                
                for req in requests[:10]:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"📝 *{req.request_id}*\n"
                    text += f"   👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    text += f"   💰 ${req.estimated_price:.2f}\n"
                    text += f"   📅 {req.created_at.strftime('%Y-%m-%d')}\n"
                    text += f"   🏷️ {req.budget_tier.title()}\n\n"
            
            keyboard = []
            for req in requests[:10]:
                user = db.query(User).filter(User.id == req.user_id).first()
                keyboard.append([
                    InlineKeyboardButton(
                        f"📝 {req.request_id} - ${req.estimated_price:.2f}",
                        callback_data=f"admin_custom_request_detail_{req.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_requests_pending: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading pending custom requests.")

async def admin_custom_request_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View custom request details"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_request_detail_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            if not request:
                await query.edit_message_text("❌ Custom request not found.")
                return
            
            user = db.query(User).filter(User.id == request.user_id).first()
            
            # Calculate request age
            request_age = (datetime.now() - request.created_at).days
            age_text = f"{request_age} day{'s' if request_age != 1 else ''}"
            
            text = f"""
📝 *CUSTOM SOFTWARE REQUEST DETAILS*

*Request ID:* {request.request_id}
*Title:* {request.title}
*Status:* {request.status.value.replace('_', ' ').title()}
*Submitted:* {request.created_at.strftime('%Y-%m-%d %H:%M')}
*Age:* {age_text}

*Customer Info:*
👤 Name: {user.first_name} (@{user.username or 'N/A'})
🆔 Telegram ID: {user.telegram_id}

*Project Details:*
💰 Estimated Price: ${request.estimated_price:.2f}
🏷️ Budget Tier: {request.budget_tier.title()}
📦 Delivery Time: {request.delivery_time}
⏰ Timeline: {request.timeline}

*Description:*
{request.description}

*Features:*
{request.features}
"""
            
            if request.admin_notes:
                text += f"\n*Admin Notes:*\n{request.admin_notes}"
            
            if request.assigned_to:
                assigned_dev = db.query(Developer).filter(Developer.id == request.assigned_to).first()
                if assigned_dev:
                    dev_user = db.query(User).filter(User.id == assigned_dev.user_id).first()
                    text += f"\n*Assigned To:* {dev_user.first_name} ({assigned_dev.developer_id})"
            
            keyboard = []
            
            if request.status == RequestStatus.NEW:
                keyboard.append([
                    InlineKeyboardButton("📝 Mark as In Review", callback_data=f"admin_custom_review_{request.id}"),
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_custom_approve_{request.id}")
                ])
                keyboard.append([
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_custom_reject_{request.id}"),
                    InlineKeyboardButton("👷 Assign Developer", callback_data=f"admin_custom_assign_{request.id}")
                ])
            
            elif request.status == RequestStatus.IN_REVIEW:
                keyboard.append([
                    InlineKeyboardButton("✅ Approve", callback_data=f"admin_custom_approve_{request.id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"admin_custom_reject_{request.id}")
                ])
                keyboard.append([
                    InlineKeyboardButton("👷 Assign Developer", callback_data=f"admin_custom_assign_{request.id}")
                ])
            
            elif request.status == RequestStatus.APPROVED and not request.assigned_to:
                keyboard.append([
                    InlineKeyboardButton("👷 Assign Developer", callback_data=f"admin_custom_assign_{request.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("💬 Add Notes", callback_data=f"admin_custom_notes_{request.id}"),
                InlineKeyboardButton("📞 Contact Customer", callback_data=f"admin_custom_contact_{request.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests_pending"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_request_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading custom request details.")

async def admin_custom_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve custom request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_approve_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            if not request:
                await query.edit_message_text("❌ Custom request not found.")
                return
            
            if request.status not in [RequestStatus.NEW, RequestStatus.IN_REVIEW]:
                await query.edit_message_text(f"❌ Request status is {request.status.value}, cannot approve.")
                return
            
            request.status = RequestStatus.APPROVED
            request.admin_notes = f"Approved by admin on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                user = db.query(User).filter(User.id == request.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
✅ *Custom Request Approved!*

Your custom software request has been approved:

📋 Request ID: `{request.request_id}`
💰 Estimated Price: ${request.estimated_price:.2f}
📦 Delivery Time: {request.delivery_time}

*Next Steps:*
1. A developer will be assigned soon
2. Developer will contact you to discuss details
3. Development will begin after agreement

Thank you for choosing Software Marketplace! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Custom Request Approved!*\n\n"
                f"Request `{request.request_id}` has been approved.\n"
                f"Customer has been notified.\n\n"
                f"*Next:* Assign a developer to start the project.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👷 Assign Developer", callback_data=f"admin_custom_assign_{request.id}")],
                    [InlineKeyboardButton("📋 View Request", callback_data=f"admin_custom_request_detail_{request.id}")],
                    [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests_pending")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error approving custom request: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error approving custom request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_approve: {e}", exc_info=True)

# ========== BROADCAST MESSAGE ==========

async def admin_broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start broadcast message process"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
📢 *BROADCAST MESSAGE*

Please send the message you want to broadcast to all users.

*Formatting:* You can use Markdown for formatting.

*Note:* This message will be sent to ALL users.
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data="admin_panel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        return BROADCAST_MESSAGE
        
    except Exception as e:
        logger.error(f"Error in admin_broadcast_start: {e}", exc_info=True)
        return ConversationHandler.END

async def admin_broadcast_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process broadcast message"""
    try:
        if not update.message:
            return BROADCAST_MESSAGE
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return ConversationHandler.END
        
        message = update.message.text
        context.user_data['broadcast_message'] = message
        
        # Show preview
        await update.message.reply_text(
            f"📢 *BROADCAST PREVIEW*\n\n"
            f"{message}\n\n"
            f"*Are you sure you want to send this to all users?*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Yes, Send Now", callback_data="admin_broadcast_confirm"),
                    InlineKeyboardButton("❌ Cancel", callback_data="admin_broadcast_cancel")
                ]
            ])
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in admin_broadcast_process: {e}", exc_info=True)
        return ConversationHandler.END

async def admin_review_custom_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin review custom request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = query.data.replace('review_request_', '')
        
        db = create_session()
        try:
            custom_request = db.query(CustomRequest).filter(
                CustomRequest.request_id == request_id
            ).first()
            
            if not custom_request:
                await query.edit_message_text("❌ Request not found.")
                return
            
            # Check if deposit is paid
            if not custom_request.is_deposit_paid:
                await query.edit_message_text(
                    f"❌ Deposit not paid for request {request_id}\n\n"
                    f"Customer must pay 20% deposit before approval."
                )
                return
            
            user = db.query(User).filter(User.id == custom_request.user_id).first()
            
            text = f"""📋 Review Custom Request

Request ID: {request_id}
Customer: {user.first_name} (@{user.username or 'N/A'})
Title: {custom_request.title}
Total Price: ${custom_request.estimated_price:.2f}
Deposit Paid: ${custom_request.deposit_paid:.2f} ✅
Delivery Time: {custom_request.delivery_time}
Timeline: {custom_request.timeline}

Description:
{custom_request.description[:500]}...

Features:
{custom_request.features[:500]}...

Budget Tier: {custom_request.budget_tier.title()}

Select action:"""
            
            keyboard = [
                [
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve_request_{request_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject_request_{request_id}")
                ],
                [
                    InlineKeyboardButton("📝 Add Notes", callback_data=f"add_notes_request_{request_id}"),
                    InlineKeyboardButton("📞 Contact Customer", callback_data=f"contact_request_{request_id}")
                ],
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in admin_review_custom_request: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_review_custom_request: {e}", exc_info=True)

async def approve_custom_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve custom request (make available to developers)"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = query.data.replace('approve_request_', '')
        
        db = create_session()
        try:
            custom_request = db.query(CustomRequest).filter(
                CustomRequest.request_id == request_id
            ).first()
            
            if not custom_request:
                await query.edit_message_text("❌ Request not found.")
                return
            
            # Check if deposit is paid
            if not custom_request.is_deposit_paid:
                await query.edit_message_text(
                    f"❌ Cannot approve. Deposit not paid for request {request_id}."
                )
                return
            
            # Update status
            custom_request.status = RequestStatus.APPROVED
            db.commit()
            
            # Notify user
            user = db.query(User).filter(User.id == custom_request.user_id).first()
            if user:
                from telegram import Bot
                from config import TELEGRAM_TOKEN
                
                if TELEGRAM_TOKEN:
                    bot = Bot(token=TELEGRAM_TOKEN)
                    
                    message = f"""✅ Custom Request Approved!

📋 Request ID: {request_id}
📝 Title: {custom_request.title}
💰 Total Price: ${custom_request.estimated_price:.2f}
📊 Deposit Paid: ${custom_request.deposit_paid:.2f}
📅 Approved: {datetime.now().strftime('%Y-%m-%d %H:%M')}

Great news! Your custom request has been approved.

What happens next:
1. Your request is now available to all developers
2. Developers can view and claim your project
3. Once claimed, development will begin
4. You'll be notified of all updates

Thank you for choosing our platform! 🚀"""
                    
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=message
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ Request {request_id} approved and made available to developers."
            )
            
        except Exception as e:
            logger.error(f"Error in approve_custom_request: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error approving request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in approve_custom_request: {e}", exc_info=True)

async def admin_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Confirm and send broadcast"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        message = context.user_data.get('broadcast_message')
        if not message:
            await query.edit_message_text("❌ No message found. Please try again.")
            return
        
        # Send to all users
        db = create_session()
        try:
            users = db.query(User).all()
            total_users = len(users)
            successful = 0
            failed = 0
            
            await query.edit_message_text(f"📤 Sending broadcast to {total_users} users...")
            
            from telegram import Bot as TelegramBot
            from telegram.error import TelegramError
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = TelegramBot(token=TELEGRAM_TOKEN)
                
                for user in users:
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"📢 *Broadcast from Admin*\n\n{message}",
                            parse_mode='Markdown'
                        )
                        successful += 1
                    except TelegramError as e:
                        logger.error(f"Failed to send to user {user.telegram_id}: {e}")
                        failed += 1
                    
                    # Small delay to avoid rate limiting
                    import asyncio
                    await asyncio.sleep(0.1)
            
            # Clear context
            context.user_data.pop('broadcast_message', None)
            
            await query.edit_message_text(
                f"✅ *Broadcast Completed!*\n\n"
                f"📤 Total Users: {total_users}\n"
                f"✅ Successful: {successful}\n"
                f"❌ Failed: {failed}\n\n"
                f"Message has been sent to all users.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_broadcast_confirm: {e}", exc_info=True)
        await query.edit_message_text("❌ Error sending broadcast.")

async def admin_broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel broadcast"""
    try:
        query = update.callback_query
        await query.answer()
        
        context.user_data.pop('broadcast_message', None)
        
        await query.edit_message_text(
            "❌ Broadcast cancelled.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Error in admin_broadcast_cancel: {e}", exc_info=True)

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any admin conversation"""
    try:
        # Clear all context data
        context.user_data.clear()
        
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "❌ Operation cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
        elif update.message:
            await update.message.reply_text(
                "❌ Operation cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in admin_cancel: {e}", exc_info=True)
        return ConversationHandler.END

async def admin_dev_approve_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Approve a developer request - FIXED VERSION"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_dev_approve_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            dev_request = db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            
            if not dev_request:
                await query.edit_message_text("❌ Developer request not found.")
                return
            
            user = db.query(User).filter(User.id == dev_request.user_id).first()
            
            if user.is_developer:
                await query.edit_message_text("❌ User is already a developer.")
                return
            
            # Generate developer ID
            last_dev = db.query(Developer).order_by(desc(Developer.id)).first()
            dev_number = last_dev.id + 1 if last_dev else 1
            developer_id = f"DEV{dev_number:03d}"
            
            # Create developer profile - REMOVED skills_experience field
            developer = Developer(
                user_id=user.id,
                developer_id=developer_id,
                status=DeveloperStatus.ACTIVE,
                is_available=True,
                # REMOVED: skills_experience=dev_request.skills_experience,
                hourly_rate=dev_request.hourly_rate or 25.0,
                completed_orders=0,
                rating=0.0,
                earnings=0.0,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # Update user and request
            user.is_developer = True
            dev_request.status = RequestStatus.APPROVED
            dev_request.reviewed_by = telegram_id  # Admin who approved
            dev_request.reviewed_at = datetime.now()
            dev_request.updated_at = datetime.now()
            
            db.add(developer)
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
🎉 *Congratulations! Your Developer Application Has Been Approved!*

👨‍💻 *Developer ID:* `{developer_id}`
📊 *Status:* ✅ Active
💰 *Earnings:* $0.00 (start earning now!)
💵 *Hourly Rate:* ${developer.hourly_rate:.2f}

*What you can do now:*
1. Use /developer to access your professional dashboard
2. Check available orders to claim
3. Update your profile and skills
4. Set your availability status
5. Start earning money from development

*Developer Dashboard:* /developer
*Check Available Orders:* Use the developer dashboard

**Welcome to the developer team!** 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Developer Approved!*\n\n"
                f"*Developer ID:* `{developer_id}`\n"
                f"*Name:* {user.first_name}\n"
                f"*Telegram ID:* {user.telegram_id}\n"
                f"*Hourly Rate:* ${developer.hourly_rate:.2f}\n\n"
                f"The user has been notified and can now access the professional developer dashboard.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 More Requests", callback_data="admin_dev_requests_pending")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error approving developer: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error approving developer request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_approve_request: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing approval.")


# ========== CONVERSATION HANDLER ==========

# ========== MISSING HANDLER FUNCTIONS ==========

async def admin_active_developers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show active developers"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            developers = db.query(Developer).filter(
                Developer.status == DeveloperStatus.ACTIVE
            ).order_by(desc(Developer.created_at)).all()
            
            text = "🟢 *ACTIVE DEVELOPERS*\n\n"
            
            if not developers:
                text += "No active developers found."
            else:
                for dev in developers:
                    user = db.query(User).filter(User.id == dev.user_id).first()
                    status_emoji = "🟢"
                    
                    text += f"{status_emoji} *{dev.developer_id}*\n"
                    text += f"   👤 {user.first_name if user else 'N/A'}\n"
                    text += f"   📱 @{user.username or 'N/A'}\n"
                    text += f"   📊 Status: {dev.status.value}\n"
                    text += f"   ✅ Completed Orders: {dev.completed_orders}\n"
                    text += f"   💰 Earnings: ${dev.earnings:.2f}\n"
                    text += f"   ⭐ Rating: {dev.rating:.1f}\n"
                    text += f"   💵 Hourly Rate: ${dev.hourly_rate:.2f}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("📋 View All Developers", callback_data="admin_view_developers")],
                [InlineKeyboardButton("⬅️ Back to Developer Management", callback_data="admin_developers")],
                [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_active_developers: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading active developers.")

async def admin_inactive_developers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show inactive developers"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            developers = db.query(Developer).filter(
                Developer.status == DeveloperStatus.INACTIVE
            ).order_by(desc(Developer.created_at)).all()
            
            text = "🔴 *INACTIVE DEVELOPERS*\n\n"
            
            if not developers:
                text += "No inactive developers found."
            else:
                for dev in developers:
                    user = db.query(User).filter(User.id == dev.user_id).first()
                    status_emoji = "🔴"
                    
                    text += f"{status_emoji} *{dev.developer_id}*\n"
                    text += f"   👤 {user.first_name if user else 'N/A'}\n"
                    text += f"   📱 @{user.username or 'N/A'}\n"
                    text += f"   📊 Status: {dev.status.value}\n"
                    text += f"   ✅ Completed Orders: {dev.completed_orders}\n"
                    text += f"   💰 Earnings: ${dev.earnings:.2f}\n"
                    text += f"   ⭐ Rating: {dev.rating:.1f}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("🟢 Active Developers", callback_data="admin_active_developers")],
                [InlineKeyboardButton("⬅️ Back to Developer Management", callback_data="admin_developers")],
                [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_inactive_developers: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading inactive developers.")

async def admin_remove_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove developer interface"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
➖ *REMOVE DEVELOPER*

Select a developer to remove:
"""
        
        db = create_session()
        try:
            developers = db.query(Developer).order_by(desc(Developer.created_at)).limit(10).all()
            
            keyboard = []
            for dev in developers:
                user = db.query(User).filter(User.id == dev.user_id).first()
                status_emoji = "🟢" if dev.status == DeveloperStatus.ACTIVE else "🟡" if dev.status == DeveloperStatus.BUSY else "🔴"
                keyboard.append([
                    InlineKeyboardButton(
                        f"{status_emoji} {user.first_name[:10]} ({dev.developer_id})",
                        callback_data=f"admin_remove_dev_{dev.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Developer Management", callback_data="admin_developers"),
                InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_remove_developer: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developers.")

async def admin_developer_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer statistics"""
    try:
        query = update.callback_query
        
        # ========== DIAGNOSTIC LOGGING ==========
        print(f"🔍 DEVELOPER STATS HANDLER CALLED!")
        print(f"🔍 Callback data: {query.data}")
        logger.error(f"🔍 DEVELOPER STATS: Called by user {update.effective_user.id}")
        # ========== END DIAGNOSTIC ==========
        
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Developer stats
            total_developers = db.query(Developer).count()
            active_devs = db.query(Developer).filter(Developer.status == DeveloperStatus.ACTIVE).count()
            busy_devs = db.query(Developer).filter(Developer.status == DeveloperStatus.BUSY).count()
            inactive_devs = db.query(Developer).filter(Developer.status == DeveloperStatus.INACTIVE).count()
            
            # Earnings stats
            total_earnings = db.query(func.sum(Developer.earnings)).scalar() or 0
            avg_rating = db.query(func.avg(Developer.rating)).scalar() or 0
            total_orders = db.query(func.sum(Developer.completed_orders)).scalar() or 0
            
            # Top developers
            top_developers = db.query(
                Developer.developer_id,
                Developer.completed_orders,
                Developer.earnings,
                Developer.rating
            ).order_by(desc(Developer.earnings)).limit(5).all()
            
            text = f"""
📊 *DEVELOPER STATISTICS*

*Overview:*
👨‍💻 Total Developers: *{total_developers}*
🟢 Active: *{active_devs}*
🟡 Busy: *{busy_devs}*
🔴 Inactive: *{inactive_devs}*

*Performance:*
💰 Total Earnings: *${total_earnings:.2f}*
✅ Total Orders: *{total_orders}*
⭐ Average Rating: *{avg_rating:.1f}/5.0*

*Top 5 Developers by Earnings:*
"""
            
            for i, (dev_id, orders, earnings, rating) in enumerate(top_developers, 1):
                text += f"{i}. `{dev_id}` - ${earnings:.2f} ({orders} orders, {rating:.1f}⭐)\n"
            
            keyboard = [
                [InlineKeyboardButton("👨‍💻 View All Developers", callback_data="admin_view_developers")],
                [InlineKeyboardButton("🟢 Active Developers", callback_data="admin_active_developers")],
                [InlineKeyboardButton("⬅️ Back to Developer Management", callback_data="admin_developers")],
                [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_developer_stats: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developer statistics.")

# Add the rest of the missing functions (placeholders for now)
async def admin_dev_busy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark developer as busy"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("🟡 Mark developer as busy - Feature coming soon!")

async def admin_dev_deactivate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Deactivate developer"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("🔴 Deactivate developer - Feature coming soon!")

async def admin_dev_activate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Activate developer"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("🟢 Activate developer - Feature coming soon!")

async def admin_dev_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit developer"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("✏️ Edit developer - Feature coming soon!")

async def admin_dev_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Update developer earnings"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("💰 Update developer earnings - Feature coming soon!")

async def admin_dev_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer payout"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("💵 Developer payout - Feature coming soon!")

# Add other missing placeholder functions...
async def admin_orders_completed(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Completed orders"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("✅ Completed orders - Feature coming soon!")

async def admin_orders_cancelled(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancelled orders"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("❌ Cancelled orders - Feature coming soon!")

async def admin_orders_assigned(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Assigned orders"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("👷 Assigned orders - Feature coming soon!")

async def admin_search_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search order"""
    await update.callback_query.answer("Feature coming soon!")
    await update.callback_query.edit_message_text("🔍 Search order - Feature coming soon!")

async def admin_debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug info"""
    await update.callback_query.answer("Debug info coming soon!")
    await update.callback_query.edit_message_text("🔧 Debug info - Feature coming soon!")

# ========== MISSING FUNCTION IMPLEMENTATIONS ==========

async def admin_verified_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show verified payments"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            orders = db.query(Order).filter(
                Order.payment_status == PaymentStatus.VERIFIED
            ).order_by(desc(Order.created_at)).limit(20).all()
            
            text = "✅ *VERIFIED PAYMENTS*\n\n"
            
            if not orders:
                text += "No verified payments found."
            else:
                for order in orders:
                    user = db.query(User).filter(User.id == order.user_id).first()
                    text += f"📦 *{order.order_id}*\n"
                    text += f"   👤 {user.first_name if user else 'Unknown'}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="admin_finance")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_verified_payments: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading verified payments.")

async def admin_rejected_payments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show rejected payments"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            orders = db.query(Order).filter(
                Order.payment_status == PaymentStatus.FAILED
            ).order_by(desc(Order.created_at)).limit(20).all()
            
            text = "❌ *REJECTED PAYMENTS*\n\n"
            
            if not orders:
                text += "No rejected payments found."
            else:
                for order in orders:
                    user = db.query(User).filter(User.id == order.user_id).first()
                    text += f"📦 *{order.order_id}*\n"
                    text += f"   👤 {user.first_name if user else 'Unknown'}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Finance", callback_data="admin_finance")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_rejected_payments: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading rejected payments.")

async def admin_edit_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Edit software - show list"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "✏️ *EDIT SOFTWARE*\n\nSelect software to edit:"
        
        db = create_session()
        try:
            bots = db.query(Bot).order_by(desc(Bot.created_at)).limit(10).all()
            
            keyboard = []
            for bot in bots:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📝 {bot.name} - ${bot.price:.2f}",
                        callback_data=f"admin_bot_edit_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_bots")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_edit_bot: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading software.")

async def admin_disable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Disable software - show list"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "🚫 *DISABLE SOFTWARE*\n\nSelect software to disable:"
        
        db = create_session()
        try:
            bots = db.query(Bot).filter(Bot.is_available == True).order_by(desc(Bot.created_at)).limit(10).all()
            
            keyboard = []
            for bot in bots:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🚫 {bot.name} - ${bot.price:.2f}",
                        callback_data=f"admin_bot_disable_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_bots")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_disable_bot: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading software.")

async def admin_enable_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Enable software - show list"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "✅ *ENABLE SOFTWARE*\n\nSelect software to enable:"
        
        db = create_session()
        try:
            bots = db.query(Bot).filter(Bot.is_available == False).order_by(desc(Bot.created_at)).limit(10).all()
            
            keyboard = []
            for bot in bots:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {bot.name} - ${bot.price:.2f}",
                        callback_data=f"admin_bot_enable_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_bots")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_enable_bot: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading software.")

async def admin_featured_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manage featured software"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            featured_bots = db.query(Bot).filter(Bot.is_featured == True).all()
            non_featured_bots = db.query(Bot).filter(Bot.is_featured == False, Bot.is_available == True).limit(10).all()
            
            text = "⭐ *FEATURED SOFTWARE*\n\n"
            
            if featured_bots:
                text += "*Currently Featured:*\n"
                for bot in featured_bots:
                    text += f"⭐ {bot.name} - ${bot.price:.2f}\n"
            else:
                text += "No featured software.\n"
            
            text += "\n*Make Featured:*\n"
            
            keyboard = []
            for bot in non_featured_bots:
                keyboard.append([
                    InlineKeyboardButton(
                        f"⭐ {bot.name} - ${bot.price:.2f}",
                        callback_data=f"admin_bot_feature_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_bots")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_featured_bots: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading featured software.")

async def admin_bot_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Software analytics overview"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "📊 *SOFTWARE ANALYTICS*\n\nSelect software for detailed analytics:"
        
        db = create_session()
        try:
            bots = db.query(Bot).order_by(desc(Bot.created_at)).limit(10).all()
            
            keyboard = []
            for bot in bots:
                # Get sales count
                sales = db.query(Order).filter(
                    Order.bot_id == bot.id,
                    Order.status == OrderStatus.COMPLETED
                ).count()
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"📊 {bot.name} ({sales} sales)",
                        callback_data=f"admin_bot_analytics_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_bots")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_analytics: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading software analytics.")

async def admin_bot_analytics_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Detailed software analytics"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('admin_bot_analytics_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            # Get sales data
            total_sales = db.query(Order).filter(
                Order.bot_id == bot.id,
                Order.status == OrderStatus.COMPLETED
            ).count()
            
            total_revenue = db.query(func.sum(Order.amount)).filter(
                Order.bot_id == bot.id,
                Order.status == OrderStatus.COMPLETED
            ).scalar() or 0
            
            # Last 30 days sales
            thirty_days_ago = datetime.now() - timedelta(days=30)
            recent_sales = db.query(Order).filter(
                Order.bot_id == bot.id,
                Order.status == OrderStatus.COMPLETED,
                Order.created_at >= thirty_days_ago
            ).count()
            
            recent_revenue = db.query(func.sum(Order.amount)).filter(
                Order.bot_id == bot.id,
                Order.status == OrderStatus.COMPLETED,
                Order.created_at >= thirty_days_ago
            ).scalar() or 0
            
            # Monthly breakdown
            monthly_data = []
            for i in range(6):
                month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
                month_end = datetime.now().replace(day=1) - timedelta(days=30*(i-1))
                
                month_sales = db.query(Order).filter(
                    Order.bot_id == bot.id,
                    Order.status == OrderStatus.COMPLETED,
                    Order.created_at >= month_start,
                    Order.created_at < month_end
                ).count()
                
                month_revenue = db.query(func.sum(Order.amount)).filter(
                    Order.bot_id == bot.id,
                    Order.status == OrderStatus.COMPLETED,
                    Order.created_at >= month_start,
                    Order.created_at < month_end
                ).scalar() or 0
                
                monthly_data.append((month_start.strftime('%b %Y'), month_sales, month_revenue))
            
            text = f"""
📊 *SOFTWARE ANALYTICS: {bot.name}*

*Overview:*
🛒 Total Sales: {total_sales}
💰 Total Revenue: ${total_revenue:.2f}
📈 Last 30 Days: {recent_sales} sales (${recent_revenue:.2f})

*Monthly Breakdown:*
"""
            
            for month, sales, revenue in monthly_data:
                text += f"  📅 {month}: {sales} sales (${revenue:.2f})\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Analytics", callback_data="admin_bot_analytics")],
                [InlineKeyboardButton("⬅️ Back to Software", callback_data="admin_bots")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_bot_analytics_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading detailed analytics.")

async def admin_make_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Make user admin - show list"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "👑 *MAKE ADMIN*\n\nSelect user to make admin:"
        
        db = create_session()
        try:
            users = db.query(User).filter(User.is_admin == False).order_by(desc(User.created_at)).limit(10).all()
            
            keyboard = []
            for user in users:
                keyboard.append([
                    InlineKeyboardButton(
                        f"👤 {user.first_name} (@{user.username or 'N/A'})",
                        callback_data=f"admin_user_make_admin_{user.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to User Management", callback_data="admin_users")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_make_admin: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading users.")

async def admin_remove_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove admin - show list"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = "👤 *REMOVE ADMIN*\n\nSelect admin to remove:"
        
        db = create_session()
        try:
            users = db.query(User).filter(User.is_admin == True).order_by(desc(User.created_at)).limit(10).all()
            
            keyboard = []
            for user in users:
                # Don't show super admin
                from config import SUPER_ADMIN_ID
                if str(user.telegram_id) == str(SUPER_ADMIN_ID):
                    continue
                    
                keyboard.append([
                    InlineKeyboardButton(
                        f"👑 {user.first_name} (@{user.username or 'N/A'})",
                        callback_data=f"admin_user_remove_admin_{user.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to User Management", callback_data="admin_users")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_remove_admin: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading admins.")

async def admin_user_activity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User activity overview"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Last 7 days activity
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=7)
            
            daily_activity = []
            for i in range(7):
                date = start_date + timedelta(days=i)
                new_users = db.query(User).filter(func.date(User.created_at) == date).count()
                new_orders = db.query(Order).filter(func.date(Order.created_at) == date).count()
                daily_activity.append((date, new_users, new_orders))
            
            # Most active users (by order count)
            active_users = db.query(
                User.first_name,
                User.username,
                User.telegram_id,
                func.count(Order.id).label('order_count'),
                func.sum(Order.amount).label('total_spent')
            ).join(Order, User.id == Order.user_id).filter(
                Order.status == OrderStatus.COMPLETED
            ).group_by(User.id).order_by(desc('order_count')).limit(10).all()
            
            text = "📊 *USER ACTIVITY*\n\n"
            
            text += "*Last 7 Days:*\n"
            for date, users, orders in daily_activity:
                text += f"  {date.strftime('%b %d')}: {users} new users, {orders} new orders\n"
            
            text += "\n*Most Active Users:*\n"
            for first_name, username, telegram_id, order_count, total_spent in active_users:
                text += f"  👤 {first_name} (@{username or 'N/A'}): {order_count} orders (${total_spent:.2f})\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to User Management", callback_data="admin_users")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_user_activity: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading user activity.")

async def admin_search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search user interface"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        text = """
🔍 *SEARCH USER*

Please use one of these methods:
1. Send /search_user USERNAME to search by username
2. Send /search_id TELEGRAM_ID to search by Telegram ID
3. Send /search_name NAME to search by name

Example: `/search_user @username`
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Back to User Management", callback_data="admin_users")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_search_user: {e}", exc_info=True)
        await query.edit_message_text("❌ Error in search interface.")

async def admin_user_make_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Make user a developer directly"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.replace('admin_user_make_dev_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
            
            if user.is_developer:
                await query.edit_message_text("❌ User is already a developer.")
                return
            
            # Generate developer ID
            last_dev = db.query(Developer).order_by(desc(Developer.id)).first()
            dev_number = last_dev.id + 1 if last_dev else 1
            developer_id = f"DEV{dev_number:03d}"
            
            # Create developer profile
            developer = Developer(
            user_id=user.id,
            developer_id=developer_id,
            status=DeveloperStatus.ACTIVE,
            is_available=True,
            hourly_rate=25.0,
            completed_orders=0,
            rating=0.0,
            earnings=0.0
        )
            user.is_developer = True
            db.add(developer)
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
🎉 *You've been registered as a developer!*

👨‍💻 *Developer ID:* `{developer_id}`
📊 *Status:* ✅ Active
💰 *Earnings:* $0.00 (start earning now!)

*What you can do now:*
1. Use /developer to access your dashboard
2. Check available orders to claim
3. Update your profile and skills
4. Set your availability status
5. Start earning money from development

Welcome to the developer team! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"✅ *Developer Added!*\n\n"
                f"*Developer ID:* `{developer_id}`\n"
                f"*Name:* {user.first_name}\n"
                f"*Telegram ID:* {user.telegram_id}\n\n"
                f"The user has been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👤 View User", callback_data=f"admin_user_detail_{user.id}")],
                    [InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_view_users")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error making user developer: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error making user developer.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_user_make_dev: {e}", exc_info=True)

async def admin_user_add_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add balance to user"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.replace('admin_user_add_balance_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        context.user_data['adding_balance'] = True
        context.user_data['balance_user_id'] = user_id
        
        text = """
💵 *ADD BALANCE*

Please send the amount to add (e.g., 100.50):
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data=f"admin_user_detail_{user_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_user_add_balance: {e}", exc_info=True)

async def admin_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View user's orders"""
    try:
        query = update.callback_query
        await query.answer()
        
        user_id = int(query.data.replace('admin_user_orders_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
            
            orders = db.query(Order).filter(Order.user_id == user.id).order_by(desc(Order.created_at)).all()
            
            text = f"""
📦 *ORDERS FOR {user.first_name}*

*Total Orders:* {len(orders)}
*Total Spent:* ${sum(order.amount for order in orders if order.status == OrderStatus.COMPLETED):.2f}

*Order List:*
"""
            
            if not orders:
                text += "No orders found."
            else:
                for order in orders[:20]:
                    bot = db.query(Bot).filter(Bot.id == order.bot_id).first() if order.bot_id else None
                    status_emoji = "✅" if order.status == OrderStatus.COMPLETED else "⏳" if order.status == OrderStatus.PENDING_REVIEW else "📦"
                    text += f"{status_emoji} *{order.order_id}*\n"
                    text += f"   🚀 {bot.name if bot else 'Custom Software'}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n"
                    text += f"   📊 {order.status.value}\n\n"
            
            keyboard = []
            for order in orders[:10]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 {order.order_id[:8]}... - ${order.amount:.2f}",
                        callback_data=f"admin_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("👤 View User", callback_data=f"admin_user_detail_{user.id}"),
                InlineKeyboardButton("⬅️ Back to Users", callback_data="admin_view_users")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_user_orders: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading user orders.")

async def admin_dev_requests_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show approved developer requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            requests = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.APPROVED
            ).order_by(desc(DeveloperRequest.created_at)).all()
            
            text = "✅ *APPROVED DEVELOPER REQUESTS*\n\n"
            
            if not requests:
                text += "No approved requests found."
            else:
                for req in requests:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"✅ *Request #{req.id}*\n"
                    text += f"   👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    text += f"   📅 Approved: {req.reviewed_at.strftime('%Y-%m-%d') if req.reviewed_at else 'N/A'}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_developer_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_requests_approved: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading approved requests.")

async def admin_dev_requests_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show rejected developer requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            requests = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.REJECTED
            ).order_by(desc(DeveloperRequest.created_at)).all()
            
            text = "❌ *REJECTED DEVELOPER REQUESTS*\n\n"
            
            if not requests:
                text += ("No rejected requests found.")
            else:
                for req in requests:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"❌ *Request #{req.id}*\n"
                    text += f"   👤 {user.first_name} (@{user.username or 'N/A'})\n"
                    text += f"   📅 Rejected: {req.reviewed_at.strftime('%Y-%m-%d') if req.reviewed_at else 'N/A'}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_developer_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_requests_rejected: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading rejected requests.")

async def admin_dev_requests_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer requests statistics"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Count by status
            pending = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.NEW
            ).count()
            
            approved = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.APPROVED
            ).count()
            
            rejected = db.query(DeveloperRequest).filter(
                DeveloperRequest.status == RequestStatus.REJECTED
            ).count()
            
            total = pending + approved + rejected
            
            # Monthly stats
            monthly_stats = []
            for i in range(6):
                month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
                month_end = datetime.now().replace(day=1) - timedelta(days=30*(i-1))
                
                month_total = db.query(DeveloperRequest).filter(
                    DeveloperRequest.created_at >= month_start,
                    DeveloperRequest.created_at < month_end
                ).count()
                
                month_approved = db.query(DeveloperRequest).filter(
                    DeveloperRequest.status == RequestStatus.APPROVED,
                    DeveloperRequest.created_at >= month_start,
                    DeveloperRequest.created_at < month_end
                ).count()
                
                monthly_stats.append((month_start.strftime('%b %Y'), month_total, month_approved))
            
            text = f"""
📊 *DEVELOPER REQUESTS STATISTICS*

*Overall:*
📋 Total Requests: {total}
⏳ Pending: {pending}
✅ Approved: {approved}
❌ Rejected: {rejected}
📈 Approval Rate: {approved/total*100:.1f}% if total > 0 else 0%

*Monthly Breakdown:*
"""
            
            for month, total_req, approved_req in monthly_stats:
                approval_rate = approved_req/total_req*100 if total_req > 0 else 0
                text += f"  📅 {month}: {total_req} requests, {approved_req} approved ({approval_rate:.1f}%)\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_developer_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_requests_stats: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading request statistics.")

async def admin_dev_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add notes to developer request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_dev_notes_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        context.user_data['adding_dev_notes'] = True
        context.user_data['dev_notes_request_id'] = request_id
        
        text = """
📝 *ADD NOTES TO DEVELOPER REQUEST*

Please send your notes:
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data=f"admin_dev_review_{request_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_dev_notes: {e}", exc_info=True)

async def admin_dev_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Contact developer applicant"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_dev_contact_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            dev_request = db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            user = db.query(User).filter(User.id == dev_request.user_id).first()
            
            text = f"""
📞 *CONTACT DEVELOPER APPLICANT*

*Applicant:* {user.first_name} (@{user.username or 'N/A'})
*Telegram ID:* {user.telegram_id}
*Request ID:* #{dev_request.id}

You can contact them directly at @{user.username or 'use Telegram ID'}.
"""
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Request", callback_data=f"admin_dev_review_{request_id}")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_dev_contact: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading contact information.")

async def admin_custom_requests_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show custom requests in review"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            requests = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.IN_REVIEW
            ).order_by(desc(CustomRequest.created_at)).all()
            
            text = "📝 *CUSTOM REQUESTS IN REVIEW*\n\n"
            
            if not requests:
                text += "No requests in review."
            else:
                for req in requests:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"📝 *{req.request_id}*\n"
                    text += f"   👤 {user.first_name}\n"
                    text += f"   💰 ${req.estimated_price:.2f}\n"
                    text += f"   📅 {req.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = []
            for req in requests[:10]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📝 {req.request_id} - ${req.estimated_price:.2f}",
                        callback_data=f"admin_custom_request_detail_{req.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_requests_review: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading requests in review.")

async def admin_custom_requests_approved(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show approved custom requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            requests = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.APPROVED
            ).order_by(desc(CustomRequest.created_at)).all()
            
            text = "✅ *APPROVED CUSTOM REQUESTS*\n\n"
            
            if not requests:
                text += "No approved requests found."
            else:
                total_value = sum(req.estimated_price for req in requests)
                text += f"*Total Value:* ${total_value:.2f}\n"
                text += f"*Count:* {len(requests)}\n\n"
                
                for req in requests[:10]:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"✅ *{req.request_id}*\n"
                    text += f"   👤 {user.first_name}\n"
                    text += f"   💰 ${req.estimated_price:.2f}\n"
                    text += f"   📅 {req.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_requests_approved: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading approved requests.")

async def admin_custom_requests_rejected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show rejected custom requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            requests = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.REJECTED
            ).order_by(desc(CustomRequest.created_at)).all()
            
            text = "❌ *REJECTED CUSTOM REQUESTS*\n\n"
            
            if not requests:
                text += "No rejected requests found."
            else:
                for req in requests[:10]:
                    user = db.query(User).filter(User.id == req.user_id).first()
                    text += f"❌ *{req.request_id}*\n"
                    text += f"   👤 {user.first_name}\n"
                    text += f"   💰 ${req.estimated_price:.2f}\n"
                    text += f"   📅 {req.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_requests_rejected: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading rejected requests.")

async def admin_custom_requests_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Custom requests statistics"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            # Count by status
            pending = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.NEW
            ).count()
            
            in_review = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.IN_REVIEW
            ).count()
            
            approved = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.APPROVED
            ).count()
            
            rejected = db.query(CustomRequest).filter(
                CustomRequest.status == RequestStatus.REJECTED
            ).count()
            
            total = pending + in_review + approved + rejected
            
            # Value by status
            pending_value = db.query(func.sum(CustomRequest.estimated_price)).filter(
                CustomRequest.status == RequestStatus.NEW
            ).scalar() or 0
            
            approved_value = db.query(func.sum(CustomRequest.estimated_price)).filter(
                CustomRequest.status == RequestStatus.APPROVED
            ).scalar() or 0
            
            total_value = pending_value + approved_value
            
            text = f"""
📊 *CUSTOM REQUESTS STATISTICS*

*By Status:*
📋 Total Requests: {total}
⏳ Pending: {pending}
📝 In Review: {in_review}
✅ Approved: {approved}
❌ Rejected: {rejected}

*Estimated Value:*
💰 Pending Value: ${pending_value:.2f}
💰 Approved Value: ${approved_value:.2f}
💰 Total Value: ${total_value:.2f}
"""
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_requests_stats: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading request statistics.")

async def admin_custom_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mark custom request as in review"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_review_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            if not request:
                await query.edit_message_text("❌ Custom request not found.")
                return
            
            request.status = RequestStatus.IN_REVIEW
            request.admin_notes = f"Marked as in review by admin on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            db.commit()
            
            await query.edit_message_text(
                f"📝 *Request Marked as In Review!*\n\n"
                f"Request `{request.request_id}` has been marked as in review.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Request", callback_data=f"admin_custom_request_detail_{request.id}")],
                    [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests_pending")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error marking request as in review: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error updating request status.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_review: {e}", exc_info=True)

async def admin_custom_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject custom request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_reject_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            if not request:
                await query.edit_message_text("❌ Custom request not found.")
                return
            
            request.status = RequestStatus.REJECTED
            request.admin_notes = f"Rejected by admin on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            db.commit()
            
            # Notify user
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                user = db.query(User).filter(User.id == request.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"""
❌ *Custom Request Rejected*

Your custom software request has been rejected:

📋 Request ID: `{request.request_id}`
📝 Title: {request.title}
💰 Estimated Price: ${request.estimated_price:.2f}

*Possible reasons:*
1. Unclear requirements
2. Outside our scope of services
3. Budget constraints

You can submit a new request with more details.
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify user: {e}")
            
            await query.edit_message_text(
                f"❌ *Custom Request Rejected!*\n\n"
                f"Request `{request.request_id}` has been rejected.\n"
                f"Customer has been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Request", callback_data=f"admin_custom_request_detail_{request.id}")],
                    [InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests_pending")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error rejecting custom request: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error rejecting custom request.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_reject: {e}", exc_info=True)

async def admin_custom_assign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Assign custom request to developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_assign_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            if not request:
                await query.edit_message_text("❌ Custom request not found.")
                return
            
            # Get available developers
            developers = db.query(Developer).filter(
                Developer.status == DeveloperStatus.ACTIVE,
                Developer.is_available == True
            ).all()
            
            if not developers:
                await query.edit_message_text(
                    "❌ No available developers.\n\n"
                    "All developers are busy or inactive.\n"
                    "Please wait or add more developers.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("👨‍💻 Add Developer", callback_data="admin_add_developer")],
                        [InlineKeyboardButton("📋 View Request", callback_data=f"admin_custom_request_detail_{request.id}")]
                    ])
                )
                return
            
            text = f"""
👷 *ASSIGN DEVELOPER TO CUSTOM REQUEST*

Select a developer for request:
📋 Request ID: `{request.request_id}`
📝 Title: {request.title}
💰 Estimated Price: ${request.estimated_price:.2f}

*Available Developers:*
"""
            
            keyboard = []
            for dev in developers[:10]:
                user = db.query(User).filter(User.id == dev.user_id).first()
                keyboard.append([
                    InlineKeyboardButton(
                        f"👨‍💻 {user.first_name} ({dev.developer_id}) - Rating: {dev.rating:.1f}⭐",
                        callback_data=f"admin_custom_assign_dev_{request.id}_{dev.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("📋 View Request", callback_data=f"admin_custom_request_detail_{request.id}"),
                InlineKeyboardButton("⬅️ Back to Requests", callback_data="admin_custom_requests_pending")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_assign: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading developers.")

async def admin_custom_notes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add notes to custom request"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_notes_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        context.user_data['adding_custom_notes'] = True
        context.user_data['custom_notes_request_id'] = request_id
        
        text = """
📝 *ADD NOTES TO CUSTOM REQUEST*

Please send your notes:
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data=f"admin_custom_request_detail_{request_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in admin_custom_notes: {e}", exc_info=True)

async def admin_custom_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Contact custom request customer"""
    try:
        query = update.callback_query
        await query.answer()
        
        request_id = int(query.data.replace('admin_custom_contact_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            user = db.query(User).filter(User.id == request.user_id).first()
            
            text = f"""
📞 *CONTACT CUSTOM REQUEST CUSTOMER*

*Customer:* {user.first_name} (@{user.username or 'N/A'})
*Telegram ID:* {user.telegram_id}
*Request ID:* {request.request_id}
*Title:* {request.title}

You can contact them directly at @{user.username or 'use Telegram ID'}.
"""
            
            keyboard = [
                [InlineKeyboardButton("⬅️ Back to Request", callback_data=f"admin_custom_request_detail_{request_id}")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_custom_contact: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading contact information.")

# ========== ADDITIONAL MESSAGE HANDLERS ==========

async def handle_add_balance_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle adding balance via message"""
    try:
        if not update.message:
            return
        
        if not context.user_data.get('adding_balance'):
            return
        
        user_id = context.user_data.get('balance_user_id')
        if not user_id:
            return
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        try:
            amount = float(update.message.text)
            if amount <= 0:
                await update.message.reply_text("❌ Amount must be positive.")
                return
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number (e.g., 100.50)")
            return
        
        db = create_session()
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                await update.message.reply_text("❌ User not found.")
                return
            
            user.balance += amount
            db.commit()
            
            # Clear context
            context.user_data.pop('adding_balance', None)
            context.user_data.pop('balance_user_id', None)
            
            await update.message.reply_text(
                f"✅ *Balance Added!*\n\n"
                f"*User:* {user.first_name}\n"
                f"*Amount Added:* ${amount:.2f}\n"
                f"*New Balance:* ${user.balance:.2f}",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👤 View User", callback_data=f"admin_user_detail_{user.id}")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error adding balance: {e}")
            db.rollback()
            await update.message.reply_text("❌ Error adding balance.")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error in handle_add_balance_message: {e}", exc_info=True)

async def handle_dev_notes_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle developer request notes via message"""
    try:
        if not update.message:
            return
        
        if not context.user_data.get('adding_dev_notes'):
            return
        
        request_id = context.user_data.get('dev_notes_request_id')
        if not request_id:
            return
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        notes = update.message.text
        
        db = create_session()
        try:
            dev_request = db.query(DeveloperRequest).filter(DeveloperRequest.id == request_id).first()
            if not dev_request:
                await update.message.reply_text("❌ Developer request not found.")
                return
            
            dev_request.admin_notes = notes
            db.commit()
            
            # Clear context
            context.user_data.pop('adding_dev_notes', None)
            context.user_data.pop('dev_notes_request_id', None)
            
            await update.message.reply_text(
                f"✅ *Notes Added!*\n\n"
                f"Notes have been added to developer request #{request_id}.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Request", callback_data=f"admin_dev_review_{request_id}")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error adding notes: {e}")
            db.rollback()
            await update.message.reply_text("❌ Error adding notes.")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error in handle_dev_notes_message: {e}", exc_info=True)

async def handle_custom_notes_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle custom request notes via message"""
    try:
        if not update.message:
            return
        
        if not context.user_data.get('adding_custom_notes'):
            return
        
        request_id = context.user_data.get('custom_notes_request_id')
        if not request_id:
            return
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        notes = update.message.text
        
        db = create_session()
        try:
            custom_request = db.query(CustomRequest).filter(CustomRequest.id == request_id).first()
            if not custom_request:
                await update.message.reply_text("❌ Custom request not found.")
                return
            
            custom_request.admin_notes = notes
            db.commit()
            
            # Clear context
            context.user_data.pop('adding_custom_notes', None)
            context.user_data.pop('custom_notes_request_id', None)
            
            await update.message.reply_text(
                f"✅ *Notes Added!*\n\n"
                f"Notes have been added to custom request {custom_request.request_id}.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📋 View Request", callback_data=f"admin_custom_request_detail_{request_id}")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error adding notes: {e}")
            db.rollback()
            await update.message.reply_text("❌ Error adding notes.")
        finally:
            db.close()
        
    except Exception as e:
        logger.error(f"Error in handle_custom_notes_message: {e}", exc_info=True)

async def admin_add_developer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return ConversationHandler.END
        
        context.user_data['adding_developer'] = True
        
        text = """
➕ *ADD NEW DEVELOPER*

Please send the Telegram ID of the user you want to make a developer.

*Instructions:*
1. Ask the user to send /start to the bot first
2. Get their Telegram ID
3. Send it here in the format: `123456789`

*Note:* The user must have used /start at least once.
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data="admin_cancel")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        return ADD_DEVELOPER  # Return the conversation state
        
    except Exception as e:
        logger.error(f"Error in admin_add_developer: {e}", exc_info=True)
        await query.edit_message_text("❌ Error starting add developer process.")
        return ConversationHandler.END

async def admin_add_developer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start adding a new developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return ConversationHandler.END
        
        context.user_data['adding_developer'] = True
        
        text = """
➕ *ADD NEW DEVELOPER*

Please send the Telegram ID of the user you want to make a developer.

*Instructions:*
1. Ask the user to send /start to the bot first
2. Get their Telegram ID
3. Send it here in the format: `123456789`

*Note:* The user must have used /start at least once.
"""
        
        keyboard = [
            [InlineKeyboardButton("⬅️ Cancel", callback_data="admin_developers")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
        return ADD_DEVELOPER
        
    except Exception as e:
        logger.error(f"Error in admin_add_developer_start: {e}", exc_info=True)
        await query.edit_message_text("❌ Error starting add developer process.")
        return ConversationHandler.END

# Also add this function to handle the conversation
async def admin_add_developer_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process adding a new developer"""
    try:
        if not update.message:
            return ADD_DEVELOPER
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return ConversationHandler.END
        
        developer_telegram_id = update.message.text.strip()
        
        if not developer_telegram_id.isdigit():
            await update.message.reply_text("❌ Please send a valid Telegram ID (numbers only).")
            return ADD_DEVELOPER
        
        developer_telegram_id = int(developer_telegram_id)
        
        db = create_session()
        try:
            # Check if user exists
            user = db.query(User).filter(User.telegram_id == str(developer_telegram_id)).first()
            if not user:
                await update.message.reply_text("❌ User not found. Please ask them to use /start first.")
                return ADD_DEVELOPER
            
            # Check if already a developer
            existing_dev = db.query(Developer).filter(Developer.user_id == user.id).first()
            if existing_dev:
                await update.message.reply_text(f"❌ User is already a developer (ID: {existing_dev.developer_id}).")
                return ADD_DEVELOPER
            
            # Generate developer ID
            last_dev = db.query(Developer).order_by(desc(Developer.id)).first()
            dev_number = last_dev.id + 1 if last_dev else 1
            developer_id = f"DEV{dev_number:03d}"
            
            # Create developer
            developer = Developer(
                user_id=user.id,
                developer_id=developer_id,
                status=DeveloperStatus.ACTIVE,
                is_available=True,
                skills_experience="Added by admin",
                hourly_rate=25.0,
                completed_orders=0,
                rating=0.0,
                earnings=0.0
            )
            
            db.add(developer)
            user.is_developer = True
            db.commit()
            
            # Send notification to new developer
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                try:
                    await bot.send_message(
                        chat_id=developer_telegram_id,
                        text=f"""
🎉 *Congratulations!*

You have been registered as a developer!

*Developer ID:* `{developer_id}`
*Status:* ✅ Active
*Earnings:* $0.00 (start earning now!)

*Next Steps:*
1. Use /developer to access your dashboard
2. Set your availability status
3. Start claiming orders
4. Build your reputation

Welcome to the developer team! 🚀
                        """,
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"Failed to notify new developer: {e}")
            
            await update.message.reply_text(
                f"✅ *Developer Added Successfully!*\n\n"
                f"*Developer ID:* `{developer_id}`\n"
                f"*Name:* {user.first_name}\n"
                f"*Telegram ID:* {user.telegram_id}\n"
                f"*Username:* @{user.username or 'N/A'}\n\n"
                f"The developer has been notified.",
                parse_mode='Markdown'
            )
            
            # Clear context
            context.user_data.pop('adding_developer', None)
            
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in admin_add_developer_process: {e}", exc_info=True)
        await update.message.reply_text("❌ Error adding developer.")
        return ConversationHandler.END

# ========== ALSO ADD THESE PLACEHOLDER FUNCTIONS ==========
async def admin_reject_job(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reject job – set status = 'rejected', is_public = False"""
    try:
        query = update.callback_query
        await query.answer()

        job_id = query.data.replace("admin_reject_job_", "")

        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return

        db = create_session()
        try:
            from database.models import Job, User

            job = db.query(Job).filter(Job.job_id == job_id).first()
            if not job:
                await query.edit_message_text("❌ Job not found.")
                return

            # Update job status
            job.status = 'rejected'
            job.is_public = False
            db.commit()

            # Notify the job poster
            user = db.query(User).filter(User.id == job.user_id).first()
            if user:
                from telegram import Bot
                from config import TELEGRAM_TOKEN
                if TELEGRAM_TOKEN:
                    bot = Bot(token=TELEGRAM_TOKEN)
                    try:
                        await bot.send_message(
                            chat_id=user.telegram_id,
                            text=f"""
❌ **Your Job Has Been Rejected**

📋 **Job ID:** `{job.job_id}`
📝 **Title:** {job.title}
💰 **Budget:** ${job.budget:.2f}
⏰ **Timeline:** {job.expected_timeline}

Unfortunately, your job did not meet our guidelines and has been rejected.

**Possible reasons:**
- Unclear or incomplete description
- Budget too low for the scope
- Violation of platform policies

You can edit and resubmit your job with more details.

If you believe this is a mistake, please contact support.
                            """,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user: {e}")

            await query.edit_message_text(
                f"❌ **Job Rejected!**\n\n"
                f"Job `{job.job_id}` has been rejected.\n"
                f"The customer has been notified.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Pending", callback_data="admin_jobs_pending_list")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )

        except Exception as e:
            logger.error(f"Error rejecting job: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error rejecting job.")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Error in admin_reject_job: {e}", exc_info=True)
        await query.edit_message_text("❌ Error rejecting job.")


async def admin_remove_dev(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        developer_id = int(query.data.replace('admin_remove_dev_', ''))
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await query.edit_message_text("❌ Access denied.")
            return
        
        db = create_session()
        try:
            developer = db.query(Developer).filter(Developer.id == developer_id).first()
            if not developer:
                await query.edit_message_text("❌ Developer not found.")
                return
            
            user = db.query(User).filter(User.id == developer.user_id).first()
            user.is_developer = False
            
            db.delete(developer)
            db.commit()
            
            await query.edit_message_text(
                f"✅ *Developer Removed!*\n\n"
                f"Developer `{developer.developer_id}` has been removed.\n"
                f"User {user.first_name} is no longer a developer.",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Developers", callback_data="admin_developers")],
                    [InlineKeyboardButton("🏠 Admin Panel", callback_data="admin_panel")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error removing developer: {e}")
            db.rollback()
            await query.edit_message_text("❌ Error removing developer.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in admin_remove_dev: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing removal.")

# ========== UPDATE THE CONVERSATION HANDLER ==========

def get_admin_conversation_handler():
    """Create admin conversation handlers"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_add_bot_start, pattern='^admin_add_bot$'),
            CallbackQueryHandler(admin_add_developer, pattern='^admin_add_developer$'),
            CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$')
        ],
        states={
            ADD_BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_bot_name)],
            ADD_BOT_DESCRIPTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_bot_description)],
            ADD_BOT_FEATURES: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_bot_features)],
            ADD_BOT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_bot_price)],
            ADD_BOT_CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_bot_category)],
            ADD_BOT_DELIVERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_bot_delivery)],
            ADD_DEVELOPER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_add_developer_process)],  # This was the key fix
            BROADCAST_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_broadcast_process)],
        },
        fallbacks=[
            CallbackQueryHandler(admin_cancel, pattern='^admin_cancel$'),
            CommandHandler('cancel', admin_cancel),
            CallbackQueryHandler(admin_panel, pattern='^admin_panel$')
        ],
        allow_reentry=True
    )

async def handle_admin_workflow_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all admin workflow messages"""
    try:
        if not update.message:
            return
        
        telegram_id = update.effective_user.id
        if not check_admin_access(telegram_id):
            await update.message.reply_text("❌ Access denied.")
            return
        
        # Check which workflow we're in
        if context.user_data.get('adding_balance'):
            user_id = context.user_data.get('balance_user_id')
            if user_id:
                await handle_add_balance_message(update, context)
                return
        
        if context.user_data.get('adding_dev_notes'):
            await handle_dev_notes_message(update, context)
            return
        
        if context.user_data.get('adding_custom_notes'):
            await handle_custom_notes_message(update, context)
            return
        
    except Exception as e:
        logger.error(f"Error in handle_admin_workflow_messages: {e}", exc_info=True)

def register_admin_handlers(application):
    """Register all admin handlers"""
    
    # ========== CRITICAL: CONVERSATION HANDLER MUST BE REGISTERED FIRST ==========
    # This allows ConversationHandler to manage multi-step workflows while
    # letting specific callback handlers work for one-off actions
    admin_conversation = get_admin_conversation_handler()
    application.add_handler(admin_conversation)
    logger.info("✅ ConversationHandler registered FIRST")

    # ========== COMMAND HANDLERS ==========
    from telegram.ext import CommandHandler
    application.add_handler(CommandHandler("admin", admin_command))
    
    # ========== MAIN ADMIN PANEL ==========
    from telegram.ext import CallbackQueryHandler
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^admin_panel$'))
    
    # ========== STATISTICS ==========
    application.add_handler(CallbackQueryHandler(admin_stats, pattern='^admin_stats$'))
    application.add_handler(CallbackQueryHandler(admin_stats_detailed, pattern='^admin_stats_detailed$'))
    
    # ========== ORDER MANAGEMENT ==========
    application.add_handler(CallbackQueryHandler(admin_orders, pattern='^admin_orders$'))
    application.add_handler(CallbackQueryHandler(admin_view_orders, pattern='^admin_view_orders$'))
    application.add_handler(CallbackQueryHandler(admin_order_detail, pattern='^admin_order_detail_'))
    application.add_handler(CallbackQueryHandler(admin_approve_payment, pattern='^admin_approve_payment_'))
    application.add_handler(CallbackQueryHandler(admin_reject_payment, pattern='^admin_reject_payment_'))
    application.add_handler(CallbackQueryHandler(admin_assign_developer, pattern='^admin_assign_developer_'))
    application.add_handler(CallbackQueryHandler(admin_assign_dev_confirm, pattern='^admin_assign_dev_'))
    application.add_handler(CallbackQueryHandler(admin_complete_order, pattern='^admin_complete_order_'))
    application.add_handler(CallbackQueryHandler(admin_orders_pending, pattern='^admin_orders_pending$'))
    application.add_handler(CallbackQueryHandler(admin_orders_completed, pattern='^admin_orders_completed$'))
    application.add_handler(CallbackQueryHandler(admin_orders_cancelled, pattern='^admin_orders_cancelled$'))
    application.add_handler(CallbackQueryHandler(admin_orders_assigned, pattern='^admin_orders_assigned$'))
    application.add_handler(CallbackQueryHandler(admin_search_order, pattern='^admin_search_order$'))
    application.add_handler(CallbackQueryHandler(admin_goto_add_developer, pattern='^admin_goto_add_developer$'))
    
    # ========== DEVELOPER MANAGEMENT ==========
    application.add_handler(CallbackQueryHandler(admin_developers, pattern='^admin_developers$'))
    application.add_handler(CallbackQueryHandler(admin_view_developers, pattern='^admin_view_developers$'))
    application.add_handler(CallbackQueryHandler(admin_developer_detail, pattern='^admin_developer_detail_'))
    application.add_handler(CallbackQueryHandler(admin_active_developers, pattern='^admin_active_developers$'))
    application.add_handler(CallbackQueryHandler(admin_inactive_developers, pattern='^admin_inactive_developers$'))
    application.add_handler(CallbackQueryHandler(admin_remove_developer, pattern='^admin_remove_developer$'))
    application.add_handler(CallbackQueryHandler(admin_developer_stats, pattern='^admin_developer_stats$'))
    application.add_handler(CallbackQueryHandler(admin_dev_busy, pattern='^admin_dev_busy_'))
    application.add_handler(CallbackQueryHandler(admin_dev_deactivate, pattern='^admin_dev_deactivate_'))
    application.add_handler(CallbackQueryHandler(admin_dev_activate, pattern='^admin_dev_activate_'))
    application.add_handler(CallbackQueryHandler(admin_dev_edit, pattern='^admin_dev_edit_'))
    application.add_handler(CallbackQueryHandler(admin_dev_earnings, pattern='^admin_dev_earnings_'))
    application.add_handler(CallbackQueryHandler(admin_dev_payout, pattern='^admin_dev_payout_'))
    application.add_handler(CallbackQueryHandler(admin_remove_dev, pattern='^admin_remove_dev_'))
    
    # ========== FINANCE MANAGEMENT ==========
    application.add_handler(CallbackQueryHandler(admin_finance, pattern='^admin_finance$'))
    application.add_handler(CallbackQueryHandler(admin_finance_overview, pattern='^admin_finance_overview$'))
    application.add_handler(CallbackQueryHandler(admin_pending_payments, pattern='^admin_pending_payments$'))
    application.add_handler(CallbackQueryHandler(admin_verified_payments, pattern='^admin_verified_payments$'))
    application.add_handler(CallbackQueryHandler(admin_rejected_payments, pattern='^admin_rejected_payments$'))
    application.add_handler(CallbackQueryHandler(admin_developer_payouts, pattern='^admin_developer_payouts$'))
    
    # ========== SOFTWARE MANAGEMENT ==========
    application.add_handler(CallbackQueryHandler(admin_bots, pattern='^admin_bots$'))
    application.add_handler(CallbackQueryHandler(admin_view_bots, pattern='^admin_view_bots$'))
    application.add_handler(CallbackQueryHandler(admin_bot_detail, pattern='^admin_bot_detail_'))
    application.add_handler(CallbackQueryHandler(admin_bot_disable, pattern='^admin_bot_disable_'))
    application.add_handler(CallbackQueryHandler(admin_bot_enable, pattern='^admin_bot_enable_'))
    application.add_handler(CallbackQueryHandler(admin_bot_feature, pattern='^admin_bot_feature_'))
    application.add_handler(CallbackQueryHandler(admin_bot_unfeature, pattern='^admin_bot_unfeature_'))
    application.add_handler(CallbackQueryHandler(admin_edit_bot, pattern='^admin_edit_bot$'))
    application.add_handler(CallbackQueryHandler(admin_disable_bot, pattern='^admin_disable_bot$'))
    application.add_handler(CallbackQueryHandler(admin_enable_bot, pattern='^admin_enable_bot$'))
    application.add_handler(CallbackQueryHandler(admin_featured_bots, pattern='^admin_featured_bots$'))
    application.add_handler(CallbackQueryHandler(admin_bot_analytics, pattern='^admin_bot_analytics$'))
    application.add_handler(CallbackQueryHandler(admin_bot_analytics_detail, pattern='^admin_bot_analytics_'))
    
    # ========== USER MANAGEMENT ==========
    application.add_handler(CallbackQueryHandler(admin_users, pattern='^admin_users$'))
    application.add_handler(CallbackQueryHandler(admin_view_users, pattern='^admin_view_users$'))
    application.add_handler(CallbackQueryHandler(admin_user_detail, pattern='^admin_user_detail_'))
    application.add_handler(CallbackQueryHandler(admin_user_make_admin, pattern='^admin_user_make_admin_'))
    application.add_handler(CallbackQueryHandler(admin_user_remove_admin, pattern='^admin_user_remove_admin_'))
    application.add_handler(CallbackQueryHandler(admin_make_admin, pattern='^admin_make_admin$'))
    application.add_handler(CallbackQueryHandler(admin_remove_admin, pattern='^admin_remove_admin$'))
    application.add_handler(CallbackQueryHandler(admin_user_activity, pattern='^admin_user_activity$'))
    application.add_handler(CallbackQueryHandler(admin_search_user, pattern='^admin_search_user$'))
    application.add_handler(CallbackQueryHandler(admin_user_make_dev, pattern='^admin_user_make_dev_'))
    application.add_handler(CallbackQueryHandler(admin_user_add_balance, pattern='^admin_user_add_balance_'))
    application.add_handler(CallbackQueryHandler(admin_user_orders, pattern='^admin_user_orders_'))
    
    # ========== DEVELOPER REQUESTS ==========
    application.add_handler(CallbackQueryHandler(admin_developer_requests, pattern='^admin_developer_requests$'))
    application.add_handler(CallbackQueryHandler(admin_dev_requests_pending, pattern='^admin_dev_requests_pending$'))
    application.add_handler(CallbackQueryHandler(admin_dev_review_request, pattern='^admin_dev_review_'))
    application.add_handler(CallbackQueryHandler(admin_dev_approve_request, pattern='^admin_dev_approve_'))
    application.add_handler(CallbackQueryHandler(admin_dev_reject_request, pattern='^admin_dev_reject_'))
    application.add_handler(CallbackQueryHandler(admin_dev_requests_approved, pattern='^admin_dev_requests_approved$'))
    application.add_handler(CallbackQueryHandler(admin_dev_requests_rejected, pattern='^admin_dev_requests_rejected$'))
    application.add_handler(CallbackQueryHandler(admin_dev_requests_stats, pattern='^admin_dev_requests_stats$'))
    application.add_handler(CallbackQueryHandler(admin_dev_notes, pattern='^admin_dev_notes_'))
    application.add_handler(CallbackQueryHandler(admin_dev_contact, pattern='^admin_dev_contact_'))
    
    # ========== CUSTOM REQUESTS ==========
    application.add_handler(CallbackQueryHandler(admin_custom_requests, pattern='^admin_custom_requests$'))
    application.add_handler(CallbackQueryHandler(admin_custom_requests_pending, pattern='^admin_custom_requests_pending$'))
    application.add_handler(CallbackQueryHandler(admin_custom_request_detail, pattern='^admin_custom_request_detail_'))
    application.add_handler(CallbackQueryHandler(admin_custom_approve, pattern='^admin_custom_approve_'))
    application.add_handler(CallbackQueryHandler(admin_custom_requests_review, pattern='^admin_custom_requests_review$'))
    application.add_handler(CallbackQueryHandler(admin_custom_requests_approved, pattern='^admin_custom_requests_approved$'))
    application.add_handler(CallbackQueryHandler(admin_custom_requests_rejected, pattern='^admin_custom_requests_rejected$'))
    application.add_handler(CallbackQueryHandler(admin_custom_requests_stats, pattern='^admin_custom_requests_stats$'))
    application.add_handler(CallbackQueryHandler(admin_custom_review, pattern='^admin_custom_review_'))
    application.add_handler(CallbackQueryHandler(admin_custom_reject, pattern='^admin_custom_reject_'))
    application.add_handler(CallbackQueryHandler(admin_custom_assign, pattern='^admin_custom_assign_'))
    application.add_handler(CallbackQueryHandler(admin_custom_notes, pattern='^admin_custom_notes_'))
    application.add_handler(CallbackQueryHandler(admin_custom_contact, pattern='^admin_custom_contact_'))
    
        # ========== JOB MANAGEMENT HANDLERS ==========
    application.add_handler(CallbackQueryHandler(admin_job_management, pattern='^admin_job_management$'))
    application.add_handler(CallbackQueryHandler(admin_jobs_pending_list, pattern='^admin_jobs_pending_list$'))
    application.add_handler(CallbackQueryHandler(admin_jobs_approved, pattern='^admin_jobs_approved$'))
    application.add_handler(CallbackQueryHandler(admin_jobs_active, pattern='^admin_jobs_active$'))
    application.add_handler(CallbackQueryHandler(admin_jobs_stats, pattern='^admin_jobs_stats$'))
    application.add_handler(CallbackQueryHandler(admin_jobs_search, pattern='^admin_jobs_search$'))
    application.add_handler(CallbackQueryHandler(admin_review_job, pattern='^admin_review_job_'))
    application.add_handler(CallbackQueryHandler(admin_approve_job, pattern='^admin_approve_job_'))
    application.add_handler(CallbackQueryHandler(admin_reject_job, pattern='^admin_reject_job_'))


    # ========== BROADCAST ==========
    application.add_handler(CallbackQueryHandler(admin_broadcast_start, pattern='^admin_broadcast$'))
    application.add_handler(CallbackQueryHandler(admin_broadcast_confirm, pattern='^admin_broadcast_confirm$'))
    application.add_handler(CallbackQueryHandler(admin_broadcast_cancel, pattern='^admin_broadcast_cancel$'))
    
    # ========== DEBUG/OTHER ==========
    application.add_handler(CallbackQueryHandler(admin_debug, pattern='^admin_debug$'))
    application.add_handler(CallbackQueryHandler(admin_cancel, pattern='^admin_cancel$'))
    
    # ========== MESSAGE HANDLERS FOR ADMIN WORKFLOWS ==========
    from telegram.ext import MessageHandler, filters
    
    # Message handlers for admin workflows
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_admin_workflow_messages
    ))
    
    logger.info("✅ Admin handlers registered successfully - ConversationHandler registered at the TOP")
    return True
