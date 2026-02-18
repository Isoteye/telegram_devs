from telegram import Bot
from config import TELEGRAM_TOKEN, ADMIN_IDS
import logging

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        try:
            self.bot = Bot(token=TELEGRAM_TOKEN)
        except Exception as e:
            logger.error(f"Failed to create bot instance: {e}")
            self.bot = None
    
    async def notify_admin(self, message: str, parse_mode: str = "Markdown") -> bool:
        """Send notification to all admins"""
        if not self.bot:
            logger.error("Bot instance not available")
            return False
        
        success = True
        for admin_id in ADMIN_IDS:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message[:4000],  # Telegram message limit
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
                logger.debug(f"Notified admin {admin_id}")
            except Exception as e:
                logger.error(f"Failed to notify admin {admin_id}: {e}")
                success = False
        
        return success
    
    async def notify_user(self, user_id: int, message: str, parse_mode: str = "Markdown") -> bool:
        """Send notification to a specific user"""
        if not self.bot:
            return False
        
        try:
            await self.bot.send_message(
                chat_id=user_id,
                text=message[:4000],
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
            logger.debug(f"Notified user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to notify user {user_id}: {e}")
            return False
    
    async def notify_new_order(self, order) -> bool:
        """Notify admin about new order"""
        try:
            message = f"""
🆕 *New Order Created*

Order: `{order.order_id}`
User: {order.user.first_name if order.user else 'Unknown'}
Amount: ${order.amount:.2f}
Status: {order.status.value}

Please review in Admin Panel.
            """
            return await self.notify_admin(message)
        except Exception as e:
            logger.error(f"Error in notify_new_order: {e}")
            return False
    
    async def notify_payment_proof(self, order) -> bool:
        """Notify admin about payment proof uploaded"""
        try:
            message = f"""
📸 *Payment Proof Uploaded*

Order: `{order.order_id}`
User: {order.user.first_name if order.user else 'Unknown'}
Amount: ${order.amount:.2f}

Status changed to: Pending Review
            """
            return await self.notify_admin(message)
        except Exception as e:
            logger.error(f"Error in notify_payment_proof: {e}")
            return False
    
    async def notify_order_status(self, order, old_status: str, new_status: str) -> bool:
        """Notify user about order status change"""
        try:
            if not order.user:
                return False
            
            status_messages = {
                'pending_review': "We've received your payment proof and will review it shortly.",
                'in_progress': "We're now working on your order. You'll be notified when it's ready.",
                'completed': "Your order is complete! Delivery information will be sent separately.",
                'cancelled': "Your order has been cancelled. Contact support if you have questions."
            }
            
            message = f"""
📦 *Order Status Updated*

Order: `{order.order_id}`
Status: {new_status}

{status_messages.get(new_status, '')}

You can check your orders anytime.
            """
            
            return await self.notify_user(order.user.telegram_id, message)
        except Exception as e:
            logger.error(f"Error in notify_order_status: {e}")
            return False