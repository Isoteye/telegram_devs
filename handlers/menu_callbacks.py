import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
logger = logging.getLogger(__name__)
from utils.helpers import get_request_status_enum

async def handle_menu_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu_main callback"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        text = """🚀 SOFTWARE MARKETPLACE - MAIN MENU

Select an option:"""
        
        keyboard = [
            [InlineKeyboardButton("🛒 Buy Software", callback_data="buy_bot")],
            [InlineKeyboardButton("⚙️ Request Custom Software", callback_data="start_custom_request")],
            [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")],
            [InlineKeyboardButton("⭐ Featured Software", callback_data="featured_bots")],
            [InlineKeyboardButton("💼 Become Developer", callback_data="start_developer_application")],
             [InlineKeyboardButton("📝 Post a Job", callback_data="post_job")],
            [InlineKeyboardButton("📞 Support", callback_data="support")],
             [InlineKeyboardButton("🔍 Browse Jobs", callback_data="job_board")],
           [InlineKeyboardButton("👨‍💻 My Jobs", callback_data="my_jobs")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ]
        
        # Try to get user info, but don't fail if there's an error
        try:
            from database.db import create_session
            from database.models import User
            
            db = create_session()
            try:
                user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
                
                if user:
                    # Add admin button if user is admin
                    if user.is_admin:
                        keyboard.insert(0, [InlineKeyboardButton("👑 Admin Panel", callback_data="admin_panel")])
                    
                    # Add developer button if user is developer
                    if user.is_developer:
                        keyboard.append([InlineKeyboardButton("👨‍💻 Developer Dashboard", callback_data="dev_dashboard")])
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Could not check user permissions for menu: {e}")
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
            
    except Exception as e:
        logger.error(f"Error in handle_menu_main: {e}")
        try:
            await query.edit_message_text("❌ Error loading menu. Please try /menu command.")
        except:
            pass

async def handle_buy_bot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buy_software callback"""
    try:
        query = update.callback_query
        await query.answer()
        
        from database.db import create_session
        from database.models import Bot
        
        db = create_session()
        try:
            # Get categories
            categories = db.query(Bot.category).distinct().filter(Bot.is_available == True).all()
            categories = [cat[0] for cat in categories if cat[0]]
            
            if not categories:
                text = """🛒 BUY SOFTWARE

No categories available yet.

Please check back later or contact support."""
                
                await query.edit_message_text(
                    text,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            text = """🛒 BUY SOFTWARE

Select a category:"""
            
            keyboard = []
            for category in categories:
                # Count software in category
                count = db.query(Bot).filter(
                    Bot.category == category, 
                    Bot.is_available == True
                ).count()
                
                keyboard.append([
                    InlineKeyboardButton(
                        f"📁 {category} ({count})",
                        callback_data=f"category_{category}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_buy_bot: {e}")
        await query.edit_message_text("❌ Error loading categories. Please try again.")

async def show_bot_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show software in category"""
    try:
        query = update.callback_query
        await query.answer()
        
        category = query.data.replace('category_', '')
        
        from database.db import create_session
        from database.models import Bot
        
        db = create_session()
        try:
            bots = db.query(Bot).filter(
                Bot.category == category,
                Bot.is_available == True
            ).all()
            
            if not bots:
                await query.edit_message_text(
                    f"🚀 No software found in category: {category}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Back to Categories", callback_data="buy_bot")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            text = f"🚀 Software in {category}\n\n"
            
            for bot in bots:
                text += f"{bot.name}\n"
                text += f"💰 ${bot.price:.2f}\n"
                text += f"🚀 {bot.delivery_time}\n\n"
            
            # Create buttons for each software
            keyboard = []
            for bot in bots[:10]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🚀 {bot.name[:20]} - ${bot.price:.2f}",
                        callback_data=f"view_bot_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Categories", callback_data="buy_bot"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_bot_categories: {e}")
        await query.edit_message_text("❌ Error loading software. Please try again.")

async def show_bot_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show software details"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('view_bot_', ''))
        
        from database.db import create_session
        from database.models import Bot
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            text = f"""🚀 {bot.name}

{bot.description}

⚡ Features:
{bot.features}

💰 Price: ${bot.price:.2f}
⏱️ Delivery: {bot.delivery_time}
📂 Category: {bot.category}"""
            
            keyboard = [
                [InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_options_{bot.id}")],
                [
                    InlineKeyboardButton("⬅️ Back to Category", callback_data=f"category_{bot.category}"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_bot_details: {e}")
        await query.edit_message_text("❌ Error loading software details. Please try again.")

async def show_buy_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show payment options for software"""
    try:
        query = update.callback_query
        await query.answer()
        
        bot_id = int(query.data.replace('buy_options_', ''))
        
        from database.db import create_session
        from database.models import Bot
        from config import PAYMENT_METHODS
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            
            if not bot:
                await query.edit_message_text("❌ Software not found.")
                return
            
            text = f"""🛒 Buy {bot.name}

💰 Price: ${bot.price:.2f}
⏱️ Delivery: {bot.delivery_time}

Select a payment method:"""
            
            keyboard = []
            
            # Add Paystack option
            if PAYMENT_METHODS.get('paystack', {}).get('is_active', True):
                keyboard.append([
                    InlineKeyboardButton(
                        "💳 Paystack (Card/Bank/USSD)",
                        callback_data=f"paystack_bot_{bot.id}"
                    )
                ])
            
            # Add bank transfer option
            if PAYMENT_METHODS.get('bank_transfer', {}).get('is_active', True):
                keyboard.append([
                    InlineKeyboardButton(
                        "🏦 Bank Transfer",
                        callback_data=f"bank_transfer_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Software", callback_data=f"view_bot_{bot.id}"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_buy_options: {e}")
        await query.edit_message_text("❌ Error loading payment options. Please try again.")

async def show_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's orders - FIXED VERSION"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        logger.info(f"Getting orders for user: {telegram_id}")
        
        from database.db import create_session
        from database.models import User, Order, Bot, OrderStatus
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            
            if not user:
                logger.warning(f"User not found: {telegram_id}")
                await query.edit_message_text(
                    "❌ Please use /start first to create your account.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            # Get orders
            orders = db.query(Order).filter(
                Order.user_id == user.id
            ).order_by(Order.created_at.desc()).all()
            
            logger.info(f"Found {len(orders)} orders for user {user.id}")
            
            # Update user's total orders count
            user.total_orders = len(orders)
            db.commit()
            
            if not orders:
                text = """📦 My Orders

You have no orders yet.

🛒 Browse our software to get started!"""
                
                keyboard = [
                    [InlineKeyboardButton("🛒 Buy Software", callback_data="buy_bot")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text,
                    reply_markup=reply_markup
                )
                return
            
            # Show orders
            text = f"📦 My Orders\n\n"
            text += f"Total Orders: {len(orders)}\n\n"
            
            for order in orders[:10]:
                # Get software name safely
                bot_name = "Custom Software"
                try:
                    if order.bot_id:
                        bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                        if bot and bot.name:
                            bot_name = bot.name[:30]
                except Exception as e:
                    logger.error(f"Error getting software name for order {order.order_id}: {e}")
                    bot_name = "Custom Software"
                
                # Status icon
                status_icon = "⏳"
                if order.status == OrderStatus.PENDING_PAYMENT:
                    status_icon = "⏳"
                    status_text = "Pending Payment"
                elif order.status == OrderStatus.PENDING_REVIEW:
                    status_icon = "⏳"
                    status_text = "Pending Review"
                elif order.status == OrderStatus.IN_PROGRESS:
                    status_icon = "⚙️"
                    status_text = "In Progress"
                elif order.status == OrderStatus.COMPLETED:
                    status_icon = "✅"
                    status_text = "Completed"
                elif order.status == OrderStatus.APPROVED:
                    status_icon = "👍"
                    status_text = "Approved"
                elif order.status == OrderStatus.ASSIGNED:
                    status_icon = "👷"
                    status_text = "Assigned"
                elif order.status == OrderStatus.CANCELLED:
                    status_icon = "❌"
                    status_text = "Cancelled"
                elif order.status == OrderStatus.REFUNDED:
                    status_icon = "💸"
                    status_text = "Refunded"
                else:
                    status_icon = "❓"
                    status_text = "Unknown"
                
                # Format amount
                amount = order.amount if order.amount is not None else 0.0
                
                # Truncate software name if too long
                display_name = bot_name
                if len(display_name) > 25:
                    display_name = display_name[:22] + "..."
                
                text += f"{status_icon} {order.order_id[:12]}...\n"
                text += f"  🚀 {display_name}\n"
                text += f"  💰 ${amount:.2f}\n"
                text += f"  📊 {status_text}\n"
                
                # Date formatting
                if order.created_at:
                    text += f"  📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
                else:
                    text += f"  📅 Unknown date\n\n"
            
            # Create buttons for each order
            keyboard = []
            for order in orders[:5]:
                amount = order.amount if order.amount is not None else 0.0
                
                button_text = f"📦 {order.order_id[:8]}..."
                button_text += f" - ${amount:.2f}"
                
                if len(button_text) > 40:
                    button_text = button_text[:37] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"order_{order.order_id}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
            
            logger.info(f"Successfully displayed {len(orders)} orders")
            
        except Exception as e:
            logger.error(f"Error in show_user_orders: {e}", exc_info=True)
            
            await query.edit_message_text(
                f"❌ Error loading orders.\n\nPlease try again or contact support.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Outer error in show_user_orders: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ An unexpected error occurred.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )

async def show_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show order details"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = query.data.replace('order_', '')
        logger.info(f"Getting order details: {order_id}")
        
        from database.db import create_session
        from database.models import Order, User, Bot, OrderStatus
        
        db = create_session()
        try:
            order = db.query(Order).filter(Order.order_id == order_id).first()
            
            if not order:
                await query.edit_message_text(
                    f"❌ Order {order_id} not found.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⬅️ My Orders", callback_data="my_orders")]
                    ])
                )
                return
            
            user = db.query(User).filter(User.id == order.user_id).first()
            
            amount = order.amount if order.amount is not None else 0.0
            
            # Get software info safely
            bot_info = ""
            if order.bot_id:
                bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                if bot:
                    bot_price = bot.price if bot.price is not None else 0.0
                    bot_info = f"""
Software: {bot.name}
Price: ${bot_price:.2f}
Delivery: {bot.delivery_time or 'N/A'}
"""
            
            # Status formatting
            if order.status:
                status_text = order.status.value.replace('_', ' ').title()
            else:
                status_text = 'Unknown'
            
            # Date formatting
            if order.created_at:
                created_date = order.created_at.strftime('%Y-%m-%d %H:%M')
            else:
                created_date = 'Unknown'
            
            text = f"""📋 Order Details

Order ID: {order.order_id}
Customer: {user.first_name if user else 'Unknown'}
Status: {status_text}
Amount: ${amount:.2f}
Created: {created_date}
{bot_info}"""
            
            if order.payment_proof_url:
                text += "\nPayment Proof: ✅ Uploaded"
            
            if order.admin_notes:
                text += f"\nAdmin Notes: {order.admin_notes[:100]}..."
            
            if order.developer_notes:
                text += f"\nDeveloper Notes: {order.developer_notes[:100]}..."
            
            # Action buttons
            keyboard = []
            
            if order.status == OrderStatus.PENDING_PAYMENT:
                keyboard.append([
                    InlineKeyboardButton("📸 Upload Payment Proof", callback_data=f"upload_proof_{order.order_id}"),
                ])
            
            keyboard.append([
                InlineKeyboardButton("⬅️ Back to Orders", callback_data="my_orders"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in show_order_details: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading order details.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ My Orders", callback_data="my_orders")]
                ])
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Outer error in show_order_details: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ An error occurred.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ My Orders", callback_data="my_orders")]
            ])
        )

async def show_my_requests(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's custom software requests"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        
        from database.db import create_session
        from database.models import User, CustomRequest
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            
            if not user:
                await query.edit_message_text(
                    "❌ Please use /start first to create your account.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            # Get custom requests
            requests = db.query(CustomRequest).filter(
                CustomRequest.user_id == user.id
            ).order_by(CustomRequest.created_at.desc()).all()
            
            if not requests:
                text = """📋 My Custom Software Requests

You have no custom software requests yet.

⚙️ Create a custom software request to get started!"""
                
                keyboard = [
                    [InlineKeyboardButton("⚙️ Request Custom Software", callback_data="start_custom_request")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    text,
                    reply_markup=reply_markup
                )
                return
            
            # Get enum values
            status_enum = get_request_status_enum()
            
            # Show requests
            text = f"📋 My Custom Software Requests\n\n"
            text += f"Total Requests: {len(requests)}\n\n"
            
            for req in requests[:10]:
                status_icon = "⏳"
                status_text = "Unknown"
                
                if req.status:
                    # Compare status with enum values
                    if status_enum['NEW'] and req.status == status_enum['NEW']:
                        status_icon = "⏳"
                        status_text = "New"
                    elif status_enum['PENDING'] and req.status == status_enum['PENDING']:
                        status_icon = "💰"
                        status_text = "Pending Review"
                    elif status_enum['APPROVED'] and req.status == status_enum['APPROVED']:
                        status_icon = "✅"
                        status_text = "Approved"
                    elif status_enum['REJECTED'] and req.status == status_enum['REJECTED']:
                        status_icon = "❌"
                        status_text = "Rejected"
                    elif status_enum['IN_PROGRESS'] and req.status == status_enum['IN_PROGRESS']:
                        status_icon = "⚙️"
                        status_text = "In Progress"
                    elif status_enum['COMPLETED'] and req.status == status_enum['COMPLETED']:
                        status_icon = "✅"
                        status_text = "Completed"
                    elif status_enum['REFUNDED'] and req.status == status_enum['REFUNDED']:
                        status_icon = "💸"
                        status_text = "Refunded"
                    else:
                        # Try to get the string value
                        try:
                            status_text = req.status.value.replace('_', ' ').title()
                        except:
                            status_text = str(req.status)
                
                # Add deposit status
                deposit_status = "✅ Paid" if req.is_deposit_paid else "❌ Unpaid"
                
                text += f"{status_icon} {req.request_id}\n"
                text += f"  📝 {req.title[:30]}{'...' if len(req.title) > 30 else ''}\n"
                text += f"  💰 ${req.estimated_price:.2f}\n"
                text += f"  📊 {status_text}\n"
                text += f"  💳 Deposit: {deposit_status}\n"
                text += f"  📅 {req.created_at.strftime('%Y-%m-%d')}\n\n"
            
            # Create buttons for each request
            keyboard = []
            for req in requests[:5]:
                button_text = f"📋 {req.request_id}"
                button_text += f" - ${req.estimated_price:.2f}"
                
                if len(button_text) > 40:
                    button_text = button_text[:37] + "..."
                
                keyboard.append([
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"request_{req.request_id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("⚙️ New Request", callback_data="start_custom_request"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in show_my_requests: {e}", exc_info=True)
            await query.edit_message_text(
                f"❌ Error loading requests.\n\nPlease try again or contact support.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Outer error in show_my_requests: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ An unexpected error occurred.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )


async def become_developer_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle become developer callback - redirect to application"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Clear any existing context
        context.user_data.clear()
        
        # Call the start_developer_application function
        try:
            from developer_handlers import start_developer_application
            await start_developer_application(update, context)
        except ImportError:
            # Fallback message if developer_handlers is not available
            await query.edit_message_text(
                "👨‍💻 **Become a Developer**\n\n"
                "The developer application system is currently unavailable.\n\n"
                "Please contact @Isope23 for developer registration.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                ])
            )
            
    except Exception as e:
        logger.error(f"Error in become_developer_callback: {e}", exc_info=True)
        await query.edit_message_text(
            "❌ Error starting developer application. Please try again.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show support information"""
    try:
        query = update.callback_query
        await query.answer()
        
        text = """📞 Support

Need help with the Software Marketplace?

Contact Options:
👨‍💻 Support: @Isope23
📧 Email: devtools520@gmail.com
⏰ Hours: 24/7

Common Issues:
1. Payment verification issues
2. Order status questions
3. Custom request status
4. Developer application status
5. Technical problems

Before Contacting:
✅ Check your order status in My Orders
✅ Check your request status in My Requests
✅ Make sure payment is completed
✅ Have your order/request ID ready

We're here to help! 🚀"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            [InlineKeyboardButton("📦 My Orders", callback_data="my_orders")],
            [InlineKeyboardButton("📋 My Requests", callback_data="my_requests")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in show_support: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading support information.")

async def show_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show about information"""
    try:
        query = update.callback_query
        await query.answer()
        
        text = """🚀 About Software Marketplace

Welcome to the premier Software Marketplace!

Our Mission:
To connect businesses with talented developers and provide high-quality software solutions.

Features:
✅ Buy pre-built software instantly
✅ Request custom software development (apps, websites, bots, desktop)
✅ Hire professional developers
✅ Secure payment processing
✅ 24/7 customer support

Types of Software:
🤖 Bots & Automation Tools
🌐 Websites & Web Applications
📱 Mobile Apps (iOS/Android)
💻 Desktop Applications
🔧 Custom Solutions

Security:
🔒 All payments are secure
🔒 Personal data is protected
🔒 Quality guaranteed

Contact:
📧 contact@softwaremarketplace.com

Version: 3.0.0
Last Updated: January 2024"""
        
        keyboard = [
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            [InlineKeyboardButton("📞 Support", callback_data="support")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Error in show_about: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading about information.")

async def show_featured_bots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show featured software"""
    try:
        query = update.callback_query
        await query.answer()
        
        from database.db import create_session
        from database.models import Bot
        
        db = create_session()
        try:
            # Get featured software
            bots = db.query(Bot).filter(
                Bot.is_featured == True,
                Bot.is_available == True
            ).order_by(Bot.created_at.desc()).all()
            
            if not bots:
                await query.edit_message_text(
                    "⭐ No featured software available at the moment.\n\n"
                    "Check back soon for new featured software!",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🛒 Browse All Software", callback_data="buy_bot")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            text = "⭐ Featured Software\n\n"
            
            for bot in bots:
                text += f"{bot.name}\n"
                text += f"💰 ${bot.price:.2f}\n"
                text += f"📦 {bot.delivery_time}\n"
                text += f"{bot.description[:100]}...\n\n"
            
            # Create buttons for each software
            keyboard = []
            for bot in bots[:5]:
                keyboard.append([
                    InlineKeyboardButton(
                        f"⭐ {bot.name[:20]} - ${bot.price:.2f}",
                        callback_data=f"view_bot_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("🛒 Browse All Software", callback_data="buy_bot"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup)
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_featured_bots: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading featured software. Please try again.")


async def generic_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Fallback handler for callback queries that no other handler processed.
    - IGNORES all admin_* callbacks (does NOT answer or edit).
    - Answers and shows an "unavailable" message for other unhandled callbacks.
    """
    query = update.callback_query
    data = query.data

    # ========== CRITICAL: Do NOT interfere with admin callbacks ==========
    if data.startswith("admin_"):
        logger.debug(f"Generic handler ignoring admin callback: {data}")
        return  # ← NO query.answer(), NO editing – admin handler will process

    # ========== Now handle truly unhandled callbacks ==========
    await query.answer()
    logger.warning(f"Unhandled callback: {data}")

    try:
        await query.edit_message_text(
            f"⚠️ Action '{data}' is not available.\n\n"
            "Please use /menu to return to the main menu.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
            ])
        )
    except Exception as e:
        logger.error(f"Error in generic_callback for {data}: {e}")