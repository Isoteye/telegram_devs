# handlers/orders.py - Updated
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import User, Order, OrderStatus, Bot
import logging

logger = logging.getLogger(__name__)

async def show_user_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user's orders - SIMPLIFIED without Markdown"""
    try:
        query = update.callback_query
        await query.answer()
        
        telegram_id = update.effective_user.id
        logger.info(f"Getting orders for user: {telegram_id}")
        
        db = create_session()
        try:
            # Get user
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            
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
            
            if not orders:
                text = """
📦 My Orders

You have no orders yet.

🛒 Browse our bots to get started!
                """
                
                keyboard = [
                    [InlineKeyboardButton("🛒 Buy a Bot", callback_data="buy_bot")],
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
            
            for order in orders:
                # Get bot name safely
                bot_name = "Custom Bot"
                try:
                    if order.bot_id:
                        bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                        if bot and bot.name:
                            bot_name = bot.name
                except Exception as e:
                    logger.error(f"Error getting bot name for order {order.order_id}: {e}")
                    bot_name = "Custom Bot"
                
                # Status icon
                status = order.status.value if order.status else "unknown"
                if status in ["pending_payment", "pending_review"]:
                    status_icon = "⏳"
                elif status == "in_progress":
                    status_icon = "⚙️"
                elif status == "completed":
                    status_icon = "✅"
                elif status == "approved":
                    status_icon = "👍"
                elif status == "assigned":
                    status_icon = "👷"
                elif status == "cancelled":
                    status_icon = "❌"
                else:
                    status_icon = "❓"
                
                # Format status text
                status_text = status.replace('_', ' ').title()
                
                # Format amount
                amount = order.amount if order.amount is not None else 0.0
                
                text += f"{status_icon} {order.order_id}\n"
                text += f"  🤖 {bot_name}\n"
                text += f"  💰 ${amount:.2f}\n"
                text += f"  📊 {status_text}\n"
                
                # Date formatting
                if order.created_at:
                    text += f"  📅 {order.created_at.strftime('%Y-%m-%d')}\n\n"
                else:
                    text += f"  📅 Unknown date\n\n"
            
            # Create buttons for each order
            keyboard = []
            for order in orders[:6]:  # Limit to 6 buttons
                amount = order.amount if order.amount is not None else 0.0
                
                button_text = f"📦 {order.order_id}"
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
                f"❌ Error loading orders.\n\nError: {str(e)[:100]}\n\nPlease try again or contact support.",
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
    """Show order details - SIMPLIFIED"""
    try:
        query = update.callback_query
        await query.answer()
        
        order_id = query.data.replace('order_', '')
        logger.info(f"Getting order details: {order_id}")
        
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
            
            # Get bot info safely
            bot_info = ""
            if order.bot_id:
                bot = db.query(Bot).filter(Bot.id == order.bot_id).first()
                if bot:
                    bot_price = bot.price if bot.price is not None else 0.0
                    bot_info = f"""
Bot: {bot.name}
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
            
            text = f"""
📋 Order Details

Order ID: {order.order_id}
Customer: {user.first_name if user else 'Unknown'}
Status: {status_text}
Amount: ${amount:.2f}
Created: {created_date}
{bot_info}
"""
            
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
                f"❌ Error loading order details: {str(e)[:100]}",
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