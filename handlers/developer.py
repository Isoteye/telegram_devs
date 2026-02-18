"""
Complete Developer Dashboard
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, CommandHandler
from database.db import create_session
from database.models import User, Developer, Order, OrderStatus, DeveloperStatus, CustomRequest, RequestStatus
import logging
from datetime import datetime
from sqlalchemy import desc

logger = logging.getLogger(__name__)

# Developer conversation states
DEV_EDIT_SKILLS = 1
DEV_EDIT_RATE = 2
DEV_EDIT_PORTFOLIO = 3
DEV_EDIT_GITHUB = 4

async def developer_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Main developer dashboard"""
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
            if not user or not user.is_developer:
                if update.callback_query:
                    await query.edit_message_text("❌ You are not a registered developer.")
                else:
                    await update.message.reply_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                if update.callback_query:
                    await query.edit_message_text("❌ Developer profile not found. Please contact admin.")
                else:
                    await update.message.reply_text("❌ Developer profile not found. Please contact admin.")
                return
            
            assigned_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).count()
            
            completed_orders = developer.completed_orders
            
            pending_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).all()
            
            pending_earnings = sum(order.amount * 0.7 for order in pending_orders)
            
            text = f"""
👨‍💻 DEVELOPER DASHBOARD

👤 Name: {user.first_name}
📊 ID: {developer.developer_id}
📈 Status: {developer.status.value.title()}
💰 Available: {'✅ Yes' if developer.is_available else '❌ No'}

📊 Statistics:
📦 Active Orders: {assigned_orders}
✅ Completed Orders: {completed_orders}
💰 Total Earnings: ${developer.earnings:.2f}
⏳ Pending Earnings: ${pending_earnings:.2f}
⭐ Rating: {developer.rating:.1f}/5.0
💸 Hourly Rate: ${developer.hourly_rate:.2f}

What would you like to do?
"""
            
            keyboard = [ [InlineKeyboardButton("📦 My Orders", callback_data="dev_my_orders")],
    [InlineKeyboardButton("🆕 Available Orders", callback_data="dev_available_orders")],
    [InlineKeyboardButton("📋 My Custom Requests", callback_data="dev_my_custom_requests")],
    [InlineKeyboardButton("💰 Earnings & Payouts", callback_data="dev_earnings")],
    [InlineKeyboardButton("⚙️ Edit Profile", callback_data="dev_edit_profile_start")],
    [InlineKeyboardButton("📊 Update Availability", callback_data="dev_toggle_availability")],
    [InlineKeyboardButton("📊 My Statistics", callback_data="dev_statistics")],
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
        logger.error(f"Error in developer_dashboard: {e}", exc_info=True)
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Error loading developer dashboard.")
        else:
            await update.message.reply_text("❌ Error loading developer dashboard.")

async def dev_my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show developer's assigned orders"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id
            ).order_by(desc(Order.created_at)).all()
            
            text = f"📦 MY ORDERS\n\n"
            
            if not orders:
                text += "No orders assigned yet."
            else:
                for order in orders[:10]:
                    status_emoji = "📦" if order.status == OrderStatus.ASSIGNED else \
                                 "⚙️" if order.status == OrderStatus.IN_PROGRESS else \
                                 "✅" if order.status == OrderStatus.COMPLETED else "📦"
                    
                    customer = db.query(User).filter(User.id == order.user_id).first()
                    bot_name = "Custom Software"
                    if order.bot_id:
                        from database.models import Bot
                        bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                        if bot:
                            bot_name = bot.name
                    
                    text += f"{status_emoji} *{order.order_id}*\n"
                    text += f"   👤 {customer.first_name if customer else 'Unknown'}\n"
                    text += f"   🚀 {bot_name[:30]}\n"
                    text += f"   💰 ${order.amount:.2f}\n"
                    text += f"   📊 {order.status.value.replace('_', ' ').title()}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = []
            for order in orders[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 {order.order_id[:8]}... - ${order.amount:.2f}",
                        callback_data=f"dev_order_detail_{order.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_my_orders: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading orders.")

async def dev_order_detail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order details for developer"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_order_detail_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ This order is not assigned to you.")
                return
            
            customer = db.query(User).filter(User.id == order.user_id).first()
            bot_name = "Custom Software"
            if order.bot_id:
                from database.models import Bot
                bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                if bot:
                    bot_name = bot.name
            
            text = f"""
📦 ORDER DETAILS

*Order ID:* `{order.order_id}`
*Customer:* {customer.first_name} (@{customer.username or 'N/A'})
*Software:* {bot_name}
*Amount:* ${order.amount:.2f}
*Status:* {order.status.value.replace('_', ' ').title()}
*Created:* {order.created_at.strftime('%Y-%m-%d %H:%M')}
*Your Earnings:* ${order.amount * 0.7:.2f} (70%)
"""
            
            if order.developer_notes:
                text += f"\n*Your Notes:* {order.developer_notes}"
            
            if order.admin_notes:
                text += f"\n*Admin Notes:* {order.admin_notes[:200]}..."
            
            keyboard = []
            
            if order.status == OrderStatus.ASSIGNED:
                keyboard.append([
                    InlineKeyboardButton("⚙️ Start Development", callback_data=f"dev_start_order_{order.id}")
                ])
            
            if order.status == OrderStatus.IN_PROGRESS:
                keyboard.append([
                    InlineKeyboardButton("📝 Update Progress", callback_data=f"dev_update_progress_{order.id}"),
                    InlineKeyboardButton("✅ Mark as Completed", callback_data=f"dev_complete_order_{order.id}")
                ])
            
            keyboard.append([
                InlineKeyboardButton("💬 Add Notes", callback_data=f"dev_add_notes_{order.id}"),
                InlineKeyboardButton("📞 Contact Customer", callback_data=f"dev_contact_customer_{order.id}")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Orders", callback_data="dev_my_orders"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_order_detail: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading order details.")

async def dev_start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer starts working on an order"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_start_order_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ This order is not assigned to you.")
                return
            
            if order.status != OrderStatus.ASSIGNED:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, must be 'assigned'.")
                return
            
            order.status = OrderStatus.IN_PROGRESS
            developer.status = DeveloperStatus.BUSY
            db.commit()
            
            from telegram import Bot
            from config import TELEGRAM_TOKEN
            
            if TELEGRAM_TOKEN:
                bot = Bot(token=TELEGRAM_TOKEN)
                customer = db.query(User).filter(User.id == order.user_id).first()
                
                try:
                    await bot.send_message(
                        chat_id=customer.telegram_id,
                        text=f"""
⚙️ *Development Started!*

Your order is now in progress:

📦 Order ID: `{order.order_id}`
👨‍💻 Developer: {user.first_name}
📊 Status: ⚙️ In Progress

The developer has started working on your order. They will keep you updated on progress.

Thank you for your patience! 🚀
                        """
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer: {e}")
            
            await query.edit_message_text(
                f"✅ *Development Started!*\n\n"
                f"Order `{order.order_id}` is now in progress.\n"
                f"Customer has been notified.\n\n"
                f"Remember to update progress regularly.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📝 Update Progress", callback_data=f"dev_update_progress_{order.id}")],
                    [InlineKeyboardButton("📦 View Order", callback_data=f"dev_order_detail_{order.id}")],
                    [InlineKeyboardButton("⬅️ Back to Orders", callback_data="dev_my_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error starting order: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error starting order.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_start_order: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing request.")

async def dev_complete_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer marks order as completed"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = int(query.data.replace('dev_complete_order_', ''))
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                await query.edit_message_text("❌ Order not found.")
                return
            
            if order.assigned_developer_id != developer.id:
                await query.edit_message_text("❌ This order is not assigned to you.")
                return
            
            if order.status != OrderStatus.IN_PROGRESS:
                await query.edit_message_text(f"❌ Order status is {order.status.value}, must be 'in_progress'.")
                return
            
            order.status = OrderStatus.COMPLETED
            order.delivered_at = datetime.now()
            
            developer.completed_orders += 1
            developer.earnings += order.amount * 0.7
            developer.status = DeveloperStatus.ACTIVE
            developer.is_available = True
            
            db.commit()
            
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

Your order has been completed by the developer:

📦 Order ID: `{order.order_id}`
👨‍💻 Developer: {user.first_name}
📊 Status: ✅ Completed
📅 Delivered: {datetime.now().strftime('%Y-%m-%d %H:%M')}

*Next Steps:*
1. Review the delivered software
2. Test all features
3. Provide feedback to the developer
4. Contact support if any issues

Thank you for choosing Software Marketplace! 🚀
                        """
                    )
                except Exception as e:
                    logger.error(f"Failed to notify customer: {e}")
            
            from config import SUPER_ADMIN_ID
            if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
                try:
                    await bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"""
✅ Order Completed by Developer

📦 Order ID: `{order.order_id}`
👨‍💻 Developer: {user.first_name} ({developer.developer_id})
👤 Customer: {customer.first_name}
💰 Amount: ${order.amount:.2f}
💰 Developer Earnings: ${order.amount * 0.7:.2f}

Order marked as completed by developer.
                        """
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")
            
            await query.edit_message_text(
                f"✅ *Order Completed!*\n\n"
                f"Order `{order.order_id}` has been marked as completed.\n"
                f"Customer has been notified.\n"
                f"💰 Earnings added: ${order.amount * 0.7:.2f}\n"
                f"Total Earnings: ${developer.earnings:.2f}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📦 View Order", callback_data=f"dev_order_detail_{order.id}")],
                    [InlineKeyboardButton("💰 My Earnings", callback_data="dev_earnings")],
                    [InlineKeyboardButton("⬅️ Back to Orders", callback_data="dev_my_orders")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error completing order: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error completing order.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_complete_order: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing request.")

async def dev_earnings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show developer earnings and payout info"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            pending_orders = db.query(Order).filter(
                Order.assigned_developer_id == developer.id,
                Order.status.in_([OrderStatus.ASSIGNED, OrderStatus.IN_PROGRESS])
            ).all()
            
            pending_earnings = sum(order.amount * 0.7 for order in pending_orders)
            
            from config import DEVELOPER_PAYOUT_THRESHOLD
            payout_threshold = DEVELOPER_PAYOUT_THRESHOLD
            
            text = f"""
💰 EARNINGS & PAYOUTS

*Developer ID:* {developer.developer_id}
👤 *Name:* {user.first_name}

📊 *Earnings Summary:*
💰 Available Balance: ${developer.earnings:.2f}
⏳ Pending Earnings: ${pending_earnings:.2f}
💸 Hourly Rate: ${developer.hourly_rate:.2f}
✅ Completed Orders: {developer.completed_orders}

🎯 *Payout Information:*
📈 Payout Threshold: ${payout_threshold:.2f}
📧 Payout Email: {user.email or 'Not set'}

*How payouts work:*
1. Earnings are available after order completion
2. Minimum ${payout_threshold:.2f} required for payout
3. Payouts processed weekly (Friday)
4. Contact admin for payout requests

*Current Status:* {'✅ Eligible for payout' if developer.earnings >= payout_threshold else f'❌ Need ${payout_threshold - developer.earnings:.2f} more'}
"""
            
            keyboard = []
            
            if developer.earnings >= payout_threshold:
                keyboard.append([
                    InlineKeyboardButton("💰 Request Payout", callback_data="dev_request_payout")
                ])
            
            keyboard.append([
                InlineKeyboardButton("📧 Update Email", callback_data=f"dev_update_email_{user.id}"),
                InlineKeyboardButton("💸 Update Rate", callback_data="dev_edit_rate")
            ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_earnings: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading earnings information.")

async def dev_edit_profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing developer profile"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            text = f"""
⚙️ EDIT DEVELOPER PROFILE

Current Information:
👤 Name: {user.first_name}
📊 ID: {developer.developer_id}
💸 Hourly Rate: ${developer.hourly_rate:.2f}
📝 Skills: {developer.skills_experience[:100] if developer.skills_experience else 'Not set'}...
🔗 Portfolio: {developer.portfolio_url or 'Not set'}
🐙 GitHub: {developer.github_url or 'Not set'}

Select what you want to edit:
"""
            
            keyboard = [
                [InlineKeyboardButton("📝 Edit Skills", callback_data="dev_edit_skills")],
                [InlineKeyboardButton("💸 Edit Hourly Rate", callback_data="dev_edit_rate")],
                [InlineKeyboardButton("🔗 Edit Portfolio URL", callback_data="dev_edit_portfolio")],
                [InlineKeyboardButton("🐙 Edit GitHub URL", callback_data="dev_edit_github")],
                [
                    InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_edit_profile_start: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading profile editor.")

async def dev_edit_skills_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing skills"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            current_skills = developer.skills_experience or "Not set"
            
            text = f"""
📝 EDIT SKILLS & EXPERIENCE

Current Skills:
{current_skills}

Please send your updated skills and experience:

Include:
• Programming languages
• Frameworks
• Years of experience
• Projects you've built
• Any certifications
"""
            
            await query.edit_message_text(text)
            
            context.user_data['editing_skills'] = True
            return DEV_EDIT_SKILLS
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_edit_skills_start: {e}", exc_info=True)
        await query.edit_message_text("❌ Error starting skills editor.")
        return ConversationHandler.END

async def dev_edit_skills_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process skills update"""
    try:
        if not update.message:
            return DEV_EDIT_SKILLS
        
        new_skills = update.message.text
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await update.message.reply_text("❌ You are not a registered developer.")
                return ConversationHandler.END
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await update.message.reply_text("❌ Developer profile not found.")
                return ConversationHandler.END
            
            developer.skills_experience = new_skills
            db.commit()
            
            context.user_data.pop('editing_skills', None)
            
            await update.message.reply_text(
                "✅ Skills updated successfully!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Profile", callback_data="dev_edit_profile_start")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error updating skills: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error updating skills.")
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in dev_edit_skills_process: {e}", exc_info=True)
        return ConversationHandler.END

async def dev_edit_rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start editing hourly rate"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            current_rate = developer.hourly_rate
            
            text = f"""
💸 EDIT HOURLY RATE

Current Rate: ${current_rate:.2f}/hour

Please send your new hourly rate in USD:

Example: 25.00, 35.50, 50.00

*Note:* This rate will be used for future custom requests.
"""
            
            await query.edit_message_text(text)
            
            context.user_data['editing_rate'] = True
            return DEV_EDIT_RATE
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_edit_rate_start: {e}", exc_info=True)
        await query.edit_message_text("❌ Error starting rate editor.")
        return ConversationHandler.END

async def dev_edit_rate_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process hourly rate update"""
    try:
        if not update.message:
            return DEV_EDIT_RATE
        
        try:
            new_rate = float(update.message.text)
            if new_rate < 5.0:
                await update.message.reply_text("❌ Rate must be at least $5.00/hour.")
                return DEV_EDIT_RATE
            if new_rate > 500.0:
                await update.message.reply_text("❌ Rate cannot exceed $500.00/hour.")
                return DEV_EDIT_RATE
        except ValueError:
            await update.message.reply_text("❌ Please enter a valid number (e.g., 25.00).")
            return DEV_EDIT_RATE
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await update.message.reply_text("❌ You are not a registered developer.")
                return ConversationHandler.END
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await update.message.reply_text("❌ Developer profile not found.")
                return ConversationHandler.END
            
            developer.hourly_rate = new_rate
            db.commit()
            
            context.user_data.pop('editing_rate', None)
            
            await update.message.reply_text(
                f"✅ Hourly rate updated to ${new_rate:.2f}/hour!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Profile", callback_data="dev_edit_profile_start")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error updating rate: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error updating rate.")
        finally:
            db.close()
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in dev_edit_rate_process: {e}", exc_info=True)
        return ConversationHandler.END

async def dev_toggle_availability(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Toggle developer availability"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            developer.is_available = not developer.is_available
            
            if developer.is_available:
                developer.status = DeveloperStatus.ACTIVE
            else:
                developer.status = DeveloperStatus.BUSY
            
            db.commit()
            
            status = "✅ Available" if developer.is_available else "❌ Busy"
            
            await query.edit_message_text(
                f"✅ Availability updated!\n\n"
                f"Your status is now: {status}\n\n"
                f"{'✅ You will receive new order assignments.' if developer.is_available else '❌ You will not receive new assignments.'}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Dashboard", callback_data="dev_dashboard")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error toggling availability: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error updating availability.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_toggle_availability: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing request.")

async def dev_request_payout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Request payout"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await query.edit_message_text("❌ Developer profile not found.")
                return
            
            if not user.email:
                await query.edit_message_text(
                    "❌ Please set your email address first.\n\n"
                    "We need your email to process payouts.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📧 Set Email", callback_data=f"dev_update_email_{user.id}")],
                        [InlineKeyboardButton("⬅️ Back", callback_data="dev_earnings")]
                    ])
                )
                return
            
            from telegram import Bot
            from config import TELEGRAM_TOKEN, SUPER_ADMIN_ID
            
            if TELEGRAM_TOKEN and SUPER_ADMIN_ID:
                bot = Bot(token=TELEGRAM_TOKEN)
                
                try:
                    await bot.send_message(
                        chat_id=SUPER_ADMIN_ID,
                        text=f"""
💰 PAYOUT REQUEST

👨‍💻 Developer: {user.first_name} ({developer.developer_id})
📧 Email: {user.email}
💰 Amount: ${developer.earnings:.2f}
📊 Completed Orders: {developer.completed_orders}

To process payout:
1. Go to Admin Panel → Developer Payouts
2. Find developer: {developer.developer_id}
3. Click "Process Payout"
4. Update developer earnings to $0.00 after payment
                        """
                    )
                except Exception as e:
                    logger.error(f"Failed to notify admin: {e}")
            
            await query.edit_message_text(
                f"✅ Payout Request Sent!\n\n"
                f"💰 Amount: ${developer.earnings:.2f}\n"
                f"📧 Email: {user.email}\n\n"
                f"Our admin team has been notified and will process your payout within 3-5 business days.\n\n"
                f"Thank you for your work! 👨‍💻",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ Back to Earnings", callback_data="dev_earnings")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            
        except Exception as e:
            logger.error(f"Error requesting payout: {e}", exc_info=True)
            await query.edit_message_text("❌ Error requesting payout.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_request_payout: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing request.")

async def dev_update_email_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start updating email"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                await query.edit_message_text("❌ User not found.")
                return
            
            current_email = user.email or "Not set"
            
            text = f"""
📧 UPDATE EMAIL

Current Email: {current_email}

Please send your email address for payouts:

*Important:* This email will be used for:
• Payment notifications
• Payout processing
• Account recovery
"""
            
            await query.edit_message_text(text)
            
            # The email will be handled by the main.py message handler
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in dev_update_email_start: {e}", exc_info=True)
        await query.edit_message_text("❌ Error starting email update.")

async def handle_dev_available_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle developer available orders callback"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        from database.db import create_session
        from database.models import User, Order, OrderStatus, Bot
        
        db = create_session()
        try:
            # Check if user is developer
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            if not user or not user.is_developer:
                await query.edit_message_text("❌ You are not a registered developer.")
                return
            
            # Get available orders (approved but not assigned)
            available_orders = db.query(Order).filter(
                Order.status == OrderStatus.APPROVED,
                Order.assigned_developer_id == None
            ).order_by(Order.created_at.desc()).limit(10).all()
            
            if not available_orders:
                text = """📦 AVAILABLE ORDERS

No orders available for claiming at the moment.

Orders will appear here when:
1. A customer places an order
2. Admin approves the order
3. No developer has claimed it yet

Check back soon! 🚀"""
            else:
                text = "📦 AVAILABLE ORDERS\n\n"
                text += f"Found {len(available_orders)} orders available for claiming:\n\n"
                
                for order in available_orders:
                    # Get bot name
                    bot_name = "Custom Software"
                    if order.bot_id:
                        bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                        if bot:
                            bot_name = bot.name[:30]
                    
                    # Format amount
                    amount = order.amount if order.amount else 0.0
                    
                    text += f"📦 {order.order_id}\n"
                    text += f"   🚀 {bot_name}\n"
                    text += f"   💰 ${amount:.2f}\n"
                    text += f"   📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
            
            keyboard = []
            
            # Add claim buttons for each order
            for order in available_orders[:5]:  # Show max 5 orders
                amount = order.amount if order.amount else 0.0
                keyboard.append([
                    InlineKeyboardButton(
                        f"📦 Claim {order.order_id[:8]}... - ${amount:.2f}",
                        callback_data=f"claim_order_{order.order_id}"
                    )
                ])
            
            keyboard.extend([
                [InlineKeyboardButton("🔄 Refresh", callback_data="dev_available_orders")],
                [
                    InlineKeyboardButton("⬅️ Developer Dashboard", callback_data="dev_dashboard"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        except Exception as e:
            logger.error(f"Error in handle_dev_available_orders: {e}", exc_info=True)
            await query.edit_message_text("❌ Error loading available orders.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Outer error in handle_dev_available_orders: {e}", exc_info=True)
        try:
            await query.edit_message_text("❌ Error processing request.")
        except:
            pass


async def dev_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel developer conversation"""
    try:
        context.user_data.clear()
        
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            await query.edit_message_text(
                "❌ Operation cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        elif update.message:
            await update.message.reply_text(
                "❌ Operation cancelled.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Error in dev_cancel: {e}", exc_info=True)
        return ConversationHandler.END

def get_developer_conversation_handler():
    """Create developer conversation handlers"""
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(dev_edit_skills_start, pattern='^dev_edit_skills$'),
            CallbackQueryHandler(dev_edit_rate_start, pattern='^dev_edit_rate$'),
        ],
        states={
            DEV_EDIT_SKILLS: [MessageHandler(filters.TEXT & ~filters.COMMAND, dev_edit_skills_process)],
            DEV_EDIT_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, dev_edit_rate_process)],
        },
        fallbacks=[
            CallbackQueryHandler(dev_cancel, pattern='^dev_cancel$'),
            CommandHandler('cancel', dev_cancel),
            CallbackQueryHandler(developer_dashboard, pattern='^dev_dashboard$')
        ],
        allow_reentry=True
    )

def register_developer_handlers(application):
    """Register all developer handlers"""
    # Main developer dashboard
    application.add_handler(CallbackQueryHandler(developer_dashboard, pattern='^dev_dashboard$'))
    
    # Developer orders
    application.add_handler(CallbackQueryHandler(dev_my_orders, pattern='^dev_my_orders$'))
    application.add_handler(CallbackQueryHandler(dev_order_detail, pattern='^dev_order_detail_'))
    application.add_handler(CallbackQueryHandler(dev_start_order, pattern='^dev_start_order_'))
    application.add_handler(CallbackQueryHandler(dev_complete_order, pattern='^dev_complete_order_'))
    
    # Developer profile
    application.add_handler(CallbackQueryHandler(dev_edit_profile_start, pattern='^dev_edit_profile_start$'))
    application.add_handler(CallbackQueryHandler(dev_earnings, pattern='^dev_earnings$'))
    application.add_handler(CallbackQueryHandler(dev_toggle_availability, pattern='^dev_toggle_availability$'))
    application.add_handler(CallbackQueryHandler(dev_request_payout, pattern='^dev_request_payout$'))
    application.add_handler(CallbackQueryHandler(dev_update_email_start, pattern='^dev_update_email_'))
    
    # Add conversation handler
    application.add_handler(get_developer_conversation_handler())