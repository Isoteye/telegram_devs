from database.models import Order, OrderStatus, User, Bot
from utils.helpers import generate_order_id
from typing import List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class OrderService:
    def __init__(self, db_session):
        self.db = db_session
    
    def get_or_create_user(self, telegram_user) -> Tuple[User, bool]:
        """Get or create user - ALWAYS WORKS"""
        try:
            user = self.db.query(User).filter(User.telegram_id == telegram_user.id).first()
            created = False
            
            if not user:
                user = User(
                    telegram_id=telegram_user.id,
                    username=telegram_user.username,
                    first_name=telegram_user.first_name,
                    last_name=telegram_user.last_name,
                    is_admin=False
                )
                self.db.add(user)
                self.db.commit()
                self.db.refresh(user)
                created = True
                logger.info(f"✅ Created user: {user.id} ({telegram_user.id})")
            else:
                logger.info(f"✅ Found user: {user.id}")
            
            return user, created
        except Exception as e:
            logger.error(f"❌ Error in get_or_create_user: {e}")
            self.db.rollback()
            raise
    
    def create_order(self, user_id: int, bot_id: int, amount: float) -> Optional[Order]:
        """Create order - SIMPLE AND RELIABLE"""
        try:
            order_id = generate_order_id()
            logger.info(f"📝 Creating order {order_id} for user {user_id}")
            
            # Verify bot exists
            bot = self.db.query(Bot).filter(Bot.id == bot_id).first()
            if not bot:
                logger.error(f"❌ Bot {bot_id} not found")
                return None
            
            # Verify user exists
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.error(f"❌ User {user_id} not found")
                return None
            
            # Create order
            order = Order(
                order_id=order_id,
                user_id=user_id,
                bot_id=bot_id,
                amount=amount,
                status=OrderStatus.PENDING_PAYMENT
            )
            
            self.db.add(order)
            self.db.commit()
            self.db.refresh(order)
            
            logger.info(f"✅ Created order {order.order_id} (ID: {order.id})")
            return order
        except Exception as e:
            logger.error(f"❌ Error creating order: {e}")
            self.db.rollback()
            return None
    
    def get_user_orders(self, telegram_id: int) -> List[Order]:
        """Get user orders - SIMPLE QUERY"""
        try:
            user = self.db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                return []
            
            orders = self.db.query(Order).filter(
                Order.user_id == user.id
            ).order_by(Order.created_at.desc()).all()
            
            return orders
        except Exception as e:
            logger.error(f"❌ Error getting orders: {e}")
            return []
    
    def get_order_by_id(self, order_id: str) -> Optional[Order]:
        """Get order by ID"""
        try:
            return self.db.query(Order).filter(Order.order_id == order_id).first()
        except Exception as e:
            logger.error(f"❌ Error getting order: {e}")
            return None
    
    def update_order_status(self, order_id: str, status: OrderStatus, admin_notes: str = None) -> bool:
        """Update order status"""
        try:
            order = self.get_order_by_id(order_id)
            if not order:
                logger.warning(f"❌ Order {order_id} not found for status update")
                return False
            
            old_status = order.status
            order.status = status
            if admin_notes:
                order.admin_notes = admin_notes
            
            self.db.commit()
            logger.info(f"✅ Updated order {order_id} from {old_status} to {status}")
            return True
        except Exception as e:
            logger.error(f"❌ Error updating order status: {e}")
            self.db.rollback()
            return False
    
    def update_payment_proof(self, order_id: str, proof_url: str) -> bool:
        """Update payment proof"""
        try:
            order = self.get_order_by_id(order_id)
            if not order:
                return False
            
            order.payment_proof_url = proof_url
            order.status = OrderStatus.PENDING_REVIEW
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error updating proof: {e}")
            self.db.rollback()
            return False