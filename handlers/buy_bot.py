# handlers/buy_bot.py - COMPLETE PURCHASE FLOW
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import create_session
from database.models import User, Bot, Order, OrderStatus, PaymentMethod
from services.order_service import OrderService
from utils.helpers import generate_order_id
from config import PAYMENT_METHODS
import logging

logger = logging.getLogger(__name__)

async def show_bot_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot categories"""
    try:
        query = update.callback_query
        await query.answer()
        
        db = create_session()
        try:
            # Get all categories from bots
            categories = db.query(Bot.category).distinct().filter(Bot.is_available == True).all()
            categories = [cat[0] for cat in categories if cat[0]]
            
            if not categories:
                await query.edit_message_text(
                    "📂 No categories available yet. Please check back later.",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            text = "📂 *Browse Categories*\n\nSelect a category to view bots:"
            
            keyboard = []
            for category in categories:
                # Count bots in category
                count = db.query(Bot).filter(Bot.category == category, Bot.is_available == True).count()
                keyboard.append([
                    InlineKeyboardButton(
                        f"📁 {category} ({count})",
                        callback_data=f"category_{category}"
                    )
                ])
            
            keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_bot_categories: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading categories. Please try again.")

async def show_bots_in_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bots in selected category"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract category from callback data (category_telegram -> telegram)
        category = query.data.replace('category_', '')
        
        db = create_session()
        try:
            # Get bots in this category
            bots = db.query(Bot).filter(
                Bot.category == category,
                Bot.is_available == True
            ).order_by(Bot.name).all()
            
            if not bots:
                await query.edit_message_text(
                    f"🤖 No bots found in category: {category}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📂 Back to Categories", callback_data="buy_bot")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]
                    ])
                )
                return
            
            text = f"🤖 *Bots in: {category}*\n\n"
            
            for bot in bots:
                text += f"*{bot.name}*\n"
                text += f"💰 ${bot.price:.2f}\n"
                text += f"🚀 {bot.delivery_time}\n\n"
            
            # Create buttons for each bot
            keyboard = []
            for bot in bots[:10]:  # Limit to 10 bots
                keyboard.append([
                    InlineKeyboardButton(
                        f"🤖 {bot.name[:20]} - ${bot.price:.2f}",
                        callback_data=f"bot_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("📂 Back to Categories", callback_data="buy_bot"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_bots_in_category: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading bots. Please try again.")

async def show_bot_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed information about a bot"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract bot ID from callback data (bot_1 -> 1)
        bot_id = int(query.data.replace('bot_', ''))
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            
            if not bot:
                await query.edit_message_text("❌ Bot not found.")
                return
            
            # Format features
            features = ""
            if bot.features:
                if isinstance(bot.features, str):
                    features_list = bot.features.split(',')
                    for feature in features_list:
                        features += f"✅ {feature.strip()}\n"
            
            text = f"""
🤖 *{bot.name}*

{bot.description or 'No description available.'}

⚡ *Features:*
{features}

💰 *Price:* ${bot.price:.2f}
⏱️ *Delivery:* {bot.delivery_time}
📂 *Category:* {bot.category}
            """
            
            keyboard = [
                [InlineKeyboardButton("🛒 Buy Now", callback_data=f"buy_{bot.id}")],
                [
                    InlineKeyboardButton("📂 Back to Category", callback_data=f"category_{bot.category}"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in show_bot_details: {e}", exc_info=True)
        await query.edit_message_text("❌ Error loading bot details. Please try again.")

async def start_payment_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start payment process for selected bot"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract bot ID from callback data (buy_1 -> 1)
        bot_id = int(query.data.replace('buy_', ''))
        
        db = create_session()
        try:
            bot = db.query(Bot).filter(Bot.id == bot_id).first()
            
            if not bot:
                await query.edit_message_text("❌ Bot not found.")
                return
            
            # Store bot ID in context for next step
            context.user_data['selected_bot'] = {
                'id': bot.id,
                'name': bot.name,
                'price': bot.price,
                'category': bot.category
            }
            
            text = f"""
🛒 *Purchase Confirmation*

🤖 Bot: {bot.name}
💰 Price: ${bot.price:.2f}
⏱️ Delivery: {bot.delivery_time}

Please select a payment method:
            """
            
            # Create payment method buttons
            keyboard = []
            for method_key, method_info in PAYMENT_METHODS.items():
                keyboard.append([
                    InlineKeyboardButton(
                        f"💳 {method_info['name']}",
                        callback_data=f"payment_{method_key}_{bot.id}"
                    )
                ])
            
            keyboard.append([
                InlineKeyboardButton("❌ Cancel", callback_data=f"bot_{bot.id}"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in start_payment_process: {e}", exc_info=True)
        await query.edit_message_text("❌ Error starting payment process. Please try again.")

async def handle_payment_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle payment method selection"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract data: payment_mobile_money_1 -> ['mobile_money', '1']
        data_parts = query.data.replace('payment_', '').split('_')
        if len(data_parts) < 2:
            await query.edit_message_text("❌ Invalid payment selection.")
            return
            
        payment_method = data_parts[0]
        bot_id = int(data_parts[1])
        
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
            
            # Generate order ID
            order_id = generate_order_id()
            
            # Create order
            order = Order(
                order_id=order_id,
                user_id=user.id,
                bot_id=bot.id,
                amount=bot.price,
                status=OrderStatus.PENDING_PAYMENT,
                payment_method=PaymentMethod(payment_method)
            )
            
            db.add(order)
            db.commit()
            
            # Get payment method details
            method_details = PAYMENT_METHODS.get(payment_method, {})
            
            text = f"""
✅ *Order Created!*

📦 Order ID: `{order_id}`
🤖 Bot: {bot.name}
💰 Amount: ${bot.price:.2f}
💳 Payment Method: {method_details.get('name', payment_method)}

📋 *Payment Instructions:*
{method_details.get('instructions', 'Please complete payment and upload proof.')}

*Account Details:*
📱 Account: {method_details.get('account', 'Not specified')}
👤 Name: {method_details.get('name', 'Not specified')}

*Important:*
1. Send exactly ${bot.price:.2f}
2. Include Order ID: `{order_id}` in payment reference
3. Upload payment proof after payment
            """
            
            keyboard = [
                [InlineKeyboardButton("📸 Upload Payment Proof", callback_data=f"upload_proof_{order_id}")],
                [
                    InlineKeyboardButton("📦 My Orders", callback_data="my_orders"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")
                ]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
            
        except Exception as e:
            logger.error(f"Error creating order: {e}", exc_info=True)
            db.rollback()
            await query.edit_message_text("❌ Error creating order. Please try again.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_payment_selection: {e}", exc_info=True)
        await query.edit_message_text("❌ Error processing payment selection.")

async def handle_upload_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle request to upload payment proof"""
    try:
        query = update.callback_query
        await query.answer()
        
        # Extract order ID from callback data
        order_id = query.data.replace('upload_proof_', '')
        
        # Store order ID in context for photo handler
        context.user_data['awaiting_payment_proof'] = order_id
        
        text = f"""
📸 *Upload Payment Proof*

Please upload a screenshot or photo of your payment proof for order:

📦 Order ID: `{order_id}`

*Instructions:*
1. Take a screenshot of your payment confirmation
2. Make sure Order ID is visible
3. Upload the image here

*Note:* Only images are accepted.
        """
        
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data=f"order_{order_id}")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in handle_upload_request: {e}", exc_info=True)
        await query.edit_message_text("❌ Error requesting payment proof.")

async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle uploaded payment proof"""
    try:
        if not update.message or not update.message.photo:
            return
        
        order_id = context.user_data.get('awaiting_payment_proof')
        if not order_id:
            await update.message.reply_text("❌ No order specified for payment proof.")
            return
        
        # Get the largest photo file
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        db = create_session()
        try:
            # Find the order
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                await update.message.reply_text("❌ Order not found.")
                return
            
            # Check if user owns this order
            user = db.query(User).filter(User.telegram_id == update.effective_user.id).first()
            if not user or order.user_id != user.id:
                await update.message.reply_text("❌ You don't have permission to upload proof for this order.")
                return
            
            # Update order with payment proof
            order.payment_proof_url = f"telegram_file:{file_id}"
            order.status = OrderStatus.PENDING_REVIEW
            db.commit()
            
            # Clear context
            context.user_data.pop('awaiting_payment_proof', None)
            
            # Send success message
            await update.message.reply_text(
                f"✅ *Payment Proof Uploaded!*\n\n"
                f"📦 Order ID: `{order_id}`\n"
                f"📊 Status: ⏳ Pending Review\n\n"
                f"Our admin team will review your payment and update the status.\n"
                f"You'll be notified once it's verified.",
                parse_mode='Markdown'
            )
            
            # Notify admin (in real implementation, you would notify admin)
            logger.info(f"Payment proof uploaded for order {order_id}")
            
        except Exception as e:
            logger.error(f"Error updating payment proof: {e}", exc_info=True)
            db.rollback()
            await update.message.reply_text("❌ Error uploading payment proof.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in handle_payment_proof: {e}", exc_info=True)
        await update.message.reply_text("❌ Error processing payment proof.")