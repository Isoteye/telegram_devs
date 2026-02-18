import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import logging
logger = logging.getLogger(__name__)

async def developer_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Developer command"""
    try:
        telegram_id = update.effective_user.id
        
        from database.db import create_session
        from database.models import User, Developer
        
        db = create_session()
        try:
            user = db.query(User).filter(User.telegram_id == str(telegram_id)).first()
            if not user or not user.is_developer:
                await update.message.reply_text(
                    "❌ You are not registered as a developer.\n\n"
                    "If you want to become a developer, use /menu → Become Developer\n\n"
                    "**Benefits of becoming a developer:**\n"
                    "✅ Earn money from software development\n"
                    "✅ Work on exciting projects\n"
                    "✅ Build your portfolio\n"
                    "✅ Flexible working hours"
                )
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await update.message.reply_text(
                    "❌ Developer profile not found. Please contact support."
                )
                return
            
            # Show developer dashboard
            try:
                from developer_handlers import developer_dashboard
                await developer_dashboard(update, context)
            except ImportError:
                await update.message.reply_text(
                    f"👨‍💻 Developer Dashboard\n\n"
                    f"Developer ID: {developer.developer_id}\n"
                    f"Status: {developer.status.value if developer.status else 'Active'}\n"
                    f"Earnings: ${developer.earnings:.2f}\n"
                    f"Completed Orders: {developer.completed_orders}\n\n"
                    f"Use /claim ORDER_ID to claim orders."
                )
                
        except Exception as e:
            logger.error(f"Error in developer_command: {e}", exc_info=True)
            await update.message.reply_text("❌ Error loading developer dashboard.")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in developer_command: {e}", exc_info=True)
        await update.message.reply_text("❌ Error loading developer dashboard.")

async def claim_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Claim order command"""
    try:
        if not context.args:
            await update.message.reply_text(
                "Usage: /claim ORDER_ID\n\n"
                "Example: /claim BOT2024011612345678ABCDEF"
            )
            return
        
        order_id = context.args[0]
        
        from database.db import create_session
        from database.models import User, Order, OrderStatus, Developer
        
        db = create_session()
        try:
            # Check if user is developer
            user = db.query(User).filter(User.telegram_id == str(update.effective_user.id)).first()
            if not user or not user.is_developer:
                await update.message.reply_text("❌ You are not a developer.")
                return
            
            developer = db.query(Developer).filter(Developer.user_id == user.id).first()
            if not developer:
                await update.message.reply_text("❌ Developer profile not found.")
                return
            
            # Find order
            order = db.query(Order).filter(Order.order_id == order_id).first()
            if not order:
                await update.message.reply_text(f"❌ Order {order_id} not found.")
                return
            
            if order.status != OrderStatus.APPROVED:
                await update.message.reply_text(f"❌ Order status is {order.status.value}, must be 'approved'.")
                return
            
            if order.assigned_developer_id:
                await update.message.reply_text("❌ Order is already assigned to another developer.")
                return
            
            # Assign order
            order.assigned_developer_id = developer.id
            order.status = OrderStatus.ASSIGNED
            developer.is_available = False
            
            db.commit()
            
            await update.message.reply_text(
                f"✅ Order {order_id} claimed successfully!\n\n"
                f"You can now start working on this order.\n"
                f"Use /developer to check your active orders."
            )
        except Exception as e:
            logger.error(f"Error claiming order: {e}")
            db.rollback()
            await update.message.reply_text("❌ Error claiming order.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in claim_command: {e}")
        await update.message.reply_text("❌ Error processing claim command.")
